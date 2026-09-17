from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel


console = Console()
ENV_FILE = Path(__file__).parent.parent / ".env"


def choose_provider():
    console.print("\n[bold]Choose your AI provider:[/bold]")
    console.print("1. LM Studio")
    console.print("2. Ollama")
    console.print("3. Custom OpenAI-compatible API")

    while True:
        choice = typer.prompt("Provider", default="1")

        if choice == "1":
            api_key = typer.prompt(
                "LM Studio API key",
                default="lm-studio",
                show_default=False,
            )

            return {
                "name": "LM Studio",
                "url": "http://localhost:1234/v1",
                "api_key": api_key,
            }

        if choice == "2":
            return {
                "name": "Ollama",
                "url": "http://localhost:11434/v1",
                "api_key": "ollama",
            }

        if choice == "3":
            url = typer.prompt("API URL")
            api_key = typer.prompt("API key")

            return {
                "name": "Custom API",
                "url": url,
                "api_key": api_key,
            }

        console.print("[yellow]Please choose 1, 2, or 3.[/yellow]")


def choose_model_profile():
    console.print("\n[bold]Choose your model size:[/bold]")
    console.print("1. Under 15B")
    console.print("2. Around 27B")
    console.print("3. Over 50B")

    profiles = {
        "1": {
            "name": "Under 15B",
            "MAX_TOKENS": 1024,
            "CONTEXT_LENGTH": 32000,
            "MAX_MEMORY_CHARS": 1000,
            "MAX_TOOL_ROUNDS": 6,
            "MAX_OUTPUT_CHARS": 3000,
            "MAX_FILE_SIZE_BYTES": 40000,
            "DEFAULT_MEMORY_MODE": "fast",
        },
        "2": {
            "name": "Around 27B",
            "MAX_TOKENS": 2048,
            "CONTEXT_LENGTH": 80000,
            "MAX_MEMORY_CHARS": 2000,
            "MAX_TOOL_ROUNDS": 10,
            "MAX_OUTPUT_CHARS": 4000,
            "MAX_FILE_SIZE_BYTES": 80000,
            "DEFAULT_MEMORY_MODE": "smart",
        },
        "3": {
            "name": "Over 50B",
            "MAX_TOKENS": 4096,
            "CONTEXT_LENGTH": 128000,
            "MAX_MEMORY_CHARS": 4000,
            "MAX_TOOL_ROUNDS": 15,
            "MAX_OUTPUT_CHARS": 8000,
            "MAX_FILE_SIZE_BYTES": 120000,
            "DEFAULT_MEMORY_MODE": "smart",
        },
    }

    while True:
        choice = typer.prompt("Model size", default="2")

        if choice in profiles:
            profile = profiles[choice]
            console.print(f"[green]Selected: {profile['name']}[/green]")
            return profile

        console.print("[yellow]Please choose 1, 2, or 3.[/yellow]")

def run_first_setup():
    if ENV_FILE.exists():
        return

    console.print(
        Panel.fit(
            "[bold cyan]Welcome to Nano Harness[/bold cyan]\n\n"
            "Let's configure your local AI agent.",
            title="First-time setup",
            border_style="cyan",
        )
    )

    try:
        provider = choose_provider()
        console.print(f"\n[green]Selected: {provider['name']}[/green]")
        profile = choose_model_profile()

        ENV_FILE.write_text(
            f"""API_KEY={provider["api_key"]}
            BASE_URL={provider["url"]}
            MAX_TOKENS={profile["MAX_TOKENS"]}
            CONTEXT_LENGTH={profile["CONTEXT_LENGTH"]}
            MAX_MEMORY_CHARS={profile["MAX_MEMORY_CHARS"]}
            MAX_TOOL_ROUNDS={profile["MAX_TOOL_ROUNDS"]}
            MAX_OUTPUT_CHARS={profile["MAX_OUTPUT_CHARS"]}
            MAX_FILE_SIZE_BYTES={profile["MAX_FILE_SIZE_BYTES"]}
            DEFAULT_MEMORY_MODE={profile["DEFAULT_MEMORY_MODE"]}
            """,
            encoding="utf-8",
        )
    except typer.Abort:
        console.print("\n[yellow]Setup cancelled.[/yellow]")
        raise typer.Exit()

    console.print("\n[bold green]Setup complete.[/bold green]\n")