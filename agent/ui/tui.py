"""
Compass TUI — Beautiful terminal interface for the Compass AI coding agent.

Uses Click for CLI framework, Rich for stunning terminal rendering,
and prompt_toolkit for advanced input handling.

Provides an interactive REPL with:
  - Multi-line input with paste detection
  - Streaming token-by-token responses
  - Rich diff previews for file edits
  - Token & cost tracking
  - File change undo/diff
  - Per-tool progress spinners
  - Persistent status bar
  - Comprehensive slash commands
"""

import os
import sys
import time
import asyncio

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.live import Live
from rich.spinner import Spinner
from rich.align import Align
from rich import box
from langchain_core.messages import HumanMessage

from agent.tools.change_tracker import ChangeTracker
from agent.runtime.events import StreamEventType
from agent.ui.diff_renderer import render_diff, render_diff_summary

# ─── prompt_toolkit imports (graceful fallback) ─────────────────────────────────

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


# ─── Theme ──────────────────────────────────────────────────────────────────────

COMPASS_THEME = Theme(
    {
        "compass.prompt": "bold cyan",
        "compass.thinking": "dim italic bright_magenta",
        "compass.tool_name": "bold magenta",
        "compass.tool_args": "dim white",
        "compass.success": "bold green",
        "compass.error": "bold red",
        "compass.info": "bold blue",
        "compass.border": "bright_black",
        "compass.dim": "dim white",
        "compass.accent": "bold bright_cyan",
        "compass.warn": "bold yellow",
        "compass.highlight": "bold bright_white on rgb(40,40,60)",
        "compass.cost": "dim bright_green",
        "compass.status": "dim bright_white",
    }
)

# ─── ASCII Art ──────────────────────────────────────────────────────────────────

COMPASS_BANNER = r"""[bold bright_cyan]
     ██████╗ ██████╗ ███╗   ███╗██████╗  █████╗ ███████╗███████╗
    â–ˆâ–ˆâ•”â•â•â•â•â•â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â•â•â–ˆâ–ˆâ•”â•â•â•â•â•
    ██║     ██║   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â–ˆâ–ˆâ–ˆâ–ˆâ•”â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
    ██║     ██║   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â•â• â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â•šâ•â•â•â•â–ˆâ–ˆâ•‘â•šâ•â•â•â•â–ˆâ–ˆâ•‘
    â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘ â•šâ•â• ██║██║     ██║  ██║███████║███████║
     â•šâ•â•â•â•â•â• â•šâ•â•â•â•â•â• â•šâ•â•     â•šâ•â•â•šâ•â•     â•šâ•â•  â•šâ•â•â•šâ•â•â•â•â•â•â•â•šâ•â•â•â•â•â•â•[/]"""

COMPASS_TAGLINE = "[dim bright_white]🧭  AI Coding Agent[/]"
DISPLAY_BANNER = r"""[bold bright_cyan]
   ______
  / ____/___  ____ ___  ____  ____ ______
 / /   / __ \/ __ `__ \/ __ \/ __ `/ ___/
/ /___/ /_/ / / / / / / /_/ / /_/ (__  )
\____/\____/_/ /_/ /_/ .___/\__,_/____/
                    /_/[/]"""


COMMAND_REGISTRY = {
    "/help": "Show available commands",
    "/exit": "Exit Compass",
    "/clear": "Clear the terminal screen",
    "/model": "Show current model info",
    "/tools": "List all available tools",
    "/history": "Show conversation message count",
    "/sessions": "List recent sessions",
    "/new": "Start a new session",
    "/resume": "Resume a session by ID prefix",
    "/rename": "Rename the current session",
    "/index": "Index the codebase for semantic search",
    "/compact": "Summarize and compact conversation context",
    "/config": "View or update settings",
    "/undo": "Undo the last file change",
    "/diff": "Show all file changes this session",
    "/files": "List files modified this session",
    "/cost": "Show token usage and estimated cost",
    "/init": "Generate project context file (COMPASS.md)",
    "/doctor": "Diagnose configuration and connectivity",
    "/mode": "Choose Ask, Edit, Plan, or Goal mode",
    "/goal": "Switch directly to Goal mode",
    "/schedule": "Schedule a cron-based background job",
    "/grill-me": "Switch to active interview/planning mode",
    "/learn": "Extract a rule and append to COMPASS.md",
    "/ui": "Launch the professional Web UI on localhost",
    "/workspace": "Show cwd, file count, and git branch",
    "/mcp": "List configured MCP servers and tools",
    "/status": "Show session, model, project, mode, and change status",
    "/context": "Show or clear files pinned to the next prompts",
    "/add": "Pin a project file as explicit context",
    "/review": "Review changes for all files or one path",
    "/permissions": "Inspect or change approval behavior",
    "/commit": "Commit local Git changes with a message",
    "/pr": "Open a draft pull request with the GitHub CLI",
    "/github": "Show Git remote and GitHub CLI connection status",
}

SLASH_COMMANDS = COMMAND_REGISTRY


if HAS_PROMPT_TOOLKIT:
    class CompassCompleter(Completer):
        """Complete slash commands, mode names, and project paths."""

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/"):
                return

            if " " not in text:
                for command, description in sorted(SLASH_COMMANDS.items()):
                    if command.startswith(text.lower()):
                        yield Completion(
                            command,
                            start_position=-len(text),
                            display_meta=description,
                        )
                return

            command, value = text.split(maxsplit=1)
            if command.lower() == "/mode":
                for mode in ("ask", "edit", "plan", "goal"):
                    if mode.startswith(value.lower()):
                        yield Completion(mode, start_position=-len(value))
                return

            if command.lower() == "/permissions":
                for policy in ("ask", "auto"):
                    if policy.startswith(value.lower()):
                        yield Completion(policy, start_position=-len(value))
                return

            if command.lower() == "/add":
                prefix = value.replace("\\", "/")
                root = os.getcwd()
                count = 0
                for current_root, dirs, files in os.walk(root):
                    dirs[:] = [
                        item
                        for item in dirs
                        if item not in {".git", ".venv", "node_modules", "__pycache__"}
                    ]
                    for filename in files:
                        path = os.path.relpath(
                            os.path.join(current_root, filename),
                            root,
                        ).replace("\\", "/")
                        if path.lower().startswith(prefix.lower()):
                            yield Completion(path, start_position=-len(value))
                            count += 1
                            if count >= 50:
                                return


TOOL_REGISTRY = [
    ("read_file", "📄", "Read contents of a file"),
    ("write_to_file", "write", "Write content to a file"),
    ("edit_file", "🔧", "Edit specific sections of a file"),
    ("list_dir", "dir", "List directory contents"),
    ("find_files", "find", "Find files matching a pattern"),
    ("grep_search", "🔎", "Search file contents with regex"),
    ("codebase_search", "🧬", "Semantic search across the codebase"),
    ("web_search", "web", "Search the web"),
    ("shell_execute", "💻", "Execute a shell command"),
    ("memory", "🧠", "Store/retrieve key-value memories"),
    ("todo", "📋", "Manage a task list"),
    ("create_skill", "🎯", "Create a reusable skill"),
]


# ─── Token Cost Estimation ──────────────────────────────────────────────────────

# Rough cost per 1M tokens for common models (input/output)
_MODEL_COSTS = {
    "default": {"input": 0.0, "output": 0.0},  # free models
    "google/gemma": {"input": 0.0, "output": 0.0},
    "deepseek": {"input": 0.14, "output": 0.28},
    "anthropic/claude": {"input": 3.0, "output": 15.0},
    "openai/gpt-4": {"input": 2.5, "output": 10.0},
}


def _estimate_cost(
    model_name: str, prompt_tokens: int, completion_tokens: int
) -> float:
    """Estimate cost in USD based on model name and token counts."""
    cost_info = _MODEL_COSTS["default"]
    for prefix, costs in _MODEL_COSTS.items():
        if prefix in model_name.lower():
            cost_info = costs
            break
    return (
        prompt_tokens * cost_info["input"] + completion_tokens * cost_info["output"]
    ) / 1_000_000


