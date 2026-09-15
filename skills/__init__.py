import inspect
from .file_io import (
    read_file,
    create_file,
    edit_file,
    delete_file,
    rename_file,
    copy_file,
    set_yolo_mode as set_file_yolo,
    get_file_length,
)
from .dir_io import (
    pwd,
    ls,
    mkdir,
    rmdir,
    set_yolo_mode as set_dir_yolo,
)
from .ai_skills import (
    summarize_file,
)


def set_yolo_mode(enabled: bool):
    """Globally toggle YOLO mode across all file and directory tools."""
    set_file_yolo(enabled)
    set_dir_yolo(enabled)


FILE_FUNCTIONS = [
    read_file,
    create_file,
    edit_file,
    delete_file,
    rename_file,
    copy_file,
    get_file_length,
]
DIR_FUNCTIONS = [
    pwd,
    ls,
    mkdir,
    rmdir,
]
AI_FUNCTIONS = [
    summarize_file,

]


ALL_FUNCTIONS = FILE_FUNCTIONS + DIR_FUNCTIONS + AI_FUNCTIONS

TOOL_MAP = {func.__name__: func for func in ALL_FUNCTIONS}


def function_to_schema(func):
    """Generates a clean OpenAI tool schema directly from a function signature."""
    sig = inspect.signature(func)
    properties = {}
    required = []
    type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}

    for param_name, param in sig.parameters.items():
        param_type = type_map.get(param.annotation, "string")
        properties[param_name] = {"type": param_type}
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


FILE_TOOLS = [function_to_schema(f) for f in FILE_FUNCTIONS]
DIR_TOOLS = [function_to_schema(f) for f in DIR_FUNCTIONS]
AI_TOOLS = [function_to_schema(f) for f in AI_FUNCTIONS]

ALL_TOOLS = FILE_TOOLS + DIR_TOOLS + AI_TOOLS

__all__ = [
    "read_file",
    "create_file",
    "edit_file",
    "delete_file",
    "rename_file",
    "copy_file",
    "get_file_length",
    "pwd",
    "ls",
    "mkdir",
    "rmdir",
    "summarize_file",
    "set_yolo_mode",
    "TOOL_MAP",
    "FILE_TOOLS",
    "DIR_TOOLS",
    "AI_TOOLS",
    "ALL_TOOLS",
]