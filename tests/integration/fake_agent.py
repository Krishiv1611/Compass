import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent.checkpoints import create_checkpoint, seal_checkpoint
from agent.hooks import VerificationHook, build_hook_run_requests, hook_result_status
from agent.orchestration.coordinator import Coordinator
from agent.orchestration.models import (
    AgentArtifact,
    AgentEvidence,
    AgentTask,
    ExecutionPlan,
    TaskStatus,
)
from agent.orchestration.synthesis import synthesize_artifacts
from agent.runtime.events import StreamEvent, StreamEventType, ToolCallData
from agent.runtime.runner import events_for_node_artifacts
from agent.safety import requires_approval
from agent.tools.registry import build_builtin_registry


FIXTURE = Path(__file__).parents[1] / "fixtures" / "run_events" / "surface_parity.json"
MULTI_AGENT_FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "run_events" / "multi_agent_journey.json"
)


class FakeAgent:
    def __init__(self):
        self.scenarios = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.resumes = []
        self.approval_pending = False
        self.approved = False

    def replay(self, name: str):
        return [StreamEvent.model_validate(event) for event in self.scenarios[name]["events"]]

    def resume(self, payload: dict):
        self.resumes.append(payload)
        if self.approval_pending and payload.get("action") in {"approve", "yes"}:
            self.approved = True
            self.approval_pending = False

    def multi_agent_journey(self):
        scenario = json.loads(MULTI_AGENT_FIXTURE.read_text(encoding="utf-8"))
        return scenario, [
            StreamEvent.model_validate(event) for event in scenario["events"]
        ]

    async def run_multi_agent_journey(self, workspace: Path) -> dict:
        """Execute the real bounded coordinator, checkpoint, tools, and hook."""
        target = workspace / "app.py"
        target.write_text("old content", encoding="utf-8")
        actions: list[str] = []
        worker = _JourneyWorker(actions)
        plan = ExecutionPlan(tasks=[
            _task("backend", "Audit backend"),
            _task("web", "Audit web"),
        ])
        worker_events: list[StreamEvent] = []
        artifacts = await Coordinator(worker, event_sink=worker_events.append).run(
            plan,
            {},
            asyncio.Event(),
        )
        synthesis = await synthesize_artifacts(artifacts, model=None)

        events = [StreamEvent(
            type=StreamEventType.PLAN_CREATED,
            content="1. Audit backend\n2. Audit web\n3. Apply approved change",
            node="planner",
        )]
        events.extend(events_for_node_artifacts("coordinator", {
            "worker_artifacts": [item.model_dump(mode="json") for item in artifacts],
            "worker_events": [item.model_dump(mode="json") for item in worker_events],
        }))
        events.extend(events_for_node_artifacts(
            "synthesis",
            {"synthesis": synthesis.model_dump(mode="json")},
        ))

        edit_args = {
            "path": "app.py",
            "old_content": "old content",
            "new_content": "new content",
        }
        if not requires_approval("edit_file", edit_args, []):
            raise AssertionError("acceptance edit must require approval")
        self.approval_pending = True
        events.append(StreamEvent(
            type=StreamEventType.APPROVAL_REQUIRED,
            content="Approve edit_file for app.py",
            data={"kind": "tool_approval", "reason": "write_requires_approval"},
        ))
        actions.append("approval_requested")
        self.resume({"action": "approve"})
        actions.append("approval_resumed")
        if not self.approved:
            raise PermissionError("write was not approved")

        checkpoint = create_checkpoint(
            workspace,
            ["app.py"],
            workspace_id="acceptance",
            thread_id="journey",
            label="Before acceptance write",
        )
        actions.append("checkpoint")
        events.append(StreamEvent(
            type=StreamEventType.CHECKPOINT_CREATED,
            content="Checkpoint created",
            data={"checkpoint_id": checkpoint.id, "affected_files": ["app.py"]},
        ))

        config = {"configurable": {
            "execution_target": "local",
            "thread_id": "journey",
            "workspace_context": {
                "root": str(workspace),
                "execution_target": "local",
                "workspace_id": "acceptance",
            },
        }}
        registry = build_builtin_registry()
        events.append(StreamEvent(
            type=StreamEventType.TOOL_CALL,
            tool_call=ToolCallData(id="edit-1", name="edit_file", args=edit_args),
            data={"actor": "main-executor"},
        ))
        edit_result = registry.get("edit_file").tool.invoke(edit_args, config=config)
        actions.append("write")
        if not str(edit_result).startswith("Successfully edited"):
            raise AssertionError(edit_result)
        seal_checkpoint(workspace, checkpoint.id)
        events.extend([
            StreamEvent(
                type=StreamEventType.TOOL_RESULT,
                tool_call_id="edit-1",
                content=str(edit_result),
                data={"name": "edit_file", "status": "success", "actor": "main-executor"},
            ),
            StreamEvent(
                type=StreamEventType.WORKSPACE_PATCH,
                data={"affected_files": ["app.py"], "actor": "main-executor"},
            ),
        ])

        hook = VerificationHook(
            name="python tests",
            command=f'"{sys.executable}" -c "print(\'hook ok\')"',
            run_on=("py",),
        )
        request = build_hook_run_requests([hook])[0]
        hook_result = registry.get(request.tool_name).tool.invoke(
            request.arguments,
            config=config,
        )
        hook_status = hook_result_status(hook_result)
        actions.append("hook")
        events.append(StreamEvent(
            type=StreamEventType.CHECK_RESULT,
            content=request.hook_name,
            data={"id": request.id, "status": hook_status, "details": str(hook_result)},
        ))

        usage_by_node = {
            "planner": {"total_tokens": 10},
            **{f"worker.{item.task_id}": item.usage for item in artifacts},
            "synthesizer": {"total_tokens": 10},
            "executor": {"total_tokens": 20},
        }
        total_tokens = sum(int(value.get("total_tokens", 0)) for value in usage_by_node.values())
        events.extend([
            StreamEvent(
                type=StreamEventType.USAGE,
                data={"total_tokens": total_tokens, "usage_by_node": usage_by_node},
            ),
            StreamEvent(
                type=StreamEventType.DONE,
                content="Applied the approved guard to app.py",
                data={"status": "completed"},
            ),
        ])
        for sequence, event in enumerate(events, 1):
            event.seq = sequence
        return {
            "events": events,
            "plan": plan,
            "artifacts": artifacts,
            "synthesis": synthesis,
            "actions": actions,
            "maximum_active": worker.maximum_active,
            "checkpoint_id": checkpoint.id,
            "hook_status": hook_status,
            "changed_content": target.read_text(encoding="utf-8"),
            "usage_by_node": usage_by_node,
        }


