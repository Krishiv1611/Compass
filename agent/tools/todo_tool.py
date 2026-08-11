"""Process-local, user-scoped task tracking for agent runs."""

import uuid

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

_tasks: dict[str, list[dict]] = {}


def _owner(config: RunnableConfig | None) -> str:
    return str((config or {}).get("configurable", {}).get("user_id") or "cli")


def get_tasks_for_user(user_id: str) -> list[dict]:
    return list(_tasks.get(str(user_id), []))


@tool
def todo(
    action: str,
    text: str = "",
    task_id: str = "",
    *,
    config: RunnableConfig,
) -> str:
    """Add, complete, list, or clear tasks for the active user."""
    tasks = _tasks.setdefault(_owner(config), [])
    action = action.strip().lower()

    if action == "add":
        if not text.strip():
            return "Error: text is required for add."
        task = {"id": uuid.uuid4().hex[:8], "text": text.strip(), "done": False}
        tasks.append(task)
        return f"Added task {task['id']}: {task['text']}"

    if action == "complete":
        for task in tasks:
            if task["id"] == task_id:
                task["done"] = True
                return f"Completed task {task_id}: {task['text']}"
        return f"Error: No task found with ID '{task_id}'"

    if action == "list":
        if not tasks:
            return "No tasks yet."
        done = sum(1 for task in tasks if task["done"])
        lines = [
            f"  [{'x' if task['done'] else ' '}] {task['id']} - {task['text']}"
            for task in tasks
        ]
        return f"Tasks ({done}/{len(tasks)} completed):\n" + "\n".join(lines)

    if action == "clear":
        active = [task for task in tasks if not task["done"]]
        removed = len(tasks) - len(active)
        _tasks[_owner(config)] = active
        return f"Cleared {removed} completed task(s). {len(active)} remaining."

    return "Error: action must be add, complete, list, or clear."
