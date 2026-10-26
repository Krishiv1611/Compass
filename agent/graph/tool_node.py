import asyncio
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

from agent.tools.registry import ToolRegistry
from agent.runtime.metrics import current_run_metrics
from agent.checkpoints import create_checkpoint, seal_checkpoint
from agent.tools.utils import get_workspace_for_tool


class CompassToolNode:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._node_cache: dict[tuple[str, bool], ToolNode] = {}

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

        from agent.runtime.turn_context import get_turn_context

        turn_context = get_turn_context(config) if isinstance(config, dict) else None
        extra_tools = list(turn_context.mcp_tools) if turn_context and turn_context.mcp_tools else []

        cache_key = (target, hook_only)
        node = self._node_cache.get(cache_key)
        if node is None or extra_tools:
            node_tools = list(tools)
            if target == "web" and hook_only:
                node_tools.append(self._registry.get("shell_execute").tool)
            if extra_tools:
                node_tools.extend(extra_tools)
            try:
                node = ToolNode(node_tools, handle_tool_errors=True)
            except TypeError:
                node = ToolNode(node_tools)
            if not extra_tools:
                self._node_cache[cache_key] = node

        # Separate available tool calls from unavailable/offline calls
        available_tools = list(tools) + extra_tools
        if target == "web" and hook_only:
            available_tools.append(self._registry.get("shell_execute").tool)
        available_names = {getattr(t, "name", str(t)) for t in available_tools}

        valid_calls = []
        unavailable_messages = {}
        for call in calls:
            name = call.get("name")
            call_id = str(call.get("id", ""))
            if name in available_names:
                valid_calls.append(call)
            else:
                unavailable_messages[call_id] = ToolMessage(
                    content=(
                        f"Tool '{name}' is unavailable because the optional MCP service or dependency is offline or unconfigured. "
                        "Please proceed using available core tools: read_file, edit_file, write_to_file, grep_search, find_files, etc."
                    ),
                    tool_call_id=call_id,
                    name=str(name or ""),
                )

        mutating = {"write_to_file", "edit_file", "delete_file", "move_file"}
        paths = []
        for call in valid_calls:
            args = call.get("args") or {}
            path = args.get("path") or args.get("file_path")
            if call.get("name") in mutating and isinstance(path, str) and path:
                paths.append(path)
        checkpoint = None
        workspace = None
        if paths:
            workspace = get_workspace_for_tool(config)
            configurable = config.get("configurable", {})
            checkpoint = await asyncio.to_thread(
                create_checkpoint,
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

        if not valid_calls:
            result = {"messages": list(unavailable_messages.values())}
        else:
            sub_state = state
            if unavailable_messages:
                last_msg = state.get("messages", [])[-1]
                if hasattr(last_msg, "model_copy"):
                    filtered_msg = last_msg.model_copy(update={"tool_calls": valid_calls})
                    sub_state = dict(state)
                    sub_state["messages"] = list(state.get("messages", [])[:-1]) + [filtered_msg]

            metrics = current_run_metrics()
            if metrics is None:
                result = await node.ainvoke(sub_state, config)
            else:
                async with metrics.span("tools.execute"):
                    result = await node.ainvoke(sub_state, config)

            if unavailable_messages:
                returned_msgs = {
                    getattr(m, "tool_call_id", ""): m
                    for m in result.get("messages", [])
                }
                all_msgs = []
                for call in calls:
                    c_id = str(call.get("id", ""))
                    if c_id in returned_msgs:
                        all_msgs.append(returned_msgs[c_id])
                    elif c_id in unavailable_messages:
                        all_msgs.append(unavailable_messages[c_id])
                result["messages"] = all_msgs

        if checkpoint is not None and workspace is not None:
            await asyncio.to_thread(seal_checkpoint, workspace.root, checkpoint.id)
            result["last_checkpoint_id"] = checkpoint.id
            result["checkpoint_files"] = paths
        return result
