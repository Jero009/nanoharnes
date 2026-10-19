# loop.py
import json
from typing import Callable

from config.connection import client, get_model_name
from config import MAX_TOOL_ROUNDS, SYSTEM_PROMPT, MAX_HISTORY_TURNS, MAX_TOKENS, MAX_OUTPUT_CHARS
from config.settings import MAX_CONTEXT_CHARS
from context.history import trim_history, budget_history, trim_with_summary
from tools import TOOLS, TOOL_FUNCTIONS


def new_messages() -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def run_turn(
    messages: list[dict],
    user_input: str,
    *,
    emit: Callable[[str, str], None] = lambda kind, text: None,
    approve: Callable[[str], bool] | None = None,
    model_name: str | None = None,
) -> None:
    """Run one user turn; emit streamed text without owning a terminal UI."""
    messages.append({"role": "user", "content": user_input})
    if model_name is None:
        try:
            model_name = get_model_name()
        except Exception as error:
            messages[:] = trim_history(messages, MAX_HISTORY_TURNS)
            emit("status", f"Model discovery failed: {error}. Question preserved; retry when available.")
            return
    try:
        summarized = trim_with_summary(client, model_name, messages)
        if summarized is not messages:
            messages[:] = summarized
            emit("status", "Older conversation summarized.")
    except Exception as error:
        emit("status", f"Summary failed ({type(error).__name__}); using recent turns.")
    messages[:] = trim_history(messages, MAX_HISTORY_TURNS)

    tool_rounds = 0
    # Keeps responding while the model requests tools.
    while True:
        request_messages = budget_history(messages, MAX_CONTEXT_CHARS)
        if request_messages is None:
            emit("status", "Request context exceeds the size limit even after shortening tool results; conversation preserved. Shorten the question or start a new chat.")
            return
        response_stream = client.chat.completions.create(
            model=model_name,
            messages=request_messages,
            tools=TOOLS,  # advertise only the model-visible tool schemas
            tool_choice="auto",
            stream=True,
            temperature=0.6,
            presence_penalty=0.3,
            frequency_penalty=0.3,
            max_tokens=MAX_TOKENS,
        )

        full_response = ""
        tool_calls_data = {}
        finish_reason = None
        malformed_call = False
        # Read every streamed chunk before executing a tool.
        for chunk in response_stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = choice.delta
            reason = getattr(choice, "finish_reason", None)
            if reason is not None:
                finish_reason = reason
            content = getattr(delta, "content", None)
            tool_calls = getattr(delta, "tool_calls", None)
            reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)

            if reasoning:
                emit("thinking", reasoning)

            if content:
                emit("assistant", content)
                full_response += content

            if tool_calls:
                # Tool arguments can arrive in multiple streamed chunks.
                for tc in tool_calls:
                    index = getattr(tc, "index", None)
                    if type(index) is not int or index < 0:
                        malformed_call = True
                        continue
                    saved_call = tool_calls_data.setdefault(
                        index, {"id": None, "name": "", "arguments": ""}
                    )
                    call_id = getattr(tc, "id", None)
                    function = getattr(tc, "function", None)
                    name = getattr(function, "name", None)
                    arguments = getattr(function, "arguments", None)
                    if call_id is not None:
                        if not isinstance(call_id, str) or not call_id.strip() or (saved_call["id"] and saved_call["id"] != call_id):
                            malformed_call = True
                        else:
                            saved_call["id"] = call_id
                    if name is not None:
                        if not isinstance(name, str) or not name.strip() or (saved_call["name"] and saved_call["name"] != name):
                            malformed_call = True
                        else:
                            saved_call["name"] = name
                    if arguments is not None:
                        if not isinstance(arguments, str):
                            malformed_call = True
                        else:
                            saved_call["arguments"] += arguments

        if finish_reason == "length":
            emit("status", "Response truncated at the token limit. No tool was run; conversation preserved.")
            return
        if finish_reason not in ("stop", "tool_calls"):
            emit("status", f"Response ended unexpectedly ({finish_reason}); no tool was run.")
            return
        if (tool_calls_data or malformed_call) and finish_reason != "tool_calls":
            emit("status", "Response ended without tool_calls finish reason; tool fragments discarded.")
            return
        if finish_reason == "tool_calls" and (malformed_call or not tool_calls_data or
                any(not tc["id"] or not tc["name"] for tc in tool_calls_data.values()) or
                len({tc["id"] for tc in tool_calls_data.values()}) != len(tool_calls_data)):
            emit("status", "Invalid tool call metadata; no tool was run. Conversation preserved.")
            return
        if not tool_calls_data and not full_response.strip():
            emit("status", "Model returned no answer; conversation preserved.")
            return

        # Save the completed assistant response, including its tool request.
        assistant_message = {"role": "assistant", "content": full_response or None}
        if tool_calls_data:
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in tool_calls_data.values()
            ]
        messages.append(assistant_message)

        # Normal answer: leave the tool loop.
        if not tool_calls_data:
            return

        if tool_rounds >= MAX_TOOL_ROUNDS:
            result = (
                f"Error: Maximum tool rounds ({MAX_TOOL_ROUNDS}) exceeded. "
                "Stop using tools and give the user a final answer."
            )
            for tc in tool_calls_data.values():
                messages.append({
                    "role": "tool", "tool_call_id": tc["id"], "content": result,
                })
            emit("status", result)
            return
        tool_rounds += 1

        # Execute only tools explicitly present in TOOL_FUNCTIONS.
        for tc in tool_calls_data.values():
            tool_name = tc["name"]
            emit("tool", tool_name)
            try:
                arguments = json.loads(tc["arguments"])
                if not isinstance(arguments, dict):
                    raise TypeError("arguments must be a JSON object")
                tool_function = TOOL_FUNCTIONS.get(tool_name)
                if tool_function is None:
                    result = f"Error: tool '{tool_name}' is not allowed."
                elif tool_name in ("delete_file", "execute_command"):
                    result = tool_function(**arguments, approve=approve)
                elif tool_name in ("create_memory", "update_memory"):
                    result = tool_function(**arguments, approve=approve, model_name=model_name)
                elif tool_name == "delete_memory":
                    result = tool_function(**arguments, approve=approve)
                else:
                    result = tool_function(**arguments)
            except json.JSONDecodeError:
                result = "Error: tool arguments were not valid JSON."
            except TypeError as error:
                result = f"Error: invalid arguments for '{tool_name}': {error}"
            except Exception as error:
                result = f"Error while running '{tool_name}': {error}"

            # Match each result to the model's original call ID.
            result_text = str(result)
            if len(result_text) > MAX_OUTPUT_CHARS:
                result_text = (result_text[:MAX_OUTPUT_CHARS] +
                               "\n...[TRUNCATED: tool result exceeds output limit]...")
            messages.append({
                "role": "tool", "tool_call_id": tc["id"], "content": result_text,
            })
