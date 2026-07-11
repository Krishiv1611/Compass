"""
Compass Memory Tool — Long-term memory backed by PostgresStore.

Uses LangGraph's PostgresStore with pgvector for semantic search.
Memories are stored as key-value pairs organized by namespaces and
automatically embedded for similarity search.
"""

import hashlib
import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langgraph.store.postgres import PostgresStore

load_dotenv()


_embeddings = OpenAIEmbeddings(
    model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    check_embedding_ctx_length=False,
)

# ─── PostgreStore with semantic index ──────────────────────────────────────────
DB_URI = os.environ.get("DB_URI")

_store = None

if DB_URI:
    try:
        _store_ctx = PostgresStore.from_conn_string(
            DB_URI,
            index={
                "dims": 1024,  # NVIDIA model supports MRL; Neon hnsw max is 2000
                "embed": _embeddings,
                "fields": ["$"],  # embed the entire value
            },
        )
        _store = _store_ctx.__enter__()
        _store.setup()
    except Exception as e:
        print(f"[memory] Warning: Could not initialize PostgresStore: {e}")
        _store = None

# ─── Default namespace for single-user CLI agent ───────────────────────────────
_DEFAULT_NAMESPACE = ("compass", "user")


@tool
def memory(
    action: str,
    content: str = "",
    key: str = "",
    namespace: str = "",
    limit: int = 5,
) -> str:
    """Save and retrieve long-term memories using a persistent store.

    Use this tool to remember important information about the user,
    their preferences, project context, or any facts worth recalling later.
    Memories persist across conversations.

    Args:
        action: One of 'save', 'search', 'get', 'list', or 'delete'.
        content: The text to save (required for 'save') or the search query (required for 'search').
        key: A short identifier for the memory (optional for 'save' — auto-generated if empty,
             required for 'get' and 'delete').
        namespace: Optional sub-category to organize memories (e.g. 'preferences', 'projects').
                   Defaults to a general namespace if empty.
        limit: Max number of results to return for 'search' and 'list' (default 5).
    """
    if _store is None:
        return "Error: Memory store is not available (database not configured)."

    action = action.strip().lower()

    # Build the namespace tuple
    ns = _DEFAULT_NAMESPACE
    if namespace and namespace.strip():
        ns = (*_DEFAULT_NAMESPACE, namespace.strip())

    # ── SAVE ────────────────────────────────────────────────────────────────
    if action == "save":
        if not content:
            return "Error: 'content' is required for the 'save' action."
        # Deterministic key from content hash prevents duplicates
        mem_key = (
            key.strip()
            if key and key.strip()
            else hashlib.sha256(content.encode()).hexdigest()[:12]
        )
        _store.put(ns, mem_key, {"content": content})
        return f"Saved memory '{mem_key}' in namespace {ns}."

    # ── SEARCH (semantic) ───────────────────────────────────────────────────
    elif action == "search":
        if not content:
            return "Error: 'content' (as search query) is required for the 'search' action."
        results = _store.search(ns, query=content, limit=limit)
        if not results:
            return "No matching memories found."
        lines = []
        for r in results:
            score = (
                f" (score: {r.score:.3f})"
                if hasattr(r, "score") and r.score is not None
                else ""
            )
            lines.append(f"  [{r.key}]{score}: {r.value}")
        return f"Found {len(results)} memories:\n" + "\n".join(lines)

    # ── GET (exact key lookup) ──────────────────────────────────────────────
    elif action == "get":
        if not key:
            return "Error: 'key' is required for the 'get' action."
        item = _store.get(ns, key.strip())
        if item is None:
            return f"No memory found with key '{key}' in namespace {ns}."
        return f"Memory [{item.key}]: {item.value}"

    # ── LIST (all items in namespace) ───────────────────────────────────────
    elif action == "list":
        results = _store.search(ns, limit=limit)
        if not results:
            return f"No memories in namespace {ns}."
        lines = []
        for r in results:
            lines.append(f"  [{r.key}]: {r.value}")
        return f"{len(results)} memories in {ns}:\n" + "\n".join(lines)

    # ── DELETE ──────────────────────────────────────────────────────────────
    elif action == "delete":
        if not key:
            return "Error: 'key' is required for the 'delete' action."
        _store.delete(ns, key.strip())
        return f"Deleted memory '{key}' from namespace {ns}."

    else:
        return f"Error: Unknown action '{action}'. Use 'save', 'search', 'get', 'list', or 'delete'."
