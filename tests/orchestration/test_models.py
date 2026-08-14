import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from agent.orchestration.models import (
    AgentArtifact,
    AgentEvidence,
    AgentTask,
    ExecutionPlan,
    TaskStatus,
)
from agent.orchestration.validation import validate_execution_plan
from tests.orchestration.factories import make_task


class OrchestrationModelTests(unittest.TestCase):
    def test_cycle_is_rejected(self):
        plan = ExecutionPlan(
            tasks=[
                make_task("a", depends_on=["b"]),
                make_task("b", depends_on=["a"]),
            ]
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_execution_plan(plan, available_tools={"read_file"})

    def test_mutating_worker_tool_is_rejected(self):
        plan = ExecutionPlan(
            tasks=[make_task("a", allowed_tools=["edit_file"])]
        )
        with self.assertRaisesRegex(ValueError, "not worker-allowed"):
            validate_execution_plan(plan, available_tools={"read_file"})

    def test_limits_are_clamped(self):
        item = make_task("a", timeout_seconds=5000, token_budget=999999)
        self.assertEqual((item.timeout_seconds, item.token_budget), (600, 50000))

    def test_missing_dependency_and_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            validate_execution_plan(
                ExecutionPlan(tasks=[make_task("a", depends_on=["missing"])]),
                available_tools={"read_file"},
            )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_execution_plan(
                ExecutionPlan(tasks=[make_task("a"), make_task("a")]),
                available_tools={"read_file"},
            )

    def test_models_reject_extra_fields_bad_ids_and_empty_criteria(self):
        with self.assertRaises(ValidationError):
            AgentTask(
                **make_task("valid").model_dump(),
                unexpected=True,
            )
        with self.assertRaises(ValidationError):
            make_task("Uppercase")
        with self.assertRaises(ValidationError):
            make_task("valid", success_criteria=["  "])

    def test_evidence_and_artifact_contracts_are_strict(self):
        evidence = AgentEvidence(
            type="file",
            locator="agent/graph/state.py:1",
            claim="The graph state is typed.",
        )
        artifact = AgentArtifact(
            task_id="audit",
            status=TaskStatus.COMPLETED,
            summary="Reviewed graph state.",
            evidence=[evidence],
            files_considered=["agent/graph/state.py"],
            proposed_changes=[],
            checks=["model validation passed"],
            usage={"input_tokens": 10, "output_tokens": 5},
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            error=None,
        )

        self.assertEqual(artifact.evidence[0].type.value, "file")
        with self.assertRaises(ValidationError):
            AgentEvidence(type="thought", locator="private", claim="hidden")

    def test_error_text_is_bounded_and_secret_values_are_redacted(self):
        secrets = [
            "Authorization: Bearer secret-token-value",
            "Authorization: Basic dXNlcjpwYXNz",
            "postgresql://alice:hunter2@db/app",
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456",
        ]
        for secret in secrets:
            with self.subTest(secret=secret):
                artifact = AgentArtifact(
                    task_id="failed",
                    status="failed",
                    summary="Worker failed safely.",
                    started_at=datetime.now(timezone.utc),
                    ended_at=datetime.now(timezone.utc),
                    error=secret,
                )
                self.assertIn("[REDACTED]", artifact.error)
                self.assertNotIn("hunter2", artifact.error)
                self.assertNotIn("dXNlcjpwYXNz", artifact.error)
                self.assertNotIn("ghp_", artifact.error)

    def test_artifact_timestamps_must_be_timezone_aware(self):
        with self.assertRaises(ValidationError):
            AgentArtifact(
                task_id="bad-time",
                status="failed",
                summary="Invalid worker timestamp.",
                started_at=datetime.now(),
                ended_at=datetime.now(timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
