import os
import re
import subprocess
from langchain_core.tools import tool

BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+[/~*]",
    r":\(\)\s*\{\s*:\|:\&\s*\};:",
    r"dd\s+if=/dev/zero",
    r"\bmkfs\b",
    r"\bformat\b\s+[a-zA-Z]:",
    r"\b(shutdown|reboot)\b",
    r"curl\s+.*\|\s*(ba)?sh",
    r"wget\s+.*\|\s*(ba)?sh",
    r">\s*/dev/sd[a-z]",
    r"\bdel\s+/[sfq]\b",
]
_SENSITIVE_ENV_PATTERNS = ["KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH"]

# Max characters of stdout/stderr to return to the agent.
_MAX_OUTPUT_CHARS = 15000


def _is_blocked(command: str) -> bool:
    """Check if a command matches any blocked pattern."""
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def _sanitize_env() -> dict[str, str]:
    """Return a copy of the environment with sensitive variables removed."""
    env = os.environ.copy()
    to_remove = [
        k for k in env if any(pat in k.upper() for pat in _SENSITIVE_ENV_PATTERNS)
    ]
    for k in to_remove:
        del env[k]
    return env


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    """Truncate long output, keeping the start and end."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return (
        text[:half]
        + f"\n\n... truncated ({len(text)} chars total) ...\n\n"
        + text[-half:]
    )


@tool
def shell_execute(command: str, timeout: int = 120, cwd: str = ".") -> str:
    """Execute a shell command and return its output.

    Use this to run terminal commands like git, pip, python, npm, etc.
    Dangerous commands (rm -rf /, fork bombs, etc.) are blocked.
    Sensitive environment variables (API keys, tokens) are stripped.

    Args:
        command: The shell command to execute.
        timeout: Max seconds to wait before killing the process (default 120).
        cwd: Working directory for the command (default current directory).
    """
    if not command or not command.strip():
        return "Error: No command provided."

    if _is_blocked(command):
        return f"Error: Command blocked for safety reasons: '{command}'"

    if not os.path.isdir(cwd):
        return f"Error: Working directory not found: '{cwd}'"

    safe_env = _sanitize_env()

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=safe_env,
        )

        parts = [f"Command: {command}", f"Exit code: {result.returncode}"]

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if stdout:
            parts.append(f"Stdout:\n{_truncate(stdout)}")
        if stderr:
            parts.append(f"Stderr:\n{_truncate(stderr)}")
        if not stdout and not stderr:
            parts.append("(no output)")

        return "\n".join(parts)

    except subprocess.TimeoutExpired:
        return (
            f"Error: Command timed out after {timeout}s: '{command}'\n"
            "The process was killed."
        )
    except Exception as e:
        return f"Error executing command: {e}"
