import os
import shlex
import shutil
import subprocess
from pathlib import Path


class AgentCliError(Exception):
    """Raised when a local agent CLI cannot produce usable output."""
    pass


def run_agent_cli(command: str, prompt: str, timeout: int) -> str:
    """Run a local agent CLI command with the prompt as the final argument."""
    if not command.strip():
        raise AgentCliError("agent CLI command is empty")

    args = shlex.split(command)
    if os.name == "nt" and args and not Path(args[0]).suffix:
        cmd_shim = shutil.which(f"{args[0]}.cmd")
        if cmd_shim:
            args[0] = cmd_shim
    try:
        result = subprocess.run(
            [*args, prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        executable = args[0] if args else command
        raise AgentCliError(
            f"agent CLI not found: {executable}. Install it or set the matching PATCHWORK_*_CLI_COMMAND."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise AgentCliError(f"agent CLI timed out after {timeout} seconds") from e

    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise AgentCliError(f"agent CLI failed with exit code {result.returncode}: {stderr}")

    output = result.stdout.strip()
    if not output:
        raise AgentCliError("agent CLI returned no output")
    return output
