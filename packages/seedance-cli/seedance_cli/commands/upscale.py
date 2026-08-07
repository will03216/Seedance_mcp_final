"""seedance upscale — enhance/upscale an existing video via AI MediaKit."""
from __future__ import annotations

import time

import typer
from rich.live import Live
from rich.spinner import Spinner

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..console import console, err, info, ok


def upscale(
    video_url: str = typer.Argument(..., help="Public HTTP(S) URL of the source video."),
    tool_version: str = typer.Option("standard", "--tool-version", help="standard | professional."),
    scene: str = typer.Option("", "--scene", help="standard only: common|ugc|short_series|aigc|old_film."),
    resolution: str = typer.Option("", "--resolution", "-r", help="Target: 240p..1080p|2k|4k (excl. --resolution-limit)."),
    resolution_limit: int = typer.Option(0, "--resolution-limit", help="Short-side px cap [128,2160] (excl. --resolution)."),
    bitrate_level: str = typer.Option("", "--bitrate-level", help="low | medium | high."),
    fps: float = typer.Option(0, "--fps", help="Target frame rate [15,120]; 0 keeps source."),
    client_token: str = typer.Option("", "--client-token", help="Explicit idempotency token (≤64 ASCII)."),
    force_new: bool = typer.Option(False, "--force-new", help="Force a fresh task for identical input."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Auto-poll until the enhanced video is ready."),
    poll_interval: int = typer.Option(10, "--poll-interval", help="Seconds between status checks (--watch mode)."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Submit an AI MediaKit video-enhancement (upscale) task.

    Requires MEDIAKIT_API_KEY (separate from ARK_API_KEY). Idempotent by default:
    identical parameters reuse the same task for 24h. Use --watch to poll until ready.
    """
    client = SeedanceClient(profile=profile)
    console.print()

    with Live(
        Spinner("dots", text="  Submitting upscale task…", style="cyan"),
        console=console, refresh_per_second=8, transient=True,
    ):
        try:
            result = client.submit_video_enhance(
                video_url,
                tool_version=tool_version,
                scene=scene or None,
                resolution=resolution or None,
                resolution_limit=resolution_limit or None,
                bitrate_level=bitrate_level or None,
                fps=fps or None,
                client_token=client_token or None,
                force_new=force_new,
            )
        except SeedanceError as exc:
            err(str(exc))
            raise typer.Exit(1) from exc

    if result.idempotent_hit:
        ok(f"Idempotent hit — reused task  [task_id=[task_id]{result.task_id}[/task_id]]")
    else:
        ok(f"Upscale task submitted  [task_id=[task_id]{result.task_id}[/task_id]]")

    if not watch:
        console.print(
            f"\n  Poll status:  [cyan]seedance upscale-status {result.task_id}[/cyan]\n"
        )
        return

    _watch_task(client, result.task_id, poll_interval)


def upscale_status(
    task_id: str = typer.Argument(..., help="Upscale task ID from `seedance upscale`."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Check the status of an AI MediaKit upscale task."""
    client = SeedanceClient(profile=profile)
    try:
        result = client.check_enhance_task(task_id)
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1) from exc

    console.print()
    if result.video_url:
        ok(f"Status: [success]{result.status}[/success]")
        console.print(f"\n  [url]{result.video_url}[/url]")
        console.print("  [dim]Valid for 24 hours — download promptly.[/dim]\n")
    elif result.status == "failed":
        err(f"Status: failed — {result.error or 'unknown error'}")
        raise typer.Exit(1)
    else:
        info(f"Status: {result.status} — still processing. Poll again shortly.")
        console.print()


def _watch_task(client: SeedanceClient, task_id: str, poll_interval: int) -> None:
    """Poll an upscale task until terminal, streaming progress."""
    console.print(f"\n  Watching [task_id]{task_id}[/task_id] (polling every {poll_interval}s)…\n")
    elapsed = 0

    with Live(console=console, refresh_per_second=4, transient=True) as live:
        while True:
            live.update(Spinner("dots", text=f"  Enhancing… [{elapsed}s elapsed]", style="cyan"))
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                status = client.check_enhance_task(task_id)
            except SeedanceError as exc:
                err(f"Poll error: {exc}")
                continue

            if status.succeeded:
                live.stop()
                console.print()
                ok(f"Enhanced video ready!  [{elapsed}s]")
                console.print(f"\n  [url]{status.video_url}[/url]")
                console.print("  [dim]This URL is valid for 24 hours — download promptly.[/dim]\n")
                return

            if status.terminal:
                live.stop()
                err(f"Task ended with status '{status.status}'.")
                if status.error:
                    info(f"Error details: {status.error}")
                raise typer.Exit(1)
