"""
Compass Diff Renderer — Rich-powered unified diff display.

Renders beautiful syntax-highlighted diffs for file changes,
used by the TUI to show what write_to_file / edit_file actually changed.
"""

import difflib
import os

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box


# Max lines to show before collapsing
_MAX_DIFF_LINES = 40


def _generate_unified_diff(
    old_content: str, new_content: str, filepath: str
) -> list[str]:
    """Generate unified diff lines between old and new content."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{os.path.basename(filepath)}",
            tofile=f"b/{os.path.basename(filepath)}",
            lineterm="",
        )
    )
    return diff


def render_diff(
    console: Console,
    filepath: str,
    old_content: str,
    new_content: str,
    tool_name: str = "edit_file",
):
    """
    Render a beautiful unified diff panel to the console.

    Args:
        console: Rich Console instance.
        filepath: Path of the file being modified.
        old_content: Original file content (before edit).
        new_content: New file content (after edit).
        tool_name: The tool that made the change (for header display).
    """
    diff_lines = _generate_unified_diff(old_content, new_content, filepath)

    if not diff_lines:
        status = Text()
        status.append("  ≡ ", style="dim")
        status.append(os.path.basename(filepath), style="bold bright_white")
        status.append(" — no changes", style="dim")
        console.print(status)
        return

    # Count additions/deletions
    additions = sum(
        1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    deletions = sum(
        1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
    )

    # Build styled diff text
    diff_text = Text()
    shown_lines = 0
    truncated = False

    for line in diff_lines:
        if shown_lines >= _MAX_DIFF_LINES:
            truncated = True
            break

        if line.startswith("+++") or line.startswith("---"):
            diff_text.append(line + "\n", style="bold bright_white")
        elif line.startswith("@@"):
            diff_text.append(line + "\n", style="bold cyan")
        elif line.startswith("+"):
            diff_text.append(line + "\n", style="green")
        elif line.startswith("-"):
            diff_text.append(line + "\n", style="red")
        else:
            diff_text.append(line + "\n", style="dim white")
        shown_lines += 1

    if truncated:
        remaining = len(diff_lines) - _MAX_DIFF_LINES
        diff_text.append(
            f"\n  ... {remaining} more lines ...\n", style="dim bright_black"
        )

    # Stats line
    stats = Text()
    stats.append(f"+{additions}", style="bold green")
    stats.append(" / ", style="dim")
    stats.append(f"-{deletions}", style="bold red")

    # File basename for title
    basename = os.path.basename(filepath)

    panel = Panel(
        diff_text,
        border_style="bright_black",
        box=box.ROUNDED,
        title=f"[bold bright_white]📝 {basename}[/]",
        title_align="left",
        subtitle=f"[dim]{stats}[/]",
        subtitle_align="right",
        padding=(0, 1),
    )
    console.print(panel)


def render_diff_summary(console: Console, changes: list[dict]):
    """
    Render a summary table of all file changes in the session.

    Args:
        console: Rich Console instance.
        changes: List of change dicts from ChangeTracker.
    """
    if not changes:
        console.print(Text("  No file changes in this session.", style="dim"))
        return

    from rich.table import Table

    # Group by file: show latest state per file
    file_stats: dict[str, dict] = {}
    for change in changes:
        path = change["path"]
        if path not in file_stats:
            file_stats[path] = {
                "original": change["old_content"],
                "current": change["new_content"],
                "count": 0,
                "tool": change["tool_name"],
            }
        else:
            file_stats[path]["current"] = change["new_content"]
        file_stats[path]["count"] += 1

    table = Table(
        title="[bold bright_cyan]📝 Session File Changes[/]",
        box=box.SIMPLE_HEAVY,
        border_style="bright_black",
        header_style="bold bright_cyan",
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("File", style="bold bright_white", min_width=25)
    table.add_column("+", style="bold green", justify="right")
    table.add_column("-", style="bold red", justify="right")
    table.add_column("Edits", style="dim", justify="right")

    for path, stats in file_stats.items():
        diff_lines = _generate_unified_diff(stats["original"], stats["current"], path)
        adds = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        dels = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )
        table.add_row(
            os.path.basename(path),
            str(adds),
            str(dels),
            str(stats["count"]),
        )

    console.print()
    console.print(table)
    console.print()

    # Render individual diffs
    for path, stats in file_stats.items():
        if stats["original"] != stats["current"]:
            render_diff(console, path, stats["original"], stats["current"])
