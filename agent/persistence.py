"""Checkpointer selection for local and durable Compass runtimes."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


_memory_saver = InMemorySaver()
_postgres_pool: AsyncConnectionPool | None = None


async def build_postgres_checkpointer(
    db_uri: str,
) -> tuple[AsyncPostgresSaver, AsyncConnectionPool]:
    """Open and initialize a PostgreSQL checkpointer and its owned pool."""

    pool = AsyncConnectionPool(
        conninfo=db_uri,
        min_size=1,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    try:
        await pool.open(wait=True, timeout=3)
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        return saver, pool
    except Exception:
        await pool.close(timeout=1)
        raise


async def get_checkpointer(
    db_uri: str | None,
    *,
    require_durable: bool = False,
):
    """Return PostgreSQL persistence or the process-local TUI fallback."""

    global _postgres_pool
    if not db_uri:
        if require_durable:
            raise RuntimeError("Durable persistence requires DB_URI")
        return _memory_saver

    try:
        saver, pool = await build_postgres_checkpointer(db_uri)
    except Exception:
        if require_durable:
            raise
        return _memory_saver

    _postgres_pool = pool
    return saver


async def close_postgres_pool() -> None:
    """Close the retained pool when the compiled workflow is reset."""

    global _postgres_pool
    if _postgres_pool is not None:
        await _postgres_pool.close(timeout=1)
        _postgres_pool = None
