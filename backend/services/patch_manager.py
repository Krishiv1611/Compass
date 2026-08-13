import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.patch import WorkspacePatch
from backend.services.workspace import get_workspace


@dataclass(slots=True)
class StagedFile:
    target: Path
    temporary: Path | None
    after_exists: bool
    before_exists: bool
    before_bytes: bytes


def _write_staged_file(target: Path, content: bytes) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.compass-{uuid.uuid4().hex}.tmp")
    with temporary.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    return temporary


def stage_patch_files(
    workspace_dir: Path,
    changes: list[dict],
    *,
    use_before: bool = False,
) -> list[StagedFile]:
    """Validate all targets and fully stage desired bytes before mutation."""
    staged: list[StagedFile] = []
    try:
        for change in changes:
            _assert_change_matches(
                workspace_dir,
                change,
                use_before=not use_before,
            )
            target = _target_for_change(workspace_dir, change.get("path", ""))
            before_exists = target.is_file()
            before_bytes = target.read_bytes() if before_exists else b""
            prefix = "before" if use_before else "after"
            desired_exists = bool(
                change.get(
                    f"{prefix}_exists",
                    change.get("type") != ("create" if use_before else "delete"),
                )
            )
            content = change.get(prefix)
            if content is None:
                content = change.get("content", "")
            temporary = (
                _write_staged_file(target, str(content).encode("utf-8"))
                if desired_exists
                else None
            )
            staged.append(
                StagedFile(
                    target=target,
                    temporary=temporary,
                    after_exists=desired_exists,
                    before_exists=before_exists,
                    before_bytes=before_bytes,
                )
            )
        return staged
    except Exception:
        discard_staged_files(staged)
        raise


def discard_staged_files(staged: list[StagedFile]) -> None:
    for item in staged:
        if item.temporary and item.temporary.exists():
            item.temporary.unlink()


def _restore_staged_file(item: StagedFile) -> None:
    if item.before_exists:
        restore = _write_staged_file(item.target, item.before_bytes)
        os.replace(restore, item.target)
    elif item.target.is_file():
        item.target.unlink()


def commit_staged_files(staged: list[StagedFile]) -> None:
    """Commit staged targets and compensate already-replaced targets on failure."""
    committed: list[StagedFile] = []
    try:
        for item in staged:
            if item.after_exists:
                if item.temporary is None:
                    raise RuntimeError("Staged content is missing")
                os.replace(item.temporary, item.target)
            elif item.target.is_file():
                item.target.unlink()
            committed.append(item)
    except Exception:
        for item in reversed(committed):
            _restore_staged_file(item)
        raise
    finally:
        discard_staged_files(staged)


def _target_for_change(workspace_dir: Path, path: str) -> Path:
    if not path:
        raise HTTPException(status_code=400, detail="Change path is required")
    target = (workspace_dir / path).resolve()
    try:
        target.relative_to(workspace_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Change path is outside the workspace") from exc
    return target


def _file_state(target: Path) -> tuple[bool, str]:
    if not target.exists():
        return False, ""
    if not target.is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patch conflict: {target.name} is not a file",
        )
    try:
        return True, target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patch conflict: {target.name} is no longer a UTF-8 text file",
        ) from exc


def _normalise_path(workspace_dir: Path, path: str) -> str:
    target = _target_for_change(workspace_dir, path)
    return target.relative_to(workspace_dir.resolve()).as_posix()


def _enrich_change(
    workspace_dir: Path,
    change: dict,
    previous: dict | None = None,
) -> dict:
    path = _normalise_path(workspace_dir, change.get("path", ""))
    target = _target_for_change(workspace_dir, path)
    change_type = change.get("type", "edit")
    if change_type not in {"create", "edit", "delete"}:
        raise HTTPException(status_code=400, detail=f"Unsupported change type: {change_type}")

    if previous:
        before_exists = bool(previous.get("before_exists", previous.get("type") != "create"))
        before = previous.get("before", "")
    else:
        before_exists, before = _file_state(target)

    after_exists = change_type != "delete"
    after = change.get("after")
    if after is None:
        after = change.get("content", "")
    if not isinstance(after, str):
        raise HTTPException(status_code=400, detail=f"Change content for {path} must be text")

    effective_type = change_type
    if after_exists:
        effective_type = "edit" if before_exists else "create"

    return {
        "type": effective_type,
        "path": path,
        "before": before,
        "before_exists": before_exists,
        "after": after,
        "after_exists": after_exists,
        "content": after,
        "status": "pending",
    }


