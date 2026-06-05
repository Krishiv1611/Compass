from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    turn_count:int
    is_done: bool
    pending_tool_calls:list[dict]
    approval_status: str| None
    loop_detected: bool
    token_usage: dict

