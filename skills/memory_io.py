from pathlib import Path

# Path to the permanent markdown file
MEMORY_FILE = Path(__file__).parent.parent / "memory" / "core_memory.md"


def save_memory(fact: str) -> str:
    """
    Saves an important fact, user preference, or project decision to permanent memory.
    Use this to remember details across chat sessions, restarts.
    """
    fact = fact.strip()
    if not fact:
        return "Error: Cannot save an empty memory."

    # Ensure the memory directory exists
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Initialize file with a title if it doesn't exist
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("# Core Memory\n\n", encoding="utf-8")

    # Append the fact as a clean Markdown bullet point
    with MEMORY_FILE.open("a", encoding="utf-8") as f:
        f.write(f"- {fact}\n")

    return f"Successfully saved to permanent memory: '{fact}'"