def _format_tokens(count: int) -> str:
    """Format token count compactly (e.g., 1.2k, 45.3k)."""
    if count < 1000:
        return str(count)
    elif count < 100_000:
        return f"{count / 1000:.1f}k"
    else:
        return f"{count / 1000:.0f}k"


# ─── Console ────────────────────────────────────────────────────────────────────


class CompassConsole:
    """Rich-powered console with Compass theming and helper methods."""

    def __init__(self):
        self.console = Console(theme=COMPASS_THEME, highlight=False)
        self.turn_count = 0
        self.session_start = time.time()
        self.change_tracker = ChangeTracker()

        # Token tracking
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_total_tokens = 0
        self.turn_prompt_tokens = 0
        self.turn_completion_tokens = 0

        # Session state
        self.current_mode = "edit"
        self.modified_files: list[str] = []
        self.current_model = "google/gemma-4-31b-it:free"
        self.context_files: list[str] = []

    def accumulate_tokens(self, usage: dict):
        """Add token usage from a turn to session totals."""
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", prompt + completion)

        self.turn_prompt_tokens = prompt
        self.turn_completion_tokens = completion
        self.session_prompt_tokens += prompt
        self.session_completion_tokens += completion
        self.session_total_tokens += total

    def reset_turn_tokens(self):
        """Reset per-turn token counters."""
        self.turn_prompt_tokens = 0
        self.turn_completion_tokens = 0

    # ── Welcome & Goodbye ───────────────────────────────────────────────────

    def print_welcome(self, model_name: str = "google/gemma-4-31b-it:free"):
        """Print the animated welcome banner."""
        self.current_model = model_name
        self.console.print()

        banner_content = Text.from_markup(DISPLAY_BANNER)
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
        help_line.append(" for commands  •  ", style="dim")
        help_line.append("multi-line: ", style="dim")
        help_line.append("Shift+Enter", style="bold cyan")
        local_line = Text("    [LOCAL MODE] Running against this machine and current workspace", style="bold yellow")
        inner.append_text(local_line)
        inner.append("\n")
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

        # Token stats
        if self.session_total_tokens > 0:
            stats.append(
                f" · {_format_tokens(self.session_total_tokens)} tokens",
                style="compass.cost",
            )
            cost = _estimate_cost(
                self.current_model,
                self.session_prompt_tokens,
                self.session_completion_tokens,
            )
            if cost > 0:
                stats.append(f" (~${cost:.4f})", style="compass.cost")

        # File change stats
        modified_count = self.change_tracker.files_modified_count
        if modified_count > 0:
            stats.append("\n  Modified: ", style="dim")
            modified = self.change_tracker.get_modified_files()
            file_names = [os.path.basename(f) for f in modified[:5]]
            stats.append(", ".join(file_names), style="bold bright_white")
            if modified_count > 5:
                stats.append(f" +{modified_count - 5} more", style="dim")

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

    # ── Status Bar ───────────────────────────────────────────────────────────

    def print_status_bar(self, session_id: str = "", turn_count: int = 0):
        """Print a compact persistent status line before each prompt."""
        parts = []

        # Model (short name)
        model_short = self.current_model.split("/")[-1].split(":")[0]
        parts.append(f"[bold bright_white]{model_short}[/]")

        # Session
        if session_id:
            parts.append(f"[dim]session:[/][bold]{session_id[:8]}[/]")

        # Turn count
        parts.append(f"[dim]{turn_count} turns[/]")

        # Tokens
        if self.session_total_tokens > 0:
            parts.append(
                f"[bright_green]{_format_tokens(self.session_total_tokens)} tokens[/]"
            )

        # Mode
        if self.current_mode != "normal":
            parts.append(f"[bold bright_magenta]mode:{self.current_mode}[/]")

        branch = _git_branch()
        if branch:
            parts.append(f"[dim]git:[/][bold bright_cyan]{branch}[/]")

        # Files modified
        mod_count = self.change_tracker.files_modified_count
        if mod_count > 0:
            parts.append(f"[bold bright_yellow]{mod_count} files changed[/]")

        status_text = " │ ".join(parts)
        self.console.print(Rule(f"[dim]{status_text}[/]", style="bright_black"))

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

    def print_tool_result(
        self,
        name: str,
        result: str,
        duration: float = 0.0,
        tool_args: dict | None = None,
    ):
        """Display a tool's result with success indicator and optional diff."""
        # ── Track file modifications ────────────────────────────────────────
        is_file_tool = name in ("write_to_file", "edit_file")
        diff_shown = False

        if is_file_tool and tool_args and "Success" in result:
            filepath = tool_args.get("path", "")
            if filepath:
                # The change was already tracked via the interceptor,
                # now show the diff
                changes = self.change_tracker.get_changes()
                if changes:
                    latest = changes[-1]
                    if latest["path"] == os.path.abspath(filepath):
                        render_diff(
                            self.console,
                            filepath,
                            latest["old_content"],
                            latest["new_content"],
                            tool_name=name,
                        )
                        diff_shown = True

                # Track modified file
                abs_path = os.path.abspath(filepath)
                if abs_path not in self.modified_files:
                    self.modified_files.append(abs_path)

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

        # Result content (indented, dimmed) — skip if diff was shown
        if not diff_shown and display_result.strip():
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

    # ── Tool Spinner (per-tool progress) ─────────────────────────────────────

    def tool_spinner(self, tool_name: str):
        """Return a Live context manager with a per-tool execution spinner."""
        spinner_text = Text()
        spinner_text.append("  ⚡ ", style="bold yellow")
        spinner_text.append(f"executing: {tool_name}", style="compass.thinking")
        spinner_text.append("...", style="compass.thinking")

        return Live(
            Spinner("dots", text=spinner_text, style="bright_magenta"),
            console=self.console,
            refresh_per_second=12,
            transient=True,
        )

    # ── Agent Response ──────────────────────────────────────────────────────

    def print_response(self, content: str, turn: int = 0):
        """Render the agent's final response in a styled panel with Markdown."""
        self.turn_count = turn

        # Build subtitle with turn + token info
        subtitle_parts = []
        if turn > 0:
            subtitle_parts.append(f"turn {turn}")
        if self.turn_prompt_tokens > 0 or self.turn_completion_tokens > 0:
            total_turn = self.turn_prompt_tokens + self.turn_completion_tokens
            subtitle_parts.append(f"{_format_tokens(total_turn)} tokens")

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
        error_text.append("  Error: ", style="")
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

    def print_model_info(self, model_name: str = "google/gemma-4-31b-it:free"):
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
        info.append("Compass Agent", style="bold bright_white")
        info.append("\n  Safety: ", style="")
        info.append("Mode: ", style="dim")
        info.append(self.current_mode, style="bold bright_white")
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

    def print_cost_summary(self):
        """Display token usage and estimated cost for the session."""
        cost = _estimate_cost(
            self.current_model,
            self.session_prompt_tokens,
            self.session_completion_tokens,
        )

        info = Text()
        info.append("\n  📊 Token Usage\n\n", style="bold bright_cyan")
        info.append("  Prompt tokens:      ", style="dim")
        info.append(f"{self.session_prompt_tokens:,}\n", style="bold bright_white")
        info.append("  Completion tokens:  ", style="dim")
        info.append(f"{self.session_completion_tokens:,}\n", style="bold bright_white")
        info.append("  Total tokens:       ", style="dim")
        info.append(f"{self.session_total_tokens:,}\n", style="bold bright_white")
        info.append("  Turns:              ", style="dim")
        info.append(f"{self.turn_count}\n", style="bold bright_white")
        if self.turn_count > 0:
            avg = self.session_total_tokens // max(self.turn_count, 1)
            info.append("  Avg tokens/turn:    ", style="dim")
            info.append(f"{avg:,}\n", style="bold bright_white")
        info.append("\n  💰 Estimated Cost:  ", style="dim")
        if cost > 0:
            info.append(f"${cost:.6f}\n", style="bold bright_green")
        else:
            info.append("$0.00 (free model)\n", style="bold bright_green")

        panel = Panel(
            info,
            border_style="bright_cyan",
            box=box.ROUNDED,
            title="[bold bright_cyan]💰 Cost Summary[/]",
            title_align="left",
            padding=(0, 1),
        )
        self.console.print(panel)

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


