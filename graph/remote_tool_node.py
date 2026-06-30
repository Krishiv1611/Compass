import json
import uuid
import asyncio
from typing import Any, Sequence
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langchain_core.runnables.config import RunnableConfig

from backend.ws.hub import manager
from backend.schemas.chat import StreamEvent

class RemoteToolNode(ToolNode):
    """
    A custom ToolNode that routes execution based on the tool's environment tag.
    
    If the tool is tagged 'edge' (e.g. file system, shell), it sends an RPC request
    via WebSocket to the connected TUI client and waits for the response.
    If the tool is 'cloud' or 'universal', it executes it directly in the backend.
    """

    # Tools that require local execution on the edge client
    EDGE_TOOLS = {
        "read_file", "write_to_file", "edit_file", 
        "list_dir", "find_files", "grep_search", 
        "shell_execute", "create_skill"
    }

    async def _ainvoke_tool(
        self,
        tool_call: dict,
        config: RunnableConfig,
        **kwargs: Any
    ) -> ToolMessage:
        
        tool_name = tool_call["name"]
        
        if tool_name not in self.EDGE_TOOLS:
            # Execute Cloud/Universal tools locally in the backend
            return await super()._ainvoke_tool(tool_call, config, **kwargs)

        # Handle EDGE tools via WebSocket RPC
        session_id = config["configurable"].get("thread_id")
        if not session_id:
            return ToolMessage(
                content="Error: No session_id found for Remote Tool Execution.",
                name=tool_name,
                tool_call_id=tool_call["id"],
                status="error"
            )

        connections = manager.get_connections(session_id)
        if not connections:
            return ToolMessage(
                content=f"Error: Disconnected Mode. You must connect a TUI client to use local edge tools like '{tool_name}'.",
                name=tool_name,
                tool_call_id=tool_call["id"],
                status="error"
            )

        # We have an active connection, issue the RPC request
        call_id = str(uuid.uuid4())
        future = asyncio.get_running_loop().create_future()
        manager.pending_calls[call_id] = future
        
        event = StreamEvent(
            type="rpc_call",
            node="tools",
            data={
                "call_id": call_id,
                "name": tool_name,
                "args": tool_call["args"]
            }
        )

        try:
            # Pick one active websocket for this session (usually there's only 1 TUI connected)
            ws = next(iter(connections))
            await manager.send_event(ws, event)

            # Wait for the client to process the tool and send back a result
            # Using a generous timeout since tools like shell_execute can take a while
            result = await asyncio.wait_for(future, timeout=300.0)
            
            # The result from the client is expected to be a string or JSON dict
            content = result if isinstance(result, str) else json.dumps(result)
            return ToolMessage(
                content=content,
                name=tool_name,
                tool_call_id=tool_call["id"]
            )
            
        except asyncio.TimeoutError:
            manager.pending_calls.pop(call_id, None)
            return ToolMessage(
                content=f"Error: The local client took too long to execute '{tool_name}'.",
                name=tool_name,
                tool_call_id=tool_call["id"],
                status="error"
            )
        except Exception as e:
            manager.pending_calls.pop(call_id, None)
            return ToolMessage(
                content=f"Error executing remote tool '{tool_name}': {str(e)}",
                name=tool_name,
                tool_call_id=tool_call["id"],
                status="error"
            )
