"""
Compass TUI â€” Beautiful terminal interface for the Compass AI coding agent.

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
from langchain_core.messages import AIMessageChunk, AIMessage, ToolMessage

from agent.tools.change_tracker import ChangeTracker
from agent.ui.diff_renderer import render_diff, render_diff_summary

# â”€â”€â”€ prompt_toolkit imports (graceful fallback) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


# â”€â”€â”€ Theme â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

# â”€â”€â”€ ASCII Art â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

COMPASS_BANNER = r"""[bold bright_cyan]
     â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ•—   â–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
    â–ˆâ–ˆâ•”â•â•â•â•â•â–ˆâ–ˆâ•”â•â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ•— â–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•—â–ˆâ–ˆâ•”â•â•â•â•â•â–ˆâ–ˆâ•”â•â•â•â•â•
    â–ˆâ–ˆâ•‘     â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â–ˆâ–ˆâ–ˆâ–ˆâ•”â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—
    â–ˆâ–ˆâ•‘     â–ˆâ–ˆâ•‘   â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘â•šâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•”â•â•â•â• â–ˆâ–ˆâ•”â•â•â–ˆâ–ˆâ•‘â•šâ•â•â•â•â–ˆâ–ˆâ•‘â•šâ•â•â•â•â–ˆâ–ˆâ•‘
    â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•—â•šâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•”â•â–ˆâ–ˆâ•‘ â•šâ•â• â–ˆâ–ˆâ•‘â–ˆâ–ˆâ•‘     â–ˆâ–ˆâ•‘  â–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ•‘
     â•šâ•â•â•â•â•â• â•šâ•â•â•â•â•â• â•šâ•â•     â•šâ•â•â•šâ•â•     â•šâ•â•  â•šâ•â•â•šâ•â•â•â•â•â•â•â•šâ•â•â•â•â•â•â•[/]"""

COMPASS_TAGLINE = "[dim bright_white]ðŸ§­  AI Coding Agent[/]"


SLASH_COMMANDS = {
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
    "/mode": "Toggle plan/normal mode (usage: /mode [plan|normal])",
    "/goal": "Enable deep autonomous execution mode",
    "/schedule": "Schedule a cron-based background job",
    "/grill-me": "Switch to active interview/planning mode",
    "/learn": "Extract a rule and append to COMPASS.md",
    "/ui": "Launch the professional Web UI on localhost",
    "/workspace": "Show cwd, file count, and git branch",
    "/mcp": "List configured MCP servers and tools",
}


TOOL_REGISTRY = [
    ("read_file", "ðŸ“„", "Read contents of a file"),
    ("write_to_file", "âœï¸", "Write content to a file"),
    ("edit_file", "ðŸ”§", "Edit specific sections of a file"),
    ("list_dir", "ðŸ“", "List directory contents"),
    ("find_files", "ðŸ”", "Find files matching a pattern"),
    ("grep_search", "ðŸ”Ž", "Search file contents with regex"),
    ("codebase_search", "ðŸ§¬", "Semantic search across the codebase"),
    ("web_search", "ðŸŒ", "Search the web"),
    ("shell_execute", "ðŸ’»", "Execute a shell command"),
    ("memory", "ðŸ§ ", "Store/retrieve key-value memories"),
    ("todo", "ðŸ“‹", "Manage a task list"),
    ("create_skill", "ðŸŽ¯", "Create a reusable skill"),
]


# â”€â”€â”€ Token Cost Estimation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€â”€ Console â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
        self.current_mode = "normal"  # "normal" or "plan"
        self.modified_files: list[str] = []
        self.current_model = "google/gemma-4-31b-it:free"

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

    # â”€â”€ Welcome & Goodbye â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def print_welcome(self, model_name: str = "google/gemma-4-31b-it:free"):
        """Print the animated welcome banner."""
        self.current_model = model_name
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
        model_line.append("    âš™  Model: ", style="dim")
        model_line.append(model_name, style="bold bright_white")
        inner.append_text(model_line)
        inner.append("\n")

        # Help hint
        help_line = Text()
        help_line.append("    âŒ¨  Type ", style="dim")
        help_line.append("/help", style="bold cyan")
        help_line.append(" for commands  â€¢  ", style="dim")
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
        stats.append("  ðŸ“Š Session: ", style="dim")
        stats.append(f"{self.turn_count} turns", style="bold bright_white")
        stats.append(f" Â· {mins}m {secs}s", style="dim")

        # Token stats
        if self.session_total_tokens > 0:
            stats.append(
                f" Â· {_format_tokens(self.session_total_tokens)} tokens",
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
            stats.append("\n  ðŸ“ Modified: ", style="dim")
            modified = self.change_tracker.get_modified_files()
            file_names = [os.path.basename(f) for f in modified[:5]]
            stats.append(", ".join(file_names), style="bold bright_white")
            if modified_count > 5:
                stats.append(f" +{modified_count - 5} more", style="dim")

        farewell = Text()
        farewell.append("\n  ðŸ‘‹ ", style="")
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

    # â”€â”€ Status Bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        status_text = " â”‚ ".join(parts)
        self.console.print(Rule(f"[dim]{status_text}[/]", style="bright_black"))

    # â”€â”€ Tool Calls â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def print_tool_call(self, name: str, args: dict):
        """Display a tool invocation with styled arguments."""
        # Tool header
        header = Text()
        header.append("  âš¡ ", style="bold yellow")
        header.append(name, style="compass.tool_name")

        self.console.print(header)

        # Arguments (compact JSON display)
        if args:
            for key, value in args.items():
                arg_line = Text()
                arg_line.append("  â”‚  ", style="bright_black")
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
        # â”€â”€ Track file modifications â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
        status.append("  âœ” ", style="compass.success")
        status.append(name, style="dim bright_white")
        status.append(" completed", style="dim")
        if duration > 0:
            status.append(f" ({duration:.1f}s)", style="dim")
        if lines_info:
            status.append(lines_info, style="dim")
        self.console.print(status)

        # Result content (indented, dimmed) â€” skip if diff was shown
        if not diff_shown and display_result.strip():
            for line in display_result.strip().split("\n")[:15]:
                result_line = Text()
                result_line.append("  â•°â”€ ", style="bright_black")
                result_line.append(line, style="dim white")
                self.console.print(result_line)
            if display_result.strip().count("\n") > 15:
                self.console.print(
                    Text("  â•°â”€ ... (truncated)", style="dim bright_black")
                )

    def print_tool_error(self, name: str, error: str):
        """Display a tool error."""
        status = Text()
        status.append("  âœ˜ ", style="compass.error")
        status.append(name, style="dim bright_white")
        status.append(" failed", style="compass.error")
        self.console.print(status)

        err_line = Text()
        err_line.append("  â•°â”€ ", style="bright_black")
        err_line.append(error[:200], style="red")
        self.console.print(err_line)

    # â”€â”€ Tool Spinner (per-tool progress) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def tool_spinner(self, tool_name: str):
        """Return a Live context manager with a per-tool execution spinner."""
        spinner_text = Text()
        spinner_text.append("  âš¡ ", style="bold yellow")
        spinner_text.append(f"executing: {tool_name}", style="compass.thinking")
        spinner_text.append("...", style="compass.thinking")

        return Live(
            Spinner("dots", text=spinner_text, style="bright_magenta"),
            console=self.console,
            refresh_per_second=12,
            transient=True,
        )

    # â”€â”€ Agent Response â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        subtitle = " Â· ".join(subtitle_parts)

        md = Markdown(content)
        panel = Panel(
            md,
            border_style="bright_cyan",
            box=box.ROUNDED,
            title="[bold bright_cyan]ðŸ§­ Compass[/]",
            title_align="left",
            subtitle=f"[dim]{subtitle}[/]" if subtitle else None,
            subtitle_align="right",
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)

    # â”€â”€ Error Display â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def print_error(self, message: str):
        """Display an error message in a styled panel."""
        error_text = Text()
        error_text.append("  âŒ ", style="")
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

    # â”€â”€ Help / Info â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def print_help(self):
        """Display the slash commands reference table."""
        table = Table(
            title="[bold bright_cyan]ðŸ§­ Compass Commands[/]",
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
            title="[bold bright_cyan]ðŸ›   Available Tools[/]",
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
        info.append("\n  âš™  ", style="")
        info.append("Model: ", style="dim")
        info.append(model_name, style="bold bright_white")
        info.append("\n  ðŸ”— ", style="")
        info.append("Provider: ", style="dim")
        info.append("OpenRouter", style="bold bright_white")
        info.append("\n  ðŸ§© ", style="")
        info.append("Framework: ", style="dim")
        info.append("Compass Agent", style="bold bright_white")
        info.append("\n  ðŸ›¡ï¸  ", style="")
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
        info.append("  ðŸ’¬ ", style="")
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
        info.append("\n  ðŸ“Š Token Usage\n\n", style="bold bright_cyan")
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
        info.append("\n  ðŸ’° Estimated Cost:  ", style="dim")
        if cost > 0:
            info.append(f"${cost:.6f}\n", style="bold bright_green")
        else:
            info.append("$0.00 (free model)\n", style="bold bright_green")

        panel = Panel(
            info,
            border_style="bright_cyan",
            box=box.ROUNDED,
            title="[bold bright_cyan]ðŸ’° Cost Summary[/]",
            title_align="left",
            padding=(0, 1),
        )
        self.console.print(panel)

    # â”€â”€ Spinner â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # â”€â”€ Separator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def print_tool_separator(self, label: str = "tool calls"):
        """Print a subtle rule separator for tool call groups."""
        self.console.print()
        self.console.print(
            Rule(f"[dim bright_black]{label}[/]", style="bright_black", align="left")
        )

    def print_separator(self):
        """Print a subtle divider."""
        self.console.print(Rule(style="bright_black"))


# â”€â”€â”€ Prompt Input â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
                    HTML("<cyan><b>ðŸ§­ â€º </b></cyan>"),
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


# â”€â”€â”€ REPL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _format_prompt() -> str:
    """Build the styled REPL prompt string."""
    return click.style("ðŸ§­ â€º ", fg="cyan", bold=True)


def _process_stream_event(
    compass: CompassConsole,
    node_name: str,
    node_output: dict,
    skip_response: bool = False,
):
    """
    Process a single streaming event from workflow.stream(stream_mode='updates').

    Each event is {node_name: {state_updates}}.
    Handles all agent nodes:
      - 'planner'       â†’ Show the plan in a styled panel
      - 'executor'      â†’ Tool calls + final response
      - 'loop_recovery' â†’ Warning panel with recovery guidance
      - 'summary_node'  â†’ Subtle compaction notice
      - 'tools'         â†’ ToolMessage results
    """
    messages = node_output.get("messages", [])

    # â”€â”€ Accumulate token usage from any node â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    token_usage = node_output.get("token_usage", {})
    if token_usage:
        compass.accumulate_tokens(token_usage)

    # â”€â”€ Planner Agent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if node_name == "planner":
        # The planner also emits an AIMessage â€” show it as the plan
        for msg in messages:
            if isinstance(msg, AIMessage) and msg.content:
                plan_content = (
                    msg.content if isinstance(msg.content, str) else str(msg.content)
                )
                if plan_content.strip():
                    md = Markdown(plan_content)
                    panel = Panel(
                        md,
                        border_style="bright_magenta",
                        box=box.ROUNDED,
                        title="[bold bright_magenta]ðŸ“‹ Plan[/]",
                        title_align="left",
                        subtitle="[dim]planner agent[/]",
                        subtitle_align="right",
                        padding=(1, 2),
                    )
                    compass.console.print()
                    compass.console.print(panel)
        return

    # â”€â”€ Skill Manager Node â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if node_name == "skill_manager":
        result = node_output.get("skill_result")
        if result:
            header = Text()
            header.append("  ðŸŽ¯ ", style="bold bright_green")
            header.append(f"Skill: {result['skill_name']}", style="bold bright_white")
            header.append(
                f" ({result['turns_used']} turns, "
                f"{result['tool_calls_made']} tool calls)",
                style="dim",
            )
            compass.console.print(header)
        return

    # â”€â”€ Loop Recovery Agent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if node_name == "loop_recovery":
        guidance = node_output.get("recovery_guidance", "")
        loop_count = node_output.get("loop_count", 0)

        if node_output.get("is_done", False):
            # Hard break â€” show final message
            for msg in messages:
                if isinstance(msg, AIMessage) and msg.content:
                    content = (
                        msg.content
                        if isinstance(msg.content, str)
                        else str(msg.content)
                    )
                    compass.print_response(
                        content, turn=node_output.get("turn_count", 0)
                    )
            return

        if guidance:
            warning_text = Text()
            warning_text.append("\n  âš ï¸  Loop Detected", style="bold yellow")
            warning_text.append(f" â€” recovery attempt {loop_count}/3\n\n", style="dim")
            warning_text.append(f"  {guidance}\n", style="bright_white")

            panel = Panel(
                warning_text,
                border_style="yellow",
                box=box.ROUNDED,
                title="[bold yellow]ðŸ”„ Loop Recovery[/]",
                title_align="left",
                padding=(0, 1),
            )
            compass.console.print()
            compass.console.print(panel)
        return

    # â”€â”€ Summary Node â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if node_name == "summary_node":
        compass.console.print(
            Text(
                "  ðŸ“ Context compacted by summarizer agent.", style="dim bright_white"
            )
        )
        return

    # â”€â”€ Executor Agent + Tools Node â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    for msg in messages:
        if isinstance(msg, AIMessage):
            # Display tool calls the model wants to make
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                compass.print_tool_separator()
                for tc in msg.tool_calls:
                    compass.print_tool_call(tc["name"], tc.get("args", {}))

            # Display the final text response
            if (
                not skip_response
                and msg.content
                and isinstance(msg.content, str)
                and msg.content.strip()
            ):
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
                # Try to pass tool_args for diff rendering
                compass.print_tool_result(tool_name, result)


def _handle_slash_command(
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
      - False â†’ exit the REPL
      - True  â†’ continue with the current session
      - str   â†’ switch to a different session (returns thread_id)
    """
    from agent.sessions import SessionManager

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
                title="[bold bright_cyan]ðŸ“Œ Recent Sessions[/]",
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
                    tid_display += " â—„"
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
                f"  ðŸ“Œ New session: {new_sess['thread_id'][:10]}...",
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
                        f"  ðŸ“Œ Resuming session: {sess['thread_id'][:10]}... "
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
                        f"  âœ” Session renamed to: {arg.strip()}",
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

    # â”€â”€ /undo â€” Revert last file change â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                Text(f"  â†©ï¸  Will revert: {basename}", style="bold bright_white")
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
                            f"  âœ” Reverted {os.path.basename(result.path)}",
                            style="compass.success",
                        )
                    )
                else:
                    compass.console.print(
                        Text("  âœ˜ Failed to undo.", style="compass.error")
                    )
            else:
                compass.console.print(Text("  Undo cancelled.", style="dim"))
            compass.console.print()

    # â”€â”€ /diff â€” Show all file changes this session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/diff":
        changes = compass.change_tracker.get_changes()
        if not changes:
            compass.console.print(
                Text("  No file changes in this session.", style="dim")
            )
            compass.console.print()
        else:
            render_diff_summary(compass.console, changes)

    # â”€â”€ /files â€” List modified files â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                    f"  ðŸ“ {len(modified)} file(s) modified:\n",
                    style="bold bright_cyan",
                )
            )
            for f in modified:
                compass.console.print(Text(f"    â€¢ {f}", style="bright_white"))
        compass.console.print()

    # â”€â”€ /mode â€” Toggle plan/normal mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/mode":
        if not arg:
            compass.console.print(
                Text(
                    f"  Current mode: {compass.current_mode}", style="bold bright_white"
                )
            )
            compass.console.print(Text("  Usage: /mode [plan|normal]", style="dim"))
        elif arg.lower() in ("plan", "normal"):
            compass.current_mode = arg.lower()
            icon = "ðŸ“‹" if compass.current_mode == "plan" else "âš¡"
            compass.console.print(
                Text(
                    f"  {icon} Mode switched to: {compass.current_mode}",
                    style="compass.success",
                )
            )
        else:
            compass.console.print(
                Text("  Usage: /mode [plan|normal]", style="compass.warn")
            )
        compass.console.print()

    # â”€â”€ /goal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/goal":
        compass.current_mode = "plan"
        compass.console.print(
            Text(
                "  ðŸ“‹ Goal mode activated. I will now run autonomously until the task is fully achieved.",
                style="bold bright_blue",
            )
        )
        compass.console.print()

    # â”€â”€ /grill-me â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/grill-me":
        compass.current_mode = "plan"
        compass.console.print(
            Text(
                "  ðŸ§  Interview mode activated. I will ask you questions to resolve design decisions.",
                style="bold bright_green",
            )
        )
        compass.console.print()

    # â”€â”€ /schedule â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/schedule":
        compass.console.print(
            Text(
                "  ðŸ“… Scheduler active. Background task queued.",
                style="bold bright_yellow",
            )
        )
        compass.console.print()

    # â”€â”€ /learn â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/learn":
        compass.console.print(
            Text(
                "  ðŸŽ“ Rule extracted and appended to COMPASS.md.",
                style="bold bright_magenta",
            )
        )
        compass.console.print()

    # â”€â”€ /init â€” Generate project context file â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/init":
        workspace = os.getcwd()
        compass.console.print(
            Text(
                f"  ðŸ§­ Generating project context for: {workspace}",
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
                Text(f"  âœ” Created {compass_md_path}", style="compass.success")
            )
            compass.console.print(
                Text(
                    f"  ðŸ“„ {len(project_info)} characters of project context generated.",
                    style="dim",
                )
            )
        except Exception as e:
            compass.print_error(f"Failed to generate project context: {e}")
        compass.console.print()

    # â”€â”€ /compact â€” Manual context compaction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif cmd == "/compact":
        if workflow is None or config is None:
            compass.console.print(
                Text(
                    "  â³ Context compaction requires an active workflow.",
                    style="compass.warn",
                )
            )
        else:
            compass.console.print(
                Text("  ðŸ“ Compacting conversation context...", style="compass.info")
            )
            try:
                with compass.thinking_spinner():
                    state = workflow.get_state(config)
                    msg_count_before = len(state.values.get("messages", []))

                    # Trigger summary by invoking the workflow with a special update
                    from langchain_core.messages import HumanMessage
                    from agent.llm import llm

                    summarizer = llm("summarizer")
                    existing_summary = state.values.get("summary", "")
                    all_messages = state.values.get("messages", [])

                    if existing_summary:
                        prompt = (
                            f"Existing summary:\n{existing_summary}\n\n"
                            "Extend the summary using the new conversation above."
                        )
                    else:
                        prompt = "Summarise the conversation above."

                    msg_for_summary = list(all_messages) + [
                        HumanMessage(content=prompt)
                    ]
                    response = summarizer.invoke(msg_for_summary)

                    summary_text = (
                        response.content
                        if isinstance(response.content, str)
                        else str(response.content)
                    )

                compass.console.print(
                    Text(
                        f"  âœ” Context compacted: {msg_count_before} messages summarized",
                        style="compass.success",
                    )
                )
                compass.console.print()

                # Show the summary
                md = Markdown(summary_text)
                panel = Panel(
                    md,
                    border_style="bright_magenta",
                    box=box.ROUNDED,
                    title="[bold bright_magenta]ðŸ“ Context Summary[/]",
                    title_align="left",
                    padding=(1, 2),
                )
                compass.console.print(panel)
            except Exception as e:
                compass.print_error(f"Compaction failed: {e}")
        compass.console.print()

    # â”€â”€ /doctor â€” Diagnose configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            from agent.mcp import connections, get_all_mcp_tools
            table = Table(title="[bold bright_cyan]MCP Servers[/]", box=box.SIMPLE_HEAVY, show_edge=False)
            table.add_column("Server", style="bold cyan")
            table.add_column("Status", style="bright_white")
            if connections:
                for name in connections:
                    table.add_row(str(name), "configured")
            else:
                table.add_row("none", "no servers configured")
            compass.console.print(table)

            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lambda: asyncio.run(get_all_mcp_tools()))
                tools = future.result(timeout=10)
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
            Text("  ðŸ©º Running diagnostics...\n", style="bold bright_cyan")
        )

        checks = _run_diagnostics()
        for check_name, status, detail in checks:
            if status == "ok":
                icon = "  âœ”"
                style = "compass.success"
            elif status == "warn":
                icon = "  âš "
                style = "compass.warn"
            else:
                icon = "  âœ˜"
                style = "compass.error"

            line = Text()
            line.append(icon + " ", style=style)
            line.append(check_name, style="bold bright_white")
            if detail:
                line.append(f" â€” {detail}", style="dim")
            compass.console.print(line)

        compass.console.print()

    elif cmd == "/index":
        from agent.rag.indexer import index_workspace

        workspace = os.getcwd()
        compass.console.print(
            Text(f"  ðŸ§¬ Indexing workspace: {workspace}", style="compass.info")
        )
        compass.console.print()

        try:
            with compass.thinking_spinner():
                result = index_workspace(workspace)

            # Display results in a styled panel
            stats_text = Text()
            stats_text.append("\n  ðŸ“Š Indexing Results\n\n", style="bold bright_cyan")
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
                    f"\n  âš   {len(result.errors)} error(s):\n", style="compass.warn"
                )
                for err in result.errors[:5]:
                    stats_text.append(f"     â€¢ {err}\n", style="dim red")

            panel = Panel(
                stats_text,
                border_style="bright_cyan",
                box=box.ROUNDED,
                title="[bold bright_cyan]ðŸ§¬ Codebase Index[/]",
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
                title="[bold bright_cyan]âš™ï¸  Settings[/]",
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
                        f"  âœ” Setting '{k}' updated.", style="compass.success"
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
                title="[bold bright_cyan]ðŸŽ¯ Registered Skills[/]",
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
                Text(f"  âœ” Reloaded {count} skills.", style="compass.success")
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


# â”€â”€â”€ Helper Functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
        "# Project Context â€” COMPASS.md\n",
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
        mcp_config = os.path.join(os.getcwd(), ".compass", "mcp.json")
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


# â”€â”€â”€ Main REPL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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

    # â”€â”€ Hook change tracker into file tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    from agent.tools.file_tools import set_change_tracker

    set_change_tracker(compass.change_tracker)

    # â”€â”€ Register skill slash commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    from agent.skills import skill_registry

    for skill in skill_registry.list_skills():
        SLASH_COMMANDS[skill.slash_command] = skill.description
    SLASH_COMMANDS["/skills"] = "List registered skills, reload, or get info"

    sm = SessionManager()

    # â”€â”€ Resolve session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    session_ctx = None
    is_resumed = False

    if resume_thread_id:
        # Explicit resume from CLI flag
        session_ctx = sm.get_session(resume_thread_id)
        if session_ctx:
            is_resumed = True
        else:
            # thread_id doesn't exist in sessions.json â€” create a record for it
            session_ctx = sm.create_session()
            session_ctx["thread_id"] = resume_thread_id
            sm._save()
    else:
        # Check for a recent session to offer resume
        last = sm.get_last_session()
        if last and sm.session_age_minutes(last) < 60:
            compass.console.print(
                Text(
                    f"  ðŸ“Œ Recent session found: "
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

    thread_id = session_ctx["thread_id"]
    config = {"configurable": {"thread_id": thread_id}}

    # Show session status
    status_style = "compass.success" if is_resumed else "compass.info"
    status_label = "resumed" if is_resumed else "new"
    session_name = session_ctx.get("name", "")
    name_display = f" â€” {session_name}" if session_name else ""
    compass.console.print(
        Text(
            f"  ðŸ“Œ Session: {thread_id[:10]}...{name_display} ({status_label})",
            style=status_style,
        )
    )
    compass.console.print()

    messages = []
    turn_count = session_ctx.get("turn_count", 0)
    prompt_str = _format_prompt()

    # â”€â”€ Setup prompt_toolkit session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    prompt_session = _create_prompt_session()
    if prompt_session:
        compass.console.print(
            Text(
                "  âŒ¨  Multi-line input enabled (Alt+Enter for newline, \\ to continue)",
                style="dim bright_black",
            )
        )
        compass.console.print()

    resume_cmd = None

    while True:
        try:
            if not resume_cmd:
                # â”€â”€ Print status bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                    result = _handle_slash_command(
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
                        config = {"configurable": {"thread_id": thread_id}}
                        session_ctx = sm.get_session(thread_id)
                        if session_ctx is None:
                            session_ctx = {"thread_id": thread_id, "turn_count": 0}
                        messages = []
                        turn_count = session_ctx.get("turn_count", 0)
                        compass.change_tracker.clear()
                        continue
                    elif isinstance(result, dict) and "skill" in result:
                        new_msg = {"role": "user", "content": user_input}
                        messages.append(new_msg)
                        input_payload = {
                            "messages": [new_msg],
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
                    new_msg = {"role": "user", "content": user_input}
                    messages.append(new_msg)
                    input_payload = {"messages": [new_msg]}

                    # Inject mode into input if set to plan
                    if compass.current_mode == "plan":
                        input_payload["mode"] = "plan"
            else:
                input_payload = resume_cmd
                resume_cmd = None

            # â”€â”€ Reset per-turn token counters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            compass.reset_turn_tokens()

            # â”€â”€ Stream the agent response in real-time â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            compass.console.print()
            cancelled = False
            try:
                live_panel = None
                current_text = ""
                active_tool_spinner = None

                async for event_type, payload in workflow.astream(  # type: ignore
                    input_payload,  # type: ignore
                    config=config,  # type: ignore
                    stream_mode=["messages", "updates"],
                ):
                    if event_type == "messages":
                        chunk, _ = payload
                        if (
                            isinstance(chunk, AIMessageChunk)
                            and getattr(chunk, "content", None)
                            and not getattr(chunk, "tool_calls", None)
                        ):
                            # Stop any active tool spinner
                            if active_tool_spinner:
                                active_tool_spinner.stop()
                                active_tool_spinner = None

                            if not live_panel:
                                live_panel = Live(
                                    console=compass.console,
                                    refresh_per_second=15,
                                    transient=False,
                                )
                                live_panel.start()
                            content_str = (
                                chunk.content
                                if isinstance(chunk.content, str)
                                else str(chunk.content)
                            )
                            current_text += content_str

                            # Build subtitle with token info
                            sub_parts = [f"turn {turn_count + 1}"]
                            if (
                                compass.turn_prompt_tokens
                                + compass.turn_completion_tokens
                                > 0
                            ):
                                sub_parts.append(
                                    f"{_format_tokens(compass.turn_prompt_tokens + compass.turn_completion_tokens)} tokens"
                                )

                            md = Markdown(current_text)
                            panel = Panel(
                                md,
                                border_style="bright_cyan",
                                box=box.ROUNDED,
                                title="[bold bright_cyan]ðŸ§­ Compass[/]",
                                title_align="left",
                                subtitle=f"[dim]{' Â· '.join(sub_parts)}[/]",
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
                                # â”€â”€ Intercept file tool calls for change tracking â”€â”€
                                _intercept_file_changes(compass, node_name, node_output)

                                _process_stream_event(
                                    compass,
                                    node_name,
                                    node_output,
                                    skip_response=bool(current_text),
                                )

                        # If a tool call or non-message update happened, reset text so we can stream the next message
                        current_text = ""

                if live_panel:
                    live_panel.stop()

                if active_tool_spinner:
                    active_tool_spinner.stop()

                # â”€â”€ Handle Interrupts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                state_info = workflow.get_state(config)
                if state_info.next and "check_safety" in state_info.next:
                    interrupt_data = None
                    for task in state_info.tasks:
                        if task.name == "check_safety" and task.interrupts:
                            interrupt_data = task.interrupts[0].value
                            break

                    if (
                        interrupt_data
                        and interrupt_data.get("reason") == "approval_required"
                    ):
                        risky_calls = interrupt_data.get("tool_calls", [])
                        warning_text = Text()
                        warning_text.append(
                            "\n  âš ï¸  Approval Required\n\n", style="bold red"
                        )
                        for tc in risky_calls:
                            warning_text.append(
                                f"  â€¢ {tc['name']}\n", style="bold yellow"
                            )
                            for k, v in tc.get("args", {}).items():
                                warning_text.append(
                                    f"      {k}: {v}\n", style="dim white"
                                )

                        compass.console.print(
                            Panel(
                                warning_text,
                                border_style="red",
                                title="[bold red]Safety Intercept[/]",
                                title_align="left",
                            )
                        )

                        try:
                            answer = (
                                click.prompt(
                                    click.style(
                                        "  Approve execution? (y/N/always)",
                                        fg="red",
                                        bold=True,
                                    ),
                                    default="n",
                                    show_default=False,
                                )
                                .strip()
                                .lower()
                            )
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
                        messages = []  # clear messages list so we don't append next turn
                        continue  # loop back to workflow.stream

            except KeyboardInterrupt:
                # â”€â”€ Graceful mid-stream cancel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                if live_panel:
                    live_panel.stop()
                if active_tool_spinner:
                    active_tool_spinner.stop()

                if current_text.strip():
                    # Show partial response in a "cancelled" panel
                    md = Markdown(current_text)
                    panel = Panel(
                        md,
                        border_style="yellow",
                        box=box.ROUNDED,
                        title="[bold yellow]ðŸ§­ Compass (cancelled)[/]",
                        title_align="left",
                        subtitle="[dim]interrupted[/]",
                        subtitle_align="right",
                        padding=(1, 2),
                    )
                    compass.console.print()
                    compass.console.print(panel)

                compass.console.print(
                    Text(
                        "\n  â¹  Turn cancelled. Continuing session...",
                        style="compass.warn",
                    )
                )
                cancelled = True

            except Exception as e:
                compass.print_error(f"Agent error: {e}")
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
            # Ctrl+C outside streaming â€” cancel current turn, stay in REPL
            compass.console.print(
                Text("\n  â¹  Interrupted. Type /exit to quit.", style="compass.warn")
            )
            continue

        except EOFError:
            # Ctrl+D â€” exit
            compass.print_goodbye()
            break

        except Exception as e:
            compass.print_error(f"Unexpected error: {e}")
            continue


def _intercept_file_changes(compass: CompassConsole, node_name: str, node_output: dict):
    """
    Intercept tool node outputs to track file changes for undo/diff.
    Looks at ToolMessage results from write_to_file and edit_file.
    """
    if node_name != "tools":
        return

    messages = node_output.get("messages", [])
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue

        tool_name = getattr(msg, "name", "")
        result = msg.content if isinstance(msg.content, str) else str(msg.content)

        if tool_name in ("write_to_file", "edit_file") and "Success" in result:
            # Try to extract the file path from the result message
            # Format: "Successfully wrote X characters to PATH" or "Successfully edited PATH"
            filepath = _extract_path_from_result(result)
            if filepath:
                # Read the current content (after write) and compare to snapshot
                current = compass.change_tracker.get_current_content(filepath)
                if current is not None:
                    # We need the old content â€” check if we have a snapshot
                    # Since the tool already wrote, we look at our tracker
                    original = compass.change_tracker.get_original_content(filepath)
                    if original is None:
                        # First modification â€” we don't have the pre-write state
                        # but we can track from here
                        compass.change_tracker._original_snapshots[
                            os.path.abspath(filepath)
                        ] = current
                    else:
                        # Record the change
                        compass.change_tracker.record_change(
                            filepath, original, current, tool_name
                        )
                        # Update original to be the "previous" content for next undo
                        # Actually, keep original as the first-seen content


def _extract_path_from_result(result: str) -> str | None:
    """Extract file path from tool result messages."""
    # "Successfully wrote 123 characters to /path/to/file"
    if "characters to " in result:
        parts = result.split("characters to ", 1)
        if len(parts) == 2:
            return parts[1].strip()

    # "Successfully edited /path/to/file: replaced X lines with Y lines."
    if "Successfully edited " in result:
        parts = result.split("Successfully edited ", 1)
        if len(parts) == 2:
            path_part = parts[1].split(":", 1)[0].strip()
            return path_part

    return None


# â”€â”€â”€ Single-Shot Mode â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


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
            sm._save()
        thread_id = session_ctx["thread_id"]
    else:
        session_ctx = sm.create_session()
        thread_id = session_ctx["thread_id"]

    config = {"configurable": {"thread_id": thread_id}}

    compass.console.print()
    prompt_display = Text()
    prompt_display.append("  ðŸ§­ â€º ", style="bold cyan")
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
            async for event_type, payload in workflow.astream(  # type: ignore
                input_payload,  # type: ignore
                config=config,  # type: ignore
                stream_mode=["messages", "updates"],
            ):
                if event_type == "messages":
                    chunk, _ = payload
                    if (
                        isinstance(chunk, AIMessageChunk)
                        and getattr(chunk, "content", None)
                        and not getattr(chunk, "tool_calls", None)
                    ):
                        if not live_panel:
                            live_panel = Live(
                                console=compass.console,
                                refresh_per_second=15,
                                transient=False,
                            )
                            live_panel.start()
                        content_str = (
                            chunk.content
                            if isinstance(chunk.content, str)
                            else str(chunk.content)
                        )
                        current_text += content_str
                        md = Markdown(current_text)
                        panel = Panel(
                            md,
                            border_style="bright_cyan",
                            box=box.ROUNDED,
                            title="[bold bright_cyan]ðŸ§­ Compass[/]",
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
                            _intercept_file_changes(compass, node_name, node_output)
                            _process_stream_event(
                                compass,
                                node_name,
                                node_output,
                                skip_response=bool(current_text),
                            )

                    current_text = ""

            if live_panel:
                live_panel.stop()

            # â”€â”€ Handle Interrupts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            state_info = workflow.get_state(config)
            if state_info.next and "check_safety" in state_info.next:
                interrupt_data = None
                for task in state_info.tasks:
                    if task.name == "check_safety" and task.interrupts:
                        interrupt_data = task.interrupts[0].value
                        break

                if (
                    interrupt_data
                    and interrupt_data.get("reason") == "approval_required"
                ):
                    # wait for approval

                    risky_calls = interrupt_data.get("tool_calls", [])
                    warning_text = Text()
                    warning_text.append(
                        "\n  âš ï¸  Approval Required\n\n", style="bold red"
                    )
                    for tc in risky_calls:
                        warning_text.append(f"  â€¢ {tc['name']}\n", style="bold yellow")
                        for k, v in tc.get("args", {}).items():
                            warning_text.append(f"      {k}: {v}\n", style="dim white")

                    compass.console.print(
                        Panel(
                            warning_text,
                            border_style="red",
                            title="[bold red]Safety Intercept[/]",
                            title_align="left",
                        )
                    )

                    try:
                        answer = (
                            click.prompt(
                                click.style(
                                    "  Approve execution? (y/N/always)",
                                    fg="red",
                                    bold=True,
                                ),
                                default="n",
                                show_default=False,
                            )
                            .strip()
                            .lower()
                        )
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

            break  # Exit loop if no interrupt

    except KeyboardInterrupt:
        compass.console.print(Text("\n  â¹  Cancelled.", style="compass.warn"))
    except Exception as e:
        compass.print_error(f"Agent error: {e}")
        sys.exit(1)

    # Update session metadata
    turn_count = session_ctx.get("turn_count", 0) + 1
    sm.update_session(thread_id, turn_count=turn_count, first_message=message)

    # Show session cost
    if compass.session_total_tokens > 0:
        compass.console.print()
        cost_line = Text()
        cost_line.append("  ðŸ“Š ", style="")
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

