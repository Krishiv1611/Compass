"""
Shared vector-store configuration for Compass RAG.

The codebase indexer, uploaded-document ingestion, and retrieval tool all use
the same PGVector collection so a single search can cover project code and
session uploads.
"""

from __future__ import annotations

import os
import hashlib
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import delete

# Note: We now use PGVector instead of Chroma
from langchain_postgres.vectorstores import PGVector

load_dotenv()

WORKSPACE_DIR = os.getcwd()
COLLECTION_NAME = "compass_workspace"

_embeddings: dict[tuple[str, str, str], object] = {}


class EmbeddingCapabilityError(RuntimeError):
    """Semantic search is unavailable until an explicit credential is selected."""


def _embedding_settings(
    provider_config: dict | None,
) -> tuple[str, str, str, str]:
    config = provider_config or {}
    is_web = config.get("execution_target") == "web"
    provider = config.get("embedding_provider")
    model = config.get("embedding_model")
    api_key = config.get("embedding_api_key")
    if is_web and not (provider and model and api_key):
        raise EmbeddingCapabilityError(
            "Semantic search is disabled. Configure an embedding provider credential."
        )
    if not provider:
        provider = "openrouter"
        model = os.environ.get(
            "COMPASS_EMBEDDING_MODEL",
            "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        )
        api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EmbeddingCapabilityError(
            "Semantic search is disabled. Configure an embedding provider credential."
        )
    collection_suffix = hashlib.sha256(
        f"{provider}:{model}".encode()
    ).hexdigest()[:12]
    collection = (
        COLLECTION_NAME
        if not is_web
        else f"{COLLECTION_NAME}_{collection_suffix}"
    )
    return str(provider), str(model), str(api_key), collection


def _get_embeddings(provider_config: dict | None = None):
    provider, model, api_key, _collection = _embedding_settings(provider_config)
    cache_key = (provider, model, hashlib.sha256(api_key.encode()).hexdigest())
    if cache_key in _embeddings:
        return _embeddings[cache_key]

    if provider in {"openrouter", "openai"}:
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            model=model.removeprefix("openai/"),
            base_url="https://openrouter.ai/api/v1"
            if provider == "openrouter"
            else None,
            api_key=api_key,
            check_embedding_ctx_length=False,
            chunk_size=16,
        )
    elif provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        embeddings = GoogleGenerativeAIEmbeddings(
            model=model.removeprefix("google/"),
            google_api_key=api_key,
        )
    else:
        raise EmbeddingCapabilityError(
            f"Embedding provider {provider!r} is not supported"
        )
    _embeddings[cache_key] = embeddings
    return embeddings

_vector_stores: dict[tuple[str, str], PGVector] = {}


def get_vector_store(
    create: bool = False,
    provider_config: dict | None = None,
) -> Optional[PGVector]:
    """Return the shared PGVector store, lazily initialized."""
    _provider, _model, api_key, collection = _embedding_settings(provider_config)
    store_key = (collection, hashlib.sha256(api_key.encode()).hexdigest())
    if store_key in _vector_stores:
        return _vector_stores[store_key]

    db_uri = os.environ.get("DB_URI")
    if not db_uri or not (db_uri.startswith("postgresql") or db_uri.startswith("postgres")):
        if not create:
            return None
        raise ValueError("DB_URI is not a valid PostgreSQL URI. Cannot initialize PGVector.")

    # Convert asyncpg to psycopg if needed (langchain_postgres usually expects psycopg3 standard URI)
    # SQLAlchemy dialect for psycopg3 is postgresql+psycopg://
    sync_uri = db_uri.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    if sync_uri.startswith("postgresql://"):
        sync_uri = sync_uri.replace("postgresql://", "postgresql+psycopg://")

    vector_store = PGVector(
        embeddings=_get_embeddings(provider_config),
        collection_name=collection,
        connection=sync_uri,
        use_jsonb=True,
    )

    # Initialize the tables if creating
    if create:
        vector_store.create_tables_if_not_exists()
        vector_store.create_collection()

    _vector_stores[store_key] = vector_store
    return vector_store


def delete_chunks_by_filter(
    where: dict,
    provider_config: dict | None = None,
) -> int:
    """Delete collection chunks whose JSON metadata contains ``where``."""
    try:
        vector_store = get_vector_store(
            create=False,
            provider_config=provider_config,
        )
    except Exception:
        return 0
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
