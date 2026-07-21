import json
import os
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

WORKSPACE_DIR = os.getcwd()
MCP_CONFIG_FILE = os.path.join(WORKSPACE_DIR, ".compass", "mcp_servers.json")


def load_mcp_config() -> dict:
    """Load MCP server connections from the JSON configuration file."""
    if not os.path.exists(MCP_CONFIG_FILE):
        # Return an empty dict so the client initializes gracefully even if no servers are configured yet
        return {}

    try:
        with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Ensure the config is a dictionary of connection params
            if isinstance(config, dict):
                return config
            return {}
    except Exception as e:
        print(
            f"[mcp] Warning: Failed to load MCP configuration from {MCP_CONFIG_FILE}: {e}"
        )
        return {}


# 1. Load the dynamic connections
connections = load_mcp_config()

# 2. Initialize the MultiServerMCPClient
# We use tool_name_prefix=True to avoid tool name collisions (e.g. "github_search" vs "local_search")
mcp_client = MultiServerMCPClient(connections=connections, tool_name_prefix=True)

_mcp_tools_cache = None

async def get_mcp_tools() -> List[BaseTool]:
    """
    Asynchronously retrieve all available tools from the configured MCP servers.
    The client automatically handles session lifecycle per tool call.
    """
    global _mcp_tools_cache
    if _mcp_tools_cache is not None:
        return _mcp_tools_cache

    if not connections:
        _mcp_tools_cache = []
        return []

    try:
        print(
            f"[mcp] Fetching tools from {len(connections)} configured MCP server(s)..."
        )
        tools = await mcp_client.get_tools()
        print(f"[mcp] Successfully loaded {len(tools)} MCP tools.")
        _mcp_tools_cache = tools
        return tools
    except Exception as e:
        print(f"[mcp] Error loading MCP tools: {e}")
        return []
