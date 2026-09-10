import json
import time
import typer
from openai import OpenAI
from rich.console import Console
from pathlib import Path

from skills import ALL_TOOLS, set_yolo_mode

app = typer.Typer()
console = Console()

# Map your Python functions by name so the loop can execute them dynamically
TOOL_MAP = {tool.__name__: tool for tool in ALL_TOOLS}

# Load agent.md system prompt
file_path = Path(__file__).parent / "config" / "agent.md"
SYSTEM_PROMPT = file_path.read_text(encoding="utf-8")

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

    # Connect to LM Studio via standard OpenAI client base_url
    try:
        client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")
        # Fetch whatever model is currently loaded in LM Studio
        models_response = client.models.list()
        model_name = models_response.data[0].id if models_response.data else "local-model"
        console.print(f"[bold green]Connected to LM Studio via OpenAI client[/bold green]")
        console.print(f"(Active Model: {model_name})\n")
    except Exception as e:
        console.print(f"[red]Error connecting to local server:[/red] {e}")
        return

    # Initialize chat messages history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    yolo_mode = False

    while True:
        try:
            user_input = typer.prompt("User").strip()
        except (KeyboardInterrupt, typer.Abort):
            console.print("\n\nbye :)", style="cyan")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd == "/bye":
                console.print("bye :)", style="cyan")
                break
            elif cmd == "/new":
                console.clear()
                console.print(BANNER)
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                console.print("[dim]Started a new chat session.[/dim]\n")
            elif cmd == "/yolo":
                yolo_mode = not yolo_mode
                set_yolo_mode(yolo_mode)
                if yolo_mode:
                    console.print("[bold red]🔥 YOLO MODE ENABLED[/bold red]\n")
                else:
                    console.print("[bold yellow]🛡️ YOLO MODE DISABLED[/bold yellow]\n")
            elif cmd == "/help":
                console.print("[bold cyan]Commands:[/bold cyan] /bye, /new, /yolo, /help\n")
            else:
                console.print(f"[red]Unknown command: {user_input}[/red]\n")
            continue

        # Append user input
        messages.append({"role": "user", "content": user_input})
        console.print("[bold blue]Agent:[/bold blue]\n", end="")
        start = time.time()

        try:
            # --- THE MANUAL AGENT LOOP ---
            # We use OpenAI's native tools feature. LM Studio parses tool schemas automatically from functions if supported,
            # but standard OpenAI client loop lets you manage rounds manually.
            
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=[{
                    "type": "function",
                    "function": {
                        "name": t.__name__,
                        "description": t.__doc__,
                        # Note: For strict OpenAI tool use, simple parameter parsing works, 
                        # but keeping manual control lets you handle outputs seamlessly.
                    }
                } for t in ALL_TOOLS],
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            messages.append(response_message) # Append assistant's response

            if response_message.content:
                console.print(response_message.content, style="bold cyan")

            # Check if the model wants to call tools
            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)
                    
                    console.print(f"\n[dim italic]Executing tool: {func_name}({func_args})[/dim italic]")

                    if func_name in TOOL_MAP:
                        # Execute your optimized skill code directly!
                        try:
                            tool_result = TOOL_MAP[func_name](**func_args)
                        except Exception as tool_err:
                            tool_result = f"Error executing tool: {tool_err}"
                    else:
                        tool_result = f"Error: Tool {func_name} not found."

                    console.print(f"[dim italic]Result: {tool_result}[/dim italic]\n")

                    # Feed the result back to the model history
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result)
                    })
                    
                    # (Optional) Here is where you could intercept tool_result 
                    # if it starts with "Error:" and inject your forced reflection prompt!

        except Exception as e:
            console.print(f"\n[red]Execution error:[/red] {e}")

        elapsed = time.time() - start
        console.print(f"\n[dim]Response time: {elapsed:.2f} seconds[/dim]\n")

if __name__ == "__main__":
    app()