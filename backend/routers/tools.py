"""
Tools router — list available agent tools.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.models.user import User

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolInfo(BaseModel):
    """Description of an available agent tool."""
    name: str
    description: str


@router.get("", response_model=list[ToolInfo])
def list_tools(current_user: User = Depends(get_current_user)):
    """List all available agent tools with their descriptions."""
    from graph.workflow import ALL_TOOLS

    return [
        ToolInfo(
            name=tool.name,
            description=(tool.description or "No description")[:300],
        )
        for tool in ALL_TOOLS
        if hasattr(tool, "name")
    ]
