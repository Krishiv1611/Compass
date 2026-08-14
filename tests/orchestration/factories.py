from agent.orchestration.models import AgentTask


def make_task(task_id: str, **overrides) -> AgentTask:
    values = {
        "id": task_id,
        "title": f"Task {task_id}",
        "objective": f"Inspect the scope for {task_id}",
        "kind": "analysis",
        "depends_on": [],
        "allowed_tools": ["read_file"],
        "success_criteria": ["Report one evidence-backed conclusion"],
        "timeout_seconds": 300,
        "token_budget": 20_000,
    }
    values.update(overrides)
    return AgentTask(**values)
