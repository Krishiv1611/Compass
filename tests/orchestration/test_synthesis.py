import unittest
from datetime import datetime, timezone

from langchain_core.messages import AIMessage

from agent.orchestration.models import AgentArtifact, AgentEvidence, TaskStatus
from agent.orchestration.models import ExecutionPlan
from agent.runtime.turn_context import TurnContext
from tests.orchestration.factories import make_task


def artifact(task_id: str, **overrides) -> AgentArtifact:
    now = datetime.now(timezone.utc)
    values = {
        "task_id": task_id,
        "status": TaskStatus.COMPLETED,
        "summary": f"Completed {task_id}",
        "evidence": [
            AgentEvidence(
                type="file",
                locator="app.py:10",
                claim="The handler validates input",
            )
        ],
        "started_at": now,
        "ended_at": now,
    }
    values.update(overrides)
    return AgentArtifact(**values)


class SummaryModel:
    def __init__(self):
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        return AIMessage(
            content="Two workers verified the handler; the executor owns any edits.",
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
            },
        )


class CompletedWorker:
    async def run(self, task, _context, _cancel_event):
        return artifact(task.id)


class SynthesisTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_evidence_is_deduplicated(self):
        from agent.orchestration.synthesis import synthesize_artifacts

        result = await synthesize_artifacts(
            [artifact("backend"), artifact("web")],
            model=None,
        )

        self.assertEqual(len(result.supported_findings), 1)
        self.assertEqual(result.supported_findings[0].locator, "app.py:10")

    async def test_contradictory_claims_at_one_locator_are_conflicts(self):
        from agent.orchestration.synthesis import synthesize_artifacts

        first = artifact("first")
        second = artifact(
            "second",
            evidence=[
                AgentEvidence(
                    type="file",
                    locator="app.py:10",
                    claim="The handler accepts input without validation",
                )
            ],
        )

        result = await synthesize_artifacts([first, second], model=None)

        self.assertEqual(result.supported_findings, [])
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("app.py:10", result.conflicts[0])
        self.assertIn("validates input", result.conflicts[0])
        self.assertIn("without validation", result.conflicts[0])

    async def test_compatible_claims_at_one_locator_remain_supported(self):
        from agent.orchestration.synthesis import synthesize_artifacts

        result = await synthesize_artifacts(
            [
                artifact("first"),
                artifact(
                    "second",
                    evidence=[AgentEvidence(
                        type="file",
                        locator="app.py:10",
                        claim="The handler returns a response object",
                    )],
                ),
            ],
            model=None,
        )

        self.assertEqual(result.conflicts, [])
        self.assertEqual(len(result.supported_findings), 2)

    async def test_negation_and_unrelated_failure_do_not_create_false_conflicts(self):
        from agent.orchestration.synthesis import _claims_conflict

        self.assertFalse(_claims_conflict(
            "Parser accepts input",
            "Parser does not trim input",
        ))
        self.assertFalse(_claims_conflict(
            "Feature flag is enabled",
            "Validation test fails",
        ))
        self.assertFalse(_claims_conflict(
            "Parser accepts valid input",
            "Parser does not accept invalid input",
        ))
        self.assertTrue(_claims_conflict(
            "Handler validates input",
            "Handler never performs validation",
        ))
        self.assertTrue(_claims_conflict(
            "Handler validates input",
            "Handler cannot validate input",
        ))

    async def test_completed_artifact_without_evidence_becomes_invalid(self):
        from agent.orchestration.synthesis import normalize_artifacts

        normalized = normalize_artifacts([artifact("empty", evidence=[])])

        self.assertEqual(normalized[0].status, TaskStatus.INVALID)
        self.assertIn("no evidence", normalized[0].error.lower())

    async def test_proposals_remain_text_and_summary_uses_one_model_call(self):
        from agent.orchestration.synthesis import synthesize_artifacts

        model = SummaryModel()
        result = await synthesize_artifacts(
            [
                artifact(
                    "audit",
                    proposed_changes=["Add a guard in app.py"],
                )
            ],
            model=model,
        )

        self.assertEqual(model.calls, 1)
        self.assertEqual(result.proposed_changes, ["Add a guard in app.py"])
        self.assertNotIn("tool_call", result.model_dump())
        self.assertIn("executor owns any edits", result.summary)

    async def test_parallel_plan_routes_through_workers_before_executor(self):
        from agent.graph.workflow import _route_after_planner

        parallel = ExecutionPlan(tasks=[make_task("backend"), make_task("web")])
        route = await _route_after_planner(
            {
                "mode": "edit",
                "orchestration_enabled": True,
                "execution_plan": parallel.model_dump(mode="json"),
            }
        )
        fallback = await _route_after_planner(
            {
                "mode": "edit",
                "orchestration_enabled": False,
                "execution_plan": ExecutionPlan(
                    tasks=[make_task("main-executor")]
                ).model_dump(mode="json"),
            }
        )

        self.assertEqual(route, "coordinator")
        self.assertEqual(fallback, "executor")

    async def test_downstream_parallel_layer_routes_through_workers(self):
        from agent.graph.workflow import _route_after_planner

        plan = ExecutionPlan(tasks=[
            make_task("root"),
            make_task("backend", depends_on=["root"]),
            make_task("web", depends_on=["root"]),
        ])
        route = await _route_after_planner({
            "mode": "edit",
            "orchestration_enabled": True,
            "execution_plan": plan.model_dump(mode="json"),
        })

        self.assertEqual(route, "coordinator")

    async def test_coordinator_node_persists_artifacts_and_redacted_events(self):
        from agent.graph.nodes import coordinator_node
        from agent.runtime.runner import events_for_node_artifacts

        plan = ExecutionPlan(tasks=[make_task("backend"), make_task("web")])
        update = await coordinator_node(
            {"execution_plan": plan.model_dump(mode="json")},
            {
                "configurable": {
                    "_worker_runner": CompletedWorker(),
                }
            },
        )

        self.assertEqual(
            [item["task_id"] for item in update["worker_artifacts"]],
            ["backend", "web"],
        )
        self.assertEqual(len(update["worker_events"]), 6)
        self.assertNotIn("objective", update["worker_events"][0]["data"])
        projected = events_for_node_artifacts("coordinator", update)
        completed = [event for event in projected if event.type.value == "agent_completed"]
        self.assertEqual(len(completed), 2)
        self.assertEqual(completed[0].content, "Completed backend")

    async def test_synthesis_node_stores_executor_briefing(self):
        from agent.graph.nodes import synthesis_node
        from agent.runtime.runner import events_for_node_artifacts

        model = SummaryModel()
        context = TurnContext(
            user_query="Audit the project",
            model_clients={"synthesizer": model},
        )
        update = await synthesis_node(
            {"worker_artifacts": [artifact("audit").model_dump(mode="json")]},
            {"configurable": {"_turn_context": context}},
        )

        self.assertEqual(model.calls, 1)
        self.assertIn("executor owns any edits", update["synthesis"]["summary"])
        self.assertEqual(update["synthesis"]["proposed_changes"], [])
        events = events_for_node_artifacts("synthesis", update)
        self.assertEqual(events[0].type.value, "status")
        self.assertEqual(events[0].data["conflicts"], [])


if __name__ == "__main__":
    unittest.main()
