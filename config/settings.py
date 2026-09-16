
from pathlib import Path

API_KEY = "sk-lm-kD9eVlDw:lQbkoiHwpqJFYq1xxUnc"

BASE_URL = "http://localhost:1234/v1" 
BASE_URL_OLLAMA = "http://localhost:11434/v1"

PROJECT_DIR = Path(__file__).parent.parent.resolve()
ALLOWED_DIR = (PROJECT_DIR / "workspace").resolve()

MAX_MEMORY_CHARS = 2000
MAX_FILE_SIZE_BYTES = 80000
CONTEXT_LENGTH = 80000
MAX_OUTPUT_CHARS = 4000
MAX_TOOL_ROUNDS = 10