from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parents[2] / ".nanoharness" / "memories.json"
MAX_MEMORY_BYTES = 100_000
MAX_COMPACTION_INPUT_BYTES = 500_000

from .memory import (
    compact_memory_if_needed,
    create_memory,
    delete_memory,
    get_memory,
    list_memory,
    update_memory,
)