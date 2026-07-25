from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_core.runnables.config import RunnableConfig

from agent.rag.vector_store import get_vector_store
from agent.tools.utils import get_workspace_for_tool

load_dotenv()

_rag_scope: ContextVar[dict[str, str] | None] = ContextVar("rag_scope", default=None)


def set_rag_scope(
    user_id: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    context_version: str | None = None,
):
    """Set request-local RAG scope for web sessions."""
    scope = {}
    if user_id:
        scope["user_id"] = user_id
    if session_id:
        scope["session_id"] = session_id
    if project_id:
        scope["project_id"] = project_id
    if context_version:
        scope["context_version"] = context_version
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

    workspace_terms: list[dict[str, str]] = [{"source_type": "workspace"}]
    if scope.get("project_id"):
        workspace_terms.append({"project_id": scope["project_id"]})
    if scope.get("context_version"):
        workspace_terms.append({"context_version": scope["context_version"]})

    return {"$or": [{"$and": workspace_terms}, {"$and": upload_terms}]}


def _format_source(doc) -> str:
    source_type = doc.metadata.get("source_type", "workspace")
    filename = doc.metadata.get("filename")
    source = filename or doc.metadata.get("source", "Unknown Source")

    if source_type == "upload":
        return f"uploaded:{source}"
    return str(source)


@tool
def codebase_search(
    query: str,
    limit: int = 5,
    config: RunnableConfig = None,
) -> str:
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
        workspace = get_workspace_for_tool(config)
        configurable = (config or {}).get("configurable", {})
        scope_token = set_rag_scope(
            user_id=configurable.get("user_id"),
            session_id=configurable.get("session_id"),
            project_id=workspace.project_id,
            context_version=workspace.context_version,
        )
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
    finally:
        if "scope_token" in locals():
            reset_rag_scope(scope_token)
