from .file_io import (
    read_file,
    create_file,
    edit_file,
    delete_file,
    rename_file,
    copy_file,
    set_yolo_mode as set_file_yolo,
)
from .dir_io import (
    pwd,
    ls,
    mkdir,
    rmdir,
    set_yolo_mode as set_dir_yolo,
)

def set_yolo_mode(enabled: bool):
    """Globally toggle YOLO mode across all file and directory tools."""
    set_file_yolo(enabled)
    set_dir_yolo(enabled)


# Tool lists for agent frameworks
FILE_TOOLS = [
    read_file,
    create_file,
    edit_file,
    delete_file,
    rename_file,
    copy_file,
]

DIR_TOOLS = [
    pwd,
    ls,
    mkdir,
    rmdir,
]

ALL_TOOLS = FILE_TOOLS + DIR_TOOLS

__all__ = [
    "read_file",
    "create_file",
    "edit_file",
    "delete_file",
    "rename_file",
    "copy_file",
    "pwd",
    "ls",
    "mkdir",
    "rmdir",
    "set_yolo_mode",
    "FILE_TOOLS",
    "DIR_TOOLS",
    "ALL_TOOLS",
]