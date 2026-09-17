import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).parent.parent.resolve()
load_dotenv(PROJECT_DIR / ".env")

API_KEY = os.getenv("API_KEY", "not-needed-for-local-server")

BASE_URL = os.getenv("BASE_URL", "http://localhost:1234/v1")
BASE_URL_OLLAMA = os.getenv("BASE_URL_OLLAMA", "http://localhost:11434/v1")

ALLOWED_DIR = (PROJECT_DIR / "workspace").resolve()

MAX_MEMORY_CHARS = int(os.getenv("MAX_MEMORY_CHARS", "2000"))
MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_BYTES", "80000"))
CONTEXT_LENGTH = int(os.getenv("CONTEXT_LENGTH", "80000"))
MAX_OUTPUT_CHARS = int(os.getenv("MAX_OUTPUT_CHARS", "4000"))
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "10"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
DEFAULT_MEMORY_MODE = os.getenv("DEFAULT_MEMORY_MODE", "fast")