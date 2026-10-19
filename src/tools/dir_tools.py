import os
import stat
from contextlib import ExitStack
from config import ALLOWED_DIR
from tools.file_tools import workspace_parent, _unsafe_path



def pwd() -> str:
    """Show the workspace path."""
    return str(ALLOWED_DIR)


def ls(dir_path: str = ".") -> str:
    """List one directory. The result is not recursive."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        with ExitStack() as stack:
            if dir_path in (".", ""):
                directory_fd = os.open(ALLOWED_DIR, flags)
            else:
                parent_fd, name = stack.enter_context(workspace_parent(dir_path))
                try:
                    directory_fd = os.open(name, flags, dir_fd=parent_fd)
                except NotADirectoryError:
                    return f"Error: '{dir_path}' is not a directory."
            stack.callback(os.close, directory_fd)
            entries = sorted(os.listdir(directory_fd))
            if not entries:
                return "(empty directory)"
            return "\n".join(
                entry + ("/" if stat.S_ISDIR(os.stat(
                    entry, dir_fd=directory_fd, follow_symlinks=False).st_mode) else "")
                for entry in entries
            )
    except FileNotFoundError:
        return f"Error: Directory '{dir_path}' not found."
    except ValueError as error:
        return f"Error: {error}"
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error listing directory: {error}")


def mkdir(dir_path: str) -> str:
    """Create a directory and its parent folders."""
    if dir_path in (".", ""):
        return "Error: Directory already exists."
    try:
        with workspace_parent(dir_path, create=True) as (parent_fd, name):
            os.mkdir(name, dir_fd=parent_fd)
    except FileExistsError:
        return "Error: Directory already exists."
    except ValueError as error:
        return f"Error: {error}"
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error: {error!r}")
    return "Directory created."
