"""Public LangGraph tool-node adapter with target-aware policy selection."""

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from agent.tools.registry import ToolRegistry
from agent.runtime.metrics import current_run_metrics


class CompassToolNode:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def __call__(self, state: dict, config: RunnableConfig) -> dict:
        target = config.get("configurable", {}).get("execution_target", "tui")
        tools = self._registry.tools_for(target)
        calls = getattr(state.get("messages", [])[-1], "tool_calls", []) if state.get("messages") else []
        hook_only = bool(calls) and all(
            str(call.get("id", "")).startswith("hook-")
            and call.get("name") == "shell_execute"
            and bool((call.get("args") or {}).get("verification_hook"))
            for call in calls
        )
        if target == "web" and hook_only:
            tools = [*tools, self._registry.get("shell_execute").tool]
        node = ToolNode(tools)
        metrics = current_run_metrics()
        if metrics is None:
            return await node.ainvoke(state, config)
        async with metrics.span("tools.execute"):
            return await node.ainvoke(state, config)
