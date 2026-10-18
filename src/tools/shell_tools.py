import subprocess
import shutil
import os
import selectors
import time
from typing import Callable
from config import ALLOWED_DIR,MAX_OUTPUT_CHARS


def execute_command(command: str, *, approve: Callable[[str], bool] | None = None) -> str:
    """Run a shell command in the isolated workspace. Network is disabled."""
    sandbox = shutil.which("bwrap")
    if sandbox is None:
        return "Error: bubblewrap is required to run shell commands safely."
    #give the user a chance to approve the command before executing it
    if approve is None or not approve(f"Run sandboxed shell command: $ {command}"):
        return "Action canceled: User denied command execution."
    try:
        # 2. Give the process a temporary root and expose only the workspace
        # as writable. Network access is disabled for shell commands.
        sandbox_command = [
            sandbox,
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--unshare-net",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/etc",
            "--bind", str(ALLOWED_DIR), "/workspace",
            "--chdir", "/workspace",
            "--", "/bin/sh", "-c", command,
        ]

        # Read at most the configured output budget; never buffer an entire
        # untrusted command's output before truncating it.
        output_chunks = {"stdout": bytearray(), "stderr": bytearray()}
        truncated = False
        deadline = time.monotonic() + 30
        with subprocess.Popen(
            sandbox_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": "/usr/bin:/bin", "HOME": "/workspace", "LANG": "C.UTF-8"},
        ) as process:
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                    while selector.get_map():
                        remaining_time = deadline - time.monotonic()
                        if remaining_time <= 0:
                            raise subprocess.TimeoutExpired(sandbox_command, 30)
                        ready = selector.select(remaining_time)
                        if not ready:
                            raise subprocess.TimeoutExpired(sandbox_command, 30)
                        for key, _ in ready:
                            remaining = MAX_OUTPUT_CHARS - sum(map(len, output_chunks.values()))
                            chunk = os.read(key.fileobj.fileno(), min(4096, remaining + 1))
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            output_chunks[key.data].extend(chunk[:remaining])
                            if len(chunk) > remaining:
                                truncated = True
                                break
                        if truncated:
                            break
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
            exit_code = process.returncode

        stdout = output_chunks["stdout"].decode("utf-8", errors="replace").strip()
        stderr = output_chunks["stderr"].decode("utf-8", errors="replace").strip()

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
        if truncated or len(output) > MAX_OUTPUT_CHARS:
            output = (
                output[:MAX_OUTPUT_CHARS]
                + f"\n\n...[TRUNCATED: Output exceeded {MAX_OUTPUT_CHARS} characters limit]..."
            )

        return output

    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as exc:
        return f"Error executing command: {exc!r}"