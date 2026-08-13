"""Public workspace schemas that never expose server filesystem paths."""

from datetime import datetime

from pydantic import BaseModel


class WorkspaceResponse(BaseModel):
    id: str
    session_id: str
    name: str
    source_type: str
    status: str
    project_id: str | None = None
    git_remote: str | None = None
    git_branch: str | None = None
    git_head: str | None = None
    context_version: str | None = None
    file_count: int
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
