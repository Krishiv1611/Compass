"""Validation for dependency-safe, read-only worker execution plans."""

from __future__ import annotations

from collections.abc import Collection

from agent.orchestration.models import ExecutionPlan


WORKER_ALLOWED_TOOLS = frozenset(
    {
        "read_file",
        "list_dir",
        "find_files",
        "grep_search",
        "web_search",
    }
)


def _reject_dependency_cycles(plan: ExecutionPlan) -> None:
    dependencies = {task.id: task.depends_on for task in plan.tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise ValueError("execution plan contains a dependency cycle")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency_id in dependencies[task_id]:
            visit(dependency_id)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in dependencies:
        visit(task_id)


def validate_execution_plan(
    plan: ExecutionPlan,
    *,
    available_tools: Collection[str],
) -> ExecutionPlan:
    """Validate IDs, dependencies, tools, and acyclic execution order."""
    task_ids = [task.id for task in plan.tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("execution plan contains duplicate task IDs")
    known_ids = set(task_ids)
    available = set(available_tools)

    for task in plan.tasks:
        for dependency_id in task.depends_on:
            if dependency_id not in known_ids:
                raise ValueError(
                    f"task '{task.id}' depends on missing task '{dependency_id}'"
                )
        for tool_name in task.allowed_tools:
            if tool_name not in WORKER_ALLOWED_TOOLS:
                raise ValueError(f"tool '{tool_name}' is not worker-allowed")
            if tool_name not in available:
                raise ValueError(f"worker tool '{tool_name}' is unavailable")

    _reject_dependency_cycles(plan)
    return plan
