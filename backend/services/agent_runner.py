"""
Agent runner — async wrapper around the LangGraph agent workflow.

Provides both streaming and non-streaming interfaces for the FastAPI backend.
"""

import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage

from backend.schemas.chat import StreamEvent, StreamEventType, ToolCallData

logger = logging.getLogger(__name__)


async def run_agent_stream(
    user_message: str,
    thread_id: str,
    mode: str = "normal",
) -> AsyncGenerator[StreamEvent, None]:
    """
    Invoke the LangGraph agent and yield StreamEvent objects.

    Streams token-by-token output, tool calls, tool results, and a final done event.
    """
    from graph.workflow import get_workflow

    workflow = await get_workflow()
    config = {"configurable": {"thread_id": thread_id}}
    input_msg = {"messages": [HumanMessage(content=user_message)], "mode": mode}

    try:
        async for event in workflow.astream_events(
            input_msg, config=config, version="v2"
        ):
            kind = event.get("event", "")

            # ── Token streaming from the executor LLM ────────────────────────
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield StreamEvent(
                        type=StreamEventType.TOKEN,
                        content=chunk.content,
                    )

                # Check for tool calls in streamed chunks
                if (
                    chunk
                    and hasattr(chunk, "tool_call_chunks")
                    and chunk.tool_call_chunks
                ):
                    for tc in chunk.tool_call_chunks:
                        if tc.get("name"):  # Only emit on the first chunk with a name
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL,
                                tool_call=ToolCallData(
                                    id=tc.get("id", ""),
                                    name=tc["name"],
                                    args=tc.get("args", {}),
                                ),
                            )

            # ── Tool execution results ───────────────────────────────────────
            elif kind == "on_tool_end":
                output = event.get("data", {}).get("output")
                tool_call_id = ""
                content = ""
                if isinstance(output, ToolMessage):
                    tool_call_id = output.tool_call_id
                    content = str(output.content)[:500]  # Truncate for WS
                elif isinstance(output, str):
                    content = output[:500]

                yield StreamEvent(
                    type=StreamEventType.TOOL_RESULT,
                    tool_call_id=tool_call_id,
                    content=content,
                )

        # ── Done ──────────────────────────────────────────────────────────────
        yield StreamEvent(type=StreamEventType.DONE)

    except Exception as exc:
        logger.exception("Agent execution error")
        yield StreamEvent(
            type=StreamEventType.ERROR,
            content=str(exc)[:500],
        )


async def run_agent_sync(
    user_message: str,
    thread_id: str,
    mode: str = "normal",
) -> list[BaseMessage]:
    """
    Invoke the LangGraph agent and return all response messages (non-streaming).

    Returns the list of AI/tool messages produced during this turn.
    """
    from graph.workflow import get_workflow

    workflow = await get_workflow()
    config = {"configurable": {"thread_id": thread_id}}
    input_msg = {"messages": [HumanMessage(content=user_message)], "mode": mode}

    result = await workflow.ainvoke(input_msg, config=config)
    messages = result.get("messages", [])

    # Return only the new messages (skip the input HumanMessage)
    new_messages = []
    for msg in messages:
        if isinstance(msg, (AIMessage, ToolMessage)):
            new_messages.append(msg)

    return new_messages
