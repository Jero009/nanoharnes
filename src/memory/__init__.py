from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parents[2] / ".nanoharness" / "memories.json"
LEGACY_MEMORY_FILE = Path(__file__).parent / "memories.json"