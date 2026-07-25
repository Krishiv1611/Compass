from pathlib import Path
from langchain_core.runnables.config import RunnableConfig
from agent.workspace import WorkspaceContext, discover_local_workspace


def get_workspace_for_tool(config: RunnableConfig | None) -> WorkspaceContext:
    """Return the configured web boundary or discover the local project root."""
    configurable = (config or {}).get("configurable", {})
    context_data = configurable.get("workspace_context")
    if context_data:
        context = WorkspaceContext.from_config(context_data)
        if context.execution_target == "web" and not context.workspace_id:
            raise ValueError("Web workspace ID is not configured.")
        return context

    if configurable.get("execution_target") == "web" or configurable.get("session_id"):
        raise ValueError("Workspace context is not configured for this web session.")

    return discover_local_workspace()


def resolve_workspace_path(workspace: WorkspaceContext, target_path: str) -> str:
    """Resolve a path relative to the workspace, ensuring it doesn't escape."""
    target_path = str(target_path).strip()
    base = workspace.root.resolve()
    requested = Path(target_path)
    target = requested.resolve() if requested.is_absolute() else (base / requested).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(f"Access denied: path '{target_path}' escapes the workspace directory.")
    return str(target)