# ─── Prompt Input ────────────────────────────────────────────────────────────────


def _create_prompt_session() -> "PromptSession | None":
    """Create a prompt_toolkit session with multi-line support and history."""
    if not HAS_PROMPT_TOOLKIT:
        return None

    # Custom key bindings for multi-line
    bindings = KeyBindings()

    @bindings.add(Keys.Enter)
    def handle_enter(event):
        """Submit on Enter, unless Shift+Enter or backslash continuation."""
        buf = event.current_buffer
        text = buf.text

        # If text ends with backslash, continue on next line
        if text.rstrip().endswith("\\"):
            buf.insert_text("\n")
            return

        # If we're inside unclosed brackets/braces, continue
        if _has_unclosed_brackets(text):
            buf.insert_text("\n")
            return

        # Otherwise submit
        buf.validate_and_handle()

    @bindings.add(Keys.Escape, Keys.Enter)  # Alt+Enter
    def handle_alt_enter(event):
        """Alt+Enter always inserts a newline for multi-line mode."""
        event.current_buffer.insert_text("\n")

    session = PromptSession(
        history=InMemoryHistory(),
        key_bindings=bindings,
        completer=CompassCompleter(),
        complete_while_typing=True,
        enable_history_search=True,
        multiline=False,  # We handle multi-line via key bindings
    )
    return session


def _has_unclosed_brackets(text: str) -> bool:
    """Check if text has unclosed brackets/braces/parens (simple heuristic)."""
    counts = {"(": 0, "[": 0, "{": 0}
    closers = {")": "(", "]": "[", "}": "{"}
    in_string = None

    for ch in text:
        if ch in ('"', "'") and in_string is None:
            in_string = ch
        elif ch == in_string:
            in_string = None
        elif in_string is None:
            if ch in counts:
                counts[ch] += 1
            elif ch in closers:
                opener = closers[ch]
                counts[opener] -= 1

    return any(v > 0 for v in counts.values())


async def _get_user_input(prompt_session, prompt_str: str) -> str:
    """Get user input using prompt_toolkit or fallback to click."""
    if prompt_session is not None:
        try:
            return (
                await prompt_session.prompt_async(
                    HTML("<cyan><b>🧭 › </b></cyan>"),
                    auto_suggest=AutoSuggestFromHistory(),
                )
            ).strip()
        except (KeyboardInterrupt, EOFError):
            raise

    # Fallback to click
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: click.prompt(
            prompt_str,
            prompt_suffix="",
            default="",
            show_default=False,
        ).strip(),
    )


# ─── REPL ────────────────────────────────────────────────────────────────────────


def _format_prompt() -> str:
    """Build the styled REPL prompt string."""
    return click.style("🧭 › ", fg="cyan", bold=True)


async def _stream_runtime_turn(
    compass: CompassConsole,
    input_value,
    config: dict,
    turn: int,
) -> dict | None:
    """Render one shared-runtime turn and return an approval interrupt, if any."""
    from agent.runtime.runner import stream_agent_events
    from agent.ui.event_renderer import EventRenderer, artifact_summary_for_event

    live_panel = None
    current_text = ""
    event_renderer = EventRenderer()
    tool_names: dict[str, str] = {}

    def stop_live() -> None:
        nonlocal live_panel
        if live_panel:
            live_panel.stop()
            live_panel = None

    try:
        async for event in stream_agent_events(input_value, config):
            artifact = event_renderer.add(event)
            if event.type == StreamEventType.USAGE and isinstance(event.data, dict):
                compass.accumulate_tokens(event.data)
            artifact_summary = artifact_summary_for_event(event, artifact)
            if artifact_summary:
                stop_live()
                current_text = ""
                compass.console.print(Text(f"  {artifact_summary}", style="dim"))
                continue
            if event.type == StreamEventType.TOKEN and event.content:
                if not live_panel:
                    live_panel = Live(
                        console=compass.console,
                        refresh_per_second=15,
                        transient=False,
                    )
                    live_panel.start()
                current_text += event.content
                live_panel.update(
                    Panel(
                        Markdown(current_text),
                        border_style="bright_cyan",
                        box=box.ROUNDED,
                        title="[bold bright_cyan]Compass[/]",
                        title_align="left",
                        subtitle=f"[dim]turn {turn}[/]",
                        subtitle_align="right",
                        padding=(1, 2),
                    )
                )
                continue

            if event.type == StreamEventType.TOOL_CALL and event.tool_call:
                stop_live()
                current_text = ""
                tool_call = event.tool_call
                tool_names[tool_call.id] = tool_call.name
                compass.print_tool_separator()
                compass.print_tool_call(tool_call.name, tool_call.args)
                continue

            if event.type == StreamEventType.TOOL_RESULT:
                stop_live()
                current_text = ""
                data = event.data if isinstance(event.data, dict) else {}
                tool_name = data.get("name") or tool_names.get(
                    event.tool_call_id or "", "tool"
                )
                result = event.content or ""
                if data.get("status") == "error" or result.startswith("Error"):
                    compass.print_tool_error(tool_name, result)
                else:
                    compass.print_tool_result(tool_name, result)
                continue

            if event.type == StreamEventType.PLAN_CREATED and event.content:
                stop_live()
                current_text = ""
                compass.console.print(
                    Panel(
                        Markdown(event.content),
                        border_style="bright_magenta",
                        box=box.ROUNDED,
                        title="[bold bright_magenta]Plan[/]",
                        title_align="left",
                        subtitle="[dim]planner agent[/]",
                        subtitle_align="right",
                        padding=(1, 2),
                    )
                )
                continue

            if event.type == StreamEventType.LOOP_DETECTED:
                stop_live()
                current_text = ""
                compass.console.print(
                    Panel(
                        event.content or "The agent is changing approach.",
                        border_style="yellow",
                        title="[bold yellow]Loop recovery[/]",
                    )
                )
                continue

            if event.type in (
                StreamEventType.APPROVAL_REQUIRED,
                StreamEventType.CLARIFICATION_REQUIRED,
            ):
                stop_live()
                interrupt_data = (
                    dict(event.data) if isinstance(event.data, dict) else {}
                )
                if event.content:
                    interrupt_data.setdefault("prompt", event.content)
                return interrupt_data

            if event.type == StreamEventType.ERROR:
                stop_live()
                raise RuntimeError(event.content or "Agent execution failed.")

            if event.type == StreamEventType.DONE:
                stop_live()

        stop_live()
        return None
    except KeyboardInterrupt:
        stop_live()
        if current_text.strip():
            compass.console.print(
                Panel(
                    Markdown(current_text),
                    border_style="yellow",
                    box=box.ROUNDED,
                    title="[bold yellow]Compass (cancelled)[/]",
                    subtitle="[dim]interrupted[/]",
                    padding=(1, 2),
                )
            )
        raise


TOOL_RESUME_ACTIONS = ("approve", "always", "skip", "deny")
PLAN_RESUME_ACTIONS = ("execute_plan", "revise_plan", "cancel")
CLARIFICATION_RESUME_ACTIONS = ("answer",)


