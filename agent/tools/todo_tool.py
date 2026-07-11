import uuid
from langchain_core.tools import tool

# Module-level task list — persists within a single process run.
_tasks: list[dict] = []


@tool
def todo(action: str, text: str = "", task_id: str = "") -> str:
    """Manage a task list to track multi-step work.

    Use this to plan complex tasks, track progress, and stay organized
    when working on something that requires multiple steps.

    Args:
        action: One of 'add', 'complete', 'list', or 'clear'.
        text: The task description (required for add).
        task_id: The task ID to mark complete (required for complete).
    """
    action = action.strip().lower()

    if action == "add":
        if not text:
            return "Error: 'text' is required for the 'add' action."
        task = {
            "id": uuid.uuid4().hex[:8],
            "text": text,
            "done": False,
        }
        _tasks.append(task)
        return f"Added task {task['id']}: {text}"

    elif action == "complete":
        if not task_id:
            return "Error: 'task_id' is required for the 'complete' action."
        for task in _tasks:
            if task["id"] == task_id:
                task["done"] = True
                return f"Completed task {task_id}: {task['text']}"
        return f"Error: No task found with ID '{task_id}'"

    elif action == "list":
        if not _tasks:
            return "No tasks yet."
        done = sum(1 for t in _tasks if t["done"])
        lines = []
        for t in _tasks:
            mark = "x" if t["done"] else " "
            lines.append(f"  [{mark}] {t['id']} — {t['text']}")
        return f"Tasks ({done}/{len(_tasks)} completed):\n" + "\n".join(lines)

    elif action == "clear":
        before = len(_tasks)
        _tasks[:] = [t for t in _tasks if not t["done"]]
        removed = before - len(_tasks)
        return f"Cleared {removed} completed task(s). {len(_tasks)} remaining."

    else:
        return f"Error: Unknown action '{action}'. Use 'add', 'complete', 'list', or 'clear'."
