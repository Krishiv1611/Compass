from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool

from rag.vector_store import WORKSPACE_DIR, get_vector_store

load_dotenv()

_rag_scope: ContextVar[dict[str, str] | None] = ContextVar("rag_scope", default=None)


def set_rag_scope(user_id: str | None = None, session_id: str | None = None):
    """Set request-local RAG scope for web sessions."""
    scope = {}
    if user_id:
        scope["user_id"] = user_id
    if session_id:
        scope["session_id"] = session_id
    return _rag_scope.set(scope or None)


def reset_rag_scope(token) -> None:
    """Reset request-local RAG scope."""
    _rag_scope.reset(token)


def _scope_filter() -> dict[str, Any] | None:
    scope = _rag_scope.get()
    if not scope:
        return None

    upload_terms: list[dict[str, str]] = [{"source_type": "upload"}]
    if scope.get("user_id"):
        upload_terms.append({"user_id": scope["user_id"]})
    if scope.get("session_id"):
        upload_terms.append({"session_id": scope["session_id"]})

    return {
        "$or": [
            {"source_type": "workspace"},
            {"$and": upload_terms},
        ]
    }


def _format_source(doc) -> str:
    source_type = doc.metadata.get("source_type", "workspace")
    filename = doc.metadata.get("filename")
    source = filename or doc.metadata.get("source", "Unknown Source")

    if source_type == "workspace" and isinstance(source, str) and source.startswith(WORKSPACE_DIR):
        source = os.path.relpath(source, WORKSPACE_DIR)

    if source_type == "upload":
        return f"uploaded:{source}"
    return str(source)


@tool
def codebase_search(query: str, limit: int = 5) -> str:
    """
    Search indexed project code and uploaded files semantically.

    Use this tool when you need to find a concept, function, class, feature,
    or information that may be inside the indexed codebase or files uploaded
    to the current chat session.

    Args:
        query: A natural language description of what you are looking for.
        limit: Max number of chunks to return (default 5).
    """
    vstore = get_vector_store(create=False)
    if vstore is None:
        return "Error: RAG index not found in .compass/chroma. Index the workspace or upload files first."

    try:
        search_filter = _scope_filter()
        kwargs: dict[str, Any] = {"k": limit}
        if search_filter:
            kwargs["filter"] = search_filter
        results = vstore.similarity_search(query, **kwargs)

        if not results:
            return f"No relevant indexed context found for query: '{query}'"

        formatted_results = []
        for i, doc in enumerate(results, 1):
            source = _format_source(doc)
            formatted_results.append(
                f"--- Result {i} | Source: {source} ---\n{doc.page_content}\n"
            )

        return "\n".join(formatted_results)

    except Exception as e:
        return f"Error performing semantic search: {str(e)}"