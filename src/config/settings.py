from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED_DIR = (PROJECT_ROOT / "workspace").resolve()
MAX_FILE_SIZE_BYTES = 100_000
MAX_OUTPUT_CHARS = 10_000
MAX_TOOL_ROUNDS = 5

ALLOWED_DIR.mkdir(parents=True, exist_ok=True)