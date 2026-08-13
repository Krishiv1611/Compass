"""TUI-facing projection of canonical runtime events."""

from agent.runtime.artifacts import RunArtifact, empty_run_artifact, reduce_run_event
from agent.runtime.events import StreamEvent


class EventRenderer:
    """Keep the TUI's run artifact in step with events it renders."""

    def __init__(self):
        self.artifact = empty_run_artifact()

    def add(self, event: StreamEvent) -> RunArtifact:
        self.artifact = reduce_run_event(self.artifact, event)
        return self.artifact


def artifact_summary_for_event(event: StreamEvent, artifact: RunArtifact) -> str | None:
    """Return a compact TUI line for artifact events that are not chat text."""
    data = event.data if isinstance(event.data, dict) else {}
    if event.type.value == "status" and event.content:
        return event.content
    if event.type.value == "plan_step":
        return f"Plan step {data.get('step', '?')}: {data.get('status', 'active')}"
    if event.type.value == "workspace_patch":
        values = data.get("affected_files", [])
        files = (
            [path for path in values if isinstance(path, str)]
            if isinstance(values, list)
            else []
        )
        return f"Changed: {', '.join(files)}" if files else None
    if event.type.value == "check_result" and artifact.checks:
        check = artifact.checks[-1]
        return f"Check: {check.name} — {check.status}"
    if event.type.value == "usage" and artifact.usage:
        total = artifact.usage.get("total_tokens")
        return f"Usage: {total} tokens" if isinstance(total, int) else None
    if event.type.value == "run_waiting":
        return "Run waiting for input"
    if event.type.value == "done":
        status = artifact.terminal_status or "completed"
        return f"Run {status.replace('_', ' ')}"
    return None