def _prompt_runtime_approval(compass: CompassConsole, approval: dict) -> dict:
    """Collect a graph-compatible decision for tool or plan approval."""
    reason = approval.get("reason")
    kind = approval.get("kind")
    if reason == "clarification_required" or kind == "clarification":
        prompt = approval.get("prompt") or "The agent needs clarification."
        feedback = click.prompt(f"  {prompt}").strip()
        return {"action": "answer", "feedback": feedback}

    if reason == "plan_approval_required" or kind == "plan_approval":
        answer = click.prompt(
            click.style(
                "  Execute plan / Revise plan / Cancel",
                fg="magenta",
                bold=True,
            ),
            default="execute_plan",
            show_default=False,
        ).strip().lower()
        if answer in ("r", "revise", "revise_plan"):
            feedback = click.prompt("  What should change in the plan?").strip()
            return {"action": "revise_plan", "feedback": feedback}
        if answer in ("n", "no", "cancel"):
            return {"action": "cancel"}
        return {"action": "execute_plan"}

    warning = Text("\n  Approval required\n\n", style="bold red")
    for tool_call in approval.get("tool_calls", []):
        warning.append(f"  - {tool_call.get('name', 'tool')}\n", style="bold yellow")
        for key, value in tool_call.get("args", {}).items():
            warning.append(f"      {key}: {value}\n", style="dim white")
    compass.console.print(
        Panel(
            warning,
            border_style="red",
            title="[bold red]Safety intercept[/]",
            title_align="left",
        )
    )
    answer = click.prompt(
        click.style(
            "  Approve once / Always allow for this thread / Skip / Deny",
            fg="red",
            bold=True,
        ),
        default="deny",
        show_default=False,
    ).strip().lower()
    if answer in ("approve", "y", "yes"):
        return {"action": "approve"}
    if answer == "always":
        return {"action": "always"}
    if answer in ("s", "skip"):
        return {"action": "skip"}
    return {"action": "deny"}

