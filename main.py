# 1. IMPORTS
import json
import time
import typer
from openai import OpenAI
from rich.console import Console
from pathlib import Path
from config import API_KEY, BASE_URL  # Import the API key and base URL from config/__init__.py

from skills import ALL_TOOLS, TOOL_MAP, set_yolo_mode

app = typer.Typer()
console = Console()


# Imports agent.md
file_path = Path(__file__).parent / "config" / "agent.md"
agent_config = file_path.read_text(encoding="utf-8")
SYSTEM_PROMPT = agent_config

# Note: Added 'r' prefix to handle backslashes as a raw string (fixes SyntaxWarning)
BANNER = r"""
[bold cyan]
  _  _   _   _  _  ___     _   ___ ___ _  _ _____ 
 | \| | /_\ | \| |/ _ \   /_\ / __| __| \| |_   _|
 | .` |/ _ \| .` | (_) | / _ \ (_ | _|| .` | | |  
 |_|\_/_/ \_\_|\_|\___/ /_/ \_\___|___|_|\_| |_|  
[/bold cyan]
[dim]           Local Minimalist Agent Harness           [/dim]
"""

@app.command()
def chat():
    console.clear()
    console.print(BANNER)
    try:
    # Connect to LM Studio via standard OpenAI client base_url
        client = OpenAI(base_url=BASE_URL, api_key=API_KEY)  # Use the imported API key

        # Fetch whatever model is currently loaded in LM Studio
        models_response = client.models.list()

        model_name = models_response.data[0].id
        print(models_response.data[1].id)  # curently choses the first model in the list, you can modify this logic to select a specific model if needed
        if models_response.data is not None and len(models_response.data) > 0:
            model_name = models_response.data[0].id
        else:
            model_name = "local-model"

        console.print(f"[bold green]Connected to client[/bold green]")
        console.print(f"(Active Model: {model_name})\n")
    except Exception as e:
        console.print(f"[red]Error connecting to server:[/red] {e}")
        return
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] # initialize chat messages history
    yolo_mode = False  # Track YOLO state locally
    reasoning_mode = True  # Track reasoning display state locally

    while True: # main chat loop

        try:
            user_input = typer.prompt("User").strip() # user input prompt
        except (KeyboardInterrupt, typer.Abort):
            console.print("\n\nbye :)", style="cyan")
            break

        if not user_input: # skip loop if user input is empty
            continue    

        elif user_input.startswith("/"): # Check for commands
            cmd = user_input.lower()
            if cmd == "/bye":
                console.print("bye :)", style="cyan")
                break
            elif cmd == "/new":
                console.clear()
                console.print(BANNER)
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] # reset messages history for new chat
                console.print("[dim]Started a new chat session.[/dim]\n")
            elif cmd == "/yolo":
                yolo_mode = not yolo_mode
                set_yolo_mode(yolo_mode)  # Update globally across all file/dir skills
                
                if yolo_mode:
                    console.print("[bold red]---YOLO MODE ENABLED---[/bold red]\n")
                else:
                    console.print("[bold yellow]---YOLO MODE DISABLED---[/bold yellow]\n")
            elif cmd == "/reasoning":
                console.print("[dim]Toggling display of reasoning content.[/dim]\n")
                reasoning_mode = not reasoning_mode
            elif cmd == "/help":
                console.print("[bold cyan]Available Commands:[/bold cyan]")
                console.print("/bye   - Exit the chat")
                console.print("/new   - Start a new chat")
                console.print("/yolo  - Toggle auto-approval for destructive actions")
                console.print("/reasoning - Toggle display of reasoning content")
                console.print("/help  - Show this help message\n")

            else:
                console.print(f"[red]Unknown command: {user_input} | try /help[/red]\n")

        else:
            messages.append({"role": "user", "content": user_input})

            console.print("[bold blue]Agent:[/bold blue]\n", end="")
            start = time.time()

            try:
                while True:  # keep looping until the model responds without tool calls
                    response_stream = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        tools=ALL_TOOLS,
                        tool_choice="auto",
                        stream=True
                    )

                    full_content = ""
                    full_reasoning = ""
                    tool_calls_data = {}

                    thinking_started = False

                    for chunk in response_stream:
                        delta = chunk.choices[0].delta
                        reasoning = getattr(delta, "reasoning_content", None)
                        
                        if reasoning:
                            if not thinking_started:
                                if reasoning_mode:
                                    console.print("[dim italic]Thinking: \n", end="")
                                else:
                                    console.print("[dim italic]Thinking...[/dim italic]\n", end="")
                                    console.print("\n", end="")
                                thinking_started = True

                            if reasoning_mode:
                                console.print(reasoning, style="dim italic\n", end="")

                            full_reasoning += reasoning


                        if delta.content:
                            console.print(delta.content, style="bold cyan", end="")
                            full_content += delta.content

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                index = tc.index
                                if index not in tool_calls_data:
                                    tool_calls_data[index] = {
                                        "id": tc.id or "",
                                        "name": tc.function.name or "",
                                        "arguments": tc.function.arguments or ""
                                    }
                                else:
                                    if tc.function.name:
                                        tool_calls_data[index]["name"] += tc.function.name
                                    if tc.function.arguments:
                                        tool_calls_data[index]["arguments"] += tc.function.arguments

                    console.print()

                    formatted_tool_calls = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]}
                        }
                        for tc in tool_calls_data.values()
                    ] if tool_calls_data else None

                    messages.append({
                        "role": "assistant",
                        "content": full_content if full_content else None,
                        "reasoning_content": full_reasoning if full_reasoning else None,
                        "tool_calls": formatted_tool_calls
                    })

                    if not formatted_tool_calls:
                        break  # model gave a final answer with no tool calls — stop looping

                    for tool_call in formatted_tool_calls:
                        func_name = tool_call["function"]["name"]
                        func_args = json.loads(tool_call["function"]["arguments"])

                        console.print(f"\n[dim italic]Executing tool: {func_name}({func_args})[/dim italic]")

                        if func_name in TOOL_MAP:
                            try:
                                tool_result = TOOL_MAP[func_name](**func_args)
                            except Exception as tool_err:
                                tool_result = f"Error executing tool: {tool_err}"
                        else:
                            tool_result = f"Error: Tool {func_name} not found."

                        console.print(f"[dim italic]Result: {tool_result}[/dim italic]\n")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result)
                        })
                    # loop again — model gets to see the tool results and respond

            except Exception as e:
                console.print(f"\n[red]Execution error:[/red] {e}")

            elapsed = time.time() - start
            console.print(f"\n[dim]Response time: {elapsed:.2f} seconds[/dim]\n")

# 4. ENTRYPOINT
if __name__ == "__main__":
    app()