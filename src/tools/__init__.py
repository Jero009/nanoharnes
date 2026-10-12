from .file_tools import read_file

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a small text file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Relative path to the file, for example "
                            "'src/main.py'. Absolute paths are forbidden."
                        ),
                    },
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "read_file": read_file,
}