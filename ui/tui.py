"""
Compass TUI — Beautiful terminal interface for the Compass AI coding agent.

Uses Click for CLI framework and Rich for stunning terminal rendering.
Provides an interactive REPL with styled output, tool call visualization,
and slash command support.
"""

import json
import os
import sys
import time
import uuid

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.live import Live
from rich.spinner import Spinner
from rich.columns import Columns
from rich.align import Align
from rich import box
from langchain_core.messages import AIMessageChunk, AIMessage, ToolMessage

# ─── Theme ──────────────────────────────────────────────────────────────────────

COMPASS_THEME = Theme({
    "compass.prompt":     "bold cyan",
    "compass.thinking":   "dim italic bright_magenta",
    "compass.tool_name":  "bold magenta",
    "compass.tool_args":  "dim white",
    "compass.success":    "bold green",
    "compass.error":      "bold red",
    "compass.info":       "bold blue",
    "compass.border":     "bright_black",
    "compass.dim":        "dim white",
    "compass.accent":     "bold bright_cyan",
    "compass.warn":       "bold yellow",
    "compass.highlight":  "bold bright_white on rgb(40,40,60)",
})

# ─── ASCII Art ──────────────────────────────────────────────────────────────────

COMPASS_BANNER = r"""[bold bright_cyan]
     ██████╗ ██████╗ ███╗   ███╗██████╗  █████╗ ███████╗███████╗
    ██╔════╝██╔═══██╗████╗ ████║██╔══██╗██╔══██╗██╔════╝██╔════╝
    ██║     ██║   ██║██╔████╔██║██████╔╝███████║███████╗███████╗
    ██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██╔══██║╚════██║╚════██║
    ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ██║  ██║███████║███████║
     ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝[/]"""

COMPASS_TAGLINE = "[dim bright_white]🧭  AI Coding Agent — powered by LangGraph[/]"


SLASH_COMMANDS = {
    "/help":     "Show available commands",
    "/exit":     "Exit Compass",
    "/clear":    "Clear the terminal screen",
    "/model":    "Show current model info",
    "/tools":    "List all available tools",
    "/history":  "Show conversation message count",
    "/sessions": "List recent sessions",
    "/new":      "Start a new session",
    "/resume":   "Resume a session by ID prefix",
    "/rename":   "Rename the current session",
    "/index":    "Index the codebase for semantic search",
    "/compact":  "Summarize and compact context (planned)",
    "/config":   "View or update settings",
}



TOOL_REGISTRY = [
    ("read_file",       "📄", "Read contents of a file"),
    ("write_to_file",   "✏️",  "Write content to a file"),
    ("edit_file",       "🔧", "Edit specific sections of a file"),
    ("list_dir",        "📁", "List directory contents"),
    ("find_files",      "🔍", "Find files matching a pattern"),
    ("grep_search",     "🔎", "Search file contents with regex"),
    ("codebase_search", "🧬", "Semantic search across the codebase"),
    ("web_search",      "🌐", "Search the web"),
    ("shell_execute",   "💻", "Execute a shell command"),
    ("memory",          "🧠", "Store/retrieve key-value memories"),
    ("todo",            "📋", "Manage a task list"),
]


# ─── Console ────────────────────────────────────────────────────────────────────

