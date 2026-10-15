from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parents[2] / ".nanoharness" / "memories.json"
MAX_MEMORY_BYTES = 100_000
MAX_COMPACTION_INPUT_BYTES = 500_000