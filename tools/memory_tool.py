from langchain_core.tools import tool

# Module-level store — persists within a single process run.
# For cross-session persistence, swap this with LangGraph Store or a DB-backed dict.
_memory_store: dict[str, str] = {}


@tool
def memory(action: str, key: str = "", value: str = "") -> str:
    """Manage a persistent key-value memory store.

    Use this to save important facts, user preferences, project conventions,
    or anything worth remembering across the conversation.

    Args:
        action: One of 'set', 'get', 'delete', or 'list'.
        key: The memory key (required for set, get, delete).
        value: The value to store (required for set).
    """
    action = action.strip().lower()

    if action == "set":
        if not key:
            return "Error: 'key' is required for the 'set' action."
        if not value:
            return "Error: 'value' is required for the 'set' action."
        _memory_store[key] = value
        return f"Saved memory: '{key}' = '{value}'"

    elif action == "get":
        if not key:
            return "Error: 'key' is required for the 'get' action."
        if key not in _memory_store:
            return f"No memory found for key: '{key}'"
        return f"{key} = {_memory_store[key]}"

    elif action == "delete":
        if not key:
            return "Error: 'key' is required for the 'delete' action."
        if key not in _memory_store:
            return f"No memory found for key: '{key}'"
        del _memory_store[key]
        return f"Deleted memory: '{key}'"

    elif action == "list":
        if not _memory_store:
            return "No memories stored yet."
        entries = [f"  {k} = {v}" for k, v in _memory_store.items()]
        return f"Stored memories ({len(_memory_store)}):\n" + "\n".join(entries)

    else:
        return f"Error: Unknown action '{action}'. Use 'set', 'get', 'delete', or 'list'."
