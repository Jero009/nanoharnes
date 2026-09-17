from pathlib import Path

import typer
from dotenv import dotenv_values, set_key
from rich.console import Console


console = Console()
ENV_FILE = Path(__file__).parent.parent / ".env"

SETTINGS = [
    ("API_KEY", "API key", "text"),
    ("BASE_URL", "API URL", "text"),
    ("MAX_TOKENS", "Maximum response tokens", "int"),
    ("CONTEXT_LENGTH", "Context length", "int"),
    ("MAX_MEMORY_CHARS", "Persistent memory size", "int"),
    ("MAX_TOOL_ROUNDS", "Maximum tool rounds", "int"),
    ("MAX_OUTPUT_CHARS", "Maximum shell output", "int"),
    ("MAX_FILE_SIZE_BYTES", "Maximum file size", "int"),
    ("DEFAULT_MEMORY_MODE", "Default memory mode", "mode"),
]


def _display_value(key, value):
    if key == "API_KEY" and value:
        return f"{value[:4]}...{value[-4:]}"
    return value or "(empty)"


def settings_menu():
    while True:
        values = dotenv_values(ENV_FILE)
        console.print("\n[bold cyan]Current settings[/bold cyan]")

        for number, (key, label, _) in enumerate(SETTINGS, start=1):
            value = _display_value(key, values.get(key))
            console.print(f"{number}. {label}: {value}")

        choice = typer.prompt("Choose a setting, or q to exit", default="q").lower()
        if choice == "q":
            return

        if not choice.isdigit() or not 1 <= int(choice) <= len(SETTINGS):
            console.print("[yellow]Choose one of the listed numbers.[/yellow]")
            continue

        key, label, value_type = SETTINGS[int(choice) - 1]
        current = values.get(key, "")

        if value_type == "int":
            value = typer.prompt(label, default=int(current or "0"), type=int)
        elif value_type == "mode":
            value = typer.prompt(label, default=current or "fast").lower()
            if value not in {"fast", "smart"}:
                console.print("[yellow]Use fast or smart.[/yellow]")
                continue
        else:
            value = typer.prompt(
                label,
                default=current,
                hide_input=key == "API_KEY",
                show_default=False,
            )

        set_key(str(ENV_FILE), key, str(value), quote_mode="auto")
        console.print(
            "[green]Saved.[/green] Restart Nano Harness for this setting to take effect."
        )