# 1. IMPORTS
import time
import typer
import lmstudio as lms
from rich.console import Console
from pathlib import Path

from skills import ALL_TOOLS 

app = typer.Typer()
console = Console()

# imports agent.md
file_path = Path(__file__).parent / "config" / "agent.md"
agent_config = file_path.read_text(encoding="utf-8")
SYSTEM_PROMPT = agent_config

BANNER = """
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
    def print_fragment(fragment, round_index=0): 
        content = getattr(fragment, "content", str(fragment))

        if "__LM_STUDIO_INTERNAL" in content:  
            console.print("\n", end="", style="dim italic white")  
            return 

        if getattr(fragment, "reasoning_type", None) == "reasoning":  
            console.print(content, end="", style="dim italic white")
        else:
            console.print(content, end="", style="bold cyan")

    console.clear()
    chat = lms.Chat(SYSTEM_PROMPT)  # Initialize chat context with agent.md

    console.print(BANNER)

    # Establish LM Studio Connection
    try:
        client = lms.Client("127.0.0.1:1234")
        model = client.llm.model()
        context_length = model.get_context_length()
        model_info = model.get_info()
        console.print("[bold green]Connected to LM Studio[/bold green] ")
        console.print(f"(model: {getattr(model_info, 'display_name', 'LM Studio')} | Context Length: {context_length} | Tool Use: {getattr(model_info, 'trainedForToolUse', False)})\n")
        
    except Exception as e:
        console.print(f"[red]Error connecting to server:[/red] {e}")
        return

    while True:
        try:
            user_input = typer.prompt("User").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\nbye :)", style="cyan")
            break

        if not user_input:
            continue

        if user_input.startswith("/"): # Check for CLI commands
            cmd = user_input.lower()
            if cmd == "/bye":
                console.print("bye :)", style="cyan")
                break
            elif cmd == "/new":
                console.clear()
                console.print(BANNER)
                chat = lms.Chat(SYSTEM_PROMPT)
                console.print("[dim]Started a new chat session.[/dim]\n")
            elif cmd == "/help":
                console.print("[bold cyan]Available Commands:[/bold cyan]")
                console.print("/bye   - Exit the chat")
                console.print("/new   - Start a new chat")
                console.print("/help  - Show this help message\n")
            else:
                console.print(f"[red]Unknown command: {user_input}[/red]\n")
        else:
            chat.add_user_message(user_input)
            
            console.print("[bold blue]Agent:[/bold blue]\n", end="") 
            start = time.time()
            try:
                # LM Studio SDK automatically manages multi-round tool execution here
                model.act(
                    chat,
                    ALL_TOOLS,
                    on_message=chat.append,
                    on_prediction_fragment=print_fragment,
                )
            except Exception as e:
                console.print(f"\n[red]Execution error:[/red] {e}")

            elapsed = time.time() - start 
            console.print(f"\n[dim]Response time: {elapsed:.2f} seconds[/dim]\n")

if __name__ == "__main__":
    app()