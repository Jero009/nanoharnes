from pathlib import Path
from settings import ALLOWED_DIR, MAX_FILE_SIZE_BYTES

def check_path_allowed(path: Path) -> str | None:
    try:
        path.relative_to(ALLOWED_DIR)
    except ValueError:
        return "Error: Path is outside the allowed workspace."
    return None

def read_file(file_path: str) -> str:
    """Read a small text file"""
    requested_path = Path(file_path)

    if requested_path.is_absolute():
        return "Error: file_path must be relative to the workspace."

    target_path = (ALLOWED_DIR / requested_path).resolve()  # check if the file is within the allowed directory
 
    error = check_path_allowed(target_path)
    if error:
        return error

    if not target_path.exists(): #check if the file exists
        return f"Error: File '{file_path}' not found."

    if not target_path.is_file():
        return f"Error: '{file_path}' is not a file." #check if the path is a file

    try:
        file_size = target_path.stat().st_size #check the file size

        if file_size > MAX_FILE_SIZE_BYTES:
            return (
                f"Error: File is too large ({file_size:,} bytes; "
                f"limit: {MAX_FILE_SIZE_BYTES:,} bytes)."
            )
        else:
            return target_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a UTF-8 text file."
    except OSError as error:
        return f"Error reading '{file_path}': {error}"

def create_file(file_path: str, content: str = "") -> str:
    """Create a new file. Parent folders are created automatically."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if target_path.exists():
        return "Error: File already exists."

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Error: {exc!r}"

    return "File created."