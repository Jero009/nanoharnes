from .file_io import (
    read_file,
    create_file,
    edit_file,
    delete_file,
    rename_file,
    copy_file,
)
from .dir_io import (
    pwd,
    ls,
    mkdir,
    rmdir,
)

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

# Register all tools in a single list
ALL_TOOLS = FILE_TOOLS + DIR_TOOLS