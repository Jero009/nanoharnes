from pathlib import Path
import typer

from sandbox import ALLOWED_DIR, check_path_allowed


def pwd() -> str:
    """Returns the current working directory (the allowed workspace root).

    Returns:
        The absolute path of the workspace directory.
    """
    return str(ALLOWED_DIR)


def ls(dir_path: str = ".") -> str:
    """Lists the files and subdirectories inside a directory.

    Args:
        dir_path: Relative path to the directory to list, e.g. "notes" or "."
            for the workspace root. Defaults to ".".

    Returns:
        A newline-separated list of entry names (directories marked with a
        trailing "/"), or an error message string if listing failed.
    """
    target_path = Path(dir_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: Directory '{dir_path}' not found."
    if not target_path.is_dir():
        return f"Error: '{dir_path}' is not a directory."

    try:
        entries = sorted(target_path.iterdir(), key=lambda p: p.name)
        if not entries:
            return "(empty directory)"
        lines = [
            f"{entry.name}/" if entry.is_dir() else entry.name
            for entry in entries
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {e}"


def mkdir(dir_path: str) -> str:
    """Creates a new directory, including any missing parent directories.

    Args:
        dir_path: Relative path of the directory to create, e.g. "notes/archive".

    Returns:
        A success message, or an error message string if creation failed.
    """
    target_path = Path(dir_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if target_path.exists():
        return "Error: Directory already exists."

    try:
        target_path.mkdir(parents=True, exist_ok=False)
    except Exception as exc:
        return f"Error: {exc!r}"

    return "Directory created."


def rmdir(dir_path: str) -> str:
    """Deletes an empty directory, after asking the user for approval.

    Args:
        dir_path: Relative path of the directory to delete, e.g. "notes/archive".
            The directory must be empty.

    Returns:
        A success message, a cancellation message, or an error message string.
    """
    target_path = Path(dir_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: Directory '{dir_path}' not found."
    if not target_path.is_dir():
        return f"Error: '{dir_path}' is not a directory."
    if target_path == ALLOWED_DIR:
        return "Error: Cannot delete the workspace root directory."

    confirm = typer.confirm(
        f"\n⚠️  [APPROVAL NEEDED] Agent wants to DELETE directory: '{dir_path}'. Allow?"
    )
    if not confirm:
        return "Action canceled: User denied deletion request."

    try:
        target_path.rmdir()
        return f"Directory deleted: {dir_path}"
    except OSError:
        return f"Error: Directory '{dir_path}' is not empty."
    except Exception as e:
        return f"Error deleting directory: {e}"