"""
Shared vector-store configuration for Compass RAG.

The codebase indexer, uploaded-document ingestion, and retrieval tool all use
the same PGVector collection so a single search can cover project code and
session uploads.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import delete

# Note: We now use PGVector instead of Chroma
from langchain_postgres.vectorstores import PGVector

load_dotenv()

WORKSPACE_DIR = os.getcwd()
COLLECTION_NAME = "compass_workspace"

_raw_embeddings = OpenAIEmbeddings(
    model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    check_embedding_ctx_length=False,
    chunk_size=16,
)

_embeddings = None

def _get_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    
    _embeddings = _raw_embeddings
    return _embeddings

_vector_store: Optional[PGVector] = None


def get_vector_store(create: bool = False) -> Optional[PGVector]:
    """Return the shared PGVector store, lazily initialized."""
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    db_uri = os.environ.get("DB_URI")
    if not db_uri:
        if not create:
            return None
        raise ValueError("DB_URI is not set. Cannot initialize PGVector.")

    # Convert asyncpg to psycopg if needed (langchain_postgres usually expects psycopg3 standard URI)
    # SQLAlchemy dialect for psycopg3 is postgresql+psycopg://
    sync_uri = db_uri.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    if sync_uri.startswith("postgresql://"):
        sync_uri = sync_uri.replace("postgresql://", "postgresql+psycopg://")

    _vector_store = PGVector(
        embeddings=_get_embeddings(),
        collection_name=COLLECTION_NAME,
        connection=sync_uri,
        use_jsonb=True,
    )

    # Initialize the tables if creating
    if create:
        _vector_store.create_tables_if_not_exists()
        _vector_store.create_collection()

    return _vector_store


def reset_vector_store_cache() -> None:
    """Clear the cached PGVector instance after writes when needed."""
    global _vector_store
    _vector_store = None


def delete_chunks_by_filter(where: dict) -> int:
    """Delete collection chunks whose JSON metadata contains ``where``."""
    vector_store = get_vector_store(create=False)
    if vector_store is None:
        return 0

    try:
        with vector_store._make_sync_session() as session:
            collection = vector_store.get_collection(session)
            if collection is None:
                return 0

            statement = (
                delete(vector_store.EmbeddingStore)
                .where(vector_store.EmbeddingStore.collection_id == collection.uuid)
                .where(vector_store.EmbeddingStore.cmetadata.contains(where))
            )
            result = session.execute(statement)
            session.commit()
            return int(result.rowcount or 0)
    except Exception as e:
        print(f"Failed to delete chunks: {e}")
        return 0