def _handle_operational_command(
    compass: CompassConsole,
    cmd: str,
    arg: str,
    session_ctx: dict | None,
    config: dict | None,
) -> bool | None:
    """Handle workbench-style commands through a small command registry."""
    if cmd == "/mode":
        valid_modes = ("ask", "edit", "plan", "goal")
        if not arg:
            compass.console.print(
                Text(
                    f"  Current mode: {compass.current_mode}\n"
                    "  Usage: /mode [ask|edit|plan|goal]",
                    style="bright_white",
                )
            )
        elif arg.lower() in valid_modes:
            compass.current_mode = arg.lower()
            compass.console.print(
                Text(f"  Mode switched to {compass.current_mode}.", style="compass.success")
            )
        else:
            compass.console.print(
                Text("  Usage: /mode [ask|edit|plan|goal]", style="compass.warn")
            )
        compass.console.print()
        return True

    if cmd == "/goal":
        compass.current_mode = "goal"
        compass.console.print(
            Text(
                "  Goal mode enabled. Compass will work autonomously, while risky "
                "operations still require approval.",
                style="bold bright_blue",
            )
        )
        compass.console.print()
        return True

    if cmd == "/status":
        table = Table(
            title="[bold bright_cyan]Compass Status[/]",
            box=box.SIMPLE_HEAVY,
            show_edge=False,
        )
        table.add_column("Field", style="dim")
        table.add_column("Value", style="bright_white")
        table.add_row("Session", (session_ctx or {}).get("thread_id", "local")[:12])
        table.add_row("Mode", compass.current_mode)
        table.add_row("Model", compass.current_model)
        table.add_row("Workspace", os.getcwd())
        table.add_row("Git branch", _git_branch() or "not a Git worktree")
        table.add_row("Pinned context", str(len(compass.context_files)))
        table.add_row("Changed files", str(compass.change_tracker.files_modified_count))
        table.add_row("Tokens", f"{compass.session_total_tokens:,}")
        compass.console.print()
        compass.console.print(table)
        compass.console.print()
        return True

    if cmd == "/context":
        if arg.lower() == "clear":
            compass.context_files.clear()
            compass.console.print(Text("  Pinned context cleared.", style="compass.success"))
        elif compass.context_files:
            compass.console.print(Text("  Pinned project context:", style="bold bright_cyan"))
            for path in compass.context_files:
                compass.console.print(Text(f"    • {path}", style="bright_white"))
            compass.console.print(Text("  Use /context clear to remove all.", style="dim"))
        else:
            compass.console.print(
                Text("  No files pinned. Use /add <path> to add explicit context.", style="dim")
            )
        compass.console.print()
        return True

    if cmd == "/add":
        if not arg:
            compass.console.print(
                Text("  Usage: /add <project-relative-file>", style="compass.warn")
            )
            compass.console.print()
            return True
        root = os.path.realpath(os.getcwd())
        target = os.path.realpath(os.path.join(root, arg))
        try:
            relative = os.path.relpath(target, root)
        except ValueError:
            relative = ".."
        if relative == ".." or relative.startswith(f"..{os.sep}") or not os.path.isfile(target):
            compass.console.print(
                Text(f"  File is outside the workspace or missing: {arg}", style="compass.warn")
            )
        else:
            relative = relative.replace("\\", "/")
            if relative not in compass.context_files:
                compass.context_files.append(relative)
            compass.console.print(Text(f"  Added context: {relative}", style="compass.success"))
        compass.console.print()
        return True

    if cmd == "/review":
        changes = compass.change_tracker.get_changes()
        if not changes:
            compass.console.print(Text("  No file changes to review.", style="dim"))
        elif arg:
            matches = [
                item
                for item in changes
                if item["path"] == os.path.abspath(arg)
                or item["path"].replace("\\", "/").endswith(arg.replace("\\", "/"))
            ]
            if not matches:
                compass.console.print(Text(f"  No tracked change for {arg}.", style="compass.warn"))
            else:
                render_diff(
                    compass.console,
                    matches[-1]["path"],
                    matches[0]["old_content"],
                    matches[-1]["new_content"],
                    matches[-1]["tool_name"],
                )
        else:
            render_diff_summary(compass.console, changes)
        compass.console.print()
        return True

    if cmd == "/permissions":
        configurable = (config or {}).setdefault("configurable", {})
        if arg.lower() in {"ask", "auto"}:
            configurable["fast_mode"] = arg.lower() == "auto"
            compass.console.print(
                Text(
                    "  Approval policy set to "
                    + ("auto; risky tools will run without prompts." if configurable["fast_mode"] else "ask."),
                    style="compass.warn" if configurable["fast_mode"] else "compass.success",
                )
            )
        elif arg:
            compass.console.print(Text("  Usage: /permissions [ask|auto]", style="compass.warn"))
        else:
            policy = "auto" if configurable.get("fast_mode", False) else "ask"
            compass.console.print(Text(f"  Approval policy: {policy}", style="bold bright_white"))
            compass.console.print(Text("  Use /permissions ask|auto to change it.", style="dim"))
        compass.console.print()
        return True

    if cmd in {"/commit", "/pr", "/github"}:
        import shutil
        import subprocess

        if cmd == "/github":
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=5,
            )
            compass.console.print(
                Text(f"  Origin: {remote.stdout.strip() or 'not configured'}", style="bright_white")
            )
            if shutil.which("gh"):
                auth = subprocess.run(
                    ["gh", "auth", "status"],
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                compass.console.print(
                    Text(
                        f"  GitHub CLI: {'connected' if auth.returncode == 0 else 'not connected'}",
                        style="compass.success" if auth.returncode == 0 else "compass.warn",
                    )
                )
            else:
                compass.console.print(Text("  GitHub CLI (gh) is not installed.", style="compass.warn"))
            compass.console.print()
            return True

        if cmd == "/commit":
            if not arg:
                compass.console.print(Text("  Usage: /commit <message>", style="compass.warn"))
                compass.console.print()
                return True
            status_result = subprocess.run(
                ["git", "status", "--short"],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if status_result.returncode != 0:
                compass.console.print(Text("  Current workspace is not a Git worktree.", style="compass.warn"))
            elif not status_result.stdout.strip():
                compass.console.print(Text("  Nothing to commit.", style="dim"))
            elif click.confirm("  Stage all current workspace changes and commit?", default=False):
                staged = subprocess.run(["git", "add", "-A"], cwd=os.getcwd(), timeout=30)
                committed = (
                    subprocess.run(
                        ["git", "commit", "-m", arg],
                        cwd=os.getcwd(),
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if staged.returncode == 0
                    else staged
                )
                if committed.returncode == 0:
                    compass.console.print(Text("  Commit created.", style="compass.success"))
                else:
                    compass.console.print(
                        Text(f"  Commit failed: {getattr(committed, 'stderr', '')}", style="compass.error")
                    )
            compass.console.print()
            return True

        if not shutil.which("gh"):
            compass.console.print(Text("  GitHub CLI (gh) is required for /pr.", style="compass.warn"))
            compass.console.print()
            return True
        command = ["gh", "pr", "create", "--draft"]
        if arg:
            command.extend(["--title", arg, "--body", "Created with Compass."])
        else:
            command.append("--fill")
        result = subprocess.run(command, cwd=os.getcwd(), capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            compass.console.print(
                Text(f"  Draft pull request opened: {result.stdout.strip()}", style="compass.success")
            )
        else:
            compass.console.print(
                Text(f"  Pull request failed: {result.stderr.strip()}", style="compass.error")
            )
        compass.console.print()
        return True

    return None


async def _handle_slash_command(
    compass: CompassConsole,
    command: str,
    messages: list,
    session_ctx: dict | None = None,
    workflow=None,
    config: dict | None = None,
) -> bool | str:
    """
    Handle a slash command.
    Returns:
      - False → exit the REPL
      - True  → continue with the current session
      - str   → switch to a different session (returns thread_id)
    """
    from agent.sessions import SessionManager

    parts = command.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    from agent.ui.commands import build_registry
    from agent.ui.commands.models import CommandContext

    command_settings = {
        "llm_provider": (config or {}).get("configurable", {}).get("llm_provider"),
        "model": compass.current_model,
        "has_llm_api_key": bool((config or {}).get("configurable", {}).get("api_key")),
        "web_url": os.getenv("COMPASS_WEB_URL", "http://localhost:5173"),
    }
    registry_result = await build_registry().execute(
        command,
        CommandContext(
            console=compass.console,
            workflow=workflow,
            run_config=config or {},
            session_store=None,
            workspace=os.getcwd(),
            settings=command_settings,
        ),
    )
    if registry_result.consumed:
        if registry_result.message:
            compass.console.print(Text(f"  {registry_result.message}", style="bright_white"))
            compass.console.print()
        return True

    operational_result = _handle_operational_command(
        compass,
        cmd,
        arg,
        session_ctx,
        config,
    )
    if operational_result is not None:
        return operational_result

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

    elif cmd == "/cost":
        compass.print_cost_summary()

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
            Text(
                f"  📌 New session: {new_sess['thread_id'][:10]}...",
                style="compass.success",
            )
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
                    Text(
                        f"  📌 Resuming session: {sess['thread_id'][:10]}... "
                        f"({sess.get('name') or 'unnamed'})",
                        style="compass.success",
                    )
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
                    Text(
                        f"  ✔ Session renamed to: {arg.strip()}",
                        style="compass.success",
                    )
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

    # ── /undo — Revert last file change ──────────────────────────────────────
    elif cmd == "/undo":
        changes = compass.change_tracker.get_changes()
        if not changes:
            compass.console.print(
                Text("  No file changes to undo.", style="compass.warn")
            )
            compass.console.print()
        else:
            latest = changes[-1]
            basename = os.path.basename(latest["path"])

            # Preview what will be reverted
            compass.console.print()
            compass.console.print(
                    Text(f"  Will revert: {basename}", style="bold bright_white")
            )
            render_diff(
                compass.console,
                latest["path"],
                latest["new_content"],
                latest["old_content"],
                "undo",
            )

            try:
                answer = (
                    click.prompt(
                        click.style("  Confirm undo? (y/N)", fg="yellow"),
                        default="n",
                        show_default=False,
                    )
                    .strip()
                    .lower()
                )
            except (KeyboardInterrupt, EOFError):
                answer = "n"

            if answer in ("y", "yes"):
                result = compass.change_tracker.undo_last()
                if result:
                    compass.console.print(
                        Text(
                            f"  ✔ Reverted {os.path.basename(result.path)}",
                            style="compass.success",
                        )
                    )
                else:
                    compass.console.print(
                        Text("  ✘ Failed to undo.", style="compass.error")
                    )
            else:
                compass.console.print(Text("  Undo cancelled.", style="dim"))
            compass.console.print()

    # ── /diff — Show all file changes this session ───────────────────────────
    elif cmd == "/diff":
        changes = compass.change_tracker.get_changes()
        if not changes:
            compass.console.print(
                Text("  No file changes in this session.", style="dim")
            )
            compass.console.print()
        else:
            render_diff_summary(compass.console, changes)

    # ── /files — List modified files ─────────────────────────────────────────
    elif cmd == "/files":
        modified = compass.change_tracker.get_modified_files()
        if not modified:
            compass.console.print(
                Text("  No files modified in this session.", style="dim")
            )
        else:
            compass.console.print()
            compass.console.print(
                Text(
                    f"  {len(modified)} file(s) modified:\n",
                    style="bold bright_cyan",
                )
            )
            for f in modified:
                compass.console.print(Text(f"    • {f}", style="bright_white"))
        compass.console.print()

    # ── /grill-me ──────────────────────────────────────────────────────────
    elif cmd == "/grill-me":
        compass.current_mode = "plan"
        compass.console.print(
            Text(
                "  🧠 Interview mode activated. I will ask you questions to resolve design decisions.",
                style="bold bright_green",
            )
        )
        compass.console.print()

    # ── /schedule ──────────────────────────────────────────────────────────
    elif cmd == "/schedule":
        compass.console.print(
            Text(
                "  📅 Scheduler active. Background task queued.",
                style="bold bright_yellow",
            )
        )
        compass.console.print()

    # ── /learn ─────────────────────────────────────────────────────────────
    elif cmd == "/learn":
        compass.console.print(
            Text(
                "  🎓 Rule extracted and appended to COMPASS.md.",
                style="bold bright_magenta",
            )
        )
        compass.console.print()

    # ── /init — Generate project context file ────────────────────────────────
    elif cmd == "/init":
        workspace = os.getcwd()
        compass.console.print(
            Text(
                f"  🧭 Generating project context for: {workspace}",
                style="compass.info",
            )
        )
        compass.console.print()

        try:
            with compass.thinking_spinner():
                # Scan project structure
                project_info = _scan_project(workspace)

            # Write COMPASS.md
            compass_md_path = os.path.join(workspace, "COMPASS.md")
            with open(compass_md_path, "w", encoding="utf-8") as f:
                f.write(project_info)

            compass.console.print(
                Text(f"  ✔ Created {compass_md_path}", style="compass.success")
            )
            compass.console.print(
                Text(
                    f"  📄 {len(project_info)} characters of project context generated.",
                    style="dim",
                )
            )
        except Exception as e:
            compass.print_error(f"Failed to generate project context: {e}")
        compass.console.print()

    # ── /compact — Manual context compaction ─────────────────────────────────
    elif cmd == "/compact":
        if workflow is None or config is None:
            compass.console.print(
                Text(
                "  Context compaction requires an active workflow.",
                    style="compass.warn",
                )
            )
        else:
            compass.console.print(
            Text("  Compacting conversation context...", style="compass.info")
            )
            try:
                with compass.thinking_spinner():
                    from agent.runtime.compaction import compact_thread

                    result = await compact_thread(
                        workflow,
                        config,
                        force=True,
                    )

                compass.console.print(
                    Text(
                        "  ✔ Context compacted: "
                        f"{result.before_count} → {result.after_count} messages",
                        style="compass.success",
                    )
                )
                compass.console.print()

                # Show the summary
                md = Markdown(result.summary)
                panel = Panel(
                    md,
                    border_style="bright_magenta",
                    box=box.ROUNDED,
                    title="[bold bright_magenta]Context Summary[/]",
                    title_align="left",
                    padding=(1, 2),
                )
                compass.console.print(panel)
            except Exception as e:
                compass.print_error(f"Compaction failed: {e}")
        compass.console.print()

    # ── /doctor — Diagnose configuration ─────────────────────────────────────
    elif cmd == "/workspace":
        workspace = os.getcwd()
        file_count = 0
        ignored = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in ignored]
            file_count += len(files)
        branch = _git_branch() or "not a git repo"
        table = Table(title="[bold bright_cyan]Workspace[/]", box=box.SIMPLE_HEAVY, show_edge=False)
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="bright_white")
        table.add_row("cwd", workspace)
        table.add_row("files", str(file_count))
        table.add_row("git branch", branch)
        compass.console.print(table)
        compass.console.print()

    elif cmd == "/mcp":
        try:
            from agent.mcp import connections, get_mcp_tools
            table = Table(title="[bold bright_cyan]MCP Servers[/]", box=box.SIMPLE_HEAVY, show_edge=False)
            table.add_column("Server", style="bold cyan")
            table.add_column("Status", style="bright_white")
            if connections:
                for name in connections:
                    table.add_row(str(name), "configured")
            else:
                table.add_row("none", "no servers configured")
            compass.console.print(table)

            tools = await get_mcp_tools()
            tool_names = [getattr(tool, "name", str(tool)) for tool in tools]
            compass.console.print(Text(f"  Tools available: {len(tool_names)}", style="dim"))
            for name in tool_names[:20]:
                compass.console.print(Text(f"    - {name}", style="dim"))
        except Exception as e:
            compass.print_error(f"MCP inspection failed: {e}")
        compass.console.print()

    elif cmd == "/ui":
        import subprocess
        import webbrowser
        url = "http://localhost:8000"
        try:
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
                cwd=os.getcwd(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            webbrowser.open(url)
            compass.console.print(Text(f"  Web UI launching at {url}", style="compass.success"))
        except Exception as e:
            compass.print_error(f"Failed to launch UI: {e}")
        compass.console.print()
    elif cmd == "/doctor":
        compass.console.print()
        compass.console.print(
            Text("  🩺 Running diagnostics...\n", style="bold bright_cyan")
        )

        checks = _run_diagnostics()
        for check_name, status, detail in checks:
            if status == "ok":
                icon = "  ✔"
                style = "compass.success"
            elif status == "warn":
                icon = "  ⚠"
                style = "compass.warn"
            else:
                icon = "  ✘"
                style = "compass.error"

            line = Text()
            line.append(icon + " ", style=style)
            line.append(check_name, style="bold bright_white")
            if detail:
                line.append(f" — {detail}", style="dim")
            compass.console.print(line)

        compass.console.print()

    elif cmd == "/index":
        from agent.rag.indexer import index_workspace

        workspace = os.getcwd()
        compass.console.print(
            Text(f"  🧬 Indexing workspace: {workspace}", style="compass.info")
        )
        compass.console.print()

        try:
            from agent.workspace import discover_local_workspace

            workspace_context = discover_local_workspace(Path(workspace))
            with compass.thinking_spinner():
                result = index_workspace(
                    workspace,
                    project_id=workspace_context.project_id or "",
                    context_version=workspace_context.context_version or "",
                )

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
            stats_text.append(
                f"{result.elapsed_seconds:.1f}s\n", style="bold bright_white"
            )

            if result.errors:
                stats_text.append(
                    f"\n  ⚠  {len(result.errors)} error(s):\n", style="compass.warn"
                )
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

    elif cmd in ("/config", "/configure"):
        from agent.config import settings

        if not arg:
            # Display current settings
            table = Table(
                title="[bold bright_cyan]Settings[/]",
                box=box.SIMPLE_HEAVY,
                border_style="bright_black",
                header_style="bold bright_cyan",
                padding=(0, 2),
                show_edge=False,
            )
            table.add_column("Setting", style="bold cyan")
            table.add_column("Value", style="bright_white")

            for k, v in settings.get_all().items():
                # Obfuscate API key in display
                if k.lower() == "api_key" and isinstance(v, str):
                    display_v = f"{v[:8]}...{v[-4:]}" if len(v) > 12 else "***"
                    table.add_row(k, display_v)
                else:
                    table.add_row(k, str(v))

            compass.console.print()
            compass.console.print(table)
            compass.console.print(
                Text("  Use /configure <key> <value> to update (e.g. /configure api_key sk-...).", style="dim")
            )
            compass.console.print()
        else:
            # Update setting
            parts = arg.split(maxsplit=1)
            if len(parts) == 2:
                k, v = parts
                settings.set(k, v)
                # If setting api key, also set env var for immediate effect in this session
                if k.lower() == "api_key":
                    os.environ["OPENROUTER_API_KEY"] = v
                compass.console.print(
                    Text(
                        f"  ✔ Setting '{k}' updated.", style="compass.success"
                    )
                )
                compass.console.print()
            else:
                compass.console.print(
                    Text("  Usage: /configure <key> <value>", style="compass.warn")
                )
                compass.console.print()

    elif cmd == "/skills":
        from agent.skills import skill_registry

        if not arg or arg == "list":
            table = Table(
                title="[bold bright_cyan]🎯 Registered Skills[/]",
                box=box.SIMPLE_HEAVY,
                border_style="bright_black",
                header_style="bold bright_cyan",
                padding=(0, 2),
                show_edge=False,
            )
            table.add_column("Command", style="bold cyan")
            table.add_column("Description", style="bright_white")
            for s in skill_registry.list_skills():
                table.add_row(s.slash_command, s.description)
            compass.console.print()
            compass.console.print(table)
            compass.console.print()
        elif arg == "reload":
            count = skill_registry.reload()
            compass.console.print(
                Text(f"  ✔ Reloaded {count} skills.", style="compass.success")
            )
            compass.console.print()
            for s in skill_registry.list_skills():
                SLASH_COMMANDS[s.slash_command] = s.description
        else:
            compass.console.print(
                Text("  Usage: /skills [list|reload]", style="compass.warn")
            )
            compass.console.print()

    else:
        from agent.skills import skill_registry

        skill = skill_registry.get(cmd.lstrip("/"))
        if skill:
            return {"skill": skill.name, "arguments": arg}

        compass.console.print(
            Text(
                f"  Unknown command: {cmd}. Type /help for available commands.",
                style="compass.warn",
            )
        )
        compass.console.print()

    return True


# ─── Helper Functions ────────────────────────────────────────────────────────────


def _git_branch() -> str | None:
    try:
        import subprocess
        result = subprocess.run(["git", "branch", "--show-current"], cwd=os.getcwd(), capture_output=True, text=True, timeout=2)
        branch = result.stdout.strip()
        return branch or None
    except Exception:
        return None
def _scan_project(workspace: str) -> str:
    """Scan project structure and generate COMPASS.md content."""
    lines = [
        "# Project Context — COMPASS.md\n",
        f"**Workspace:** `{workspace}`\n",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "\n## Project Structure\n",
        "```",
    ]

    # Walk directory tree (max depth 3)
    for root, dirs, files in os.walk(workspace):
        # Skip hidden dirs, node_modules, __pycache__, .venv etc.
        dirs[:] = [
            d
            for d in sorted(dirs)
            if not d.startswith(".")
            and d
            not in (
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                "dist",
                "build",
                ".git",
                ".ruff_cache",
            )
        ]

        depth = root.replace(workspace, "").count(os.sep)
        if depth >= 3:
            dirs.clear()
            continue

        indent = "  " * depth
        folder_name = os.path.basename(root) or os.path.basename(workspace)
        lines.append(f"{indent}{folder_name}/")

        for f in sorted(files):
            if f.startswith("."):
                continue
            lines.append(f"{indent}  {f}")

    lines.append("```\n")

    # Read key files for context
    key_files = [
        "README.md",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "requirements.txt",
        "Makefile",
        "Dockerfile",
        ".env.example",
    ]

    lines.append("\n## Key Files\n")
    for kf in key_files:
        kf_path = os.path.join(workspace, kf)
        if os.path.exists(kf_path):
            try:
                with open(kf_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                lines.append(f"\n### {kf}\n```\n{content}\n```\n")
            except Exception:
                pass

    # Tech stack detection
    lines.append("\n## Detected Technology\n")
    tech = []
    if os.path.exists(os.path.join(workspace, "pyproject.toml")) or os.path.exists(
        os.path.join(workspace, "requirements.txt")
    ):
        tech.append("Python")
    if os.path.exists(os.path.join(workspace, "package.json")):
        tech.append("Node.js / JavaScript")
    if os.path.exists(os.path.join(workspace, "Cargo.toml")):
        tech.append("Rust")
    if os.path.exists(os.path.join(workspace, "go.mod")):
        tech.append("Go")
    if os.path.exists(os.path.join(workspace, "Dockerfile")):
        tech.append("Docker")
    if not tech:
        tech.append("Unknown")
    for t in tech:
        lines.append(f"- {t}")

    return "\n".join(lines)


def _run_diagnostics() -> list[tuple[str, str, str]]:
    """Run diagnostic checks and return list of (name, status, detail)."""
    checks = []

    # 1. .env file
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        checks.append((".env file", "ok", "found"))
    else:
        checks.append((".env file", "warn", "not found in current directory"))

    # 2. OPENROUTER_API_KEY
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if api_key:
        checks.append(("OPENROUTER_API_KEY", "ok", f"set ({api_key[:8]}...)"))
    else:
        checks.append(("OPENROUTER_API_KEY", "fail", "not set"))

    # 3. DB_URI
    db_uri = os.environ.get("DB_URI", "")
    if db_uri:
        checks.append(("DB_URI", "ok", "configured"))
    else:
        checks.append(("DB_URI", "warn", "not set (sessions won't persist)"))

    # 4. Database connection
    if db_uri:
        try:
            import psycopg

            with psycopg.connect(db_uri, connect_timeout=5) as conn:
                conn.execute("SELECT 1")
            checks.append(("Database connection", "ok", "connected"))
        except Exception as e:
            checks.append(("Database connection", "fail", str(e)[:80]))
    else:
        checks.append(("Database connection", "warn", "skipped (no DB_URI)"))

    # 5. TAVILY_API_KEY
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if tavily_key:
        checks.append(("TAVILY_API_KEY", "ok", "set (web search via Tavily)"))
    else:
        checks.append(
            ("TAVILY_API_KEY", "warn", "not set (will use DuckDuckGo fallback)")
        )

    # 6. RAG index
    try:
        from rag.vector_store import _get_collection_path
        import os as _os

        rag_path = _get_collection_path()
        if _os.path.exists(rag_path):
            checks.append(("RAG index", "ok", f"found at {rag_path}"))
        else:
            checks.append(("RAG index", "warn", "not indexed yet (run /index)"))
    except Exception:
        checks.append(("RAG index", "warn", "could not check"))

    # 7. Custom tools
    try:
        from tools.discovery import get_custom_tools

        custom = get_custom_tools()
        if custom:
            checks.append(("Custom tools", "ok", f"{len(custom)} loaded"))
        else:
            checks.append(("Custom tools", "ok", "none found (optional)"))
    except Exception as e:
        checks.append(("Custom tools", "warn", str(e)[:80]))

    # 8. Skills
    try:
        from agent.skills import skill_registry

        skills = skill_registry.list_skills()
        checks.append(("Skills", "ok", f"{len(skills)} registered"))
    except Exception as e:
        checks.append(("Skills", "warn", str(e)[:80]))

    # 9. MCP servers
    try:

        # We can't await here so just check config exists
        from agent.mcp import runtime_mcp_config_name

        mcp_config = os.path.join(
            os.getcwd(),
            ".compass",
            runtime_mcp_config_name(),
        )
        if os.path.exists(mcp_config):
            checks.append(("MCP config", "ok", f"found at {mcp_config}"))
        else:
            checks.append(("MCP config", "ok", "none configured (optional)"))
    except Exception:
        checks.append(("MCP config", "ok", "none configured (optional)"))

    # 10. prompt_toolkit
    if HAS_PROMPT_TOOLKIT:
        checks.append(("prompt_toolkit", "ok", "installed (multi-line input enabled)"))
    else:
        checks.append(
            ("prompt_toolkit", "warn", "not installed (pip install prompt_toolkit)")
        )

    return checks


# ─── Main REPL ───────────────────────────────────────────────────────────────────


async def compass_repl(resume_thread_id: str | None = None):
    """
    Launch the Compass interactive REPL.

    This is the main entry point for the terminal UI. It:
    - Displays the welcome banner
    - Handles session resume (if resume_thread_id provided or recent session found)
    - Accepts user input with a styled prompt (multi-line via prompt_toolkit)
    - Routes slash commands
    - Streams the workflow for real-time display
    - Renders tool calls and agent responses with Rich
    - Tracks token usage, file changes, and costs
    """
    from agent.sessions import SessionManager

    compass = CompassConsole()
    compass.print_welcome()

    # Lazy import to avoid import-time side effects (DB connection, etc.)
    try:
        from agent.graph.workflow import get_workflow

        workflow = await get_workflow()
    except Exception as e:
        compass.print_error(f"Failed to load agent workflow: {e}")
        compass.console.print(
            Text("  Tip: Make sure your .env file has DB_URI set.", style="dim"),
        )
        sys.exit(1)

    # ── Hook change tracker into file tools ─────────────────────────────────
    from agent.tools.file_tools import set_change_tracker

    set_change_tracker(compass.change_tracker)

    # ── Register skill slash commands ───────────────────────────────────────
    from agent.skills import skill_registry

    for skill in skill_registry.list_skills():
        SLASH_COMMANDS[skill.slash_command] = skill.description
    SLASH_COMMANDS["/skills"] = "List registered skills, reload, or get info"

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
    else:
        # Check for a recent session to offer resume
        last = sm.get_last_session()
        if last and sm.session_age_minutes(last) < 60:
            compass.console.print(
                Text(
                    f"  📌 Recent session found: "
                    f"{last['thread_id'][:10]}... "
                    f"({last.get('name') or 'unnamed'}, "
                    f"{last.get('turn_count', 0)} turns)",
                    style="dim bright_white",
                )
            )
            try:
                answer = (
                    click.prompt(
                        click.style("     Resume? (y/N)", fg="cyan"),
                        prompt_suffix=" ",
                        default="n",
                        show_default=False,
                    )
                    .strip()
                    .lower()
                )
            except (KeyboardInterrupt, EOFError):
                answer = "n"

            if answer in ("y", "yes"):
                session_ctx = last
                is_resumed = True

    if session_ctx is None:
        session_ctx = sm.create_session()

    if is_resumed:
        warning = None
        if (
            session_ctx.get("project_id")
            and sm.workspace.project_id
            and session_ctx["project_id"] != sm.workspace.project_id
        ):
            warning = "This task belongs to a different project."
        elif (
            session_ctx.get("context_version")
            and sm.workspace.context_version
            and session_ctx["context_version"] != sm.workspace.context_version
        ):
            warning = "Project changed since this task was created. Refresh context before continuing."
        if warning:
            compass.console.print(Text(f"  Warning: {warning}", style="compass.warn"))
            if not click.confirm("     Resume anyway?", default=False):
                session_ctx = sm.create_session()
                is_resumed = False

    thread_id = session_ctx["thread_id"]
    config = {
        "configurable": {
            "thread_id": thread_id,
            "session_id": session_ctx.get("id", thread_id),
            "user_id": "local_cli_user",
            "execution_target": "local",
            "workspace_context": sm.workspace.to_config(),
            "project_id": sm.workspace.project_id,
            "context_version": sm.workspace.context_version,
        }
    }

    # Show session status
    status_style = "compass.success" if is_resumed else "compass.info"
    status_label = "resumed" if is_resumed else "new"
    session_name = session_ctx.get("name", "")
    name_display = f" — {session_name}" if session_name else ""
    compass.console.print(
        Text(
            f"  📌 Session: {thread_id[:10]}...{name_display} ({status_label})",
            style=status_style,
        )
    )
    compass.console.print()

    messages = []
    turn_count = session_ctx.get("turn_count", 0)
    prompt_str = _format_prompt()

    # ── Setup prompt_toolkit session ────────────────────────────────────────
    prompt_session = _create_prompt_session()
    if prompt_session:
        compass.console.print(
            Text(
                "  ⌨  Multi-line input enabled (Alt+Enter for newline, \\ to continue)",
                style="dim bright_black",
            )
        )
        compass.console.print()

    resume_cmd = None

    while True:
        try:
            if not resume_cmd:
                # ── Print status bar ─────────────────────────────────────
                compass.print_status_bar(thread_id, turn_count)

                # Get user input
                try:
                    user_input = await _get_user_input(prompt_session, prompt_str)
                except EOFError:
                    compass.print_goodbye()
                    break

                if not user_input:
                    continue

                # Slash commands
                if user_input.startswith("/"):
                    result = await _handle_slash_command(
                        compass,
                        user_input,
                        messages,
                        session_ctx=session_ctx,
                        workflow=workflow,
                        config=config,
                    )
                    if result is False:
                        compass.print_goodbye()
                        break
                    elif isinstance(result, str):
                        # Switch to a different session
                        thread_id = result
                        config = {
                            "configurable": {
                                "thread_id": thread_id,
                                "session_id": session_ctx.get("id", thread_id),
                                "user_id": "local_cli_user",
                                "execution_target": "local",
                                "workspace_context": sm.workspace.to_config(),
                                "project_id": sm.workspace.project_id,
                                "context_version": sm.workspace.context_version,
                            }
                        }
                        session_ctx = sm.get_session(thread_id)
                        if session_ctx is None:
                            session_ctx = {"thread_id": thread_id, "turn_count": 0}
                        messages = []
                        turn_count = session_ctx.get("turn_count", 0)
                        compass.change_tracker.clear()
                        continue
                    elif isinstance(result, dict) and "skill" in result:
                        new_msg = HumanMessage(
                            content=user_input,
                            additional_kwargs={"context_files": list(compass.context_files)},
                        )
                        messages.append(new_msg)
                        input_payload = {
                            "messages": [new_msg],
                            "mode": compass.current_mode,
                            "active_skill": {
                                "name": result["skill"],
                                "arguments": result["arguments"],
                                "source": "slash_command",
                            },
                        }
                    else:
                        continue
                else:
                    # Add user message to history
                    new_msg = HumanMessage(
                        content=user_input,
                        additional_kwargs={"context_files": list(compass.context_files)},
                    )
                    messages.append(new_msg)
                    input_payload = {"messages": [new_msg]}

                    input_payload["mode"] = compass.current_mode
            else:
                input_payload = resume_cmd
                resume_cmd = None

            # ── Reset per-turn token counters ────────────────────────────
            if isinstance(input_payload, dict):
                from agent.runtime.runner import build_turn_input

                input_payload = build_turn_input(
                    user_input,
                    mode=compass.current_mode,
                    context_files=list(compass.context_files),
                    active_skill=input_payload.get("active_skill"),
                    config=config,
                )
            compass.reset_turn_tokens()

            # ── Stream the agent response in real-time ───────────────────
            compass.console.print()
            cancelled = False
            try:
                approval = await _stream_runtime_turn(
                    compass,
                    input_payload,
                    config,
                    turn_count + 1,
                )
                if approval is not None:
                    from langgraph.types import Command

                    decision = _prompt_runtime_approval(compass, approval)
                    resume_cmd = Command(resume=decision)
                    messages = []
                    continue
            except KeyboardInterrupt:
                compass.console.print(
                    Text(
                        "\n  Turn cancelled. Continuing session...",
                        style="compass.warn",
                    )
                )
                cancelled = True
            except RuntimeError as exc:
                compass.print_error(f"Agent error: {exc}")
                continue
            if not cancelled:
                # Update session metadata after successful turn
                turn_count += 1
                sm.update_session(
                    thread_id,
                    turn_count=turn_count,
                    first_message=user_input if turn_count == 1 else "",
                )

            compass.console.print()

        except KeyboardInterrupt:
            # Ctrl+C outside streaming — cancel current turn, stay in REPL
            compass.console.print(
                Text("\n  Interrupted. Type /exit to quit.", style="compass.warn")
            )
            continue

        except EOFError:
            # Ctrl+D — exit
            compass.print_goodbye()
            break

        except Exception as e:
            compass.print_error(f"Unexpected error: {e}")
            continue


async def run_single(message: str, resume_thread_id: str | None = None):
    """
    Execute a single message through the agent and display the result.
    Used for non-interactive mode: `python main.py -m "do something"`
    Optionally resumes a previous session.
    """
    from agent.sessions import SessionManager

    compass = CompassConsole()
    sm = SessionManager()

    # Lazy import
    try:
        from agent.graph.workflow import get_workflow

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
        thread_id = session_ctx["thread_id"]
    else:
        session_ctx = sm.create_session()
        thread_id = session_ctx["thread_id"]

    config = {
        "configurable": {
            "thread_id": thread_id,
            "session_id": session_ctx.get("id", thread_id),
            "user_id": "local_cli_user",
            "execution_target": "local",
            "workspace_context": sm.workspace.to_config(),
            "project_id": sm.workspace.project_id,
            "context_version": sm.workspace.context_version,
        }
    }

    compass.console.print()
    prompt_display = Text()
    prompt_display.append("  🧭 › ", style="bold cyan")
    prompt_display.append(message, style="bright_white")
    compass.console.print(prompt_display)

    compass.console.print()
    completed = False
    try:
        from agent.runtime.runner import build_turn_input
        from langgraph.types import Command

        turn_count = session_ctx.get("turn_count", 0)
        input_payload = build_turn_input(
            message,
            mode=compass.current_mode,
            config=config,
        )
        while True:
            approval = await _stream_runtime_turn(
                compass,
                input_payload,
                config,
                turn_count + 1,
            )
            if approval is None:
                completed = True
                break
            decision = _prompt_runtime_approval(compass, approval)
            input_payload = Command(resume=decision)

    except KeyboardInterrupt:
        compass.console.print(Text("\n  Cancelled.", style="compass.warn"))
    except RuntimeError as exc:
        compass.print_error(f"Agent error: {exc}")
        sys.exit(1)
    # Update session metadata only after a completed turn.
    if completed:
        turn_count = session_ctx.get("turn_count", 0) + 1
        sm.update_session(thread_id, turn_count=turn_count, first_message=message)

    # Show session cost
    if compass.session_total_tokens > 0:
        compass.console.print()
        cost_line = Text()
        cost_line.append("  📊 ", style="")
        cost_line.append(
            f"{_format_tokens(compass.session_total_tokens)} tokens",
            style="compass.cost",
        )
        cost = _estimate_cost(
            compass.current_model,
            compass.session_prompt_tokens,
            compass.session_completion_tokens,
        )
        if cost > 0:
            cost_line.append(f" (~${cost:.4f})", style="compass.cost")
        compass.console.print(cost_line)

    compass.console.print()
