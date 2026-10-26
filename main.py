import asyncio
import os
import sys
import click
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

"""
Compass — AI Developer Workbench Entry Point.

Usage:
    python main.py                      → Start Compass Web backend on port 8000
    python main.py -p 8080              → Start Compass Web backend on custom port
    python main.py -m "Write a tests"   → Run single-shot headless query
    python main.py serve --reload       → Run dev server with auto-reload
"""


async def run_headless_message(message: str, workspace: str | None = None):
    """Execute a single prompt headless through the shared agent runtime."""
    from agent.runtime.runner import run_agent_stream
    from agent.runtime.events import StreamEventType
    from agent.workspace import WorkspaceContext

    ws_ctx = WorkspaceContext(root=workspace or os.getcwd())
    click.echo(f"Running Compass in: {ws_ctx.root}\nPrompt: {message}\n")

    async for event in run_agent_stream(
        message=message,
        workspace_context=ws_ctx,
        execution_target="web",
    ):
        if event.type == StreamEventType.TOKEN:
            click.echo(event.content, nl=False)
        elif event.type == StreamEventType.STATUS:
            click.echo(f"\n[status: {event.content}]")
        elif event.type == StreamEventType.ERROR:
            click.echo(f"\n[error: {event.content}]", err=True)
    click.echo("\n")


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "-m",
    "--message",
    type=str,
    default=None,
    help="Run a single message and exit (headless mode).",
)
@click.option(
    "-w",
    "--workspace",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Workspace directory to run Compass from.",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Host to bind the web server to.",
)
@click.option(
    "-p",
    "--port",
    type=int,
    default=8000,
    help="Port to bind the web server to.",
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable auto-reload for development.",
)
def cli(ctx, message: str | None, workspace: str | None, host: str, port: int, reload: bool):
    """Compass - AI Developer Workbench powered by FastAPI & LangGraph."""
    if ctx.invoked_subcommand is not None:
        return

    if workspace:
        os.chdir(workspace)

    load_dotenv()

    if message:
        asyncio.run(run_headless_message(message, workspace=workspace))
    else:
        import uvicorn
        click.echo(f"Starting Compass Web Server on http://{host}:{port} ...")
        uvicorn.run("backend.main:app", host=host, port=port, reload=reload)


@cli.command("serve")
@click.option("--host", type=str, default="127.0.0.1", help="Host to bind to.")
@click.option("-p", "--port", type=int, default=8000, help="Port to bind to.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
def serve_command(host: str, port: int, reload: bool):
    """Start the Compass Web Server."""
    import uvicorn
    load_dotenv()
    click.echo(f"Starting Compass Web Server on http://{host}:{port} ...")
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
