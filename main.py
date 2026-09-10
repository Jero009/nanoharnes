# 1. IMPORTS
from pyexpat import model
import subprocess
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

    def print_fragment(fragment, round_index=0): # used instead of chat to stream tokens
        content = getattr(fragment, "content", str(fragment))

        if "__LM_STUDIO_INTERNAL" in content:  # separate thinking from response
            console.print( "\n",end="", style="dim italic white")  # thinking
            return # can't `continue` inside a callback — just return instead

        if getattr(fragment, "reasoning_type", None) == "reasoning":  # response is reasoning
            console.print(content, end="", style="dim italic white")
        else:
            console.print(content, end="", style="bold cyan") #normal response

    console.clear()
    chat = lms.Chat(SYSTEM_PROMPT)  # initialize chat context

    console.print(BANNER)

    # ------------Establish LM Studio Connection-----
    try:
        client = lms.Client("127.0.0.1:1234")
        model = client.llm.model()
        context_length = model.get_context_length()
        model_info =model.get_info()
        console.print("[bold green]Connected to LM Studio[/bold green] ")
        console.print(f"(model:{getattr(model_info, 'display_name', 'LM Studio')} | Context Length: {context_length}) | tool use: {getattr(model_info, 'trainedForToolUse', False)}\n")
        
    except Exception as e:
        console.print(f"[red]Error connecting to server:[/red] {e}")
        return

    while True:
        user_input = typer.prompt("User").strip() # user input

        if user_input.startswith("/"): # check for commands
            if user_input.lower() == "/bye":
                console.print("bye :)", style = "cyan")
                break
            elif user_input.lower() == "/clear":
                console.clear()
                console.print(BANNER)
                chat = lms.Chat(SYSTEM_PROMPT)  # reset chat context
            elif user_input.lower() == "/help":
                console.print("[bold cyan]Available Commands:[/bold cyan]")
                console.print("/bye   - Exit the chat")
                console.print("/clear - Clear the chat and reset context")
                console.print("/help  - Show this help message")
            else:
                console.print(f"[red]Unknown command: {user_input}[/red]\n")

        else:
            chat.add_user_message(user_input) # user input into streaming chat
            

            console.print("[bold blue]Agent:[/bold blue]\n", end="") #agent start line
            start = time.time()
            try:
                model.act(
                        chat,
                        ALL_TOOLS,
                        on_message=chat.append,
                        on_prediction_fragment=print_fragment,
                    )
            except Exception as e:
                console.print(f"[red]Execution error:[/red] {e}")

            elapsed = time.time() - start 
            console.print(f"\n[dim]Response time: {elapsed:.2f} seconds[/dim]\n") #output time





# 4. ENTRYPOINT
if __name__ == "__main__":
    app()