def _assert_change_matches(
    workspace_dir: Path,
    change: dict,
    *,
    use_before: bool,
) -> None:
    target = _target_for_change(workspace_dir, change.get("path", ""))
    actual_exists, actual_content = _file_state(target)
    prefix = "before" if use_before else "after"
    expected_exists = bool(
        change.get(
            f"{prefix}_exists",
            change.get("type") != ("create" if use_before else "delete"),
        )
    )
    expected_content = change.get(prefix, "")
    if actual_exists != expected_exists or (
        actual_exists and actual_content != expected_content
    ):
        operation = "apply" if use_before else "undo"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Patch conflict in {change.get('path')}: the file changed after "
                f"this patch was captured. Refresh the diff before trying to {operation} it."
            ),
        )


def _write_change(workspace_dir: Path, change: dict, *, use_before: bool = False) -> None:
    target = _target_for_change(workspace_dir, change.get("path", ""))
    change_type = change.get("type")
    if use_before:
        before_exists = bool(change.get("before_exists", change_type != "create"))
        if not before_exists:
            if target.is_file():
                target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.get("before", ""), encoding="utf-8")
        return

    after_exists = bool(change.get("after_exists", change_type != "delete"))
    content = change.get("after")
    if content is None:
        content = change.get("content", "")
    if after_exists:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    elif target.is_file():
        target.unlink()


def _update_patch_status(patch: WorkspacePatch) -> None:
    statuses = [change.get("status", "pending") for change in patch.changes]
    if any(value == "pending" for value in statuses):
        patch.status = "pending"
    elif any(value == "applied" for value in statuses):
        patch.status = "applied"
    elif any(value == "reverted" for value in statuses):
        patch.status = "reverted"
    else:
        patch.status = "rejected"


def create_patch(db: Session, workspace_id: str, run_id: str | None, changes: list) -> WorkspacePatch:
    """Create a new WorkspacePatch with proposed changes.

    Each change dict should have: {type, path, content}.
    This function enriches each change with 'before' (existing content)
    and 'after' (new content) so the diff viewer has real data.
    """
    from backend.models.workspace import Workspace

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_dir = Path(workspace.storage_path)

    enriched_changes = []
    for change in changes:
        normalised_path = _normalise_path(workspace_dir, change.get("path", ""))
        existing_index = next(
            (
                index
                for index, item in enumerate(enriched_changes)
                if item.get("path") == normalised_path
            ),
            None,
        )
        previous = enriched_changes[existing_index] if existing_index is not None else None
        enriched = _enrich_change(workspace_dir, change, previous)
        if existing_index is None:
            enriched_changes.append(enriched)
        else:
            enriched_changes[existing_index] = enriched

    patch = WorkspacePatch(
        workspace_id=workspace_id,
        run_id=run_id,
        project_id=workspace.project_id if workspace else None,
        context_version=workspace.context_version if workspace else None,
        status="pending",
        changes=enriched_changes,
    )
    db.add(patch)
    db.commit()
    db.refresh(patch)
    if run_id:
        from backend.models.run import RunEvent

        db.add(
            RunEvent(
                run_id=run_id,
                event_type="workspace_patch",
                content={
                    "patch_id": patch.id,
                    "workspace_id": workspace.id,
                    "session_id": workspace.session_id,
                },
            )
        )
        db.commit()
    return patch


def append_patch_change(
    db: Session,
    workspace_id: str,
    run_id: str | None,
    change: dict,
) -> WorkspacePatch:
    """Add or consolidate a pending file proposal for a run."""
    from backend.models.workspace import Workspace

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if not run_id:
        return create_patch(db, workspace_id, run_id, [change])

    patch = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.run_id == run_id,
            WorkspacePatch.workspace_id == workspace_id,
            WorkspacePatch.status == "pending",
        )
        .first()
    )
    if not patch:
        return create_patch(db, workspace_id, run_id, [change])

    workspace_dir = Path(workspace.storage_path)
    path = _normalise_path(workspace_dir, change.get("path", ""))
    updated = [dict(item) for item in patch.changes]
    existing_index = next(
        (index for index, item in enumerate(updated) if item.get("path") == path),
        None,
    )
    previous = updated[existing_index] if existing_index is not None else None
    enriched = _enrich_change(workspace_dir, change, previous)
    if existing_index is None:
        updated.append(enriched)
    else:
        updated[existing_index] = enriched
    patch.changes = updated
    patch.version += 1
    db.commit()
    db.refresh(patch)
    return patch


