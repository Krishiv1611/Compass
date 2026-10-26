"""Incremental workspace metadata updates for ordinary file mutations."""

import hashlib
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    before_size: int
    after_size: int
    operation: Literal["create", "edit", "delete", "rename"]


def apply_workspace_metadata_delta(workspace, changes: list[FileChange]) -> None:
    """Apply exact known file deltas without walking the workspace tree."""
    count_delta = sum(
        1 if change.operation == "create" else -1 if change.operation == "delete" else 0
        for change in changes
    )
    size_delta = sum(change.after_size - change.before_size for change in changes)
    workspace.file_count = max(0, int(workspace.file_count or 0) + count_delta)
    workspace.size_bytes = max(0, int(workspace.size_bytes or 0) + size_delta)

    if hasattr(workspace, "context_version") and changes:
        digest = hashlib.sha256()
        digest.update(str(getattr(workspace, "context_version", "")).encode())
        for change in sorted(changes, key=lambda item: (item.path, item.operation)):
            digest.update(
                f"{change.operation}\0{change.path}\0{change.before_size}\0{change.after_size}".encode()
            )
        workspace.context_version = f"delta:{digest.hexdigest()[:32]}"
        session = getattr(workspace, "session", None)
        if session is not None and getattr(session, "active_workspace_id", None) == getattr(workspace, "id", None):
            session.context_version = workspace.context_version
