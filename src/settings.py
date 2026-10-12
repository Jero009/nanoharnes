from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_DIR = PROJECT_ROOT / "workspace"
MAX_FILE_SIZE_BYTES = 100000