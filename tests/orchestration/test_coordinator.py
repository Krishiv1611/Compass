import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.orchestration.models import (
    AgentArtifact,
    AgentEvidence,
    ExecutionPlan,
    TaskStatus,
)
from agent.runtime.metrics import begin_run_metrics, end_run_metrics
from agent.skills.manager import SkillManagerAgent
from agent.tools.registry import build_builtin_registry
from tests.orchestration.factories import make_task


def artifact(task_id: str, status: TaskStatus = TaskStatus.COMPLETED, **overrides):
    now = datetime.now(timezone.utc)
    values = {
        "task_id": task_id,
        "status": status,
        "summary": f"{task_id} {status.value}",
        "started_at": now,
        "ended_at": now,
    }
    values.update(overrides)
    return AgentArtifact(**values)


class GateWorker:
    def __init__(self, gated_ids=()):
        self.gated_ids = set(gated_ids)
        self.release = asyncio.Event()
        self.started = {task_id: asyncio.Event() for task_id in gated_ids}
        self.active = 0
        self.max_active = 0
        self.completed = set()
        self.dependencies_seen = {}

    async def run(self, task, _context, _cancel_event):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.dependencies_seen[task.id] = set(self.completed)
        if task.id in self.started:
            self.started[task.id].set()
        try:
            if task.id in self.gated_ids:
                await self.release.wait()
            self.completed.add(task.id)
            return artifact(
                task.id,
                evidence=[
                    AgentEvidence(
                        type="finding",
                        locator=task.id,
                        claim=f"Completed {task.id}",
                    )
                ],
                usage={"input_tokens": 3, "output_tokens": 2},
            )
        finally:
            self.active -= 1


class CancellationWorker:
    def __init__(self):
        self.started = {"a": asyncio.Event(), "b": asyncio.Event()}

    async def run(self, task, _context, _cancel_event):
        self.started[task.id].set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return artifact(task.id, TaskStatus.CANCELLED)


class FailedWorker:
    async def run(self, task, _context, _cancel_event):
        status = TaskStatus.FAILED if task.id == "source" else TaskStatus.COMPLETED
        return artifact(task.id, status)


class NestedWorker:
    def __init__(self):
        self.nesting_denied = False

    async def run(self, task, context, cancel_event):
        from agent.orchestration.coordinator import Coordinator

        nested = ExecutionPlan(tasks=[make_task("nested")])
        try:
            await Coordinator(self).run(nested, context, cancel_event)
        except PermissionError:
            self.nesting_denied = True
        return artifact(task.id)


class FakeGraph:
    def __init__(self, final_state):
        self.final_state = final_state

    async def ainvoke(self, _initial_state, *, config):
        self.config = config
        return self.final_state


class FakeFactory:
    final_state = {}
    last_delegation_allowed = None
    tool_names = []

    def __init__(self, tools):
        type(self).tool_names = [tool.name for tool in tools]

    def build(self, _skill, _arguments, *, delegation_allowed=True):
        type(self).last_delegation_allowed = delegation_allowed
        return FakeGraph(type(self).final_state)


class BlockingGraph:
    async def ainvoke(self, _initial_state, *, config):
        usage = config["configurable"]["_worker_usage"]
        usage.update({"input_tokens": 4, "output_tokens": 1, "total_tokens": 5})
        await asyncio.Event().wait()


