"""seedance status / watch / list / cancel — task management commands."""
from __future__ import annotations

import typer

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..commands.generate import _watch_task
from ..console import console, err, info, ok, warn
from ..formatters import tasks_table

app = typer.Typer(help="Manage video generation tasks.")


@app.command("status")
def status(
    task_id: str = typer.Argument(..., help="Task ID to check."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Check the current status of a task."""
    client = SeedanceClient(profile=profile)
    try:
        result = client.check_task(task_id)
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1) from exc

    console.print()
    if result.succeeded:
        ok(f"[task_id]{task_id}[/task_id]  status=[green]succeeded[/green]")
        facts = [
            f"{label}={value}"
            for label, value in (
                ("duration", f"~{result.duration}s" if result.duration is not None else None),
                ("ratio", result.ratio),
                ("resolution", result.resolution),
                ("format", result.output_format),
            )
            if value
        ]
        if facts:
            info("  ".join(facts))
        console.print(f"\n  [url]{result.video_url}[/url]\n")
    elif result.terminal:
        err(f"[task_id]{task_id}[/task_id]  status=[red]{result.status}[/red]")
        if result.error:
            info(f"Error: {result.error}")
        if result.task_type_constraint_error:
            warn(
                "The parameters clashed with the task type the model inferred from the "
                "prompt. Seedance 2.5 locks the aspect ratio to the source for first-frame, "
                "edit, and extend tasks, and locks the duration to the source for edits. "
                "Resubmit with 'seedance edit' or 'seedance extend', which set these for you."
            )
        raise typer.Exit(1)
    else:
        info(f"[task_id]{task_id}[/task_id]  status=[yellow]{result.status}[/yellow]")
        console.print(f"\n  Watch live:  [cyan]seedance watch {task_id}[/cyan]\n")


@app.command("watch")
def watch(
    task_id: str = typer.Argument(..., help="Task ID to watch."),
    poll_interval: int = typer.Option(10, "--poll-interval", help="Seconds between status checks."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Stream live progress for a task until it completes."""
    client = SeedanceClient(profile=profile)
    _watch_task(client, task_id, poll_interval)


@app.command("list")
def list_tasks(
    page: int = typer.Option(1, "--page", help="Page number."),
    limit: int = typer.Option(10, "--limit", "-n", help="Results per page (max 50)."),
    status_filter: str = typer.Option("", "--status", "-s", help="Filter by status."),
    model_filter: str = typer.Option("", "--model", "-m", help="Filter by model: 2.5 | 2.0 | 2.0-fast, or a full model ID."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """List recent video generation tasks."""
    client = SeedanceClient(profile=profile)
    try:
        data = client.list_tasks(page, limit, status_filter, model_filter)
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1) from exc

    console.print()
    tasks_table(data["tasks"])
    console.print(
        f"\n  Showing {len(data['tasks'])} of {data['total']} tasks  "
        f"(page {data['page_num']})\n"
    )


@app.command("cancel")
def cancel(
    task_id: str = typer.Argument(..., help="Task ID to cancel."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Cancel a queued or running task."""
    if not yes:
        typer.confirm(f"Cancel task '{task_id}'?", abort=True)

    client = SeedanceClient(profile=profile)
    try:
        client.cancel_task(task_id)
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1) from exc

    ok(f"Cancellation requested for [task_id]{task_id}[/task_id].")
