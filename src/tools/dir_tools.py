from config import ALLOWED_DIR
from tools.file_tools import check_path_allowed



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
        lines = []
        for entry in entries:
            if entry.is_dir():
                lines.append(f"{entry.name}/")
            else:
                lines.append(entry.name)
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

"""
def rmdir(dir_path: str) -> str:
    #Delete an empty directory. Asks for approval unless YOLO mode is on.
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
    try:
        target_path.rmdir()
        return f"Directory deleted: {dir_path}"
    except OSError:
        return f"Error: Directory '{dir_path}' is not empty."
    except Exception as e:
        return f"Error deleting directory: {e}"
"""