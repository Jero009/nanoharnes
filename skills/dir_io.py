from pathlib import Path
import typer

from config.sandbox import ALLOWED_DIR, check_path_allowed, MAX_FILE_SIZE_BYTES

# Global safety switch
YOLO_MODE = False

def set_yolo_mode(enabled: bool):
    global YOLO_MODE
    YOLO_MODE = enabled


def pwd() -> str:
    """Show the workspace path."""
    return str(ALLOWED_DIR)


def ls(dir_path: str = ".") -> str:
    """List one directory. The result is not recursive."""
    target_path = (ALLOWED_DIR / dir_path).resolve()

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
    """Create a directory and its parent folders."""
    target_path = (ALLOWED_DIR / dir_path).resolve()

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
    """Delete an empty directory. Asks for approval unless YOLO mode is on."""
    target_path = (ALLOWED_DIR / dir_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: Directory '{dir_path}' not found."
    if not target_path.is_dir():
        return f"Error: '{dir_path}' is not a directory."
    if target_path == ALLOWED_DIR:
        return "Error: Cannot delete the workspace root directory."

    if not YOLO_MODE:
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