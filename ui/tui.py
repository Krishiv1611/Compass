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

# Force UTF-8 output on Windows to handle Unicode characters
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

# ─── Slash Commands ─────────────────────────────────────────────────────────────

SLASH_COMMANDS = {
    "/help":    "Show available commands",
    "/exit":    "Exit Compass",
    "/clear":   "Clear the terminal screen",
    "/model":   "Show current model info",
    "/tools":   "List all available tools",
    "/history": "Show conversation message count",
    "/compact": "Summarize and compact context (planned)",
}

# ─── Available Tools (for /tools display) ───────────────────────────────────────

TOOL_REGISTRY = [
    ("read_file",     "📄", "Read contents of a file"),
    ("write_to_file", "✏️",  "Write content to a file"),
    ("edit_file",     "🔧", "Edit specific sections of a file"),
    ("list_dir",      "📁", "List directory contents"),
    ("find_files",    "🔍", "Find files matching a pattern"),
    ("grep_search",   "🔎", "Search file contents with regex"),
    ("web_search",    "🌐", "Search the web"),
    ("shell_execute", "💻", "Execute a shell command"),
    ("memory",        "🧠", "Store/retrieve key-value memories"),
    ("todo",          "📋", "Manage a task list"),
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


def _process_stream_event(compass: CompassConsole, node_name: str, node_output: dict):
    """
    Process a single streaming event from workflow.stream(stream_mode='updates').

    Each event is {node_name: {state_updates}}.
    - 'call_model' node emits AIMessages (may contain tool_calls and/or content)
    - 'tools' node emits ToolMessages with results
    """
    from langchain_core.messages import AIMessage, ToolMessage

    messages = node_output.get("messages", [])

    for msg in messages:
        if isinstance(msg, AIMessage):
            # Display tool calls the model wants to make
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                compass.print_tool_separator()
                for tc in msg.tool_calls:
                    compass.print_tool_call(tc["name"], tc.get("args", {}))

            # Display the final text response
            if msg.content and isinstance(msg.content, str) and msg.content.strip():
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


def _handle_slash_command(compass: CompassConsole, command: str, messages: list) -> bool:
    """
    Handle a slash command. Returns True if the REPL should continue,
    False if it should exit.
    """
    cmd = command.strip().lower()

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

    elif cmd == "/compact":
        compass.console.print(
            Text("  ⏳ Context compaction is not yet implemented.", style="compass.warn")
        )
        compass.console.print()

    else:
        compass.console.print(
            Text(f"  Unknown command: {cmd}. Type /help for available commands.",
                 style="compass.warn")
        )
        compass.console.print()

    return True


def compass_repl():
    """
    Launch the Compass interactive REPL.

    This is the main entry point for the terminal UI. It:
    - Displays the welcome banner
    - Accepts user input with a styled prompt
    - Routes slash commands
    - Streams the LangGraph workflow for real-time display
    - Renders tool calls and agent responses with Rich
    """
    compass = CompassConsole()
    compass.print_welcome()

    # Lazy import to avoid import-time side effects (DB connection, etc.)
    try:
        from graph.workflow import workflow
    except Exception as e:
        compass.print_error(f"Failed to load agent workflow: {e}")
        compass.console.print(
            Text("  Tip: Make sure your .env file has DB_URI set.", style="dim"),
        )
        sys.exit(1)

    messages = []
    prompt_str = _format_prompt()

    # Generate a unique thread_id for this session (required by checkpointer)
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
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
                should_continue = _handle_slash_command(compass, user_input, messages)
                if not should_continue:
                    compass.print_goodbye()
                    break
                continue

            # Add user message to history
            messages.append({"role": "user", "content": user_input})

            # Stream the agent response in real-time
            compass.console.print()
            try:
                for chunk in workflow.stream(
                    {"messages": messages},
                    config=config,
                    stream_mode="updates",
                ):
                    # Each chunk is {node_name: {state_updates}}
                    for node_name, node_output in chunk.items():
                        _process_stream_event(compass, node_name, node_output)
            except Exception as e:
                compass.print_error(f"Agent error: {e}")
                continue

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

def run_single(message: str):
    """
    Execute a single message through the agent and display the result.
    Used for non-interactive mode: `python main.py -m "do something"`
    """
    compass = CompassConsole()

    # Lazy import
    try:
        from graph.workflow import workflow
    except Exception as e:
        compass.print_error(f"Failed to load agent workflow: {e}")
        sys.exit(1)

    compass.console.print()
    prompt_display = Text()
    prompt_display.append("  🧭 › ", style="bold cyan")
    prompt_display.append(message, style="bright_white")
    compass.console.print(prompt_display)

    # Generate a one-off thread_id for this run
    config = {"configurable": {"thread_id": uuid.uuid4().hex}}

    compass.console.print()
    try:
        for chunk in workflow.stream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_output in chunk.items():
                _process_stream_event(compass, node_name, node_output)
    except Exception as e:
        compass.print_error(f"Agent error: {e}")
        sys.exit(1)

    compass.console.print()

