from pathlib import Path
import typer

ALLOWED_DIR = Path("workspace").resolve()


def _check_allowed(target_path: Path) -> str | None:
    """Returns an error string if target_path is outside ALLOWED_DIR, else None."""
    if not target_path.is_relative_to(ALLOWED_DIR):
        return f"Error: Access denied. Cannot access files outside {ALLOWED_DIR}."
    return None


def read_file(file_path: str) -> str:
    """Reads the content of a file and returns it as a string.

    Args:
        file_path: The relative or absolute path to the file to be read.
    """
    target_path = Path(file_path).resolve()

    err = _check_allowed(target_path)
    if err:
        return err
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."

    try:
        return target_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: The file at {file_path} was not found."
    except Exception as e:
        return f"Error reading file: {e}"


def create_file(name: str, content: str) -> str:
    """Create a file with the given name and content."""
    target_path = Path(name).resolve()

    err = _check_allowed(target_path)
    if err:
        return err
    if target_path.exists():
        return "Error: File already exists."

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Error: {exc!r}"

    return "File created."


def edit_file(name: str, content: str, mode: str = "overwrite") -> str:
    """Edit an existing file. mode = "overwrite" or "append"."""
    target_path = Path(name).resolve()

    err = _check_allowed(target_path)
    if err:
        return err
    if not target_path.exists():
        return f"Error: File '{name}' not found."
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
    """Deletes the specified file inside the workspace."""
    target_path = Path(file_path).resolve()

    err = _check_allowed(target_path)
    if err:
        return err
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