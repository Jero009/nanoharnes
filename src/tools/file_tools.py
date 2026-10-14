from pathlib import Path
from config import ALLOWED_DIR, MAX_FILE_SIZE_BYTES
import typer

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


def edit_file(file_path: str, content: str, mode: str = "overwrite") -> str:
    """Replace or append to an existing file."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."
    if mode not in ("overwrite", "append"):
        return f"Error: Invalid mode '{mode}'. Use 'overwrite' or 'append'."

    try:
        if mode == "append":
            with target_path.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            target_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Error: {exc!r}"

    return f"File updated ({mode} mode)."


def delete_file(file_path: str) -> str:
    """Delete a file."""
    requested_path = Path(file_path)

    if requested_path.is_absolute():
        return "Error: file_path must be relative to the workspace."

    path = (ALLOWED_DIR / requested_path).resolve()

    error = check_path_allowed(path)
    if error:
        return error

    if not path.is_file():
        return f"Error: File not found: {file_path}"

    if not typer.confirm(
        f" [!]  APPROVAL NEEDED: Agent wants to DELETE file: '{file_path}'. Allow? ",
        default=False,
    ):
        return "Action canceled: User denied deletion request."

    path.unlink()
    return f"File deleted: {file_path}"



def rename_file(file_path: str, new_file_path: str) -> str:
    """Rename or move a file. The destination must not exist."""
    source_path = (ALLOWED_DIR / file_path).resolve()
    dest_path = (ALLOWED_DIR / new_file_path).resolve()

    error = check_path_allowed(source_path) or check_path_allowed(dest_path)
    if error:
        return error
    if not source_path.exists():
        return f"Error: File '{file_path}' not found."
    if dest_path.exists():
        return "Error: A file with that name already exists."

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.rename(dest_path)
    except Exception as exc:
        return f"Error: {exc!r}"

    return f"File renamed: {file_path} -> {new_file_path}"


def get_file_length(file_path: str) -> str:
    """Get a file's line count and size."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."
    if not target_path.is_file():
        return f"Error: '{file_path}' is not a file."

    try:
        size_bytes = target_path.stat().st_size

        # Stream lines efficiently without loading the whole file into RAM
        line_count = 0
        with target_path.open("r", encoding="utf-8") as f:
            for line in f:
                line_count += 1

        # Format human-readable size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"

        return f"File '{file_path}': {line_count} lines ({size_str})."
    
    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a UTF-8 text file."
    except Exception as exc:
        return f"Error: {exc!r}"