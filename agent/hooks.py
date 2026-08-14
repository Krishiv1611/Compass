"""Parse and select deterministic, approval-gated post-edit hooks."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
import re


@dataclass(frozen=True, slots=True)
class VerificationHook:
    name: str
    command: str
    cwd: str = "."
    timeout_seconds: int = 120
    run_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HookRunRequest:
    id: str
    hook_name: str
    tool_name: str
    arguments: dict[str, Any]
    requires_approval: bool = True


@dataclass(frozen=True, slots=True)
class HookConfiguration:
    hooks: list[VerificationHook] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _safe_cwd(root: Path, value: object) -> str:
    cwd = str(value or ".").replace("\\", "/").strip() or "."
    candidate = PurePosixPath(cwd)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"cwd {cwd!r} is outside workspace")
    resolved = (root / Path(*candidate.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"cwd {cwd!r} is outside workspace") from exc
    return candidate.as_posix()


def _parse_hook(root: Path, raw: object, index: int) -> VerificationHook:
    if not isinstance(raw, dict):
        raise ValueError(f"hooks.after_edit[{index}] must be a table")
    name = str(raw.get("name") or "").strip()
    command = str(raw.get("command") or "").strip()
    if not name or not command:
        raise ValueError(f"hooks.after_edit[{index}] requires name and command")
    if "\x00" in command:
        raise ValueError(f"hooks.after_edit[{index}] command contains a null byte")
    try:
        timeout = int(raw.get("timeout_seconds", 120))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"hooks.after_edit[{index}] timeout must be an integer") from exc
    timeout = max(1, min(timeout, 600))
    values = raw.get("run_on", [])
    if not isinstance(values, list):
        raise ValueError(f"hooks.after_edit[{index}] run_on must be a list")
    run_on = tuple(
        dict.fromkeys(str(value).lower().strip().lstrip(".") for value in values if str(value).strip())
    )
    if not run_on:
        raise ValueError(f"hooks.after_edit[{index}] requires at least one extension")
    return VerificationHook(
        name=name,
        command=command,
        cwd=_safe_cwd(root, raw.get("cwd", ".")),
        timeout_seconds=timeout,
        run_on=run_on,
    )


def load_verification_hooks(workspace_root: str | Path) -> HookConfiguration:
    root = Path(workspace_root).resolve()
    path = root / ".compass" / "config.toml"
    if not path.is_file():
        return HookConfiguration()
    try:
        parsed = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return HookConfiguration(errors=[f"{path}: {exc}"])
    raw_hooks = parsed.get("hooks", {}).get("after_edit", [])
    if not isinstance(raw_hooks, list):
        return HookConfiguration(errors=["hooks.after_edit must be an array of tables"])
    hooks: list[VerificationHook] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_hooks):
        try:
            hooks.append(_parse_hook(root, raw, index))
        except ValueError as exc:
            errors.append(str(exc))
    return HookConfiguration(hooks=hooks, errors=errors)


def select_verification_hooks(
    hooks: list[VerificationHook], changed_files: list[str]
) -> list[VerificationHook]:
    extensions = {
        Path(path.replace("\\", "/")).suffix.lower().lstrip(".")
        for path in changed_files
    }
    return [hook for hook in hooks if extensions.intersection(hook.run_on)]


def build_hook_run_requests(hooks: list[VerificationHook]) -> list[HookRunRequest]:
    requests = []
    for index, hook in enumerate(hooks):
        digest = hashlib.sha256(
            f"{hook.name}\0{hook.command}\0{hook.cwd}".encode("utf-8")
        ).hexdigest()[:12]
        requests.append(HookRunRequest(
            id=f"hook-{index + 1}-{digest}",
            hook_name=hook.name,
            tool_name="shell_execute",
            arguments={
                "command": hook.command,
                "cwd": hook.cwd,
                "timeout": hook.timeout_seconds,
                "verification_hook": True,
                "hook_name": hook.name,
            },
        ))
    return requests


_MUTATING_TOOLS = {"write_to_file", "edit_file", "delete_file", "move_file"}


def changed_files_from_messages(messages: list[Any]) -> list[str]:
    """Return successful main-executor mutation paths from the current turn."""
    calls: dict[str, str] = {}
    changed: list[str] = []
    for message in messages:
        if getattr(message, "type", "") == "human":
            calls.clear()
            changed.clear()
            continue
        for call in getattr(message, "tool_calls", []) or []:
            args = call.get("args") or {}
            path = args.get("path") or args.get("file_path")
            if call.get("name") in _MUTATING_TOOLS and isinstance(path, str) and path:
                calls[str(call.get("id"))] = path
        call_id = str(getattr(message, "tool_call_id", ""))
        if call_id in calls and getattr(message, "status", "success") != "error":
            content = str(getattr(message, "content", "")).lstrip().lower()
            if content.startswith("successfully ") and calls[call_id] not in changed:
                changed.append(calls[call_id])
    return changed


_SECRET_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|credential)\b(\s*[:=]\s*)([^\s,;]+)"
)


def redact_hook_output(value: object, limit: int = 2_000) -> str:
    text = str(value)
    text = _SECRET_VALUE.sub(r"\1\2[redacted]", text)
    text = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[redacted]", text)
    if len(text) <= limit:
        return text
    return text[: limit - 24] + "\n... output truncated ..."


def hook_result_status(content: object, tool_status: str = "success") -> str:
    text = str(content).lower()
    if "user skipped" in text or "user denied" in text:
        return "skipped"
    if tool_status == "error" or text.startswith("error:"):
        return "failed"
    match = re.search(r"exit code:\s*(-?\d+)", text)
    return "passed" if match and int(match.group(1)) == 0 else "failed"
