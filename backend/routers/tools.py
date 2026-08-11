"""Tool catalog and compatibility activity endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agent.tools.memory_tool import list_memories
from agent.tools.todo_tool import get_tasks_for_user
from backend.auth.dependencies import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInfo(BaseModel):
    name: str
    description: str
    environment: str = "web"


@router.get("", response_model=list[ToolInfo])
def list_tools(current_user: User = Depends(get_current_user)):
    from agent.graph.tools_registry import ALL_TOOLS

    tui_only = {"shell_execute"}
    return [
        ToolInfo(
            name=tool.name,
            description=(tool.description or "No description")[:300],
            environment="tui" if tool.name in tui_only else "web",
        )
        for tool in ALL_TOOLS
        if hasattr(tool, "name")
    ]


@router.get("/tasks")
def get_tasks(current_user: User = Depends(get_current_user)):
    """Return the current task list."""
    return {"tasks": get_tasks_for_user(str(current_user.id))}


@router.get("/memory")
def get_memories(current_user: User = Depends(get_current_user)):
    """Backward-compatible global memory list for the Context Drawer."""
    memories, enabled, error = list_memories(str(current_user.id))
    return {"memories": memories, "enabled": enabled, "error": error}
