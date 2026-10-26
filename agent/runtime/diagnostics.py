"""Redacted capability, route, and timing reports shared by TUI and web."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_COMPLEX_MARKERS = (
    "across the codebase", "across the project", "whole codebase",
    "entire project", "multiple services", "multi-file", "end-to-end",
    "architecture", "architectural", "database migration", "schema migration",
    "authentication system", "authorization system", "redesign", "restructure",
    "productionize", "breaking change", "backward compatibility",
)
_CHAT_PREFIXES = (
    "hi", "hello", "hey", "who are you", "what can you do",
    "thanks", "thank you", "goodbye", "bye",
)


def _values(config: dict[str, Any]) -> dict[str, Any]:
    configurable = config.get("configurable")
    return {**config, **configurable} if isinstance(configurable, dict) else dict(config)


def _first(values: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in values and values[name] is not None:
            return values[name]
    return default


def _explicit_bool(values: dict[str, Any], *names: str) -> bool | None:
    value = _first(values, *names)
    return value if isinstance(value, bool) else None


def _capability(available: bool, available_reason: str, missing_reason: str) -> dict[str, Any]:
    return {"available": available, "reason": available_reason if available else missing_reason}


def capability_report(config: dict[str, Any]) -> dict[str, Any]:
    """Describe effective runtime features without returning credentials or URLs."""

    values = _values(config)
    provider = str(_first(values, "llm_provider", "provider", default="not configured"))
    model = str(_first(values, "model", "model_executor", "model.executor", default="not configured"))
    selected_credentials = _first(values, "credential_providers", default=[])
    has_provider_key = bool(
        _first(values, "has_llm_api_key", default=False)
        or _first(values, "api_key", "llm_api_key")
        or (isinstance(selected_credentials, (list, tuple, set)) and provider in selected_credentials)
    )

    database_explicit = _explicit_bool(values, "database_enabled", "db_enabled")
    database_available = database_explicit if database_explicit is not None else bool(
        _first(values, "database_url", "db_uri", "DB_URI") or os.getenv("DB_URI")
    )

    embeddings_explicit = _explicit_bool(values, "embeddings_enabled")
    embeddings_available = embeddings_explicit if embeddings_explicit is not None else bool(
        _first(values, "embedding_provider")
        and _first(values, "embedding_model")
        and (
            _first(values, "embedding_credential_configured", default=False)
            or _first(values, "embedding_api_key", "api_key")
        )
    )

    mcp_explicit = _explicit_bool(values, "mcp_enabled")
    mcp_servers = _first(values, "mcp_servers", "mcp.connections")
    if mcp_explicit is None and mcp_servers is None:
        mcp_path = Path.cwd() / ".compass" / "mcp_servers.json"
        mcp_available = mcp_path.is_file() and mcp_path.stat().st_size > 2
    else:
        mcp_available = mcp_explicit if mcp_explicit is not None else bool(mcp_servers)

    custom_explicit = _explicit_bool(values, "custom_tools.enabled", "custom_tools_enabled")
    approved_paths = _first(values, "custom_tools.approved_paths", "approved_custom_tool_paths", default=[])
    custom_available = bool(custom_explicit and approved_paths)

    shell_explicit = _explicit_bool(values, "shell_enabled")
    execution_target = str(_first(values, "execution_target", default="tui"))
    shell_available = shell_explicit if shell_explicit is not None else execution_target not in {"web", "worker"}

    if _first(values, "permission_profile"):
        permission_profile = str(values["permission_profile"])
    elif bool(_first(values, "safe_mode", default=False)):
        permission_profile = "review"
    elif bool(_first(values, "fast_mode", default=False)):
        permission_profile = "fast"
    else:
        permission_profile = str(_first(values, "safety.mode", default="standard"))

    capabilities = {
        "database": _capability(database_available, "durable persistence configured", "using process-local persistence"),
        "embeddings": _capability(embeddings_available, "semantic retrieval configured", "embedding provider/model/credential missing"),
        "mcp": _capability(mcp_available, "one or more MCP servers configured", "no MCP servers configured"),
        "custom_tools": _capability(custom_available, "approved custom tool paths configured", "custom tools disabled or no paths approved"),
        "shell": _capability(shell_available, "shell tool available with its approval policy", "shell tool unavailable for this execution target"),
    }
    unavailable = ([] if has_provider_key else ["provider"]) + [
        name for name, value in capabilities.items() if not value["available"]
    ]
    return {
        "provider": {"name": provider, "model": model, "credential_configured": has_provider_key},
        "execution_target": execution_target,
        "permission_profile": permission_profile,
        "capabilities": capabilities,
        "unavailable": unavailable,
    }


def _message_text(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content", ""))
    return str(getattr(message, "content", ""))


def _needs_planning(text: str) -> bool:
    request = " ".join(text.lower().split())
    if any(marker in request for marker in _COMPLEX_MARKERS):
        return True
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    listed_steps = sum(
        line.startswith(("- ", "* "))
        or (len(line) > 2 and line[0].isdigit() and line[1] in ".)")
        for line in lines
    )
    return listed_steps >= 3 or len(request) >= 600 or (
        len(request) >= 250 and request.count(" and ") >= 3
    )


def route_report(state: dict[str, Any]) -> dict[str, Any]:
    """Return the same entry route used by the workflow, with a short explanation."""

    if state.get("active_skill"):
        return {"route": "skill", "entry_node": "skill_manager", "path": ["skill_manager"], "reason": "an active skill was selected"}
    mode = {"normal": "edit", "fast": "ask"}.get(str(state.get("mode", "edit")), str(state.get("mode", "edit")))
    if mode in {"plan", "goal"}:
        return {"route": "context-planner", "entry_node": "planner", "path": ["planner", "executor"], "reason": f"{mode} mode requires an explicit plan"}
    messages = state.get("messages") or []
    if not messages:
        return {"route": "executor", "entry_node": "executor", "path": ["executor"], "reason": "no user message was available"}
    text = _message_text(messages[-1]).lower()
    if len(text) < 50 and any(text.strip().startswith(prefix) for prefix in _CHAT_PREFIXES):
        return {"route": "direct-chat", "entry_node": "direct_chat", "path": ["direct_chat"], "reason": "short conversational request"}
    if mode == "edit" and _needs_planning(text):
        return {"route": "context-planner", "entry_node": "planner", "path": ["planner", "executor"], "reason": "cross-cutting edit benefits from planning"}
    return {"route": "executor", "entry_node": "executor", "path": ["executor"], "reason": "request can enter the executor directly"}


def _metrics_dict(metrics: Any) -> dict[str, Any]:
    if hasattr(metrics, "model_dump"):
        return metrics.model_dump(mode="json")
    if isinstance(metrics, dict):
        nested = metrics.get("metrics")
        return nested if isinstance(nested, dict) else metrics
    return {}


def timing_report(metrics: Any) -> dict[str, Any]:
    """Group safe aggregate spans into user-facing runtime categories."""

    values = _metrics_dict(metrics)
    categories = {
        "provider_wait_ms": 0.0,
        "local_compute_ms": 0.0,
        "tool_time_ms": 0.0,
        "approval_wait_ms": 0.0,
        "persistence_ms": 0.0,
    }
    stages = []
    for name, raw_span in (values.get("spans") or {}).items():
        span = raw_span if isinstance(raw_span, dict) else {}
        duration = float(span.get("duration_ms") or 0)
        lowered = name.lower()
        if lowered.endswith(".model") or "provider" in lowered:
            category = "provider_wait_ms"
        elif "tool" in lowered:
            category = "tool_time_ms"
        elif "approval" in lowered or ".wait" in lowered:
            category = "approval_wait_ms"
        elif any(marker in lowered for marker in ("persist", "database", "checkpoint", "db.")):
            category = "persistence_ms"
        else:
            category = "local_compute_ms"
        categories[category] = round(categories[category] + duration, 3)
        stages.append({
            "name": name,
            "duration_ms": duration,
            "calls": int(span.get("calls") or 0),
            "errors": int(span.get("errors") or 0),
            "category": category,
        })

    calls = sum(int(value or 0) for value in (values.get("calls_by_node") or {}).values())
    estimated_cost = values.get("estimated_cost_usd")
    cost_status = "unavailable" if estimated_cost is None else ("free" if estimated_cost == 0 else "estimated")
    tags = values.get("tags") if isinstance(values.get("tags"), dict) else {}
    cache = {
        name.removesuffix("_cache"): str(value)
        for name, value in tags.items()
        if name.endswith("_cache")
    }
    return {
        "provider": tags.get("provider"),
        "model": tags.get("model"),
        "calls": calls,
        "tokens": {
            "input": int(values.get("total_input_tokens") or values.get("prompt_tokens") or 0),
            "output": int(values.get("total_output_tokens") or values.get("completion_tokens") or 0),
            "total": int(values.get("total_tokens") or 0),
        },
        "cost": {"status": cost_status, "estimated_usd": estimated_cost},
        "categories": categories,
        "stages": stages,
        "cache": cache,
    }
