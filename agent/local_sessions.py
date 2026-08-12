"""Workspace-local session metadata for database-free TUI use."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path


class LocalSessionStore:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.path = self.workspace_root / ".compass" / "sessions.json"

    def create(
        self,
        title: str = "",
        *,
        project_id: str | None = None,
        context_version: str | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": uuid.uuid4().hex,
            "thread_id": uuid.uuid4().hex,
            "title": title or "New Chat",
            "turn_count": 0,
            "created_at": now,
            "updated_at": now,
            "project_id": project_id,
            "context_version": context_version,
        }
        records = self._read()
        records.append(record)
        self._write(records)
        return record.copy()

    def get(self, thread_id_prefix: str) -> dict | None:
        matches = [
            record
            for record in self._read()
            if record["thread_id"] == thread_id_prefix
            or record["thread_id"].startswith(thread_id_prefix)
        ]
        if len(matches) != 1:
            return None
        return matches[0].copy()

    def list(self, limit: int = 10) -> list[dict]:
        records = sorted(
            self._read(),
            key=lambda record: record["updated_at"],
            reverse=True,
        )
        return [record.copy() for record in records[:limit]]

    def rename(self, thread_id: str, title: str) -> bool:
        records = self._read()
        record = self._find(records, thread_id)
        if record is None:
            return False
        record["title"] = title
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(records)
        return True

    def touch(
        self,
        thread_id: str,
        *,
        turn_count: int | None = None,
        title: str | None = None,
    ) -> dict | None:
        records = self._read()
        record = self._find(records, thread_id)
        if record is None:
            return None
        if turn_count is not None:
            record["turn_count"] = turn_count
        if title:
            record["title"] = title
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(records)
        return record.copy()

    def _read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    @staticmethod
    def _find(records: list[dict], thread_id: str) -> dict | None:
        for record in records:
            if record["thread_id"] == thread_id:
                return record
        return None

    def _write(self, records: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(
            f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            temporary.write_text(
                json.dumps(records, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
