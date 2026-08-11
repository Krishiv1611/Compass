"""Public LangGraph tool-node adapter with target-aware policy selection."""

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from agent.tools.registry import ToolRegistry


class CompassToolNode:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def __call__(self, state: dict, config: RunnableConfig) -> dict:
        target = config.get("configurable", {}).get("execution_target", "tui")
        node = ToolNode(self._registry.tools_for(target))
        return await node.ainvoke(state, config)
