import asyncio
import json
import logging
from typing import Any
import websockets
from langgraph.prebuilt.tool_node import ToolNode
from graph.workflow import ALL_TOOLS

logger = logging.getLogger(__name__)

# Re-use the existing tools to execute them locally
local_tool_node = ToolNode(ALL_TOOLS)

async def connect_and_relay(session_id: str, token: str, backend_url: str = "ws://localhost:8000"):
    uri = f"{backend_url}/chat/ws/{session_id}?token={token}"
    print(f"Connecting to Relay: {uri}")
    
    async with websockets.connect(uri) as websocket:
        print("Connected to edge relay.")
        
        # Keep listening for RPC calls from the backend
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                if data.get("type") == "rpc_call":
                    call_id = data.get("data", {}).get("call_id")
                    tool_name = data.get("data", {}).get("name")
                    args = data.get("data", {}).get("args", {})
                    
                    print(f"\n[RPC CALL] Received tool execution request: {tool_name}")
                    print(f"Arguments: {json.dumps(args, indent=2)}")
                    
                    # Optional: Add user approval prompt here
                    
                    # Execute tool locally
                    try:
                        # Find the tool in our registry
                        tool = next((t for t in ALL_TOOLS if t.name == tool_name), None)
                        if not tool:
                            raise ValueError(f"Tool {tool_name} not found locally.")
                            
                        # Execute
                        if asyncio.iscoroutinefunction(tool.func):
                            result = await tool.ainvoke(args)
                        else:
                            result = tool.invoke(args)
                            
                        # Send result back
                        await websocket.send(json.dumps({
                            "type": "tool_result",
                            "call_id": call_id,
                            "result": str(result),
                            "error": None
                        }))
                        print(f"[RPC RESULT] Successfully executed and returned result for {tool_name}")
                        
                    except Exception as e:
                        logger.exception(f"Error executing local tool: {tool_name}")
                        await websocket.send(json.dumps({
                            "type": "tool_result",
                            "call_id": call_id,
                            "result": None,
                            "error": str(e)
                        }))
                        
            except websockets.exceptions.ConnectionClosed:
                print("Relay connection closed.")
                break
            except Exception as e:
                logger.error(f"Relay error: {e}")
                
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python relay.py <session_id> <token>")
        sys.exit(1)
        
    asyncio.run(connect_and_relay(sys.argv[1], sys.argv[2]))
