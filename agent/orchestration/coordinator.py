"""Dependency-aware scheduler for bounded, non-nesting read-only workers."""

from __future__ import annotations

import asyncio
import inspect
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from agent.orchestration.models import AgentArtifact, AgentTask, ExecutionPlan, TaskStatus
from agent.runtime.events import StreamEvent, StreamEventType
from agent.runtime.metrics import current_run_metrics


DEFAULT_MAX_WORKERS = 2
HARD_MAX_WORKERS = 4
_WORKER_DEPTH: ContextVar[int] = ContextVar("compass_worker_depth", default=0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _terminal_artifact(
    task: AgentTask,
    status: TaskStatus,
    message: str,
    *,
    started_at: datetime | None = None,
    usage: dict[str, int | float] | None = None,
) -> AgentArtifact:
    return AgentArtifact(
        task_id=task.id,
        status=status,
        summary=message,
        error=message if status != TaskStatus.CANCELLED else None,
        usage=usage or {},
        started_at=started_at or _now(),
        ended_at=_now(),
    )


class Coordinator:
    """Run ready tasks concurrently while respecting dependencies and limits."""

    def __init__(self, worker, *, event_sink: Callable[[StreamEvent], Any] | None = None):
        self.worker = worker
        self.event_sink = event_sink

    async def _emit(
        self,
        event_type: StreamEventType,
        task: AgentTask,
        artifact=None,
        duration_ms=0,
    ):
        if self.event_sink is None:
            return
        status = (
            artifact.status.value
            if artifact is not None and event_type != StreamEventType.AGENT_PROGRESS
            else TaskStatus.RUNNING.value
        )
        data = {
            "task_id": task.id,
            "title": task.title,
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "evidence_count": len(artifact.evidence) if artifact is not None else 0,
        }
        result = self.event_sink(StreamEvent(type=event_type, data=data))
        if inspect.isawaitable(result):
            await result

    def _take_worker_usage(self, task_id: str) -> dict[str, int | float]:
        take_usage = getattr(self.worker, "take_usage", None)
        if not callable(take_usage):
            return {}
        value = take_usage(task_id)
        return value if isinstance(value, dict) else {}

    async def _run_one(
        self,
        task: AgentTask,
        context,
        cancel_event: asyncio.Event,
        semaphore: asyncio.Semaphore,
    ) -> AgentArtifact:
        started_at = _now()
        started_clock = perf_counter()
        emitted_start = False
        try:
            async with semaphore:
                if cancel_event.is_set():
                    raise asyncio.CancelledError
                await self._emit(StreamEventType.AGENT_STARTED, task)
                emitted_start = True
                depth_token = _WORKER_DEPTH.set(_WORKER_DEPTH.get() + 1)
                try:
                    async with asyncio.timeout(task.timeout_seconds):
                        value = await self.worker.run(task, context, cancel_event)
                finally:
                    _WORKER_DEPTH.reset(depth_token)
        except asyncio.CancelledError:
            result = _terminal_artifact(
                task,
                TaskStatus.CANCELLED,
                "Worker cancelled",
                started_at=started_at,
            )
        except TimeoutError:
            result = _terminal_artifact(
                task,
                TaskStatus.FAILED,
                f"Worker exceeded {task.timeout_seconds} second timeout",
                started_at=started_at,
                usage=self._take_worker_usage(task.id),
            )
        except Exception as exc:
            result = _terminal_artifact(
                task,
                TaskStatus.FAILED,
                f"Worker failed: {exc}",
                started_at=started_at,
                usage=self._take_worker_usage(task.id),
            )
        else:
            try:
                result = AgentArtifact.model_validate(value)
                if result.task_id != task.id:
                    raise ValueError(
                        "worker artifact task ID does not match scheduled task"
                    )
            except Exception as exc:
                result = _terminal_artifact(
                    task,
                    TaskStatus.INVALID,
                    f"Invalid worker result: {exc}",
                    started_at=started_at,
                )

        duration_ms = (perf_counter() - started_clock) * 1000
        if emitted_start:
            await self._emit(
                StreamEventType.AGENT_PROGRESS,
                task,
                result,
                duration_ms,
            )
        if metrics := current_run_metrics():
            metrics.add_usage(f"worker.{task.id}", result.usage)
        event_type = (
            StreamEventType.AGENT_COMPLETED
            if result.status == TaskStatus.COMPLETED
            else StreamEventType.AGENT_FAILED
        )
        if emitted_start or result.status != TaskStatus.CANCELLED:
            await self._emit(event_type, task, result, duration_ms)
        return result

    async def run(
        self,
        plan: ExecutionPlan,
        context,
        cancel_event: asyncio.Event,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> list[AgentArtifact]:
        """Return artifacts in plan order; nested coordinator calls are denied."""
        if _WORKER_DEPTH.get() > 0:
            raise PermissionError("workers cannot create nested coordinators")

        worker_limit = max(1, min(int(max_workers), HARD_MAX_WORKERS))
        semaphore = asyncio.Semaphore(worker_limit)
        tasks_by_id = {task.id: task for task in plan.tasks}
        pending = set(tasks_by_id)
        results: dict[str, AgentArtifact] = {}
        running: dict[asyncio.Task, str] = {}
        cancel_waiter = asyncio.create_task(cancel_event.wait())

        try:
            while pending or running:
                if cancel_event.is_set():
                    for child in running:
                        child.cancel()
                    completed = await asyncio.gather(*running, return_exceptions=True)
                    for task_id, value in zip(list(running.values()), completed):
                        if isinstance(value, AgentArtifact):
                            results[task_id] = value
                        else:
                            results[task_id] = _terminal_artifact(
                                tasks_by_id[task_id],
                                TaskStatus.CANCELLED,
                                "Worker cancelled",
                            )
                    running.clear()
                    for task_id in pending:
                        results[task_id] = _terminal_artifact(
                            tasks_by_id[task_id], TaskStatus.CANCELLED, "Worker cancelled"
                        )
                    pending.clear()
                    break

                for task_id in list(pending):
                    task = tasks_by_id[task_id]
                    failed_dependencies = [
                        dependency
                        for dependency in task.depends_on
                        if dependency in results
                        and results[dependency].status != TaskStatus.COMPLETED
                    ]
                    if failed_dependencies:
                        message = "Blocked by failed dependency: " + ", ".join(
                            failed_dependencies
                        )
                        results[task_id] = _terminal_artifact(
                            task, TaskStatus.BLOCKED, message
                        )
                        pending.remove(task_id)

                available_slots = worker_limit - len(running)
                if available_slots > 0:
                    ready = [
                        task_id
                        for task_id in pending
                        if all(
                            dependency in results
                            and results[dependency].status == TaskStatus.COMPLETED
                            for dependency in tasks_by_id[task_id].depends_on
                        )
                    ]
                    for task_id in sorted(ready)[:available_slots]:
                        pending.remove(task_id)
                        child = asyncio.create_task(
                            self._run_one(
                                tasks_by_id[task_id], context, cancel_event, semaphore
                            )
                        )
                        running[child] = task_id

                if not running:
                    if pending:
                        for task_id in pending:
                            results[task_id] = _terminal_artifact(
                                tasks_by_id[task_id],
                                TaskStatus.BLOCKED,
                                "Blocked because dependencies could not complete",
                            )
                        pending.clear()
                    continue

                done, _ = await asyncio.wait(
                    [*running, cancel_waiter],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if cancel_waiter in done:
                    continue
                for child in done:
                    task_id = running.pop(child)
                    results[task_id] = await child
        finally:
            cancel_waiter.cancel()
            await asyncio.gather(cancel_waiter, return_exceptions=True)

        return [results[task.id] for task in plan.tasks]
