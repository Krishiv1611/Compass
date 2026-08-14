"""Small, testable routing decisions for the Compass workflow."""

from __future__ import annotations

from agent.config import settings


def needs_compaction(state: dict) -> bool:
    """Return true only when old context is safe to summarize."""

    threshold = int(settings.get("context.summarize_after", 10))
    return (
        not state.get("pending_tool_calls")
        and len(state.get("messages", [])) > threshold
    )


async def route_after_executor(state: dict) -> str:
    """Choose the next node while preserving tool-message ordering."""

    if state.get("pending_tool_calls"):
        return "check_safety"
    if state.get("mode") == "goal" and state.get(
        "goal_iteration", 0
    ) >= state.get("goal_iteration_limit", 3):
        return "goal_limit"
    if state.get("loop_detected"):
        return "loop_recovery" if state.get("mode") == "goal" else "loop_limit"
    if state.get("needs_replan"):
        return "context_injector"
    if state.get("mode") == "goal":
        if state.get("is_done"):
            return "linter_node"
        return "summary_node" if needs_compaction(state) else "executor"
    if needs_compaction(state):
        return "summary_node"
    if state.get("is_done") and not state.get("verification_hooks_scheduled"):
        from agent.hooks import changed_files_from_messages

        if changed_files_from_messages(state.get("messages", [])):
            return "verification_hooks"
    return "end" if state.get("is_done") else "executor"
