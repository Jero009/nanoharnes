from pathlib import Path

ALLOWED_DIR = (Path(__file__).parent.parent / "workspace").resolve()

CONTEXT_LENGTH = 80000  # Max characters to read from a file for LLM processing

MAX_FILE_SIZE_BYTES = 80000  

def check_path_allowed(target_path: Path) -> str | None: # check if the target path is within the allowed directory
    if not target_path.is_relative_to(ALLOWED_DIR):
        return f"Error: Access denied. Cannot access files outside {ALLOWED_DIR}."
    return None