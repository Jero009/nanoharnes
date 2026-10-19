from pathlib import Path
from contextlib import ExitStack, contextmanager
import errno
import os
import stat
import tempfile
from typing import Callable
from config import ALLOWED_DIR, MAX_FILE_SIZE_BYTES

from config import MAX_OUTPUT_CHARS


@contextmanager
def workspace_parent(file_path: str, *, create: bool = False):
    """Pin each workspace directory without following symlinks or traversal."""
    requested = Path(file_path)
    parts = requested.parts
    if requested.is_absolute() or not parts or ".." in parts:
        raise ValueError("Path is outside the allowed workspace.")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    with ExitStack() as stack:
        directory_fd = os.open(ALLOWED_DIR, flags)
        stack.callback(os.close, directory_fd)
        for part in parts[:-1]:
            if create:
                try:
                    os.mkdir(part, dir_fd=directory_fd)
                except FileExistsError:
                    pass
            directory_fd = os.open(part, flags, dir_fd=directory_fd)
            stack.callback(os.close, directory_fd)
        yield directory_fd, parts[-1]


def _unsafe_path(error: OSError) -> bool:
    return error.errno in (errno.ELOOP, errno.ENOTDIR)

def read_file(file_path: str) -> str:
    """Read a small UTF-8 file without following workspace symlinks."""
    if Path(file_path).is_absolute():
        return "Error: file_path must be relative to the workspace."
    try:
        with workspace_parent(file_path) as (parent_fd, name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                 dir_fd=parent_fd)
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    return f"Error: '{file_path}' is not a file."
                with os.fdopen(descriptor, "rb", closefd=False) as file:
                    if info.st_size > MAX_FILE_SIZE_BYTES:
                        return (f"Error: File is too large ({info.st_size:,} bytes; "
                                f"limit: {MAX_FILE_SIZE_BYTES:,} bytes).")
                    data = file.read(MAX_FILE_SIZE_BYTES + 1)
                    if len(data) > MAX_FILE_SIZE_BYTES:
                        return "Error: File is too large (changed during read)."
                    return data.decode("utf-8")
            finally:
                os.close(descriptor)
    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a UTF-8 text file."
    except ValueError as error:
        return f"Error: {error}"
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error reading '{file_path}': {error}")

def create_file(file_path: str, content: str = "") -> str:
    """Create a new file. Parent folders are created automatically."""
    if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        return "Error: File content is too large."
    try:
        with workspace_parent(file_path, create=True) as (parent_fd, name):
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 os.O_NOFOLLOW | os.O_CLOEXEC, 0o666, dir_fd=parent_fd)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as file:
                    file.write(content)
            finally:
                os.close(descriptor)
    except FileExistsError:
        return "Error: File already exists."
    except ValueError as error:
        return f"Error: {error}"
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error: {error!r}")
    return "File created."


def edit_file(file_path: str, content: str, mode: str = "overwrite") -> str:
    """Replace or append to an existing regular file."""
    if mode not in ("overwrite", "append"):
        return f"Error: Invalid mode '{mode}'. Use 'overwrite' or 'append'."
    try:
        with workspace_parent(file_path) as (parent_fd, name):
            if mode == "append":
                descriptor = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW |
                                     os.O_CLOEXEC, dir_fd=parent_fd)
                try:
                    with os.fdopen(descriptor, "a", encoding="utf-8", closefd=False) as existing:
                        info = os.fstat(existing.fileno())
                        if not stat.S_ISREG(info.st_mode):
                            return f"Error: '{file_path}' is not a file."
                        if info.st_size + len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
                            return "Error: File content is too large."
                        existing.write(content)
                finally:
                    os.close(descriptor)
            else:
                info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    return f"Error: '{file_path}' is not a file."
                if len(content.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
                    return "Error: File content is too large."
                temporary_path = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w", encoding="utf-8", dir=f"/proc/self/fd/{parent_fd}",
                        prefix=f".{name}.", delete=False,
                    ) as temporary:
                        temporary_path = Path(temporary.name)
                        temporary.write(content)
                        os.fchmod(temporary.fileno(), stat.S_IMODE(info.st_mode))
                    os.replace(temporary_path, name, dst_dir_fd=parent_fd)
                finally:
                    if temporary_path is not None:
                        temporary_path.unlink(missing_ok=True)
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except ValueError as error:
        return f"Error: {error}"
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error: {error!r}")
    return f"File updated ({mode} mode)."


