"""Public LangGraph tool-node adapter with target-aware policy selection."""

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from agent.tools.registry import ToolRegistry
from agent.runtime.metrics import current_run_metrics
from agent.checkpoints import create_checkpoint, seal_checkpoint
from agent.tools.utils import get_workspace_for_tool


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
        mutating = {"write_to_file", "edit_file", "delete_file", "move_file"}
        paths = []
        for call in calls:
            args = call.get("args") or {}
            path = args.get("path") or args.get("file_path")
            if call.get("name") in mutating and isinstance(path, str) and path:
                paths.append(path)
        checkpoint = None
        workspace = None
        if paths:
            workspace = get_workspace_for_tool(config)
            configurable = config.get("configurable", {})
            checkpoint = create_checkpoint(
                workspace.root,
                paths,
                workspace_id=workspace.workspace_id or workspace.project_id or "local",
                thread_id=str(
                    configurable.get("thread_id")
                    or configurable.get("session_id")
                    or "local"
                ),
                label="Before agent write batch",
            )
        metrics = current_run_metrics()
        if metrics is None:
            result = await node.ainvoke(state, config)
        else:
            async with metrics.span("tools.execute"):
                result = await node.ainvoke(state, config)
        if checkpoint is not None and workspace is not None:
            seal_checkpoint(workspace.root, checkpoint.id)
            result["last_checkpoint_id"] = checkpoint.id
            result["checkpoint_files"] = paths
        return result
