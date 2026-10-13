from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIR = (PROJECT_ROOT / "workspace").resolve()
MAX_FILE_SIZE_BYTES = 100_000

ALLOWED_DIR.mkdir(parents=True, exist_ok=True)