class CompassConsole:
    """Rich-powered console with Compass theming and helper methods."""

    def __init__(self):
        self.console = Console(theme=COMPASS_THEME, highlight=False)
        self.turn_count = 0
        self.session_start = time.time()

    # ── Welcome & Goodbye ───────────────────────────────────────────────────

    def print_welcome(self, model_name: str = "poolside/laguna-m.1"):
        """Print the animated welcome banner."""
        self.console.print()

        banner_content = Text.from_markup(COMPASS_BANNER)
        tagline = Text.from_markup(COMPASS_TAGLINE)

        inner = Text()
        inner.append_text(banner_content)
        inner.append("\n\n")
        inner.append_text(tagline)
        inner.append("\n")

        # Model info line
        model_line = Text()
        model_line.append("    ⚙  Model: ", style="dim")
        model_line.append(model_name, style="bold bright_white")
        inner.append_text(model_line)
        inner.append("\n")

        # Help hint
        help_line = Text()
        help_line.append("    ⌨  Type ", style="dim")
        help_line.append("/help", style="bold cyan")
        help_line.append(" for commands", style="dim")
        inner.append_text(help_line)

        panel = Panel(
            Align.center(inner),
            border_style="bright_cyan",
            box=box.DOUBLE_EDGE,
            padding=(1, 2),
        )
        self.console.print(panel)
        self.console.print()

    def print_goodbye(self):
        """Print session summary and farewell."""
        elapsed = time.time() - self.session_start
        mins, secs = divmod(int(elapsed), 60)

        stats = Text()
        stats.append("  📊 Session: ", style="dim")
        stats.append(f"{self.turn_count} turns", style="bold bright_white")
        stats.append(f" · {mins}m {secs}s", style="dim")

        farewell = Text()
        farewell.append("\n  👋 ", style="")
        farewell.append("See you next time!", style="bold bright_cyan")
        farewell.append("\n")
        farewell.append_text(stats)

        panel = Panel(
            farewell,
            border_style="bright_cyan",
            box=box.ROUNDED,
            title="[bold bright_cyan]Compass[/]",
            title_align="left",
            padding=(0, 1),
        )
        self.console.print()
        self.console.print(panel)
        self.console.print()

    # ── Tool Calls ──────────────────────────────────────────────────────────

    def print_tool_call(self, name: str, args: dict):
        """Display a tool invocation with styled arguments."""
        # Tool header
        header = Text()
        header.append("  ⚡ ", style="bold yellow")
        header.append(name, style="compass.tool_name")

        self.console.print(header)

        # Arguments (compact JSON display)
        if args:
            for key, value in args.items():
                arg_line = Text()
                arg_line.append("  │  ", style="bright_black")
                arg_line.append(f"{key}: ", style="dim cyan")

                # Truncate long values
                str_val = str(value)
                if len(str_val) > 120:
                    str_val = str_val[:117] + "..."
                arg_line.append(str_val, style="compass.tool_args")

                self.console.print(arg_line)

    def print_tool_result(self, name: str, result: str, duration: float = 0.0):
        """Display a tool's result with success indicator."""
        # Truncate very long results for display
        display_result = result
        if len(result) > 500:
            display_result = result[:497] + "..."
            lines_info = f" ({len(result)} chars)"
        else:
            lines_info = ""

        # Status line
        status = Text()
        status.append("  ✔ ", style="compass.success")
        status.append(name, style="dim bright_white")
        status.append(" completed", style="dim")
        if duration > 0:
            status.append(f" ({duration:.1f}s)", style="dim")
        if lines_info:
            status.append(lines_info, style="dim")
        self.console.print(status)

        # Result content (indented, dimmed)
        if display_result.strip():
            for line in display_result.strip().split("\n")[:15]:
                result_line = Text()
                result_line.append("  ╰─ ", style="bright_black")
                result_line.append(line, style="dim white")
                self.console.print(result_line)
            if display_result.strip().count("\n") > 15:
                self.console.print(
                    Text("  ╰─ ... (truncated)", style="dim bright_black")
                )

    def print_tool_error(self, name: str, error: str):
        """Display a tool error."""
        status = Text()
        status.append("  ✘ ", style="compass.error")
        status.append(name, style="dim bright_white")
        status.append(" failed", style="compass.error")
        self.console.print(status)

        err_line = Text()
        err_line.append("  ╰─ ", style="bright_black")
        err_line.append(error[:200], style="red")
        self.console.print(err_line)

    # ── Agent Response ──────────────────────────────────────────────────────

    def print_response(self, content: str, turn: int = 0):
        """Render the agent's final response in a styled panel with Markdown."""
        self.turn_count = turn

        # Build subtitle
        subtitle_parts = []
        if turn > 0:
            subtitle_parts.append(f"turn {turn}")
        subtitle = " · ".join(subtitle_parts)

        md = Markdown(content)
        panel = Panel(
            md,
            border_style="bright_cyan",
            box=box.ROUNDED,
            title="[bold bright_cyan]🧭 Compass[/]",
            title_align="left",
            subtitle=f"[dim]{subtitle}[/]" if subtitle else None,
            subtitle_align="right",
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)

    # ── Error Display ───────────────────────────────────────────────────────

    def print_error(self, message: str):
        """Display an error message in a styled panel."""
        error_text = Text()
        error_text.append("  ❌ ", style="")
        error_text.append(message, style="compass.error")

        panel = Panel(
            error_text,
            border_style="red",
            box=box.ROUNDED,
            title="[bold red]Error[/]",
            title_align="left",
            padding=(0, 1),
        )
        self.console.print(panel)

    # ── Help / Info ─────────────────────────────────────────────────────────

    def print_help(self):
        """Display the slash commands reference table."""
        table = Table(
            title="[bold bright_cyan]🧭 Compass Commands[/]",
            box=box.SIMPLE_HEAVY,
            border_style="bright_black",
            title_style="bold",
            header_style="bold bright_cyan",
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column("Command", style="bold cyan", min_width=12)
        table.add_column("Description", style="bright_white")

        for cmd, desc in SLASH_COMMANDS.items():
            table.add_row(cmd, desc)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def print_tools(self):
        """Display the available tools in a styled table."""
        table = Table(
            title="[bold bright_cyan]🛠  Available Tools[/]",
            box=box.SIMPLE_HEAVY,
            border_style="bright_black",
            header_style="bold bright_cyan",
            padding=(0, 2),
            show_edge=False,
        )
        table.add_column("", min_width=2)  # icon
        table.add_column("Tool", style="bold magenta", min_width=15)
        table.add_column("Description", style="bright_white")

        for name, icon, desc in TOOL_REGISTRY:
            table.add_row(icon, name, desc)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def print_model_info(self, model_name: str = "poolside/laguna-m.1"):
        """Display current model configuration."""
        info = Text()
        info.append("\n  ⚙  ", style="")
        info.append("Model: ", style="dim")
        info.append(model_name, style="bold bright_white")
        info.append("\n  🔗 ", style="")
        info.append("Provider: ", style="dim")
        info.append("OpenRouter", style="bold bright_white")
        info.append("\n  🧩 ", style="")
        info.append("Framework: ", style="dim")
        info.append("LangGraph + LangChain", style="bold bright_white")
        info.append("\n")

        panel = Panel(
            info,
            border_style="bright_cyan",
            box=box.ROUNDED,
            title="[bold bright_cyan]Model Info[/]",
            title_align="left",
            padding=(0, 1),
        )
        self.console.print(panel)

    def print_history_summary(self, message_count: int):
        """Display conversation history info."""
        info = Text()
        info.append("  💬 ", style="")
        info.append(f"{message_count} messages", style="bold bright_white")
        info.append(" in this session", style="dim")
        self.console.print(info)
        self.console.print()

    # ── Spinner ─────────────────────────────────────────────────────────────

    def thinking_spinner(self):
        """Return a Live context manager with a thinking spinner."""
        spinner_text = Text()
        spinner_text.append("  ", style="")
        spinner_text.append("Thinking", style="compass.thinking")
        spinner_text.append("...", style="compass.thinking")

        return Live(
            Spinner("dots", text=spinner_text, style="bright_magenta"),
            console=self.console,
            refresh_per_second=12,
            transient=True,
        )

    # ── Separator ───────────────────────────────────────────────────────────

    def print_tool_separator(self, label: str = "tool calls"):
        """Print a subtle rule separator for tool call groups."""
        self.console.print()
        self.console.print(
            Rule(f"[dim bright_black]{label}[/]", style="bright_black", align="left")
        )

    def print_separator(self):
        """Print a subtle divider."""
        self.console.print(Rule(style="bright_black"))


# ─── REPL ────────────────────────────────────────────────────────────────────────

def _format_prompt() -> str:
    """Build the styled REPL prompt string."""
    return click.style("🧭 › ", fg="cyan", bold=True)


def _process_stream_event(compass: CompassConsole, node_name: str, node_output: dict, skip_response: bool = False):
    """
    Process a single streaming event from workflow.stream(stream_mode='updates').

    Each event is {node_name: {state_updates}}.
    Handles all four agent nodes:
      - 'planner'       → Show the plan in a styled panel
      - 'executor'      → Tool calls + final response
      - 'loop_recovery' → Warning panel with recovery guidance
      - 'summary_node'  → Subtle compaction notice
      - 'tools'         → ToolMessage results
    """
    messages = node_output.get("messages", [])

    # ── Planner Agent ────────────────────────────────────────────────────────
    if node_name == "planner":
        plan = node_output.get("plan", "")
        # The planner also emits an AIMessage — show it as the plan
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.content:
                plan_content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if plan_content.strip():
                    md = Markdown(plan_content)
                    panel = Panel(
                        md,
                        border_style="bright_magenta",
                        box=box.ROUNDED,
                        title="[bold bright_magenta]📋 Plan[/]",
                        title_align="left",
                        subtitle="[dim]planner agent[/]",
                        subtitle_align="right",
                        padding=(1, 2),
                    )
                    compass.console.print()
                    compass.console.print(panel)
        return

    # ── Loop Recovery Agent ──────────────────────────────────────────────────
    if node_name == "loop_recovery":
        guidance = node_output.get("recovery_guidance", "")
        loop_count = node_output.get("loop_count", 0)

        if node_output.get("is_done", False):
            # Hard break — show final message
            for msg in messages:
                if isinstance(msg, AIMessage) and msg.content:
                    content = msg.content if isinstance(msg.content, str) else str(msg.content)
                    compass.print_response(content, turn=node_output.get("turn_count", 0))
            return

        if guidance:
            warning_text = Text()
            warning_text.append("\n  ⚠️  Loop Detected", style="bold yellow")
            warning_text.append(f" — recovery attempt {loop_count}/3\n\n", style="dim")
            warning_text.append(f"  {guidance}\n", style="bright_white")

            panel = Panel(
                warning_text,
                border_style="yellow",
                box=box.ROUNDED,
                title="[bold yellow]🔄 Loop Recovery[/]",
                title_align="left",
                padding=(0, 1),
            )
            compass.console.print()
            compass.console.print(panel)
        return

    # ── Summary Node ─────────────────────────────────────────────────────────
    if node_name == "summary_node":
        compass.console.print(
            Text("  📝 Context compacted by summarizer agent.", style="dim bright_white")
        )
        return

    # ── Executor Agent + Tools Node ──────────────────────────────────────────
    for msg in messages:
        if isinstance(msg, AIMessage):
            # Display tool calls the model wants to make
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                compass.print_tool_separator()
                for tc in msg.tool_calls:
                    compass.print_tool_call(tc["name"], tc.get("args", {}))

            # Display the final text response
            if not skip_response and msg.content and isinstance(msg.content, str) and msg.content.strip():
                turn = node_output.get("turn_count", 0)
                compass.print_response(msg.content, turn=turn)

        elif isinstance(msg, ToolMessage):
            result = msg.content if isinstance(msg.content, str) else str(msg.content)
            tool_name = getattr(msg, "name", "tool")

            # Check if the tool returned an error
            status = getattr(msg, "status", "success")
            if status == "error" or result.startswith("Error"):
                compass.print_tool_error(tool_name, result)
            else:
                compass.print_tool_result(tool_name, result)



def _handle_slash_command(
    compass: CompassConsole,
    command: str,
    messages: list,
    session_ctx: dict | None = None,
) -> bool | str:
    """
    Handle a slash command.
    Returns:
      - False → exit the REPL
      - True  → continue with the current session
      - str   → switch to a different session (returns thread_id)
    """
    from sessions import SessionManager

    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/exit":
        return False

    elif cmd == "/help":
        compass.print_help()

    elif cmd == "/clear":
        click.clear()
        compass.print_welcome()

    elif cmd == "/model":
        compass.print_model_info()

    elif cmd == "/tools":
        compass.print_tools()

    elif cmd == "/history":
        compass.print_history_summary(len(messages))

    elif cmd == "/sessions":
        sm = SessionManager()
        sessions = sm.list_sessions(limit=10)
        if not sessions:
            compass.console.print(Text("  No sessions found.", style="dim"))
            compass.console.print()
        else:
            table = Table(
                title="[bold bright_cyan]📌 Recent Sessions[/]",
                box=box.SIMPLE_HEAVY,
                border_style="bright_black",
                header_style="bold bright_cyan",
                padding=(0, 2),
                show_edge=False,
            )
            table.add_column("ID", style="bold cyan", min_width=10)
            table.add_column("Name", style="bright_white", min_width=20)
            table.add_column("Last Active", style="dim", min_width=16)
            table.add_column("Turns", style="bold", justify="right")

            current_tid = session_ctx["thread_id"] if session_ctx else ""
            for s in sessions:
                tid_display = s["thread_id"][:10]
                if s["thread_id"] == current_tid:
                    tid_display += " ◄"
                name = s.get("name", "") or "(unnamed)"
                age = sm.session_age_minutes(s)
                if age < 60:
                    last_active = f"{int(age)}m ago"
                elif age < 1440:
                    last_active = f"{int(age / 60)}h ago"
                else:
                    last_active = f"{int(age / 1440)}d ago"
                turns = str(s.get("turn_count", 0))
                table.add_row(tid_display, name, last_active, turns)

            compass.console.print()
            compass.console.print(table)
            compass.console.print()

    elif cmd == "/new":
        sm = SessionManager()
        new_sess = sm.create_session()
        compass.console.print(
            Text(f"  📌 New session: {new_sess['thread_id'][:10]}...", style="compass.success")
        )
        compass.console.print()
        return new_sess["thread_id"]  # signal to switch session

    elif cmd == "/resume":
        if not arg:
            compass.console.print(
                Text("  Usage: /resume <session_id_prefix>", style="compass.warn")
            )
            compass.console.print()
        else:
            sm = SessionManager()
            sess = sm.get_session(arg)
            if sess:
                compass.console.print(
                    Text(f"  📌 Resuming session: {sess['thread_id'][:10]}... "
                         f"({sess.get('name') or 'unnamed'})",
                         style="compass.success")
                )
                compass.console.print()
                return sess["thread_id"]  # signal to switch session
            else:
                compass.console.print(
                    Text(f"  No session found matching '{arg}'.", style="compass.error")
                )
                compass.console.print()

    elif cmd == "/rename":
        if not arg:
            compass.console.print(
                Text("  Usage: /rename <new name>", style="compass.warn")
            )
            compass.console.print()
        elif session_ctx:
            sm = SessionManager()
            if sm.rename_session(session_ctx["thread_id"], arg):
                session_ctx["name"] = arg.strip()
                compass.console.print(
                    Text(f"  ✔ Session renamed to: {arg.strip()}", style="compass.success")
                )
            else:
                compass.console.print(
                    Text("  Error: Could not rename session.", style="compass.error")
                )
            compass.console.print()
        else:
            compass.console.print(
                Text("  No active session to rename.", style="compass.warn")
            )
            compass.console.print()

    elif cmd == "/compact":
        compass.console.print(
            Text("  ⏳ Context compaction is not yet implemented.", style="compass.warn")
        )
        compass.console.print()

    elif cmd == "/index":
        from rag.indexer import index_workspace

        workspace = os.getcwd()
        compass.console.print(
            Text(f"  🧬 Indexing workspace: {workspace}", style="compass.info")
        )
        compass.console.print()

        try:
            with compass.thinking_spinner():
                result = index_workspace(workspace)

            # Display results in a styled panel
            stats_text = Text()
            stats_text.append("\n  📊 Indexing Results\n\n", style="bold bright_cyan")
            stats_text.append("  Files scanned:  ", style="dim")
            stats_text.append(f"{result.files_scanned}\n", style="bold bright_white")
            stats_text.append("  Files indexed:  ", style="dim")
            stats_text.append(f"{result.files_indexed}", style="bold green")
            stats_text.append(f"  ({result.chunks_added} chunks)\n", style="dim")
            stats_text.append("  Files skipped:  ", style="dim")
            stats_text.append(f"{result.files_skipped}", style="bold bright_white")
            stats_text.append("  (unchanged)\n", style="dim")
            if result.files_removed > 0:
                stats_text.append("  Files removed:  ", style="dim")
                stats_text.append(f"{result.files_removed}", style="bold yellow")
                stats_text.append(f"  ({result.chunks_removed} chunks)\n", style="dim")
            stats_text.append("  Elapsed:        ", style="dim")
            stats_text.append(f"{result.elapsed_seconds:.1f}s\n", style="bold bright_white")

            if result.errors:
                stats_text.append(f"\n  ⚠  {len(result.errors)} error(s):\n", style="compass.warn")
                for err in result.errors[:5]:
                    stats_text.append(f"     • {err}\n", style="dim red")

            panel = Panel(
                stats_text,
                border_style="bright_cyan",
                box=box.ROUNDED,
                title="[bold bright_cyan]🧬 Codebase Index[/]",
                title_align="left",
                padding=(0, 1),
            )
            compass.console.print(panel)
            compass.console.print()
        except Exception as e:
            compass.print_error(f"Indexing failed: {e}")

    elif cmd == "/config":
        from config.settings import settings

        if not arg:
            # Display current settings
            table = Table(
                title="[bold bright_cyan]⚙️  Settings[/]",
                box=box.SIMPLE_HEAVY,
                border_style="bright_black",
                header_style="bold bright_cyan",
                padding=(0, 2),
                show_edge=False,
            )
            table.add_column("Setting", style="bold cyan")
            table.add_column("Value", style="bright_white")

            for k, v in settings.get_all().items():
                table.add_row(k, str(v))

            compass.console.print()
            compass.console.print(table)
            compass.console.print(
                Text("  Use /config <key> <value> to update.", style="dim")
            )
            compass.console.print()
        else:
            # Update setting
            parts = arg.split(maxsplit=1)
            if len(parts) == 2:
                k, v = parts
                settings.set(k, v)
                compass.console.print(
                    Text(f"  ✔ Setting '{k}' updated to '{v}'.", style="compass.success")
                )
                compass.console.print()
            else:
                compass.console.print(
                    Text("  Usage: /config <key> <value>", style="compass.warn")
                )
                compass.console.print()

    else:
        compass.console.print(
            Text(f"  Unknown command: {cmd}. Type /help for available commands.",
                 style="compass.warn")
        )
        compass.console.print()

    return True


async def compass_repl(resume_thread_id: str | None = None):
    """
    Launch the Compass interactive REPL.

    This is the main entry point for the terminal UI. It:
    - Displays the welcome banner
    - Handles session resume (if resume_thread_id provided or recent session found)
    - Accepts user input with a styled prompt
    - Routes slash commands
    - Streams the LangGraph workflow for real-time display
    - Renders tool calls and agent responses with Rich
    """
    from sessions import SessionManager

    compass = CompassConsole()
    compass.print_welcome()

    # Lazy import to avoid import-time side effects (DB connection, etc.)
    try:
        from graph.workflow import get_workflow
        workflow = await get_workflow()
    except Exception as e:
        compass.print_error(f"Failed to load agent workflow: {e}")
        compass.console.print(
            Text("  Tip: Make sure your .env file has DB_URI set.", style="dim"),
        )
        sys.exit(1)

    sm = SessionManager()

    # ── Resolve session ─────────────────────────────────────────────────────
    session_ctx = None
    is_resumed = False

    if resume_thread_id:
        # Explicit resume from CLI flag
        session_ctx = sm.get_session(resume_thread_id)
        if session_ctx:
            is_resumed = True
        else:
            # thread_id doesn't exist in sessions.json — create a record for it
            session_ctx = sm.create_session()
            session_ctx["thread_id"] = resume_thread_id
            sm._save()
    else:
        # Check for a recent session to offer resume
        last = sm.get_last_session()
        if last and sm.session_age_minutes(last) < 60:
            compass.console.print(
                Text(f"  📌 Recent session found: "
                     f"{last['thread_id'][:10]}... "
                     f"({last.get('name') or 'unnamed'}, "
                     f"{last.get('turn_count', 0)} turns)",
                     style="dim bright_white")
            )
            try:
                answer = click.prompt(
                    click.style("     Resume? (y/N)", fg="cyan"),
                    prompt_suffix=" ",
                    default="n",
                    show_default=False,
                ).strip().lower()
            except (KeyboardInterrupt, EOFError):
                answer = "n"

            if answer in ("y", "yes"):
                session_ctx = last
                is_resumed = True

    if session_ctx is None:
        session_ctx = sm.create_session()

    thread_id = session_ctx["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Show session status
    status_style = "compass.success" if is_resumed else "compass.info"
    status_label = "resumed" if is_resumed else "new"
    session_name = session_ctx.get("name", "")
    name_display = f" — {session_name}" if session_name else ""
    compass.console.print(
        Text(f"  📌 Session: {thread_id[:10]}...{name_display} ({status_label})",
             style=status_style)
    )
    compass.console.print()

    messages = []
    turn_count = session_ctx.get("turn_count", 0)
    prompt_str = _format_prompt()

    resume_cmd = None

    while True:
        try:
            if not resume_cmd:
                # Get user input
                user_input = click.prompt(
                    prompt_str,
                    prompt_suffix="",
                    default="",
                    show_default=False,
                ).strip()

                if not user_input:
                    continue

                # Slash commands
                if user_input.startswith("/"):
                    result = _handle_slash_command(
                        compass, user_input, messages, session_ctx=session_ctx
                    )
                    if result is False:
                        compass.print_goodbye()
                        break
                    elif isinstance(result, str):
                        # Switch to a different session
                        thread_id = result
                        config = {"configurable": {"thread_id": thread_id}}
                        session_ctx = sm.get_session(thread_id)
                        if session_ctx is None:
                            session_ctx = {"thread_id": thread_id, "turn_count": 0}
                        messages = []
                        turn_count = session_ctx.get("turn_count", 0)
                    continue

                # Add user message to history
                messages.append({"role": "user", "content": user_input})
                input_payload = {"messages": messages}
            else:
                input_payload = resume_cmd
                resume_cmd = None

            # Stream the agent response in real-time
            compass.console.print()
            try:
                live_panel = None
                current_text = ""

                async for event_type, payload in workflow.astream( # type: ignore
                    input_payload, # type: ignore
                    config=config, # type: ignore
                    stream_mode=["messages", "updates"],
                ):
                    if event_type == "messages":
                        chunk, _ = payload
                        if isinstance(chunk, AIMessageChunk) and getattr(chunk, "content", None) and not getattr(chunk, "tool_calls", None):
                            if not live_panel:
                                live_panel = Live(console=compass.console, refresh_per_second=15, transient=False)
                                live_panel.start()
                            content_str = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                            current_text += content_str
                            md = Markdown(current_text)
                            panel = Panel(
                                md,
                                border_style="bright_cyan",
                                box=box.ROUNDED,
                                title="[bold bright_cyan]🧭 Compass[/]",
                                title_align="left",
                                subtitle=f"[dim]turn {turn_count + 1}[/]",
                                subtitle_align="right",
                                padding=(1, 2),
                            )
                            live_panel.update(panel)
                    elif event_type == "updates":
                        if live_panel:
                            live_panel.stop()
                            live_panel = None

                        # Each payload is {node_name: {state_updates}}
                        if isinstance(payload, dict):
                            for node_name, node_output in payload.items():
                                _process_stream_event(compass, node_name, node_output, skip_response=bool(current_text))
                            
                        # If a tool call or non-message update happened, reset text so we can stream the next message
                        current_text = ""

                if live_panel:
                    live_panel.stop()

                # ── Handle Interrupts ───────────────────────────────────────
                state_info = workflow.get_state(config)
                if state_info.next and "check_safety" in state_info.next:
                    interrupt_data = None
                    for task in state_info.tasks:
                        if task.name == "check_safety" and task.interrupts:
                            interrupt_data = task.interrupts[0].value
                            break
                            
                    if interrupt_data and interrupt_data.get("reason") == "approval_required":
                        from rich.panel import Panel
                        from rich.text import Text
                        
                        risky_calls = interrupt_data.get("tool_calls", [])
                        warning_text = Text()
                        warning_text.append("\n  ⚠️  Approval Required\n\n", style="bold red")
                        for tc in risky_calls:
                            warning_text.append(f"  • {tc['name']}\n", style="bold yellow")
                            for k, v in tc.get("args", {}).items():
                                warning_text.append(f"      {k}: {v}\n", style="dim white")
                                
                        compass.console.print(Panel(
                            warning_text, 
                            border_style="red",
                            title="[bold red]Safety Intercept[/]",
                            title_align="left"
                        ))
                        
                        try:
                            answer = click.prompt(
                                click.style("  Approve execution? (y/N/always)", fg="red", bold=True),
                                default="n",
                                show_default=False
                            ).strip().lower()
                        except (KeyboardInterrupt, EOFError):
                            answer = "n"
                            
                        if answer in ("y", "yes"):
                            action = "approve"
                        elif answer == "always":
                            action = "always"
                        else:
                            action = "deny"
                            
                        from langgraph.types import Command
                        resume_cmd = Command(resume={"action": action})
                        messages = [] # clear messages list so we don't append next turn
                        continue # loop back to workflow.stream

            except Exception as e:
                compass.print_error(f"Agent error: {e}")
                continue

            # Update session metadata after successful turn
            turn_count += 1
            sm.update_session(
                thread_id,
                turn_count=turn_count,
                first_message=user_input if turn_count == 1 else "",
            )

            compass.console.print()

        except KeyboardInterrupt:
            # Ctrl+C — cancel current turn, stay in REPL
            compass.console.print(
                Text("\n  ⏹  Interrupted. Type /exit to quit.", style="compass.warn")
            )
            continue

        except EOFError:
            # Ctrl+D — exit
            compass.print_goodbye()
            break

        except Exception as e:
            compass.print_error(f"Unexpected error: {e}")
            continue


# ─── Single-Shot Mode ────────────────────────────────────────────────────────────

async def run_single(message: str, resume_thread_id: str | None = None):
    """
    Execute a single message through the agent and display the result.
    Used for non-interactive mode: `python main.py -m "do something"`
    Optionally resumes a previous session.
    """
    from sessions import SessionManager

    compass = CompassConsole()
    sm = SessionManager()

    # Lazy import
    try:
        from graph.workflow import get_workflow
        workflow = await get_workflow()
    except Exception as e:
        compass.print_error(f"Failed to load agent workflow: {e}")
        sys.exit(1)

    # Resolve session
    if resume_thread_id:
        session_ctx = sm.get_session(resume_thread_id)
        if session_ctx is None:
            session_ctx = sm.create_session()
            session_ctx["thread_id"] = resume_thread_id
            sm._save()
        thread_id = session_ctx["thread_id"]
    else:
        session_ctx = sm.create_session()
        thread_id = session_ctx["thread_id"]

    config = {"configurable": {"thread_id": thread_id}}

    compass.console.print()
    prompt_display = Text()
    prompt_display.append("  🧭 › ", style="bold cyan")
    prompt_display.append(message, style="bright_white")
    compass.console.print(prompt_display)

    compass.console.print()
    try:
        live_panel = None
        current_text = ""
        turn_count = session_ctx.get("turn_count", 0)
        
        resume_cmd = None
        input_payload = {"messages": [{"role": "user", "content": message}]}
        
        while True:
            async for event_type, payload in workflow.astream( # type: ignore
                input_payload, # type: ignore
                config=config, # type: ignore
                stream_mode=["messages", "updates"],
            ):
                if event_type == "messages":
                    chunk, _ = payload
                    if isinstance(chunk, AIMessageChunk) and getattr(chunk, "content", None) and not getattr(chunk, "tool_calls", None):
                        if not live_panel:
                            live_panel = Live(console=compass.console, refresh_per_second=15, transient=False)
                            live_panel.start()
                        content_str = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        current_text += content_str
                        md = Markdown(current_text)
                        panel = Panel(
                            md,
                            border_style="bright_cyan",
                            box=box.ROUNDED,
                            title="[bold bright_cyan]🧭 Compass[/]",
                            title_align="left",
                            subtitle=f"[dim]turn {turn_count + 1}[/]",
                            subtitle_align="right",
                            padding=(1, 2),
                        )
                        live_panel.update(panel)
                elif event_type == "updates":
                    if live_panel:
                        live_panel.stop()
                        live_panel = None

                    if isinstance(payload, dict):
                        for node_name, node_output in payload.items():
                            _process_stream_event(compass, node_name, node_output, skip_response=bool(current_text))
                    
                    current_text = ""

            if live_panel:
                live_panel.stop()
                
            # ── Handle Interrupts ───────────────────────────────────────
            state_info = workflow.get_state(config)
            if state_info.next and "check_safety" in state_info.next:
                interrupt_data = None
                for task in state_info.tasks:
                    if task.name == "check_safety" and task.interrupts:
                        interrupt_data = task.interrupts[0].value
                        break
                        
                if interrupt_data and interrupt_data.get("reason") == "approval_required":
                    from rich.panel import Panel
                    from rich.text import Text
                    
                    risky_calls = interrupt_data.get("tool_calls", [])
                    warning_text = Text()
                    warning_text.append("\n  ⚠️  Approval Required\n\n", style="bold red")
                    for tc in risky_calls:
                        warning_text.append(f"  • {tc['name']}\n", style="bold yellow")
                        for k, v in tc.get("args", {}).items():
                            warning_text.append(f"      {k}: {v}\n", style="dim white")
                            
                    compass.console.print(Panel(
                        warning_text, 
                        border_style="red",
                        title="[bold red]Safety Intercept[/]",
                        title_align="left"
                    ))
                    
                    try:
                        answer = click.prompt(
                            click.style("  Approve execution? (y/N/always)", fg="red", bold=True),
                            default="n",
                            show_default=False
                        ).strip().lower()
                    except (KeyboardInterrupt, EOFError):
                        answer = "n"
                        
                    if answer in ("y", "yes"):
                        action = "approve"
                    elif answer == "always":
                        action = "always"
                    else:
                        action = "deny"
                        
                    from langgraph.types import Command
                    resume_cmd = Command(resume={"action": action})
                    input_payload = resume_cmd
                    continue
                    
            break # Exit loop if no interrupt

    except Exception as e:
        compass.print_error(f"Agent error: {e}")
        sys.exit(1)

    # Update session metadata
    turn_count = session_ctx.get("turn_count", 0) + 1
    sm.update_session(thread_id, turn_count=turn_count, first_message=message)

    compass.console.print()
