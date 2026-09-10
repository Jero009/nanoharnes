from pathlib import Path

ALLOWED_DIR = Path("workspace").resolve()


def check_path_allowed(target_path: Path) -> str | None:
    """Checks whether a resolved path is inside the allowed workspace directory.

    Args:
        target_path: The resolved (absolute) path to check.

    Returns:
        An error message string if the path is outside ALLOWED_DIR, otherwise None.
    """
    if not target_path.is_relative_to(ALLOWED_DIR):
        return f"Error: Access denied. Cannot access files outside {ALLOWED_DIR}."
    return None