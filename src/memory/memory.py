import json
import os
import tempfile
from typing import Callable
from memory import MEMORY_FILE
def get_memory(key: str) -> str | None:
    """Return a saved fact, or None if the key does not exist."""
    if not key.strip():
        raise ValueError("Memory key cannot be empty.")
    return list_memory().get(key)
def list_memory() -> dict[str, str]:
    """Read all saved facts; missing file is an empty store."""
    try:
        if MEMORY_FILE.stat().st_size > 100_000:
            raise ValueError("Memory file is too large.")
        with MEMORY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("Memory file is not valid UTF-8 JSON.") from error
    if not isinstance(data, dict) or any(
        not isinstance(k, str) or not isinstance(v, str)
        for k, v in data.items()
    ):
        raise ValueError("Memory file must contain string keys and values.")
    return data
def _write_memory(data: dict[str, str]) -> None:
    """Replace the entire store without exposing a partially written file."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if len(content.encode("utf-8")) > 100_000:
        raise ValueError("Memory file would be too large.")
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=MEMORY_FILE.parent,
            prefix=".memory-", delete=False,
        ) as temp:
            temp_name = temp.name
            temp.write(content)
        os.replace(temp_name, MEMORY_FILE)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
def _approved(description: str, approve: Callable[[str], bool] | None) -> bool:
    try:
        return approve is not None and approve(description) is True
    except Exception:
        return False
def create_memory(
    key: str, value: str, *, approve: Callable[[str], bool] | None = None,
) -> str:
    """Save a new fact only after explicit approval; never overwrite."""
    if not key.strip() or not value.strip():
        raise ValueError("Memory key and value cannot be empty.")
    data = list_memory()
    if key in data:
        return f"Memory key already exists: {key}"
    if not _approved(f"Create memory {key!r}: {value!r}", approve):
        return "Memory creation denied."
    data[key] = value
    _write_memory(data)
    return f"Memory created: {key}"
def update_memory(
    key: str, value: str, *, approve: Callable[[str], bool] | None = None,
) -> str:
    """Change an existing fact only after explicit approval."""
    if not key.strip() or not value.strip():
        raise ValueError("Memory key and value cannot be empty.")
    data = list_memory()
    if key not in data:
        return f"Memory key not found: {key}"
    if not _approved(f"Update memory {key!r}: {data[key]!r} -> {value!r}", approve):
        return "Memory update denied."
    data[key] = value
    _write_memory(data)
    return f"Memory updated: {key}"
def delete_memory(
    key: str, *, approve: Callable[[str], bool] | None = None,
) -> str:
    """Delete an existing fact only after explicit approval."""
    if not key.strip():
        raise ValueError("Memory key cannot be empty.")
    data = list_memory()
    if key not in data:
        return f"Memory key not found: {key}"
    if not _approved(f"Delete memory {key!r}: {data[key]!r}", approve):
        return "Memory deletion denied."
    del data[key]
    _write_memory(data)
    return f"Memory deleted: {key}"
