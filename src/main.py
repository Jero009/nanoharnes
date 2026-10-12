# src/main.py
from loop import loop
from rich.console import Console

console = Console()
BANNER = r"""
[bold cyan]
  _  _   _   _  _  ___     _   ___ ___ _  _ _____ 
 | \| | /_\ | \| |/ _ \   /_\ / __| __| \| |_   _|
 | .` |/ _ \| .` | (_) | / _ \ (_ | _|| .` | | |  
 |_|\_/_/ \_\_|\_|\___/ /_/ \_\___|___|_|\_| |_|  
[/bold cyan]
[dim]           Local Agent Harness           [/dim]
"""
console.print(BANNER)
if __name__ == "__main__":

    loop()