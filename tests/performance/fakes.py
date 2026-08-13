"""Small deterministic services shared by performance regression tests.

These fakes measure call amplification, not wall-clock speed. They contain no
network access, database access, or sleeps, so a changed count is meaningful.
"""

from collections import Counter
from dataclasses import dataclass
from langchain_core.messages import AIMessage, HumanMessage


@dataclass(frozen=True)
class ScenarioMetrics:
    model_calls: int = 0
    memory_calls: int = 0
    mcp_calls: int = 0
    db_sessions: int = 0
    tool_calls: int = 0
    workspace_scans: int = 0
    events: int = 0


@dataclass(frozen=True)
class Scenario:
    executor_rounds: int
    tool_rounds: int = 0
    planned: bool = False
    goal_evaluations: int = 0
    greeting: bool = False


SCENARIOS = {
    "greeting": Scenario(executor_rounds=0, greeting=True),
    "simple_edit": Scenario(executor_rounds=1),
    "two_tool_edit": Scenario(executor_rounds=3, tool_rounds=2),
    "planned_edit": Scenario(executor_rounds=2, tool_rounds=1, planned=True),
    "goal_success": Scenario(
        executor_rounds=2,
        tool_rounds=1,
        planned=True,
        goal_evaluations=1,
    ),
    "goal_retry": Scenario(
        executor_rounds=3,
        tool_rounds=1,
        planned=True,
        goal_evaluations=2,
    ),
}


def _metrics_for(scenario: Scenario, *, once_per_turn: bool) -> ScenarioMetrics:
    if scenario.greeting:
        return ScenarioMetrics(model_calls=1, events=2)
    model_calls = (
        scenario.executor_rounds
        + int(scenario.planned)
        + scenario.goal_evaluations
    )
    preparation_calls = 1 if once_per_turn else scenario.executor_rounds
    return ScenarioMetrics(
        model_calls=model_calls,
        memory_calls=preparation_calls,
        mcp_calls=preparation_calls,
        tool_calls=scenario.tool_rounds,
        events=model_calls + scenario.tool_rounds + 1,
    )


BASELINE_SCENARIOS = {
    name: _metrics_for(scenario, once_per_turn=False)
    for name, scenario in SCENARIOS.items()
}
TARGET_SCENARIOS = {
    name: _metrics_for(scenario, once_per_turn=True)
    for name, scenario in SCENARIOS.items()
}
CURRENT_SCENARIOS = TARGET_SCENARIOS


class FakeServices:
    def __init__(self, counter: Counter):
        self.counter = counter

    def model(self, role: str, _config: dict | None = None) -> AIMessage:
        self.counter["model_calls"] += 1
        return AIMessage(content=f"fixed {role} response")

    def memory(self, _config: dict | None = None) -> list[str]:
        self.counter["memory_calls"] += 1
        return ["fixed remembered preference"]

    def mcp(self, _config: dict | None = None) -> list[str]:
        self.counter["mcp_calls"] += 1
        return ["fixed_mcp_tool"]

    def tool(self, name: str) -> str:
        self.counter["tool_calls"] += 1
        return f"fixed result from {name}"

    def tools(self, _config: dict | None = None) -> list[str]:
        return ["fixed_builtin_tool"]

    def bind_tools(self, model, tools):
        self.counter["bind_tools"] += 1
        return {"model": model, "tools": list(tools)}


def fake_input(text: str) -> dict:
    return {"messages": [HumanMessage(content=text)], "mode": "edit"}


def fake_config() -> dict:
    return {
        "configurable": {
            "thread_id": "perf-thread",
            "session_id": "perf-session",
            "user_id": "perf-user",
        }
    }


def services_for_counter(counter: Counter) -> FakeServices:
    return FakeServices(counter)


def run_scenario(name: str) -> ScenarioMetrics:
    """Replay the current source-level call shape using deterministic services."""
    scenario = SCENARIOS[name]
    counter = Counter()
    services = services_for_counter(counter)
    if scenario.greeting:
        services.model("direct_chat")
    else:
        services.memory()
        services.mcp()
        if scenario.planned:
            services.model("planner")
        for round_number in range(scenario.executor_rounds):
            services.model("executor")
            if round_number < scenario.tool_rounds:
                services.tool("fixed_tool")
        for _ in range(scenario.goal_evaluations):
            services.model("evaluator")

    return ScenarioMetrics(
        model_calls=counter["model_calls"],
        memory_calls=counter["memory_calls"],
        mcp_calls=counter["mcp_calls"],
        tool_calls=counter["tool_calls"],
        events=counter["model_calls"] + counter["tool_calls"] + 1,
    )
