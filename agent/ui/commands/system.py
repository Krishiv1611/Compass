import importlib.util
import os
from pathlib import Path

from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand
from agent.runtime.diagnostics import capability_report, route_report, timing_report


async def schedule(_argument: str, _context: CommandContext) -> CommandResult:
    return CommandResult(
        True,
        "Scheduling is not available; no task was created.",
        status="unavailable",
    )


async def grill_me(_argument: str, _context: CommandContext) -> CommandResult:
    return CommandResult(
        True,
        "Plan mode enabled. Describe the decision you want to plan next.",
        {"mode": "plan"},
        "performed",
    )


async def doctor(_argument: str, context: CommandContext) -> CommandResult:
    try:
        from agent.mcp import MCP_CONFIG_FILE

        mcp_config = Path(MCP_CONFIG_FILE)
    except ImportError:
        mcp_config = Path.cwd() / ".compass" / "mcp_servers.json"
    checks = [
        f"agent imports: {'ok' if importlib.util.find_spec('agent') else 'missing'}",
        f"workflow: {'active' if context.workflow else 'not active'}",
        f"provider credential: {'configured' if context.settings.get('has_llm_api_key') else 'missing'}",
        f"MCP config: {'found' if mcp_config.exists() else 'not found'} ({mcp_config})",
        f"workspace writable: {'yes' if os.access(Path.cwd(), os.W_OK) else 'no'}",
        f"web URL: {context.settings.get('web_url') or 'http://localhost:5173'}",
    ]
    return CommandResult(True, "Doctor:\n" + "\n".join(checks))


async def capabilities(_argument: str, context: CommandContext) -> CommandResult:
    report = capability_report({**context.run_config, **context.settings})
    lines = [
        f"Provider: {report['provider']['name']} / {report['provider']['model']} "
        f"({'ready' if report['provider']['credential_configured'] else 'credential missing'})",
        f"Target: {report['execution_target']} · permissions: {report['permission_profile']}",
    ]
    lines.extend(
        f"{name.replace('_', ' ').title()}: {'available' if value['available'] else 'unavailable'} — {value['reason']}"
        for name, value in report["capabilities"].items()
    )
    return CommandResult(True, "Capabilities:\n" + "\n".join(lines))


async def route(_argument: str, context: CommandContext) -> CommandResult:
    state: dict = {}
    if context.workflow and context.run_config:
        try:
            snapshot = await context.workflow.aget_state(context.run_config)
            if isinstance(getattr(snapshot, "values", None), dict):
                state = snapshot.values
        except Exception:
            state = {}
    state.setdefault("mode", context.settings.get("mode", "edit"))
    report = route_report(state)
    return CommandResult(
        True,
        "Route:\n"
        f"{report['route']} · {' → '.join(report['path'])}\n"
        f"Reason: {report['reason']}",
    )


async def timing(_argument: str, context: CommandContext) -> CommandResult:
    report = timing_report(context.settings.get("last_run_metrics") or {})
    categories = report["categories"]
    cost = report["cost"]
    cost_text = "cost unavailable" if cost["status"] == "unavailable" else (
        "free" if cost["status"] == "free" else f"${cost['estimated_usd']:.6f} estimated"
    )
    return CommandResult(
        True,
        "Timing (latest run):\n"
        f"Provider wait: {categories['provider_wait_ms']:.1f} ms\n"
        f"Local compute: {categories['local_compute_ms']:.1f} ms\n"
        f"Tools: {categories['tool_time_ms']:.1f} ms\n"
        f"Approval wait: {categories['approval_wait_ms']:.1f} ms\n"
        f"Persistence: {categories['persistence_ms']:.1f} ms\n"
        f"Model calls: {report['calls']} · tokens: {report['tokens']['total']} · {cost_text}",
    )


async def hooks(_argument: str, context: CommandContext) -> CommandResult:
    from agent.hooks import load_verification_hooks

    configuration = load_verification_hooks(context.workspace or ".")
    lines = [
        f"{hook.name}: {hook.command} · cwd={hook.cwd} · "
        f"timeout={hook.timeout_seconds}s · run_on={','.join(hook.run_on)}"
        for hook in configuration.hooks
    ]
    lines.extend(f"Invalid: {error}" for error in configuration.errors)
    if not lines:
        lines.append("No hooks configured in .compass/config.toml.")
    return CommandResult(True, "Verification hooks (inspection only):\n" + "\n".join(lines))


async def agents(_argument: str, context: CommandContext) -> CommandResult:
    from agent.runtime.artifacts import RunArtifact
    from agent.ui.event_renderer import workers_table

    configurable = context.run_config.get("configurable", {})
    payload = configurable.get("last_run_artifact", {})
    try:
        artifact = RunArtifact.model_validate(payload)
    except Exception:
        artifact = RunArtifact()
    return CommandResult(True, workers_table(artifact))


COMMANDS = [
    SlashCommand("/schedule", (), "Report scheduling availability", schedule),
    SlashCommand("/grill-me", (), "Enter Plan mode", grill_me),
    SlashCommand("/doctor", (), "Inspect local Compass configuration", doctor),
    SlashCommand("/capabilities", (), "Show effective runtime capabilities", capabilities),
    SlashCommand("/route", (), "Explain the current workflow route", route),
    SlashCommand("/timing", (), "Show timing and cost for the latest run", timing),
    SlashCommand("/hooks", (), "Inspect configured post-edit hooks", hooks),
    SlashCommand("/agents", (), "Show worker tasks from the latest run", agents),
]
