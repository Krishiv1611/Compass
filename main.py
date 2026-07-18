import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

"""
Compass â€” AI Coding Agent CLI Entry Point.

Usage:
    python main.py              â†’ Interactive REPL (new session)
    python main.py -r           â†’ Resume last session
    python main.py -s abc123    â†’ Resume session by ID prefix
    python main.py -m "query"   â†’ Single-shot mode (new session)
    python main.py -r -m "msg"  â†’ Single-shot, resume last session
"""

import os
import click
from agent.sessions import SessionManager
from agent.ui.tui import compass_repl, run_single


@click.command()
@click.option(
    "-m",
    "--message",
    type=str,
    default=None,
    help="Run a single message and exit (non-interactive mode).",
)
@click.option(
    "-r",
    "--resume",
    is_flag=True,
    default=False,
    help="Resume the most recent session.",
)
@click.option(
    "-w",
    "--workspace",
    "workspace",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Workspace directory to run Compass from.",
)
@click.option(
    "-s",
    "--session",
    "session_id",
    type=str,
    default=None,
    help="Resume a specific session by thread_id or prefix.",
)
def cli(message: str | None, resume: bool, workspace: str | None, session_id: str | None):
    """Compass - AI Coding Agent powered by LangGraph."""

    if workspace:
        os.chdir(workspace)

    sm = SessionManager()
    resume_thread_id = None

    # Resolve which session to resume
    if session_id:
        sess = sm.get_session(session_id)
        if sess:
            resume_thread_id = sess["thread_id"]
        else:
            click.echo(f"Error: No session found matching '{session_id}'.")
            raise SystemExit(1)
    elif resume:
        sess = sm.get_last_session()
        if sess:
            resume_thread_id = sess["thread_id"]
        else:
            click.echo("No previous sessions found. Starting a new session.")

    if message:
        asyncio.run(run_single(message, resume_thread_id=resume_thread_id))
    else:
        asyncio.run(compass_repl(resume_thread_id=resume_thread_id))


if __name__ == "__main__":
    cli()

