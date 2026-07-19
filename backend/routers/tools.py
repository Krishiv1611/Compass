from fastapi import APIRouter, Depends
from backend.auth.dependencies import get_current_user
from backend.models.user import User

from agent.tools.todo_tool import _tasks
from agent.tools.memory_tool import _store, _DEFAULT_NAMESPACE

router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("/tasks")
def get_tasks(current_user: User = Depends(get_current_user)):
    """Returns the current list of agent tasks."""
    return {"tasks": _tasks}

@router.get("/memory")
def get_memories(current_user: User = Depends(get_current_user)):
    """Returns the current long-term memories."""
    if not _store:
        return {"memories": [], "enabled": False}
    try:
        results = _store.search(_DEFAULT_NAMESPACE, offset=0, limit=100)
        memories = [
            {"key": r.key, "value": r.value, "updated_at": str(r.updated_at) if r.updated_at else None}
            for r in results
        ]
        return {"memories": memories, "enabled": True}
    except Exception as e:
        return {"memories": [], "enabled": False, "error": str(e)}
