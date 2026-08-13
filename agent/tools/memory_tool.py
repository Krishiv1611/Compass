"""Scoped long-term memory backed by LangGraph's PostgresStore.

The store and embedding client are initialized on first memory access, so normal
chat and backend startup do not pay the semantic-memory startup cost.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Iterable

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.store.base import BaseStore, Op, Result
from langgraph.store.postgres import PostgresStore

load_dotenv()

DB_URI = os.environ.get("DB_URI")
_stores: dict[str, PostgresStore] = {}
_store_contexts: dict[str, object] = {}
_store_errors: dict[str, str] = {}
_store_error: str | None = None
_store_lock = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_embedding_index(provider_config: dict | None) -> dict | None:
    config = provider_config or {}
    provider = config.get("embedding_provider")
    model = config.get("embedding_model")
    api_key = config.get("embedding_api_key")
    if not (provider and model and api_key):
        return None
    if provider in {"openrouter", "openai"}:
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            model=str(model).removeprefix("openai/"),
            base_url="https://openrouter.ai/api/v1"
            if provider == "openrouter"
            else None,
            api_key=api_key,
            check_embedding_ctx_length=False,
        )
    elif provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embeddings = GoogleGenerativeAIEmbeddings(
            model=str(model).removeprefix("google/"),
            google_api_key=api_key,
        )
    else:
        return None
    return {"dims": 1024, "embed": embeddings, "fields": ["content"]}


def get_memory_store(provider_config: dict | None = None) -> PostgresStore | None:
    """Return a store whose embedding client is isolated by credential."""
    global _store_error
    config = provider_config or {}
    embedding_key = str(config.get("embedding_api_key") or "")
    store_key = (
        hashlib.sha256(embedding_key.encode()).hexdigest()
        if embedding_key
        else "plain"
    )
    if store_key in _stores:
        return _stores[store_key]
    if not DB_URI or store_key in _store_errors:
        return None

    with _store_lock:
        if store_key in _stores:
            return _stores[store_key]
        try:
            index = _memory_embedding_index(provider_config)
            store_context = PostgresStore.from_conn_string(DB_URI, index=index)
            store = store_context.__enter__()
            store.setup()
            _store_contexts[store_key] = store_context
            _stores[store_key] = store
            return store
        except Exception as exc:
            _store_error = str(exc)
            _store_errors[store_key] = _store_error
            return None


class LazyMemoryStore(BaseStore):
    """BaseStore proxy that keeps LangGraph Store injection lazy."""

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        store = get_memory_store()
        if store is None:
            raise RuntimeError(_store_error or "Long-term memory database is not configured.")
        return store.batch(ops)

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return await asyncio.to_thread(self.batch, list(ops))


MEMORY_STORE = LazyMemoryStore()


def memory_namespace(
    user_id: str,
    *,
    scope: str = "global",
    project_id: str | None = None,
    category: str | None = None,
) -> tuple[str, ...]:
    """Build an isolated namespace for one user and optional project."""
    namespace = ("users", str(user_id), "memory")
    if scope == "project" and project_id:
        namespace += ("projects", str(project_id))
    else:
        namespace += ("global",)
    if category:
        namespace += (category.strip().lower(),)
    return namespace


def _scope_from_config(
    config: RunnableConfig | None, scope: str, category: str
) -> tuple[tuple[str, ...], str, str | None]:
    configurable = (config or {}).get("configurable", {})
    user_id = str(configurable.get("user_id") or "cli")
    project_id = configurable.get("project_id")
    resolved_scope = "project" if scope == "project" and project_id else "global"
    return (
        memory_namespace(
            user_id,
            scope=resolved_scope,
            project_id=str(project_id) if project_id else None,
            category=category or None,
        ),
        resolved_scope,
        str(project_id) if project_id else None,
    )


def list_memories(
    user_id: str,
    *,
    scope: str = "global",
    project_id: str | None = None,
    limit: int = 100,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    store = get_memory_store()
    if store is None:
        return [], False, _store_error
    namespace = memory_namespace(user_id, scope=scope, project_id=project_id)
    results = store.search(namespace, limit=min(max(limit, 1), 200))
    return [
        {
            "key": item.key,
            **item.value,
            "updated_at": str(item.updated_at) if item.updated_at else item.value.get("updated_at"),
        }
        for item in results
    ], True, None


def save_memory(
    user_id: str,
    content: str,
    *,
    key: str | None = None,
    scope: str = "global",
    project_id: str | None = None,
    category: str = "general",
    enabled: bool = True,
) -> dict[str, Any]:
    store = get_memory_store()
    if store is None:
        raise RuntimeError(_store_error or "Long-term memory database is not configured.")
    content = content.strip()
    if not content:
        raise ValueError("Memory content cannot be empty.")
    memory_key = (key or hashlib.sha256(content.encode()).hexdigest()[:12]).strip()
    namespace = memory_namespace(user_id, scope=scope, project_id=project_id)
    existing = store.get(namespace, memory_key)
    created_at = existing.value.get("created_at") if existing else _now()
    value = {
        "content": content,
        "category": category.strip() or "general",
        "scope": scope,
        "project_id": project_id if scope == "project" else None,
        "enabled": enabled,
        "created_at": created_at,
        "updated_at": _now(),
    }
    store.put(namespace, memory_key, value)
    return {"key": memory_key, **value}


def delete_memory(
    user_id: str,
    key: str,
    *,
    scope: str = "global",
    project_id: str | None = None,
) -> None:
    store = get_memory_store()
    if store is None:
        raise RuntimeError(_store_error or "Long-term memory database is not configured.")
    store.delete(memory_namespace(user_id, scope=scope, project_id=project_id), key)



def recall_memories(config: RunnableConfig | None, limit: int = 8) -> list[str]:
    """Return enabled global and project memories for an executor turn."""
    configurable = (config or {}).get("configurable", {})
    store = get_memory_store(configurable)
    if store is None:
        return []
    user_id = str(configurable.get("user_id") or "cli")
    project_id = configurable.get("project_id")
    namespaces = [memory_namespace(user_id)]
    if project_id:
        namespaces.append(
            memory_namespace(user_id, scope="project", project_id=str(project_id))
        )
    recalled: list[str] = []
    for namespace in namespaces:
        for item in store.search(namespace, limit=limit):
            if not item.value.get("enabled", True):
                continue
            content = str(item.value.get("content", "")).strip()
            if content and content not in recalled:
                recalled.append(content)
            if len(recalled) >= limit:
                return recalled
    return recalled

@tool
def memory(
    action: str,
    content: str = "",
    key: str = "",
    namespace: str = "",
    scope: str = "global",
    limit: int = 5,
    *,
    config: RunnableConfig,
) -> str:
    """Save or retrieve durable user memory.

    Use global scope for user preferences that apply everywhere and project
    scope for facts that only apply to the active project. Actions are save,
    search, get, list, and delete.
    """
    configurable = (config or {}).get("configurable", {})
    store = get_memory_store(configurable)
    if store is None:
        return f"Memory unavailable: {_store_error or 'database not configured'}."

    action = action.strip().lower()
    ns, resolved_scope, project_id = _scope_from_config(config, scope, namespace)

    if (
        action == "search"
        and configurable.get("execution_target") == "web"
        and not configurable.get("embedding_api_key")
    ):
        return (
            "Memory semantic search is disabled. "
            "Configure an embedding provider credential."
        )

    if action == "save":
        value = save_memory(
            str(configurable.get("user_id") or "cli"),
            content,
            key=key or None,
            scope=resolved_scope,
            project_id=project_id,
            category=namespace or "general",
        )
        return f"Saved memory '{value['key']}' in {resolved_scope} scope."

    if action == "search":
        if not content.strip():
            return "Error: content is required for search."
        try:
            results = store.search(ns, query=content.strip(), limit=limit)
        except Exception:
            results = [
                item for item in store.search(ns, limit=100)
                if content.lower() in str(item.value.get("content", "")).lower()
            ][:limit]
        enabled_results = [item for item in results if item.value.get("enabled", True)]
        if not enabled_results:
            return "No matching memories found."
        return "\n".join(
            f"[{item.key}] {item.value.get('content', '')}" for item in enabled_results
        )

    if action == "get":
        item = store.get(ns, key.strip()) if key.strip() else None
        return str(item.value) if item else "No memory found."

    if action == "list":
        results = store.search(ns, limit=limit)
        return "\n".join(
            f"[{item.key}] {item.value.get('content', '')}" for item in results
        ) or "No memories found."

    if action == "delete":
        if not key.strip():
            return "Error: key is required for delete."
        store.delete(ns, key.strip())
        return f"Deleted memory '{key.strip()}'."

    return "Error: action must be save, search, get, list, or delete."