def get_pending_file_overlay(
    db: Session,
    workspace_id: str,
    run_id: str | None,
    path: str,
) -> tuple[bool, str] | None:
    """Return a run's latest proposed file state, if one exists."""
    if not run_id:
        return None
    patch = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.run_id == run_id,
            WorkspacePatch.workspace_id == workspace_id,
            WorkspacePatch.status == "pending",
        )
        .first()
    )
    if not patch:
        return None
    normalised = Path(os.path.normpath(path)).as_posix()
    for change in reversed(patch.changes):
        if (
            Path(os.path.normpath(change.get("path", ""))).as_posix() == normalised
            and change.get("status", "pending") == "pending"
        ):
            exists = bool(change.get("after_exists", change.get("type") != "delete"))
            return exists, change.get("after", change.get("content", ""))
    return None


def get_patch(db: Session, patch_id: str, user_id: str) -> WorkspacePatch:
    patch = db.query(WorkspacePatch).filter(WorkspacePatch.id == patch_id).first()
    if not patch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patch not found")

    workspace = get_workspace(db, patch.workspace_id, user_id)
    return patch


def _assert_patch_version(patch: WorkspacePatch, expected_version: int) -> None:
    if patch.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patch changed in another client. Refresh before retrying.",
        )


def _commit_patch_update(
    db: Session,
    patch: WorkspacePatch,
    expected_version: int,
    values: dict,
) -> WorkspacePatch:
    updated = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.id == patch.id,
            WorkspacePatch.version == expected_version,
        )
        .update(
            {**values, "version": expected_version + 1},
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patch changed in another client. Refresh before retrying.",
        )
    db.commit()
    db.expire_all()
    return db.query(WorkspacePatch).filter(WorkspacePatch.id == patch.id).one()


def apply_patch(
    db: Session,
    patch_id: str,
    user_id: str,
    *,
    expected_version: int,
) -> WorkspacePatch:
    """Apply a pending patch to the filesystem."""
    patch = get_patch(db, patch_id, user_id)
    _assert_patch_version(patch, expected_version)
    if patch.status != "pending":
        raise HTTPException(status_code=400, detail=f"Patch is already {patch.status}")

    workspace = get_workspace(db, patch.workspace_id, user_id)
    workspace_dir = Path(workspace.storage_path)

    pending = [
        dict(change)
        for change in patch.changes
        if change.get("status", "pending") == "pending"
    ]
    updated_changes = []
    for raw_change in patch.changes:
        change = dict(raw_change)
        if change.get("status", "pending") == "pending":
            change["status"] = "applied"
        updated_changes.append(change)

    staged = stage_patch_files(workspace_dir, pending)
    commit_staged_files(staged)
    try:
        patch = _commit_patch_update(
            db,
            patch,
            expected_version,
            {
                "changes": updated_changes,
                "status": "applied",
                "applied_at": datetime.now(timezone.utc),
            },
        )
    except Exception:
        for item in reversed(staged):
            _restore_staged_file(item)
        raise
    from backend.services.workspace import update_workspace_stats
    update_workspace_stats(db, workspace, sync_session=False)
    return patch


def reject_patch(
    db: Session,
    patch_id: str,
    user_id: str,
    *,
    expected_version: int,
) -> WorkspacePatch:
    """Reject a pending patch."""
    patch = get_patch(db, patch_id, user_id)
    _assert_patch_version(patch, expected_version)
    if patch.status != "pending":
        raise HTTPException(status_code=400, detail=f"Patch is already {patch.status}")

    changes = [
        {**change, "status": "rejected"}
        if change.get("status", "pending") == "pending"
        else change
        for change in patch.changes
    ]
    return _commit_patch_update(
        db,
        patch,
        expected_version,
        {"changes": changes, "status": "rejected"},
    )


