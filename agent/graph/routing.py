"""Small, testable routing decisions for the Compass workflow."""

from __future__ import annotations


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
        return "linter_node" if state.get("is_done") else "executor"
    return "end" if state.get("is_done") else "executor"
