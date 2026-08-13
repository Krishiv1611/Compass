from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand


async def mcp(_argument: str, _context: CommandContext) -> CommandResult:
    try:
        from agent.mcp import get_mcp_tools

        tools = await get_mcp_tools()
        names = [getattr(tool, "name", str(tool)) for tool in tools]
        return CommandResult(True, f"MCP tools ({len(names)}):\n" + "\n".join(names))
    except Exception as exc:
        return CommandResult(True, f"MCP inspection failed: {exc}")


async def ui(_argument: str, context: CommandContext) -> CommandResult:
    import urllib.error
    import urllib.request
    import webbrowser

    url = context.settings.get("web_url") or "http://localhost:5173"
    try:
        with urllib.request.urlopen(url, timeout=0.5):
            webbrowser.open(url)
        return CommandResult(True, f"Opened Web UI at {url}")
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    return CommandResult(True, f"Web UI is not reachable at {url}. Start it with: cd frontend && npm run dev")


COMMANDS = [
    SlashCommand("/mcp", (), "List configured MCP tools", mcp),
    SlashCommand("/ui", ("/web",), "Open or explain how to start the Web UI", ui),
]
