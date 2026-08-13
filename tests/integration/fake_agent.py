import json
from pathlib import Path

from agent.runtime.events import StreamEvent


FIXTURE = Path(__file__).parents[1] / "fixtures" / "run_events" / "surface_parity.json"


class FakeAgent:
    def __init__(self):
        self.scenarios = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.resumes = []

    def replay(self, name: str):
        return [StreamEvent.model_validate(event) for event in self.scenarios[name]["events"]]

    def resume(self, payload: dict):
        self.resumes.append(payload)
