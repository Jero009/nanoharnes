import subprocess
import typer
from config.sandbox import ALLOWED_DIR

# Global safety switch
YOLO_MODE = False
MAX_OUTPUT_CHARS = 4000


def set_yolo_mode(enabled: bool):
    """Updates YOLO mode for shell executions."""
    global YOLO_MODE
    YOLO_MODE = enabled


def execute_command(command: str) -> str:
    """
    Executes a shell command inside the sandboxed workspace. 
    """
    # 1. Approval check (bypassed if YOLO is enabled)
    if not YOLO_MODE:
        confirm = typer.confirm(
            f"\n⚠️  [APPROVAL NEEDED] Agent wants to run shell command:\n  $ {command}\nAllow?"
        )
        if not confirm:
            return "Action canceled: User denied command execution."

    try:
        # 2. Run inside the sandboxed directory with a 30-second timeout
        result = subprocess.run(
            command,
            shell=True,
            cwd=ALLOWED_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        exit_code = result.returncode

        # Format readable output
        parts = [f"Exit Code: {exit_code}"]
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        if not stdout and not stderr:
            parts.append("(Command completed with no output)")

        output = "\n\n".join(parts)

        # 3. Output truncation: protect memory from runaway log commands
        if len(output) > MAX_OUTPUT_CHARS:
            output = (
                output[:MAX_OUTPUT_CHARS]
                + f"\n\n...[TRUNCATED: Output exceeded {MAX_OUTPUT_CHARS} characters limit]..."
            )

        return output

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as exc:
        return f"Error executing command: {exc!r}"