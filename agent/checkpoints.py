"""Recoverable, workspace-bounded file checkpoints."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class CheckpointConflictError(RuntimeError):
    def __init__(self, conflicts: list[str]):
        super().__init__("Checkpoint restore conflicts: " + ", ".join(conflicts))
        self.conflicts = conflicts


class CheckpointFile(BaseModel):
    path: str
    existed: bool
    sha256: str | None = None
    size: int = 0
    content_path: str | None = None
    expected_current_existed: bool | None = None
    expected_current_sha256: str | None = None


class CheckpointManifest(BaseModel):
    id: str
    workspace_id: str
    thread_id: str
    created_at: datetime
    label: str = ""
    files: list[CheckpointFile] = Field(default_factory=list)


class RestorePreview(BaseModel):
    checkpoint_id: str
    changes: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _checkpoint_root(root: Path) -> Path:
    return root / ".compass" / "checkpoints"


def _target(root: Path, value: str) -> tuple[Path, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Checkpoint path is required")
    base = root.resolve()
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
    try:
        relative = resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Checkpoint path {value!r} is outside workspace") from exc
    if not relative.parts or relative.parts[:2] == (".compass", "checkpoints"):
        raise ValueError(f"Checkpoint path {value!r} is reserved")
    return resolved, relative.as_posix()


def _manifest_path(root: Path, checkpoint_id: str) -> Path:
    if not checkpoint_id or any(character not in "0123456789abcdef" for character in checkpoint_id):
        raise ValueError("Invalid checkpoint ID")
    return _checkpoint_root(root.resolve()) / checkpoint_id / "manifest.json"


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_checkpoint(
    workspace_root: str | Path,
    paths: list[str],
    *,
    workspace_id: str,
    thread_id: str,
    label: str = "",
) -> CheckpointManifest:
    root = Path(workspace_root).resolve()
    checkpoint_id = uuid.uuid4().hex
    directory = _checkpoint_root(root) / checkpoint_id
    bodies = directory / "files"
    files: list[CheckpointFile] = []
    seen: set[str] = set()
    try:
        for value in paths:
            target, relative = _target(root, value)
            if relative in seen:
                continue
            seen.add(relative)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError(f"Checkpoint target {relative!r} must be a regular file")
            if target.is_file():
                content = target.read_bytes()
                content_path = f"files/{len(files):04d}.gz"
                body = directory / content_path
                body.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(body, "wb") as handle:
                    handle.write(content)
                with body.open("ab") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
                files.append(CheckpointFile(
                    path=relative,
                    existed=True,
                    sha256=_sha256_bytes(content),
                    size=len(content),
                    content_path=content_path,
                ))
            else:
                files.append(CheckpointFile(path=relative, existed=False))
        manifest = CheckpointManifest(
            id=checkpoint_id,
            workspace_id=str(workspace_id),
            thread_id=str(thread_id),
            created_at=datetime.now(timezone.utc),
            label=label.strip()[:200],
            files=files,
        )
        _write_json_atomic(
            directory / "manifest.json", manifest.model_dump(mode="json")
        )
        return manifest
    except Exception:
        if directory.exists():
            import shutil

            shutil.rmtree(directory)
        raise


def get_checkpoint(
    workspace_root: str | Path, checkpoint_id: str
) -> CheckpointManifest:
    path = _manifest_path(Path(workspace_root), checkpoint_id)
    if not path.is_file():
        raise FileNotFoundError(f"Checkpoint {checkpoint_id} was not found")
    return CheckpointManifest.model_validate_json(path.read_text(encoding="utf-8"))


def list_checkpoints(
    workspace_root: str | Path,
    *,
    workspace_id: str | None = None,
    thread_id: str | None = None,
) -> list[CheckpointManifest]:
    root = _checkpoint_root(Path(workspace_root).resolve())
    if not root.is_dir():
        return []
    manifests: list[CheckpointManifest] = []
    for path in root.glob("*/manifest.json"):
        try:
            value = CheckpointManifest.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if workspace_id is not None and value.workspace_id != str(workspace_id):
            continue
        if thread_id is not None and value.thread_id != str(thread_id):
            continue
        manifests.append(value)
    return sorted(manifests, key=lambda item: (item.created_at, item.id), reverse=True)


def _current_state(target: Path) -> tuple[bool, str | None]:
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("target is not a regular file")
    if not target.is_file():
        return False, None
    return True, _sha256_bytes(target.read_bytes())


def seal_checkpoint(workspace_root: str | Path, checkpoint_id: str) -> CheckpointManifest:
    """Record the expected post-write hashes used to detect later divergence."""
    root = Path(workspace_root).resolve()
    manifest = get_checkpoint(root, checkpoint_id)
    for item in manifest.files:
        target, _ = _target(root, item.path)
        existed, digest = _current_state(target)
        item.expected_current_existed = existed
        item.expected_current_sha256 = digest
    _write_json_atomic(
        _manifest_path(root, checkpoint_id), manifest.model_dump(mode="json")
    )
    return manifest


def preview_restore(
    workspace_root: str | Path, checkpoint_id: str
) -> RestorePreview:
    root = Path(workspace_root).resolve()
    manifest = get_checkpoint(root, checkpoint_id)
    changes: list[str] = []
    conflicts: list[str] = []
    for item in manifest.files:
        target, relative = _target(root, item.path)
        try:
            current_exists, current_sha = _current_state(target)
        except ValueError:
            conflicts.append(relative)
            continue
        if item.expected_current_existed is not None and (
            current_exists != item.expected_current_existed
            or (current_exists and current_sha != item.expected_current_sha256)
        ):
            conflicts.append(relative)
        if current_exists != item.existed or (
            current_exists and current_sha != item.sha256
        ):
            changes.append(relative)
    return RestorePreview(
        checkpoint_id=checkpoint_id,
        changes=changes,
        conflicts=conflicts,
    )


def _checkpoint_content(root: Path, manifest: CheckpointManifest, item: CheckpointFile) -> bytes:
    if not item.existed or not item.content_path:
        return b""
    directory = _manifest_path(root, manifest.id).parent.resolve()
    path = (directory / item.content_path).resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ValueError(f"Invalid content path for {item.path}") from exc
    with gzip.open(path, "rb") as handle:
        content = handle.read()
    if len(content) != item.size or _sha256_bytes(content) != item.sha256:
        raise ValueError(f"Checkpoint body for {item.path} is corrupt")
    return content


def _stage_file(target: Path, content: bytes) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.checkpoint-{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    return temporary


def restore_checkpoint(
    workspace_root: str | Path,
    checkpoint_id: str,
    *,
    force: bool = False,
) -> CheckpointManifest:
    root = Path(workspace_root).resolve()
    manifest = get_checkpoint(root, checkpoint_id)
    preview = preview_restore(root, checkpoint_id)
    if preview.conflicts and not force:
        raise CheckpointConflictError(preview.conflicts)

    staged: list[tuple[CheckpointFile, Path, Path | None]] = []
    previous: list[tuple[Path, bool, bytes]] = []
    try:
        for item in manifest.files:
            target, _ = _target(root, item.path)
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise CheckpointConflictError([item.path])
            content = _checkpoint_content(root, manifest, item)
            temporary = _stage_file(target, content) if item.existed else None
            staged.append((item, target, temporary))
            previous.append((target, target.is_file(), target.read_bytes() if target.is_file() else b""))

        committed = 0
        try:
            for item, target, temporary in staged:
                if item.existed:
                    if temporary is None:
                        raise RuntimeError("Staged checkpoint content is missing")
                    os.replace(temporary, target)
                elif target.is_file():
                    target.unlink()
                committed += 1
        except Exception:
            for target, existed, content in reversed(previous[:committed]):
                if existed:
                    os.replace(_stage_file(target, content), target)
                elif target.is_file():
                    target.unlink()
            raise
    finally:
        for _, _, temporary in staged:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return manifest
