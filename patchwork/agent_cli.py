import os
import shlex
import shutil
import subprocess
from pathlib import Path


class AgentCliError(Exception):
    """Raised when a local agent CLI cannot produce usable output."""
    pass


def run_agent_cli(
    command: str,
    prompt: str,
    timeout: int,
    system_prompt: str | None = None,
    prompt_via_stdin: bool = True,
) -> str:
    """Run a local agent CLI command with the prompt as the final argument."""
    if not command.strip():
        raise AgentCliError("agent CLI command is empty")

    args = shlex.split(command)
    if args:
        args[0] = resolve_agent_executable(args[0])
    if system_prompt and args and Path(args[0]).name.lower() in {"claude", "claude.cmd", "claude.exe"}:
        args.extend(["--system-prompt", system_prompt])
    try:
        result = subprocess.run(
            args if prompt_via_stdin else [*args, prompt],
            input=prompt if prompt_via_stdin else None,
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


def resolve_agent_executable(executable: str) -> str:
    """Resolve an agent executable, preferring .cmd shims on Windows."""
    if os.name == "nt" and not Path(executable).suffix:
        cmd_shim = shutil.which(f"{executable}.cmd")
        if cmd_shim:
            return cmd_shim
    return executable


def find_agent_command(command: str) -> str | None:
    """Return the resolved executable path for a command string, or None."""
    if not command.strip():
        return None
    args = shlex.split(command)
    if not args:
        return None
    executable = resolve_agent_executable(args[0])
    return shutil.which(executable) or None
