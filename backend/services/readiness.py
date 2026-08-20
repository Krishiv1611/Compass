"""Fast, secret-safe dependency readiness checks for the web backend."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal

import structlog
from pydantic import BaseModel
from sqlalchemy import text

from backend.config import settings

logger = structlog.get_logger(__name__)
Probe = Callable[[], bool | None]
_REQUIRED_COMPONENTS = frozenset({"database", "checkpointer", "workspace"})
_CACHE_SECONDS = 5.0
_PROBE_EXECUTOR = ThreadPoolExecutor(
    max_workers=6,
    thread_name_prefix="compass-readiness",
)
_active_probe_lock = Lock()
_active_probes: dict[tuple[str, int], tuple[Probe, Future[bool | None]]] = {}


class ComponentStatus(BaseModel):
    status: Literal["ok", "failed", "unavailable"]
    required: bool


class ReadinessReport(BaseModel):
    ready: bool
    components: dict[str, ComponentStatus]


@dataclass(frozen=True, slots=True)
class ReadinessServices:
    database: Probe
    checkpointer: Probe
    workspace: Probe
    memory_store: Probe
    embeddings: Probe
    mcp: Probe


def _component_status(name: str, result: bool | None) -> ComponentStatus:
    required = name in _REQUIRED_COMPONENTS
    if result is True:
        status: Literal["ok", "failed", "unavailable"] = "ok"
    elif result is None:
        status = "unavailable"
    else:
        status = "failed"
    return ComponentStatus(status=status, required=required)


def _submit_probe(name: str, probe: Probe) -> Future[bool | None]:
    key = (name, id(probe))
    with _active_probe_lock:
        active = _active_probes.get(key)
        if active is not None and active[0] is probe and not active[1].done():
            return active[1]
        future = _PROBE_EXECUTOR.submit(probe)
        _active_probes[key] = (probe, future)
        return future


def _release_completed_probe(
    name: str,
    probe: Probe,
    future: Future[bool | None],
) -> None:
    key = (name, id(probe))
    with _active_probe_lock:
        active = _active_probes.get(key)
        if active == (probe, future):
            _active_probes.pop(key, None)


def build_readiness_report(
    services: ReadinessServices,
    *,
    timeout_seconds: float = 1.0,
) -> ReadinessReport:
    """Run all probes concurrently without exposing their exception details."""
    probes = {
        "database": services.database,
        "checkpointer": services.checkpointer,
        "workspace": services.workspace,
        "memory_store": services.memory_store,
        "embeddings": services.embeddings,
        "mcp": services.mcp,
    }
    futures = {
        _submit_probe(name, probe): (name, probe)
        for name, probe in probes.items()
    }
    done, pending = wait(futures, timeout=max(timeout_seconds, 0.001))
    components: dict[str, ComponentStatus] = {}

    for future in done:
        name, probe = futures[future]
        try:
            components[name] = _component_status(name, future.result())
        except Exception as exc:  # noqa: BLE001 - probes are isolated dependency boundaries
            logger.warning(
                "Readiness probe failed",
                component=name,
                error_type=type(exc).__name__,
            )
            components[name] = _component_status(name, False)
        finally:
            _release_completed_probe(name, probe, future)

    for future in pending:
        name, _ = futures[future]
        logger.warning(
            "Readiness probe timed out",
            component=name,
            error_type="TimeoutError",
        )
        components[name] = _component_status(name, False)

    ordered = {name: components[name] for name in probes}
    ready = all(
        component.status == "ok"
        for component in ordered.values()
        if component.required
    )
    return ReadinessReport(ready=ready, components=ordered)


def _database_probe() -> bool:
    from backend.db import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def _checkpointer_probe() -> bool:
    from backend.db import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1 FROM checkpoints LIMIT 1"))
    return True


def _workspace_probe() -> bool:
    root = Path(settings.workspace_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir() or not os.access(root, os.W_OK):
        return False
    with tempfile.NamedTemporaryFile(prefix=".compass-ready-", dir=root):
        pass
    return True


def _memory_probe() -> bool | None:
    from agent.tools.memory_tool import get_memory_store

    return True if get_memory_store() is not None else None


def _embedding_probe() -> bool | None:
    configured = bool(settings.embedding_provider and settings.embedding_model)
    return True if configured else None


def _mcp_probe() -> bool | None:
    if settings.mcp_servers_file is None:
        return None
    return settings.mcp_servers_file.is_file()


def default_readiness_services() -> ReadinessServices:
    return ReadinessServices(
        database=_database_probe,
        checkpointer=_checkpointer_probe,
        workspace=_workspace_probe,
        memory_store=_memory_probe,
        embeddings=_embedding_probe,
        mcp=_mcp_probe,
    )


_cache_lock = Lock()
_default_services = default_readiness_services()
_cached_services: ReadinessServices | None = None
_cached_until = 0.0
_cached_report: ReadinessReport | None = None


def get_readiness_report(
    *,
    services: ReadinessServices | None = None,
    force: bool = False,
) -> ReadinessReport:
    """Return a report cached for five seconds for the selected probe set."""
    global _cached_report, _cached_services, _cached_until
    selected = services or _default_services
    now = time.monotonic()
    with _cache_lock:
        if (
            not force
            and _cached_report is not None
            and _cached_services is selected
            and now < _cached_until
        ):
            return _cached_report
        report = build_readiness_report(services=selected)
        _cached_report = report
        _cached_services = selected
        _cached_until = time.monotonic() + _CACHE_SECONDS
        return report
