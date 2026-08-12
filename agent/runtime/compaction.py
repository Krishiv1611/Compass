"""Checkpoint-backed conversation compaction."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import BaseMessage
from langgraph.graph.message import RemoveMessage

from agent.config import settings


@dataclass(frozen=True)
class CompactionResult:
    before_count: int
    after_count: int
    summary: str
    compacted: bool


def build_compaction_update(
    messages: list[BaseMessage],
    summary: str,
    *,
    keep_recent: int = 6,
) -> dict:
    """Build a LangGraph update that removes all but recent messages."""

    removable = messages[:-keep_recent] if keep_recent else messages
    return {
        "summary": summary,
        "messages": [
            RemoveMessage(id=message.id)
            for message in removable
            if message.id is not None
        ],
    }


async def compact_thread(
    workflow,
    config: dict,
    *,
    force: bool = False,
) -> CompactionResult:
    """Summarize a thread once and persist the compaction update."""

    snapshot = await workflow.aget_state(config)
    values = snapshot.values or {}
    messages = list(values.get("messages", []))
    threshold = int(settings.get("context.summarize_after", 10))
    if not force and len(messages) <= threshold:
        return CompactionResult(
            before_count=len(messages),
            after_count=len(messages),
            summary=str(values.get("summary", "")),
            compacted=False,
        )

    from agent.graph.nodes import summary_node

    update = await summary_node(values, config)
    await workflow.aupdate_state(
        config,
        update,
        as_node="summary_node",
    )
    removed_ids = {
        item.id
        for item in update.get("messages", [])
        if isinstance(item, RemoveMessage)
    }
    after_count = sum(
        message.id not in removed_ids
        for message in messages
    )
    return CompactionResult(
        before_count=len(messages),
        after_count=after_count,
        summary=str(update.get("summary", "")),
        compacted=True,
    )
