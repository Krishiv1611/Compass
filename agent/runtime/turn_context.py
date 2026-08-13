"""Prepare expensive coding context once and share it across executor rounds."""

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnContext:
    user_query: str
    recalled_memory: list[str] = field(default_factory=list)
    mcp_tools: list[Any] = field(default_factory=list)
    tools: list[Any] = field(default_factory=list)
    executor_model: Any | None = None
    model_clients: dict[str, Any] = field(default_factory=dict)
    direct_chat: bool = False


class RuntimePreparationServices:
    async def memory(self, config: dict) -> list[str]:
        from agent.tools.memory_tool import recall_memories

        return await asyncio.to_thread(recall_memories, config)

    async def mcp(self, _config: dict) -> list[Any]:
        from agent.mcp import get_mcp_tools

        return await get_mcp_tools()

    def tools(self, _config: dict) -> list[Any]:
        from agent.graph.tools_registry import ALL_TOOLS

        return list(ALL_TOOLS)

    def model(self, role: str, config: dict):
        from agent.llm import llm

        configurable = config.get("configurable", {})
        return llm(
            role,
            api_key=configurable.get("api_key"),
            provider=configurable.get("provider"),
            model=configurable.get("model"),
        )

    def bind_tools(self, model, tools):
        return model.bind_tools(tools)


async def _resolve(value):
    return await value if inspect.isawaitable(value) else value


async def _resolve_or(value, default):
    try:
        return await _resolve(value)
    except Exception:
        return default


def _input_details(input_value: object) -> tuple[str, str, bool]:
    if not isinstance(input_value, dict):
        return "", "edit", False
    messages = input_value.get("messages", [])
    query = ""
    for message in reversed(messages if isinstance(messages, list) else []):
        content = getattr(message, "content", "")
        if isinstance(content, str):
            query = content
            break
    mode = str(input_value.get("mode", "edit"))
    active_skill = bool(input_value.get("active_skill"))
    return query, mode, active_skill


def _is_direct_chat(query: str, mode: str, active_skill: bool) -> bool:
    if active_skill or mode in {"plan", "goal"}:
        return False
    normalized = " ".join(query.lower().split())
    greetings = ("hi", "hello", "hey", "who are you", "what can you do", "thanks", "thank you", "bye")
    return len(normalized) < 50 and normalized.startswith(greetings)


async def prepare_turn_context(
    input_value: object,
    config: dict,
    *,
    services: object | None = None,
) -> TurnContext:
    """Prepare memory, MCP, tools, and the bound executor once per turn."""
    from agent.runtime.metrics import current_run_metrics

    configurable = config.setdefault("configurable", {})
    existing = configurable.get("_turn_context")
    if isinstance(existing, TurnContext):
        if metrics := current_run_metrics():
            metrics.add_tag("turn_context_cache", "hit")
        return existing

    if metrics := current_run_metrics():
        metrics.add_tag("turn_context_cache", "miss")

    query, mode, active_skill = _input_details(input_value)
    direct_chat = _is_direct_chat(query, mode, active_skill)
    context = TurnContext(user_query=query, direct_chat=direct_chat)
    configurable["_turn_context"] = context
    if direct_chat:
        return context

    runtime = services or RuntimePreparationServices()
    memory, mcp_tools = await asyncio.gather(
        _resolve_or(runtime.memory(config), []),
        _resolve_or(runtime.mcp(config), []),
    )
    builtin_tools = await _resolve(runtime.tools(config))
    combined_tools = list(builtin_tools) + list(mcp_tools)
    if mode in {"ask", "fast"}:
        read_only = {
            "read_file", "list_dir", "find_files", "grep_search",
            "codebase_search", "web_search",
        }
        combined_tools = [
            tool for tool in combined_tools
            if getattr(tool, "name", str(tool)) in read_only
        ]
    executor = await _resolve(runtime.model("executor", config))
    context.recalled_memory = list(memory)
    context.mcp_tools = list(mcp_tools)
    context.tools = combined_tools
    context.executor_model = await _resolve(runtime.bind_tools(executor, combined_tools))
    context.model_clients["executor"] = context.executor_model
    return context


def get_turn_context(config: dict) -> TurnContext | None:
    value = config.get("configurable", {}).get("_turn_context")
    return value if isinstance(value, TurnContext) else None