class BlockingFactory(FakeFactory):
    def build(self, _skill, _arguments, *, delegation_allowed=True):
        return BlockingGraph()


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_tasks_overlap_and_dependency_waits_for_both(self):
        from agent.orchestration.coordinator import Coordinator

        worker = GateWorker(gated_ids={"backend", "web"})
        plan = ExecutionPlan(
            tasks=[
                make_task("backend"),
                make_task("web"),
                make_task("synthesis", depends_on=["backend", "web"]),
            ]
        )
        running = asyncio.create_task(
            Coordinator(worker).run(plan, context={}, cancel_event=asyncio.Event())
        )
        await asyncio.wait_for(worker.started["backend"].wait(), 1)
        await asyncio.wait_for(worker.started["web"].wait(), 1)

        self.assertEqual(worker.max_active, 2)
        self.assertNotIn("synthesis", worker.dependencies_seen)
        worker.release.set()
        results = await asyncio.wait_for(running, 1)

        self.assertEqual(worker.dependencies_seen["synthesis"], {"backend", "web"})
        self.assertEqual([item.task_id for item in results], ["backend", "web", "synthesis"])

    async def test_requested_concurrency_is_clamped_to_four(self):
        from agent.orchestration.coordinator import Coordinator

        ids = {f"task-{index}" for index in range(5)}
        worker = GateWorker(gated_ids=ids)
        plan = ExecutionPlan(tasks=[make_task(task_id) for task_id in sorted(ids)])
        running = asyncio.create_task(
            Coordinator(worker).run(
                plan,
                context={},
                cancel_event=asyncio.Event(),
                max_workers=99,
            )
        )
        for task_id in sorted(ids)[:4]:
            await asyncio.wait_for(worker.started[task_id].wait(), 1)

        self.assertEqual(worker.max_active, 4)
        self.assertEqual(sum(event.is_set() for event in worker.started.values()), 4)
        worker.release.set()
        await asyncio.wait_for(running, 1)

    async def test_cancellation_reaches_every_active_worker(self):
        from agent.orchestration.coordinator import Coordinator

        worker = CancellationWorker()
        cancel_event = asyncio.Event()
        running = asyncio.create_task(
            Coordinator(worker).run(
                ExecutionPlan(tasks=[make_task("a"), make_task("b")]),
                context={},
                cancel_event=cancel_event,
            )
        )
        await asyncio.wait_for(worker.started["a"].wait(), 1)
        await asyncio.wait_for(worker.started["b"].wait(), 1)
        cancel_event.set()
        results = await asyncio.wait_for(running, 1)

        self.assertEqual(
            [item.status for item in results],
            [TaskStatus.CANCELLED, TaskStatus.CANCELLED],
        )

    async def test_failed_dependency_blocks_dependent_task(self):
        from agent.orchestration.coordinator import Coordinator

        results = await Coordinator(FailedWorker()).run(
            ExecutionPlan(
                tasks=[
                    make_task("source"),
                    make_task("dependent", depends_on=["source"]),
                ]
            ),
            context={},
            cancel_event=asyncio.Event(),
        )

        self.assertEqual(results[0].status, TaskStatus.FAILED)
        self.assertEqual(results[1].status, TaskStatus.BLOCKED)
        self.assertIn("source", results[1].error)

    async def test_worker_rejects_mutating_and_skill_creation_tools(self):
        from agent.orchestration.worker import WorkerRunner

        runner = WorkerRunner(registry=build_builtin_registry())
        for tool_name in ("edit_file", "create_skill"):
            result = await runner.run(
                make_task("unsafe", allowed_tools=[tool_name]),
                context={},
                cancel_event=asyncio.Event(),
            )
            self.assertEqual(result.status, TaskStatus.INVALID)
            self.assertIn("not worker-allowed", result.error)

    async def test_worker_adapter_returns_validated_json_artifact(self):
        from agent.orchestration.worker import WorkerRunner

        FakeFactory.final_state = {
            "messages": [
                AIMessage(
                    content=(
                        '{"summary":"Read the file","evidence":[{"type":"file",'
                        '"locator":"app.py:1","claim":"Entry point exists"}],'
                        '"files_considered":["app.py"],"proposed_changes":[],"checks":[]}'
                    )
                )
            ],
            "usage": {"input_tokens": 8, "output_tokens": 3, "total_tokens": 11},
        }
        runner = WorkerRunner(
            registry=build_builtin_registry(), factory_type=FakeFactory
        )

        result = await runner.run(
            make_task("audit", allowed_tools=["read_file"]),
            context={"configurable": {"workspace_context": {"root": "repo"}}},
            cancel_event=asyncio.Event(),
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.evidence[0].locator, "app.py:1")
        self.assertEqual(result.usage["total_tokens"], 11)
        self.assertEqual(FakeFactory.tool_names, ["read_file"])
        self.assertFalse(FakeFactory.last_delegation_allowed)

    async def test_worker_adapter_rejects_unresolved_tool_calls(self):
        from agent.orchestration.worker import WorkerRunner

        FakeFactory.final_state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "read_file", "args": {"path": "app.py"}, "id": "call-1"}
                    ],
                )
            ],
            "usage": {"input_tokens": 6, "output_tokens": 1, "total_tokens": 7},
        }

        result = await WorkerRunner(
            registry=build_builtin_registry(), factory_type=FakeFactory
        ).run(make_task("audit"), context={}, cancel_event=asyncio.Event())

        self.assertEqual(result.status, TaskStatus.INVALID)
        self.assertIn("unresolved tool calls", result.error)
        self.assertEqual(result.usage["total_tokens"], 7)

    async def test_timeout_is_failed_and_preserves_partial_usage(self):
        from agent.orchestration.coordinator import Coordinator
        from agent.orchestration.worker import WorkerRunner

        runner = WorkerRunner(
            registry=build_builtin_registry(), factory_type=BlockingFactory
        )
        real_timeout = asyncio.timeout
        with patch(
            "agent.orchestration.coordinator.asyncio.timeout",
            side_effect=lambda _seconds: real_timeout(0.01),
        ):
            result = await Coordinator(runner).run(
                ExecutionPlan(tasks=[make_task("slow")]),
                context={},
                cancel_event=asyncio.Event(),
            )

        self.assertEqual(result[0].status, TaskStatus.FAILED)
        self.assertIn("timeout", result[0].error)
        self.assertEqual(result[0].usage["total_tokens"], 5)

    async def test_failed_worker_emits_redacted_failure_event(self):
        from agent.orchestration.coordinator import Coordinator

        events = []
        result = await Coordinator(FailedWorker(), event_sink=events.append).run(
            ExecutionPlan(tasks=[make_task("source")]),
            context={},
            cancel_event=asyncio.Event(),
        )

        self.assertEqual(result[0].status, TaskStatus.FAILED)
        self.assertEqual(
            [event.type.value for event in events],
            ["agent_started", "agent_progress", "agent_failed"],
        )
        self.assertNotIn("summary", events[-1].data)

    async def test_skill_manager_denies_nested_worker_delegation(self):
        manager = SkillManagerAgent(
            factory=SimpleNamespace(build=lambda *_args, **_kwargs: self.fail("spawned")),
            registry=SimpleNamespace(get=lambda _name: self.fail("looked up")),
        )

        update = await manager(
            {"active_skill": {"name": "nested", "arguments": "do more"}},
            {"configurable": {"delegation_allowed": False}},
        )

        self.assertEqual(update["skill_result"]["status"], "error")
        self.assertIn("disabled", update["skill_result"]["error"].lower())

    async def test_nested_coordinator_is_denied_inside_worker(self):
        from agent.orchestration.coordinator import Coordinator

        worker = NestedWorker()
        results = await Coordinator(worker).run(
            ExecutionPlan(tasks=[make_task("outer")]),
            context={},
            cancel_event=asyncio.Event(),
        )

        self.assertTrue(worker.nesting_denied)
        self.assertEqual(results[0].status, TaskStatus.COMPLETED)

    async def test_events_are_redacted_and_worker_usage_is_aggregated(self):
        from agent.orchestration.coordinator import Coordinator

        events = []
        metrics, token = begin_run_metrics()
        try:
            results = await Coordinator(GateWorker(), event_sink=events.append).run(
                ExecutionPlan(tasks=[make_task("audit")]),
                context={},
                cancel_event=asyncio.Event(),
            )
            snapshot = metrics.snapshot()
        finally:
            end_run_metrics(token)

        self.assertEqual(results[0].status, TaskStatus.COMPLETED)
        self.assertEqual(
            [event.type.value for event in events],
            ["agent_started", "agent_progress", "agent_completed"],
        )
        for event in events:
            self.assertLessEqual(
                set(event.data),
                {"task_id", "title", "status", "duration_ms", "evidence_count"},
            )
            self.assertNotIn("objective", event.data)
        self.assertEqual(snapshot.total_tokens, 5)


if __name__ == "__main__":
    unittest.main()
