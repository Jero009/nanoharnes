from .file_io import delete_file, edit_file, read_file, create_file

# Register all tools in a single list
ALL_TOOLS = [read_file, create_file,edit_file, delete_file]