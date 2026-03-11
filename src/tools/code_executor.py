"""Sandboxed code executor — runs commands in a subprocess with timeout."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    """Result of a sandboxed command execution."""
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool

    @property
    def success(self) -> bool:
        return self.return_code == 0 and not self.timed_out


def run_command(
    command: list[str],
    cwd: Path | str | None = None,
    timeout: int = 60,
    env: dict[str, str] | None = None,
) -> ExecutionResult:
    """Execute a command in a sandboxed subprocess.

    Args:
        command: Command and arguments as a list.
        cwd: Working directory for the command.
        timeout: Maximum execution time in seconds.
        env: Optional environment variables.

    Returns:
        ExecutionResult with stdout, stderr, return code, and timeout status.
    """
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return ExecutionResult(
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            return_code=-1,
            stdout="",
            stderr=f"Command timed out after {timeout} seconds",
            timed_out=True,
        )
    except FileNotFoundError:
        return ExecutionResult(
            return_code=-1,
            stdout="",
            stderr=f"Command not found: {command[0]}",
            timed_out=False,
        )
    except Exception as e:
        return ExecutionResult(
            return_code=-1,
            stdout="",
            stderr=f"Execution error: {e!s}",
            timed_out=False,
        )
