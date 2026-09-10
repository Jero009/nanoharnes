from pathlib import Path
import typer

from sandbox import ALLOWED_DIR, check_path_allowed


def read_file(file_path: str) -> str:
    """Reads the content of a file and returns it as a string.

    Args:
        file_path: Relative path to the file to read, e.g. "notes/todo.txt".

    Returns:
        The file's text content, or an error message string if the read failed.
    """
    target_path = Path(file_path).resolve()

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


def create_file(file_path: str, content: str) -> str:
    """Creates a new file with the given content. Fails if the file already exists.

    Args:
        file_path: Relative path for the new file, e.g. "notes/todo.txt".
            Parent directories are created automatically if they don't exist.
        content: The text content to write to the new file.

    Returns:
        A success message, or an error message string if creation failed.
    """
    target_path = Path(file_path).resolve()

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
    """Edits an existing file by overwriting or appending content. Fails if the file does not exist.

    Args:
        file_path: Relative path to the file to edit, e.g. "notes/todo.txt".
        content: The text content to write or append.
        mode: Either "overwrite" (replace all content) or "append" (add to the end).
            Defaults to "overwrite".

    Returns:
        A success message, or an error message string if the edit failed.
    """
    target_path = Path(file_path).resolve()

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
    """Deletes a file, after asking the user for approval.

    Args:
        file_path: Relative path to the file to delete, e.g. "notes/todo.txt".

    Returns:
        A success message, a cancellation message, or an error message string.
    """
    target_path = Path(file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."

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
    """Renames or moves a file from one path to another within the workspace.

    Args:
        file_path: Current relative path of the file, e.g. "notes/old.txt".
        new_file_path: New relative path for the file, e.g. "notes/new.txt".
            Parent directories are created automatically if they don't exist.

    Returns:
        A success message, or an error message string if the rename failed.
    """
    source_path = Path(file_path).resolve()
    dest_path = Path(new_file_path).resolve()

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