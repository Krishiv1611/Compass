"""
Compass — AI Coding Agent CLI Entry Point.

Usage:
    python main.py              → Interactive REPL (new session)
    python main.py -r           → Resume last session
    python main.py -s abc123    → Resume session by ID prefix
    python main.py -m "query"   → Single-shot mode (new session)
    python main.py -r -m "msg"  → Single-shot, resume last session
"""

import click


@click.command()
@click.option(
    "-m", "--message",
    type=str,
    default=None,
    help="Run a single message and exit (non-interactive mode).",
)
@click.option(
    "-r", "--resume",
    is_flag=True,
    default=False,
    help="Resume the most recent session.",
)
@click.option(
    "-s", "--session",
    "session_id",
    type=str,
    default=None,
    help="Resume a specific session by thread_id or prefix.",
)
def cli(message: str | None, resume: bool, session_id: str | None):
    """Compass - AI Coding Agent powered by LangGraph."""
    from sessions import SessionManager
    from ui.tui import compass_repl, run_single

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
        run_single(message, resume_thread_id=resume_thread_id)
    else:
        compass_repl(resume_thread_id=resume_thread_id)


if __name__ == "__main__":
    cli()
