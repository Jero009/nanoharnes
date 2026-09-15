from pathlib import Path
import os
import shutil
import typer

from .sandbox import ALLOWED_DIR, check_path_allowed

# Global safety switch
YOLO_MODE = False

def set_yolo_mode(enabled: bool):
    global YOLO_MODE
    YOLO_MODE = enabled


def read_file(file_path: str) -> str:
    """Reads and returns the text content of a file. file_path e.g. "notes/todo.txt"."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."

    try:
        return target_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: The file at {file_path} was not found."
    except Exception as e:
        return f"Error reading file: {e}"


def create_file(file_path: str, content: str = "") -> str:
    """Creates a new file with content or without. Fails if it already exists. Auto-creates parent dirs."""
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
    """Edits an existing file. mode: "overwrite" (default) or "append". Fails if file is missing."""
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
    """Deletes a file after user approval (bypassed if YOLO_MODE is True)."""
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
    """Renames or moves a file to a new path. Fails if destination exists. Auto-creates parent dirs."""
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
    """Copies a file to a new path, leaving the original. Fails if destination exists. Auto-creates parent dirs."""
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
    """Returns the line count and size of a file without loading its full content into context."""
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