def accept_all_patches(db: Session, workspace_id: str, user_id: str) -> int:
    """Accept all pending patches for a workspace. Returns count applied."""
    from backend.models.workspace import Workspace

    patches = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.workspace_id == workspace_id,
            WorkspacePatch.status == "pending",
        )
        .all()
    )
    count = 0
    for patch in patches:
        apply_patch(
            db,
            patch.id,
            user_id,
            expected_version=patch.version,
        )
        count += 1
    return count


def reject_all_patches(db: Session, workspace_id: str, user_id: str) -> int:
    """Reject all pending patches for a workspace. Returns count rejected."""
    patches = (
        db.query(WorkspacePatch)
        .filter(
            WorkspacePatch.workspace_id == workspace_id,
            WorkspacePatch.status == "pending",
        )
        .all()
    )
    count = 0
    for patch in patches:
        reject_patch(
            db,
            patch.id,
            user_id,
            expected_version=patch.version,
        )
        count += 1
    return count

def undo_patch(
    db: Session,
    patch_id: str,
    user_id: str,
    *,
    expected_version: int,
) -> WorkspacePatch:
    """Undo an applied patch (revert file changes)."""
    patch = get_patch(db, patch_id, user_id)
    _assert_patch_version(patch, expected_version)
    if patch.status != "applied":
        raise HTTPException(status_code=400, detail=f"Cannot undo patch with status {patch.status}")

    workspace = get_workspace(db, patch.workspace_id, user_id)
    workspace_dir = Path(workspace.storage_path)

    applied = [
        dict(change)
        for change in patch.changes
        if change.get("status", "applied") == "applied"
    ]
    updated_changes = []
    for raw_change in patch.changes:
        change = dict(raw_change)
        if change.get("status", "applied") == "applied":
            change["status"] = "reverted"
        updated_changes.append(change)

    staged = stage_patch_files(workspace_dir, applied, use_before=True)
    commit_staged_files(staged)
    try:
        patch = _commit_patch_update(
            db,
            patch,
            expected_version,
            {"changes": updated_changes, "status": "reverted"},
        )
    except Exception:
        for item in reversed(staged):
            _restore_staged_file(item)
        raise
    from backend.services.workspace import update_workspace_stats
    update_workspace_stats(db, workspace, sync_session=False)
    return patch


def resolve_patch_file(
    db: Session,
    patch_id: str,
    user_id: str,
    path: str,
    action: str,
    *,
    expected_version: int,
) -> WorkspacePatch:
    """Apply, reject, or undo one file in a patch."""
    patch = get_patch(db, patch_id, user_id)
    _assert_patch_version(patch, expected_version)
    workspace = get_workspace(db, patch.workspace_id, user_id)
    workspace_dir = Path(workspace.storage_path)
    found = False
    updated_changes = []
    selected_change = None

    for raw_change in patch.changes:
        change = dict(raw_change)
        if change.get("path") != path:
            updated_changes.append(change)
            continue
        found = True
        current = change.get("status", "pending")
        if action == "apply" and current == "pending":
            change["status"] = "applied"
            selected_change = dict(raw_change)
        elif action == "reject" and current == "pending":
            change["status"] = "rejected"
        elif action == "undo" and current == "applied":
            change["status"] = "reverted"
            selected_change = dict(raw_change)
        else:
            raise HTTPException(status_code=400, detail=f"Cannot {action} a {current} change")
        updated_changes.append(change)

    if not found:
        raise HTTPException(status_code=404, detail="File change not found")

    statuses = [change.get("status", "pending") for change in updated_changes]
    if any(value == "pending" for value in statuses):
        patch_status = "pending"
    elif any(value == "applied" for value in statuses):
        patch_status = "applied"
    elif any(value == "reverted" for value in statuses):
        patch_status = "reverted"
    else:
        patch_status = "rejected"
    values = {"changes": updated_changes, "status": patch_status}
    if action == "apply":
        values["applied_at"] = datetime.now(timezone.utc)

    staged = []
    if selected_change is not None:
        staged = stage_patch_files(
            workspace_dir,
            [selected_change],
            use_before=action == "undo",
        )
        commit_staged_files(staged)
    try:
        patch = _commit_patch_update(
            db,
            patch,
            expected_version,
            values,
        )
    except Exception:
        for item in reversed(staged):
            _restore_staged_file(item)
        raise
    if action in {"apply", "undo"}:
        from backend.services.workspace import update_workspace_stats
        update_workspace_stats(db, workspace, sync_session=False)
    return patch
