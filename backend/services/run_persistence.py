"""Pure run-lifecycle helpers shared by runtime and persistence adapters."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import BaseMessage

from agent.runtime.events import StreamEvent, StreamEventType

RUN_STATUSES = frozenset(
    {
        "running",
        "waiting_for_approval",
        "completed",
        "cancelled",
        "failed",
        "interrupted",
    }
)
_TERMINAL_EVENT_TYPES = {
    StreamEventType.RUN_WAITING,
    StreamEventType.DONE,
    StreamEventType.ERROR,
}


@dataclass(frozen=True, slots=True)
class RunTerminal:
    status: str
    token_usage: dict | None = None
    assistant_content: str | None = None


def terminal_from_events(events: list[StreamEvent]) -> RunTerminal:
    """Derive one truthful terminal record from canonical runtime events."""
    terminal = RunTerminal(status="interrupted")
    for event in events:
        data = event.data if isinstance(event.data, dict) else {}
        if event.type == StreamEventType.ERROR:
            terminal = RunTerminal(
                status="failed",
                token_usage=data.get("token_usage"),
                assistant_content=data.get("assistant_content"),
            )
        elif event.type == StreamEventType.RUN_WAITING:
            terminal = RunTerminal(
                status="waiting_for_approval",
                token_usage=data.get("token_usage"),
                assistant_content=data.get("assistant_content"),
            )
        elif event.type == StreamEventType.DONE:
            status = data.get("status", "completed")
            if status not in {"completed", "cancelled"}:
                status = "failed"
            terminal = RunTerminal(
                status=status,
                token_usage=data.get("token_usage"),
                assistant_content=data.get("assistant_content"),
            )
    return terminal


def messages_created_this_turn(
    before_ids: set[str],
    after_messages: list[BaseMessage],
) -> list[BaseMessage]:
    """Return graph messages whose stable IDs were absent before this turn."""
    return [
        message
        for message in after_messages
        if getattr(message, "id", None) not in before_ids
    ]


class RunEventBatcher:
    """Collect meaningful run events in bounded persistence batches."""

    def __init__(self, max_size: int = 25):
        if max_size < 1:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self._pending: list[tuple[str, dict]] = []

    def add(self, event: StreamEvent) -> list[tuple[str, dict]]:
        if event.type == StreamEventType.TOKEN:
            return []
        self._pending.append(
            (
                event.type.value,
                event.model_dump(mode="json", exclude_none=True),
            )
        )
        if len(self._pending) >= self.max_size or event.type in _TERMINAL_EVENT_TYPES:
            return self.flush()
        return []

    def flush(self) -> list[tuple[str, dict]]:
        pending = self._pending
        self._pending = []
        return pending
