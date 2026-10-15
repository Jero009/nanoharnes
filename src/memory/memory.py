import json
def get_memory(key: str) -> str | None:
    """Return a saved fact, or None if the key does not exist."""
    if not key.strip():
        raise ValueError("Memory key cannot be empty.")

    try:
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        raise ValueError("Memory file contains invalid JSON.") from error

    if not isinstance(data, dict) or any(
        not isinstance(k, str) or not isinstance(v, str)
        for k, v in data.items()
    ):
        raise ValueError("Memory file must contain string keys and values.")

    return data.get(key)
def create_memory(key:str, value:str)-> dict[str, str]:
    """
    Store a key-value pair in memory.
    """
    pass
def delete_memory(key:str)-> dict[str, str]:
    """
    Delete a value from memory based on the provided key.
    """
    pass
def update_memory(key:str, value:str)-> dict[str, str]:
    """
    Update the value associated with a key in memory.
    """
    pass
def list_memory()-> dict[str, str]:
    """
    List all key-value pairs stored in memory.
    """
    pass