from pathlib import Path
from config import ALLOWED_DIR

def check_path_allowed(target_path: Path) -> str | None: # check if the target path is within the allowed directory
    if not target_path.is_relative_to(ALLOWED_DIR):
        return f"Error: Access denied. Cannot access files outside {ALLOWED_DIR}."
    return None