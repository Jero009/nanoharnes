from pathlib import Path
from openai import OpenAI
from rich.console import Console

# 1. Imported from config (Single Source of Truth)
from config import API_KEY, BASE_URL, MAX_MEMORY_CHARS

console = Console()
tool_client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# 2. Path to persistent memory file
MEMORY_FILE = Path(__file__).parent.parent / "memory" / "core_memory.md"


def _get_active_model() -> str:
    """Detect active model for isolated consolidation calls."""
    try:
        models = tool_client.models.list()
        if models.data:
            return models.data[0].id
    except Exception:
        pass
    return "local-model"


def _consolidate_memory(current_content: str, new_fact: str) -> str:
    """
    Hermes consolidation: Merges, deduplicates, and condenses memory
    to fit comfortably under the character limit.
    """
    console.print(f"\n[bold yellow]Memory limit reached ({MAX_MEMORY_CHARS} chars). Consolidating memory...[/bold yellow]")

    prompt = f"""You are a memory consolidation engine.
The core memory has exceeded its budget of {MAX_MEMORY_CHARS} characters.

EXISTING MEMORY:
{current_content}

NEW FACT TO INCLUDE:
- {new_fact}

TASK:
1. Merge related facts and eliminate duplicate or outdated information.
2. Keep user identity, preferences, and important technical/project rules.
3. Re-write the entire memory as dense, concise Markdown bullet points.
4. Target length: Under {int(MAX_MEMORY_CHARS * 0.70)} characters so there is room for future entries.

CONSOLIDATED MEMORY (Markdown bullet points only):"""

    try:
        response = tool_client.chat.completions.create(
            model=_get_active_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500
        )
        compacted = response.choices[0].message.content.strip()
        if compacted:
            return compacted
    except Exception as e:
        console.print(f"[dim red]Consolidation call failed ({e}). Pruning oldest entry manually.[/dim red]")

    # Fallback if API fails: drop the oldest bullet points to fit
    lines = current_content.splitlines()
    while len("\n".join(lines)) + len(new_fact) + 20 > MAX_MEMORY_CHARS and len(lines) > 2:
        lines.pop(2)  # Skip header lines, drop oldest bullet
    lines.append(f"- {new_fact}")
    return "\n".join(lines)


def save_memory(fact: str) -> str:
    """
    Saves an important fact or user preference to permanent memory.
    Bounded by a hard character limit. Automatically consolidates and compacts when full.
    """
    fact = fact.strip()
    if not fact:
        return "Error: Cannot save an empty memory."

    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("# Core Memory\n\n", encoding="utf-8")

    current_content = MEMORY_FILE.read_text(encoding="utf-8").strip()

    # Calculate what size would be if we just appended
    projected_length = len(current_content) + len(f"\n- {fact}")

    # Case 1: Fits comfortably within budget -> simple append
    if projected_length <= MAX_MEMORY_CHARS:
        with MEMORY_FILE.open("a", encoding="utf-8") as f:
            f.write(f"- {fact}\n")
        
        new_size = len(MEMORY_FILE.read_text(encoding="utf-8"))
        pct = int((new_size / MAX_MEMORY_CHARS) * 100)
        return f"Saved to memory [{pct}% — {new_size}/{MAX_MEMORY_CHARS} chars]: '{fact}'"

    # Case 2: Exceeds limit -> Hermes Consolidation
    consolidated_content = _consolidate_memory(current_content, fact)
    MEMORY_FILE.write_text(consolidated_content + "\n", encoding="utf-8")

    new_size = len(consolidated_content)
    pct = int((new_size / MAX_MEMORY_CHARS) * 100)
    return (
        f"Memory full! Consolidated and compacted memory to make space "
        f"[{pct}% — {new_size}/{MAX_MEMORY_CHARS} chars]. Saved: '{fact}'"
    )