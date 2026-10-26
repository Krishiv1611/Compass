"""Workspace identity and execution boundary handling for Compass."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit


ExecutionTarget = Literal["local", "web"]


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    root: Path
    execution_target: ExecutionTarget
    workspace_id: str | None = None
    project_id: str | None = None
    source_type: str | None = None
    git_remote: str | None = None
    git_branch: str | None = None
    git_head: str | None = None
    context_version: str | None = None

    def to_config(self) -> dict[str, str | None]:
        data = asdict(self)
        data["root"] = str(self.root)
        return data

    @classmethod
    def from_config(cls, data: dict) -> "WorkspaceContext":
        target = data.get("execution_target")
        if target not in ("local", "web"):
            raise ValueError("Workspace execution target must be 'local' or 'web'.")
        root = data.get("root")
        if not root:
            raise ValueError("Workspace root is not configured.")
        return cls(
            root=Path(root).resolve(),
            execution_target=target,
            workspace_id=data.get("workspace_id"),
            project_id=data.get("project_id"),
            source_type=data.get("source_type"),
            git_remote=data.get("git_remote"),
            git_branch=data.get("git_branch"),
            git_head=data.get("git_head"),
            context_version=data.get("context_version"),
        )


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def canonical_git_remote(remote: str | None) -> str | None:
    """Return a credential-free, stable repository identity."""
    if not remote:
        return None
    value = remote.strip().removesuffix("/")
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        value = f"https://{host}/{path}"
    parts = urlsplit(value)
    if parts.scheme and parts.hostname:
        host = parts.hostname.lower()
        if parts.port:
            host = f"{host}:{parts.port}"
        value = urlunsplit((parts.scheme.lower(), host, parts.path, "", ""))
    return value.removesuffix(".git")


def _content_identity(root: Path) -> str:
    manifests = (
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "requirements.txt",
    )
    digest = hashlib.sha256()
    found_manifest = False
    for name in manifests:
        path = root / name
        if path.is_file():
            found_manifest = True
            digest.update(name.encode())
            digest.update(path.read_bytes())

    if not found_manifest:
        for path in sorted(
            item for item in root.rglob("*")
            if item.is_file()
            and ".git" not in item.parts
            and not _is_checkpoint_storage(root, item)
        )[:500]:
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode())
            digest.update(str(path.stat().st_size).encode())
    return f"folder:{digest.hexdigest()[:24]}"


def content_context_version(root: Path) -> str:
    """Hash project-relative file identities and contents into a portable revision."""
    digest = hashlib.sha256()
    excluded = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
    files = sorted(
        item for item in root.rglob("*")
        if item.is_file()
        and not any(part in excluded for part in item.parts)
        and not _is_checkpoint_storage(root, item)
    )
    for path in files[:2000]:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(str(path.stat().st_size).encode())
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        except OSError:
            continue
    return f"content:{digest.hexdigest()[:24]}"


def _is_checkpoint_storage(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return len(parts) >= 2 and parts[0] == ".compass" and parts[1] == "checkpoints"


def discover_local_workspace(
    start: Path | None = None,
    allow_parent_git: bool = True,
) -> WorkspaceContext:
    start = (start or Path.cwd()).resolve()
    git_root_value = _git(start, "rev-parse", "--show-toplevel")
    if git_root_value and not allow_parent_git:
        if Path(git_root_value).resolve() != start:
            git_root_value = None

    if git_root_value:
        root = Path(git_root_value).resolve()
        remote = canonical_git_remote(_git(root, "remote", "get-url", "origin"))
        branch = _git(root, "branch", "--show-current")
        head = _git(root, "rev-parse", "HEAD")
    else:
        root = start
        remote = None
        branch = None
        head = None

    project_id = remote or _content_identity(root)
    return WorkspaceContext(
        root=root,
        execution_target="local",
        project_id=project_id,
        source_type="git" if head else "local",
        git_remote=remote,
        git_branch=branch,
        git_head=head,
        context_version=head or content_context_version(root),
    )
