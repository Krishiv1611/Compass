"""
Compass — Loop Detector.

Detects when the agent is stuck in a loop by identifying repeated identical
tool call patterns in the conversation history.
"""

import hashlib
import json
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage

if TYPE_CHECKING:
    from agent.graph.state import AgentState


def _hash_tool_call(tool_call: dict) -> str:
    """
    Create a deterministic hash for a tool call (name + args).

    We sort the args dict to ensure consistent hashing regardless of key order.
    """
    name = tool_call.get("name", "")
    args = tool_call.get("args", {})

    # Sort args for deterministic hashing
    try:
        args_str = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        args_str = str(args)

    signature = f"{name}:{args_str}"
    return hashlib.md5(signature.encode()).hexdigest()


def _extract_recent_tool_call_hashes(
    state: "AgentState", lookback: int = 10
) -> list[str]:
    """
    Extract tool call hashes from recent AIMessages.

    Returns a flat list of hashes in chronological order,
    one hash per tool call (an AIMessage can have multiple tool calls).
    """
    messages = state.get("messages", [])
    recent_ai_messages = [
        m
        for m in messages[-lookback:]
        if isinstance(m, AIMessage) and hasattr(m, "tool_calls") and m.tool_calls
    ]

    hashes = []
    for msg in recent_ai_messages:
        for tc in msg.tool_calls:
            hashes.append(_hash_tool_call(tc))

    return hashes


def is_looping(state: "AgentState", max_identical_calls: int = 3) -> bool:
    """
    Detect if the agent is calling the same tool(s) with the same arguments repeatedly.

    Checks for `max_identical_calls` consecutive identical tool call hashes
    in the recent message history.

    Args:
        state: The current agent state.
        max_identical_calls: Number of consecutive identical calls to trigger detection.

    Returns:
        True if a loop pattern is detected.
    """
    hashes = _extract_recent_tool_call_hashes(state)

    if len(hashes) < max_identical_calls:
        return False

    # Check the last `max_identical_calls` hashes — are they all the same?
    tail = hashes[-max_identical_calls:]
    return len(set(tail)) == 1


def get_loop_summary(state: "AgentState", max_identical_calls: int = 3) -> str:
    """
    Get a human-readable summary of the detected loop pattern.

    Returns a description of what tool call is being repeated, or an empty
    string if no loop is detected.
    """
    if not is_looping(state, max_identical_calls):
        return ""

    messages = state.get("messages", [])
    # Find the last AIMessage with tool calls (the repeating one)
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            calls = []
            for tc in msg.tool_calls:
                name = tc.get("name", "unknown")
                args = tc.get("args", {})
                # Format args concisely
                args_preview = ", ".join(
                    f"{k}={repr(v)[:50]}" for k, v in list(args.items())[:3]
                )
                calls.append(f"{name}({args_preview})")

            call_str = " + ".join(calls)
            return (
                f"Loop detected: {call_str} has been called "
                f"{max_identical_calls} times consecutively with identical arguments."
            )

    return "Loop detected: repeated identical tool calls."
