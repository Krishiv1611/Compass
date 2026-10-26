import json
import os
import asyncio
import time
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

WORKSPACE_DIR = os.getcwd()


def runtime_mcp_config_name() -> str:
    """Return the one MCP configuration filename used by Compass."""

    return "mcp_servers.json"


MCP_CONFIG_FILE = os.path.join(
    WORKSPACE_DIR,
    ".compass",
    runtime_mcp_config_name(),
)


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
# We use tool_name_prefix=True to avoid tool name collisions and handle_tool_errors=True
mcp_client = MultiServerMCPClient(
    connections=connections,
    tool_name_prefix=True,
    handle_tool_errors=True,
)

_mcp_tools_cache = None
_mcp_tools_expires_at = 0.0
_mcp_cache_lock = asyncio.Lock()
MCP_SERVER_TIMEOUT_SECONDS = 2.0


def reset_mcp_cache() -> None:
    global _mcp_tools_cache, _mcp_tools_expires_at
    _mcp_tools_cache = None
    _mcp_tools_expires_at = 0.0

async def get_mcp_tools() -> List[BaseTool]:
    """
    Asynchronously retrieve all available tools from the configured MCP servers.
    Each server is bounded by a timeout and isolated so offline servers do not block or crash the turn.
    """
    global _mcp_tools_cache, _mcp_tools_expires_at
    from agent.runtime.metrics import current_run_metrics

    metrics = current_run_metrics()
    now = time.monotonic()
    if _mcp_tools_cache is not None and now < _mcp_tools_expires_at:
        if metrics:
            metrics.add_tag("mcp_cache", "hit")
        return _mcp_tools_cache

    async with _mcp_cache_lock:
        now = time.monotonic()
        if _mcp_tools_cache is not None and now < _mcp_tools_expires_at:
            if metrics:
                metrics.add_tag("mcp_cache", "hit")
            return _mcp_tools_cache
        if metrics:
            metrics.add_tag("mcp_cache", "miss")
        if not connections:
            _mcp_tools_cache = []
            _mcp_tools_expires_at = now + 300
            return []

        async def _load_from_server(server_name: str) -> list[BaseTool]:
            try:
                try:
                    call = mcp_client.get_tools(server_name=server_name)
                except TypeError:
                    call = mcp_client.get_tools()
                server_tools = await asyncio.wait_for(
                    call,
                    timeout=MCP_SERVER_TIMEOUT_SECONDS,
                )
                return list(server_tools)
            except Exception as exc:
                print(f"[mcp] Server '{server_name}' is offline or timed out: {exc}")
                return []

        try:
            print(
                f"[mcp] Fetching tools from {len(connections)} configured MCP server(s)..."
            )
            tasks = [_load_from_server(name) for name in connections]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_tools: list[BaseTool] = []
            for r in results:
                if isinstance(r, list):
                    all_tools.extend(r)
            print(f"[mcp] Successfully loaded {len(all_tools)} MCP tools.")
            _mcp_tools_cache = all_tools
            _mcp_tools_expires_at = time.monotonic() + (300 if all_tools or not connections else 30)
            return all_tools
        except Exception as e:
            print(f"[mcp] Error loading MCP tools: {e}")
            _mcp_tools_cache = []
            _mcp_tools_expires_at = time.monotonic() + 30
            return []
