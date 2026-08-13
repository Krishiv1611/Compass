import importlib.util
import os
from pathlib import Path

from agent.ui.commands.models import CommandContext, CommandResult, SlashCommand
from agent.runtime.diagnostics import capability_report, route_report, timing_report


async def schedule(_argument: str, _context: CommandContext) -> CommandResult:
    return CommandResult(True, "Scheduling is not available in the TUI yet; no task was created.")


async def doctor(_argument: str, context: CommandContext) -> CommandResult:
    from agent.mcp import MCP_CONFIG_FILE

    mcp_config = Path(MCP_CONFIG_FILE)
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


COMMANDS = [
    SlashCommand("/schedule", (), "Report scheduling availability", schedule),
    SlashCommand("/doctor", (), "Inspect local Compass configuration", doctor),
    SlashCommand("/capabilities", (), "Show effective runtime capabilities", capabilities),
    SlashCommand("/route", (), "Explain the current workflow route", route),
    SlashCommand("/timing", (), "Show timing and cost for the latest run", timing),
]
