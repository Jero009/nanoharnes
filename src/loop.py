# loop.py
import json
from typing import Callable

from config.connection import client, get_model_name
from config import MAX_TOOL_ROUNDS, SYSTEM_PROMPT, MAX_HISTORY_TURNS,MAX_TOKENS
from context.history import trim_history
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
    if model_name is None:
        model_name = get_model_name()
    messages.append({"role": "user", "content": user_input})
    messages[:] = trim_history(messages, MAX_HISTORY_TURNS)  # keep newest complete turns

    tool_rounds = 0
    # Keeps responding while the model requests tools.
    while True:
        response_stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=TOOLS,  # advertise only the model-visible tool schemas
            tool_choice="auto",
            stream=True,
            temperature=0.6,
            presence_penalty=0.3,
            frequency_penalty=0.3,
            max_completion_tokens=MAX_TOKENS
        )

        full_response = ""
        tool_calls_data = {}
        # Read every streamed chunk before executing a tool.
        for chunk in response_stream:
            delta = chunk.choices[0].delta
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
                    saved_call = tool_calls_data.setdefault(
                        tc.index, {"id": None, "name": "", "arguments": ""}
                    )
                    if tc.id:
                        saved_call["id"] = tc.id
                    if tc.function.name:
                        saved_call["name"] = tc.function.name
                    saved_call["arguments"] += tc.function.arguments or ""

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
            messages.append({
                "role": "tool", "tool_call_id": tc["id"], "content": str(result),
            })
