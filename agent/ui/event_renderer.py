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
