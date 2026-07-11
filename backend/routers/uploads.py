"""
Session file uploads for RAG.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.session import ChatSession
from backend.models.upload import UploadedFile
from backend.models.user import User
from backend.schemas.upload import UploadCapabilityResponse, UploadResponse
from agent.rag.loaders import supported_extensions
from agent.rag.uploads import (
    MAX_UPLOAD_BYTES,
    delete_uploaded_document_chunks,
    delete_uploaded_file,
    index_uploaded_file,
    sanitize_filename,
    save_upload_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/uploads", tags=["uploads"])


def _get_owned_session(db: Session, user_id: str, session_id: str) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session


@router.get("/capabilities", response_model=UploadCapabilityResponse)
def upload_capabilities(current_user: User = Depends(get_current_user)):
    """Return supported upload types and size limits."""
    return UploadCapabilityResponse(
        max_upload_bytes=MAX_UPLOAD_BYTES,
        supported_extensions=supported_extensions(),
    )


@router.get("", response_model=list[UploadResponse])
def list_uploads(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List files uploaded to a session."""
    _get_owned_session(db, current_user.id, session_id)
    return (
        db.query(UploadedFile)
        .filter(
            UploadedFile.session_id == session_id,
            UploadedFile.user_id == current_user.id,
        )
        .order_by(UploadedFile.created_at.desc())
        .all()
    )


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a document, extract text, and index it for session RAG."""
    _get_owned_session(db, current_user.id, session_id)

    upload_id = uuid.uuid4().hex
    filename = sanitize_filename(file.filename or "upload")

    try:
        document_id, storage_path, size_bytes = await save_upload_file(
            file,
            current_user.id,
            session_id,
            document_id=upload_id,
            max_bytes=MAX_UPLOAD_BYTES,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Failed to store uploaded file")
        raise HTTPException(
            status_code=500, detail="Failed to store uploaded file"
        ) from exc

    record = UploadedFile(
        id=document_id,
        user_id=current_user.id,
        session_id=session_id,
        filename=filename,
        content_type=file.content_type,
        size_bytes=size_bytes,
        storage_path=str(storage_path),
        status="processing",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        result = index_uploaded_file(
            storage_path,
            document_id=document_id,
            filename=filename,
            user_id=current_user.id,
            session_id=session_id,
            content_type=file.content_type or "",
        )
        record.status = "ready"
        record.chunk_count = result.chunks_added
        record.error = None
    except Exception as exc:
        logger.exception("Failed to index uploaded file")
        record.status = "failed"
        record.error = str(exc)[:1000]
    finally:
        db.commit()
        db.refresh(record)

    return record


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    session_id: str,
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an uploaded file and its vector chunks."""
    _get_owned_session(db, current_user.id, session_id)
    record = (
        db.query(UploadedFile)
        .filter(
            UploadedFile.id == upload_id,
            UploadedFile.session_id == session_id,
            UploadedFile.user_id == current_user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found"
        )

    delete_uploaded_document_chunks(record.id)
    delete_uploaded_file(record.storage_path)
    db.delete(record)
    db.commit()
    return None
