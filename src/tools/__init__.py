import inspect
from .file_tools import edit_file, read_file, create_file,delete_file, rename_file, get_file_length,read_lines
from .dir_tools import pwd, ls, mkdir
from .shell_tools import execute_command

FUNCTIONS = [
    read_file,
    create_file,
    edit_file,
    delete_file,
    rename_file,
    get_file_length,
    pwd,
    ls,
    mkdir,
    execute_command,
    read_lines
]
TOOL_FUNCTIONS = {
    function.__name__: function
    for function in FUNCTIONS
}

def function_to_schema(func):
    """Generate an OpenAI tool schema from a Python function."""
    signature = inspect.signature(func)
    properties = {}
    required = []
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
    }
    for parameter_name, parameter in signature.parameters.items():
        if parameter_name == "approve":
            continue
        parameter_type = type_map.get(parameter.annotation, "string")
        properties[parameter_name] = {
            "type": parameter_type,
        }
        if parameter.default is inspect.Parameter.empty:
            required.append(parameter_name)
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
TOOLS = [
    function_to_schema(function)
    for function in FUNCTIONS
]