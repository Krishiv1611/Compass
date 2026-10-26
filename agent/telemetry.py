"""Local run metadata and token accounting."""

from typing import Any, Optional

from langchain_core.runnables import RunnableConfig


def get_run_config(
    thread_id: str,
    user_id: Optional[str] = None,
    session_metadata: Optional[dict[str, Any]] = None,
) -> RunnableConfig:
    """Build the LangGraph configuration used for thread persistence and nodes."""
    metadata = dict(session_metadata or {})
    metadata["thread_id"] = thread_id
    configurable: dict[str, Any] = {"thread_id": thread_id}
    if user_id:
        metadata["user_id"] = user_id
        configurable["user_id"] = user_id
    return {
        "configurable": configurable,
        "metadata": metadata,
        "tags": ["compass-agent", f"thread:{thread_id}"],
    }
