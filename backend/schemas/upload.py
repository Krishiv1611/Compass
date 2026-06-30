from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    """Metadata returned for an uploaded RAG file."""

    id: str
    session_id: str
    filename: str
    content_type: str | None = None
    size_bytes: int
    status: str
    error: str | None = None
    chunk_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadCapabilityResponse(BaseModel):
    """Frontend upload limits and supported file types."""

    max_upload_bytes: int
    supported_extensions: list[str]
