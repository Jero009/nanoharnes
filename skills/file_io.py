from pathlib import Path
import os
import shutil
import typer

from config import ALLOWED_DIR, MAX_FILE_SIZE_BYTES
from config.sandbox import check_path_allowed

# Global safety switch
YOLO_MODE = False

def set_yolo_mode(enabled: bool):
    global YOLO_MODE
    YOLO_MODE = enabled


def read_file(file_path: str) -> str:
    """Read a small text file. Use read_lines for large files."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."
    if not target_path.is_file():
        return f"Error: '{file_path}' is not a file."

    try:
        # Instant OS size check (0 RAM used)
        file_size = target_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return (
                f"Error: File is too large ({file_size:,} bytes, limit is {MAX_FILE_SIZE_BYTES:,} bytes). "
                "Use 'read_lines' to inspect a specific section, or 'summarize_file' to understand it."
            )

        return target_path.read_text(encoding="utf-8", errors="ignore")

    except FileNotFoundError:
        return f"Error: The file at {file_path} was not found."
    except Exception as e:
        return f"Error reading file: {e}"

def read_lines(file_path: str, start_line: int = 1, line_count: int = 50) -> str: # read specific lines in a file
    """Read selected lines from a text file."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."
    if not target_path.is_file():
        return f"Error: '{file_path}' is not a file."

    start_line = max(1, start_line)
    line_count = max(1, line_count)
    end_line = start_line + line_count - 1

    try:
        lines = []
        with target_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                if line_no < start_line:
                    continue
                if line_no <= end_line:
                    lines.append(line)
                else:
                    break

        if not lines:
            return f"File '{file_path}' has fewer than {start_line} lines."

        return "".join(lines)

    except Exception as e:
        return f"Error reading file lines: {e}"
    

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
    """Delete a file. Asks for approval unless YOLO mode is on."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."

    if not YOLO_MODE:
        confirm = typer.confirm(
            f"\n⚠️  [APPROVAL NEEDED] Agent wants to DELETE file: '{file_path}'. Allow?"
        )
        if not confirm:
            return "Action canceled: User denied deletion request."

    try:
        target_path.unlink()
        return f"File deleted: {file_path}"
    except Exception as e:
        return f"Error deleting file: {e}"


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


def copy_file(file_path: str, new_file_path: str) -> str:
    """Copy a file. The destination must not exist."""
    source_path = (ALLOWED_DIR / file_path).resolve()
    dest_path = (ALLOWED_DIR / new_file_path).resolve()

    error = check_path_allowed(source_path) or check_path_allowed(dest_path)
    if error:
        return error
    if not source_path.exists():
        return f"Error: File '{file_path}' not found."
    if not source_path.is_file():
        return f"Error: '{file_path}' is not a file."
    if dest_path.exists():
        return "Error: A file already exists at the destination."

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
    except Exception as exc:
        return f"Error: {exc!r}"

    return f"File copied: {file_path} -> {new_file_path}"


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
        with target_path.open("r", encoding="utf-8", errors="ignore") as f:
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
    except Exception as exc:
        return f"Error: {exc!r}"