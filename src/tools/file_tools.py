from pathlib import Path
import os
import stat
import tempfile
from typing import Callable
from config import ALLOWED_DIR, MAX_FILE_SIZE_BYTES

from config import MAX_OUTPUT_CHARS

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
    if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        return "Error: File content is too large."
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
        size = len(content.encode("utf-8"))
        if mode == "append":
            size += target_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            return "Error: File content is too large."
        if mode == "append":
            with target_path.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target_path.parent,
                                                 prefix=f".{target_path.name}.", delete=False) as temporary:
                    temporary_path = Path(temporary.name)
                    temporary.write(content)
                os.chmod(temporary_path, stat.S_IMODE(target_path.stat().st_mode))
                os.replace(temporary_path, target_path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
    except Exception as exc:
        return f"Error: {exc!r}"

    return f"File updated ({mode} mode)."


def delete_file(file_path: str, *, approve: Callable[[str], bool] | None = None) -> str:
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

    # Never let a model invoke deletion without an explicit human approver.
    try:
        approved = approve(f"Delete file: {path}") if approve is not None else False
    except Exception:
        approved = False
    if approved is not True:
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

def read_lines(file_path: str,start_line: int = 1,line_count: int = 50,) -> str:
    """Read a limited range of UTF-8 text-file lines."""
    target_path = (ALLOWED_DIR / file_path).resolve()

    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."
    if not target_path.is_file():
        return f"Error: '{file_path}' is not a file."

    if start_line < 1:
        return "Error: start_line must be at least 1."
    if line_count < 1:
        return "Error: line_count must be at least 1."
    if line_count > 200:
        return "Error: line_count cannot exceed 200."

    end_line = start_line + line_count - 1

    try:
        lines = []

        with target_path.open("r", encoding="utf-8") as file:
            for line_no, line in enumerate(file, start=1):
                if line_no < start_line:
                    continue
                if line_no > end_line:
                    break

                lines.append(line)

                if sum(len(item) for item in lines) > MAX_OUTPUT_CHARS:
                    return (
                        f"Error: selected lines exceed the "
                        f"{MAX_OUTPUT_CHARS}-character output limit."
                    )

        if not lines:
            return f"File '{file_path}' has fewer than {start_line} lines."

        return "".join(lines)

    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a UTF-8 text file."
    except OSError as error:
        return f"Error reading file lines: {error}"