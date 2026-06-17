from langchain_core.tools import tool

@tool
def compass_ping() -> str:
    """A simple ping tool to verify dynamic loading works. Returns 'pong'."""
    return "pong"
