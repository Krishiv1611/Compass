"""
Compass Change Tracker — File change history for undo/diff support.

Intercepts file modifications to maintain an in-memory stack of changes,
enabling /undo, /diff, and session change summary features.
"""

import os
import time
from dataclasses import dataclass, field


@dataclass
class FileChange:
    """Record of a single file modification."""

    path: str
    old_content: str
    new_content: str
    tool_name: str  # "write_to_file", "edit_file", etc.
    timestamp: float = field(default_factory=time.time)
    undone: bool = False

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
            "undone": self.undone,
        }


class ChangeTracker:
    """
    Tracks file changes made during a session.

    Maintains an ordered stack of FileChange objects. Supports:
    - Recording changes (before/after snapshots)
    - Undoing the last change
    - Listing all modified files
    - Generating cumulative diffs
    """

    def __init__(self):
        self._changes: list[FileChange] = []
        self._original_snapshots: dict[str, str] = {}  # path -> first-seen content

    def snapshot_before_write(self, path: str) -> str | None:
        """
        Capture the current file content before a write/edit operation.
        Returns the old content, or None if the file doesn't exist.
        """
        abs_path = os.path.abspath(path)
        try:
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Store original snapshot (first time only)
                if abs_path not in self._original_snapshots:
                    self._original_snapshots[abs_path] = content
                return content
            else:
                if abs_path not in self._original_snapshots:
                    self._original_snapshots[abs_path] = ""
                return ""
        except (UnicodeDecodeError, OSError):
            return None

    def record_change(
        self, path: str, old_content: str, new_content: str, tool_name: str
    ):
        """Record a file change after it has been made."""
        abs_path = os.path.abspath(path)
        change = FileChange(
            path=abs_path,
            old_content=old_content,
            new_content=new_content,
            tool_name=tool_name,
        )
        self._changes.append(change)

    def undo_last(self) -> FileChange | None:
        """
        Undo the most recent non-undone change by restoring the previous content.
        Returns the undone FileChange, or None if nothing to undo.
        """
        # Find the last non-undone change
        for i in range(len(self._changes) - 1, -1, -1):
            change = self._changes[i]
            if not change.undone:
                # Restore the file
                try:
                    with open(change.path, "w", encoding="utf-8") as f:
                        f.write(change.old_content)
                    change.undone = True
                    return change
                except Exception:
                    return None
        return None

    def get_changes(self, include_undone: bool = False) -> list[dict]:
        """Get all recorded changes as dicts."""
        changes = self._changes
        if not include_undone:
            changes = [c for c in changes if not c.undone]
        return [c.to_dict() for c in changes]

    def get_modified_files(self) -> list[str]:
        """Get list of unique file paths modified in this session."""
        seen = set()
        result = []
        for change in self._changes:
            if not change.undone and change.path not in seen:
                seen.add(change.path)
                result.append(change.path)
        return result

    def get_original_content(self, path: str) -> str | None:
        """Get the original content of a file before any modifications."""
        abs_path = os.path.abspath(path)
        return self._original_snapshots.get(abs_path)

    def get_current_content(self, path: str) -> str | None:
        """Read the current content of a file from disk."""
        abs_path = os.path.abspath(path)
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return f.read()
        except (FileNotFoundError, UnicodeDecodeError, OSError):
            return None

    @property
    def change_count(self) -> int:
        """Number of active (non-undone) changes."""
        return sum(1 for c in self._changes if not c.undone)

    @property
    def files_modified_count(self) -> int:
        """Number of unique files modified."""
        return len(self.get_modified_files())

    def clear(self):
        """Clear all change history."""
        self._changes.clear()
        self._original_snapshots.clear()
