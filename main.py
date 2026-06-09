"""
Compass — AI Coding Agent CLI Entry Point.

Usage:
    python main.py              → Interactive REPL
    python main.py -m "query"   → Single-shot mode
"""

import click


@click.command()
@click.option(
    "-m", "--message",
    type=str,
    default=None,
    help="Run a single message and exit (non-interactive mode).",
)
def cli(message: str | None):
    """🧭 Compass — AI Coding Agent powered by LangGraph."""
    from ui.tui import compass_repl, run_single

    if message:
        run_single(message)
    else:
        compass_repl()


if __name__ == "__main__":
    cli()
