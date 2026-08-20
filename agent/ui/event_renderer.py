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
    if event.type.value == "agent_started":
        return f"Worker: {data.get('title', 'task')} — started"
    if event.type.value in {"agent_completed", "agent_failed"}:
        status = data.get("status", "completed")
        evidence = data.get("evidence_count", 0)
        duration = data.get("duration_ms", 0)
        duration_text = (
            str(int(duration)) if isinstance(duration, (int, float)) else "0"
        )
        return (
            f"Worker: {data.get('title', 'task')} — {status} · "
            f"{evidence} evidence · {duration_text}ms"
        )
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


def workers_table(artifact: RunArtifact) -> str:
    """Return a compact `/agents`-ready table without worker prompts or contents."""
    if not artifact.workers:
        return "No worker tasks in the current run."
    lines = ["TASK | STATUS | EVIDENCE | TIME", "--- | --- | ---: | ---:"]
    for worker in artifact.workers:
        lines.append(
            f"{worker.title} | {worker.status} | {worker.evidence_count} | "
            f"{int(worker.duration_ms)}ms"
        )
    return "\n".join(lines)


def walkthrough_summary(artifact: RunArtifact) -> str:
    """Render the final run ownership, results, checks, usage, and conflicts."""
    walkthrough = artifact.walkthrough
    if not walkthrough:
        return ""
    lines = [f"Final walkthrough — {walkthrough.get('terminal_status') or 'unknown'}"]
    if walkthrough.get("plan"):
        lines.append(f"Plan: {walkthrough['plan']}")
    workers = walkthrough.get("worker_contributions") or []
    lines.append("Workers: " + ("; ".join(workers) if workers else "none"))
    files = walkthrough.get("changed_files") or []
    lines.append("Files: " + (", ".join(files) if files else "none"))
    checks = walkthrough.get("checks") or []
    check_text = ", ".join(
        f"{item.get('name', 'check')}={item.get('status', 'unknown')}"
        for item in checks
        if isinstance(item, dict)
    )
    lines.append("Checks: " + (check_text or "none"))
    usage = walkthrough.get("usage") or {}
    total = usage.get("total_tokens") if isinstance(usage, dict) else None
    lines.append(f"Usage: {total} tokens" if isinstance(total, int) else "Usage: unavailable")
    conflicts = walkthrough.get("unresolved_conflicts") or []
    lines.append("Conflicts: " + ("; ".join(conflicts) if conflicts else "none"))
    return "\n".join(lines)
