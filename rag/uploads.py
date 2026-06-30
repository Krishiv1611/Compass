"""
Uploaded-document ingestion for session-scoped RAG.
"""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile

from rag.chunker import chunk_file
from rag.loaders import SUPPORTED_EXTENSIONS, extract_text
from rag.vector_store import WORKSPACE_DIR, delete_chunks_by_filter, get_vector_store

UPLOAD_ROOT = Path(WORKSPACE_DIR) / ".compass" / "uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@dataclass
class UploadIndexResult:
    document_id: str
    filename: str
    storage_path: str
    text_chars: int
    chunks_added: int


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe display filename."""
    name = Path(filename or "upload").name.strip() or "upload"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name[:180]


def is_supported_upload(filename: str) -> bool:
    """Check if a filename can be parsed for RAG."""
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def build_storage_path(user_id: str, session_id: str, document_id: str, filename: str) -> Path:
    """Build the private storage path for an uploaded file."""
    safe_name = sanitize_filename(filename)
    return UPLOAD_ROOT / user_id / session_id / f"{document_id}_{safe_name}"


async def save_upload_file(
    upload: UploadFile,
    user_id: str,
    session_id: str,
    document_id: str | None = None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> tuple[str, Path, int]:
    """Persist an UploadFile to disk with a size limit."""
    original_name = sanitize_filename(upload.filename or "upload")
    if not is_supported_upload(original_name):
        ext = Path(original_name).suffix.lower() or "unknown"
        raise ValueError(f"Unsupported file type '{ext}'.")

    doc_id = document_id or uuid.uuid4().hex
    destination = build_storage_path(user_id, session_id, doc_id, original_name)
    destination.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    try:
        with destination.open("wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Upload exceeds the {max_bytes // (1024 * 1024)} MB limit.")
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return doc_id, destination, total


def index_uploaded_file(
    path: str | Path,
    *,
    document_id: str,
    filename: str,
    user_id: str,
    session_id: str,
    content_type: str = "",
) -> UploadIndexResult:
    """Extract text from a file and index it into the shared vector store."""
    storage_path = Path(path)
    extracted = extract_text(storage_path, original_filename=filename).strip()
    if not extracted:
        raise ValueError("No indexable text could be extracted from the uploaded file.")

    uploaded_at = datetime.now(timezone.utc).isoformat()
    chunks = chunk_file(
        filename,
        extracted,
        metadata={
            "source": str(storage_path),
            "source_type": "upload",
            "document_id": document_id,
            "filename": filename,
            "user_id": user_id,
            "session_id": session_id,
            "content_type": content_type or "",
            "uploaded_at": uploaded_at,
        },
    )
    chunks = [chunk for chunk in chunks if chunk.page_content.strip()]
    if not chunks:
        raise ValueError("No non-empty chunks were produced from the uploaded file.")

    vector_store = get_vector_store(create=True)
    if vector_store is None:
        raise RuntimeError("Vector store could not be initialized.")

    delete_uploaded_document_chunks(document_id)
    vector_store.add_documents(chunks)

    return UploadIndexResult(
        document_id=document_id,
        filename=filename,
        storage_path=str(storage_path),
        text_chars=len(extracted),
        chunks_added=len(chunks),
    )


def delete_uploaded_document_chunks(document_id: str) -> int:
    """Delete all vector chunks for an uploaded document."""
    return delete_chunks_by_filter({"document_id": document_id})


def delete_uploaded_file(path: str | None) -> None:
    """Best-effort deletion of a stored uploaded file."""
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def delete_session_upload_dir(user_id: str, session_id: str) -> None:
    """Best-effort deletion of all raw uploads for a session."""
    target = UPLOAD_ROOT / user_id / session_id
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
