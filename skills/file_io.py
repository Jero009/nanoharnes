from pathlib import Path


def read_file(file_path: str) -> str:
    """Reads the content of a file and returns it as a string.

    Args:
        file_path: The relative or absolute path to the file to be read.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: The file at {file_path} was not found."
    except Exception as e:
        return f"Error reading file: {e}"


def create_file(name: str, content: str) -> str:
    """Create a file with the given name and content."""
    dest_path = Path(name)
    if dest_path.exists():
        return "Error: File already exists."
    try:
        dest_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Error: {exc!r}"
    return "File created."


def edit_file(name: str, content: str, mode: str = "overwrite") -> str:
    """Edit an existing file mode = "overwrite" or "append"."""
    dest_path = Path(name)

    if not dest_path.exists():
        return "Error: File does not exist."

    try:
        if mode == "append":
            with dest_path.open("a", encoding="utf-8") as f:
                f.write(content)
        elif mode == "overwrite":
            dest_path.write_text(content, encoding="utf-8")
        else:
            return f"Error: Invalid mode '{mode}'. Use 'overwrite' or 'append'."
    except Exception as exc:
        return f"Error: {exc!r}"

    return f"File updated ({mode} mode)."

# skills/file_io.py
from pathlib import Path
import typer

ALLOWED_DIR = Path("./workspace").resolve()


def delete_file(file_path: str) -> str:
    """Deletes the specified file inside the workspace after user confirmation."""
    target_path = Path(file_path).resolve()

    # Directory restriction check
    if not target_path.is_relative_to(ALLOWED_DIR):
        return (
            f"Error: Access denied. Cannot delete files outside {ALLOWED_DIR}."
        )

    if not target_path.exists():
        return f"Error: File '{file_path}' not found."

    # Intercept with Typer user confirmation prompt
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