def delete_file(file_path: str, *, approve: Callable[[str], bool] | None = None) -> str:
    """Delete a file after approval without re-resolving a changed parent path."""
    if Path(file_path).is_absolute():
        return "Error: file_path must be relative to the workspace."
    try:
        with workspace_parent(file_path) as (parent_fd, name):
            try:
                before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                return f"Error: File not found: {file_path}"
            if not stat.S_ISREG(before.st_mode):
                return f"Error: File not found: {file_path}"

            try:
                approved = approve(f"Delete file: {ALLOWED_DIR / file_path}") if approve is not None else False
            except Exception:
                approved = False
            if approved is not True:
                return "Action canceled: User denied deletion request."
            after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                return "Error: File changed during approval; deletion canceled."
            os.unlink(name, dir_fd=parent_fd)
    except ValueError as error:
        return f"Error: {error}"
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error deleting file: {error}")
    return f"File deleted: {file_path}"



def rename_file(file_path: str, new_file_path: str) -> str:
    """Rename or move a regular file. The destination must not exist."""
    try:
        with workspace_parent(file_path) as (source_fd, source_name):
            source = os.stat(source_name, dir_fd=source_fd, follow_symlinks=False)
            if not stat.S_ISREG(source.st_mode):
                return f"Error: File '{file_path}' not found."
            with workspace_parent(new_file_path, create=True) as (dest_fd, dest_name):
                try:
                    os.stat(dest_name, dir_fd=dest_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    return "Error: A file with that name already exists."
                os.rename(source_name, dest_name, src_dir_fd=source_fd, dst_dir_fd=dest_fd)
    except ValueError as error:
        return f"Error: {error}"
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error: {error!r}")
    return f"File renamed: {file_path} -> {new_file_path}"


def get_file_length(file_path: str) -> str:
    """Get a file's line count and size."""
    try:
        with workspace_parent(file_path) as (parent_fd, name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                 dir_fd=parent_fd)
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode):
                    return f"Error: '{file_path}' is not a file."
                with os.fdopen(descriptor, "r", encoding="utf-8", closefd=False) as file:
                    size_bytes = info.st_size
                    line_count = sum(1 for _ in file)
            finally:
                os.close(descriptor)

        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
        return f"File '{file_path}': {line_count} lines ({size_str})."
    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a UTF-8 text file."
    except ValueError as error:
        return f"Error: {error}"
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error: {error!r}")

def read_lines(file_path: str, start_line: int = 1, line_count: int = 50) -> str:
    """Read a limited range of UTF-8 text-file lines."""
    if start_line < 1:
        return "Error: start_line must be at least 1."
    if line_count < 1:
        return "Error: line_count must be at least 1."
    if line_count > 200:
        return "Error: line_count cannot exceed 200."

    end_line = start_line + line_count - 1
    try:
        with workspace_parent(file_path) as (parent_fd, name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                 dir_fd=parent_fd)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    return f"Error: '{file_path}' is not a file."
                with os.fdopen(descriptor, "r", encoding="utf-8", closefd=False) as file:
                    lines = []
                    length = 0
                    for line_no, line in enumerate(file, start=1):
                        if line_no < start_line:
                            continue
                        if line_no > end_line:
                            break
                        lines.append(line)
                        length += len(line)
                        if length > MAX_OUTPUT_CHARS:
                            return (f"Error: selected lines exceed the "
                                    f"{MAX_OUTPUT_CHARS}-character output limit.")
            finally:
                os.close(descriptor)
        if not lines:
            return f"File '{file_path}' has fewer than {start_line} lines."
        return "".join(lines)
    except UnicodeDecodeError:
        return f"Error: '{file_path}' is not a UTF-8 text file."
    except ValueError as error:
        return f"Error: {error}"
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found."
    except OSError as error:
        return ("Error: Path is outside the allowed workspace." if _unsafe_path(error)
                else f"Error reading file lines: {error}")