def _task(task_id: str, title: str) -> AgentTask:
    return AgentTask(
        id=task_id,
        title=title,
        objective=f"Inspect {task_id}",
        kind="analysis",
        allowed_tools=["read_file", "grep_search"],
        success_criteria=["Return evidence"],
    )


class _JourneyWorker:
    def __init__(self, actions: list[str]):
        self.actions = actions
        self.active = 0
        self.maximum_active = 0

    async def run(self, task: AgentTask, _context, _cancel_event) -> AgentArtifact:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        self.actions.append(f"worker:{task.id}:start")
        await asyncio.sleep(0)
        now = datetime.now(timezone.utc)
        evidence = [AgentEvidence(
            type="file",
            locator="app.py:1",
            claim=(
                "Handler validates input"
                if task.id == "backend"
                else "Handler cannot validate input"
            ),
        )]
        if task.id == "web":
            evidence.append(AgentEvidence(
                type="finding",
                locator="web-client",
                claim="Web client handles the guarded response",
            ))
        artifact = AgentArtifact(
            task_id=task.id,
            status=TaskStatus.COMPLETED,
            summary=(
                "Backend route needs the approved guard."
                if task.id == "backend"
                else "Web client already handles the guarded response."
            ),
            evidence=evidence,
            usage={"total_tokens": 15},
            started_at=now,
            ended_at=now,
        )
        self.active -= 1
        self.actions.append(f"worker:{task.id}:complete")
        return artifact
