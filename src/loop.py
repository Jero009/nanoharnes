# loop.py
from connection import client, get_model_name
from rich.console import Console
from rich.text import Text

console = Console()

def loop():
    model_name = get_model_name()
    messages = [{
                    "role": "system", 
                    "content": "You are are a helpful assistant."
                }]

    while True:
        user_input = console.input("[white]\nUser: [/white]")
        messages.append({"role": "user", "content": user_input})

        response_stream = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        stream=True,
                        temperature=0.6,          # 0.6 - 0.7 prevents rigid deterministic loops
                        presence_penalty=0.3,     # Penalizes words the model has already used
                        frequency_penalty=0.3,    # Discourages repeating the exact same phrases
        )
        console.print("[bold cyan]Nanocode: [/bold cyan]", end="")
        full_response = ""
        full_reasoning = ""

        for chunk in response_stream:
            choice = chunk.choices[0]
            delta = choice.delta

            reasoning = (
                getattr(delta, "reasoning_content", None)
                or getattr(delta, "reasoning", None)
            )

            if reasoning: # reasoning content
                console.print(reasoning,style="dim italic" ,end="")
                full_reasoning += reasoning

            token = delta.content or ""

            if token: # chat response
                console.print(token, end="")
                full_response += token

            if delta.tool_calls:
                console.print("\n[Model requested a tool call]")
                # Later: collect the chunks here before executing the tool.

        messages.append({
            "role": "assistant",
            "content": full_response,
        })