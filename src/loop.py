# loop.py
from config.connection import client, get_model_name
from rich.console import Console
import json

from tools import TOOLS, TOOL_FUNCTIONS

console = Console()

def loop():
    model_name = get_model_name()
    messages = [{
        "role": "system",
        "content": "You are are a helpful assistant."
    }]

    while True:
        user_input = console.input("[white]\nUser: [/white]")
        messages.append({
            "role": "user",
            "content": user_input,
        })

        # Keeps responding while the model requests tools.
        console.print("[bold cyan]Nanocode: [/bold cyan]", end="")
        while True:
            response_stream = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=TOOLS,  # gives a list of tools to the model, so it can call them if needed
                tool_choice="auto",
                stream=True,
                temperature=0.6,          # 0.6 - 0.7 prevents rigid deterministic loops
                presence_penalty=0.3,     # Penalizes words the model has already used
                frequency_penalty=0.3,    # Discourages repeating the exact same phrases
            )

            

            full_response = ""
            full_reasoning = ""
            tool_calls_data = {}

            # Read every streamed chunk before executing a tool.
            for chunk in response_stream:
                choice = chunk.choices[0]
                delta = choice.delta

                reasoning = getattr(delta, "reasoning_content", None)
                content = getattr(delta, "content", None)
                tool_calls = getattr(delta, "tool_calls", None)

                if reasoning: # if reasoning is present print it
                    console.print(reasoning, style="dim italic", end="")
                    full_reasoning += reasoning

                if content: #if content is present print it
                    console.print(content, end="")
                    full_response += content

                if tool_calls: # if tool calls are present
                    # Tool arguments can arrive in multiple streamed chunks.
                    for tc in tool_calls:
                        saved_call = tool_calls_data.setdefault( 
                            tc.index,
                            {
                                "id": None,
                                "name": "",
                                "arguments": "",
                            },
                        )

                        if tc.id: #set the id for the json 
                            saved_call["id"] = tc.id

                        if tc.function.name: #set the name for the json
                            saved_call["name"] = tc.function.name

                        saved_call["arguments"] += (
                            tc.function.arguments or ""
                        )

            # Save the completed assistant response, including its tool request.
            assistant_message = {
                "role": "assistant",
                "content": full_response or None,
            }

            if tool_calls_data: # if there are tool calls, add them to the assistant message
                assistant_message["tool_calls"] = [
                    {
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["name"],
                            "arguments": tool_call["arguments"],
                        },
                    }
                    for tool_call in tool_calls_data.values()
                ]

            messages.append(assistant_message)

            # Normal answer: leave the tool loop and ask the user again.
            if not tool_calls_data:
                break

            # Execute only tools explicitly present in TOOL_FUNCTIONS.
            for tc in tool_calls_data.values():
                tool_name = tc["name"]

                try:
                    arguments = json.loads(tc["arguments"])

                    tool_function = TOOL_FUNCTIONS.get(tool_name)

                    if tool_function is None:
                        result = f"Error: tool '{tool_name}' is not allowed."
                    else:
                        result = tool_function(**arguments)

                except json.JSONDecodeError:
                    result = "Error: tool arguments were not valid JSON."

                except TypeError as error:
                    result = (
                        f"Error: invalid arguments for '{tool_name}': {error}"
                    )

                except Exception as error:
                    result = f"Error while running '{tool_name}': {error}"

                # Send the tool result back to the model using its original call ID.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                })