"""seedance generate — submit video generation jobs."""
from __future__ import annotations

import time
from typing import Optional

import typer
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..console import console, err, info, ok
from ..formatters import steps_panel

app = typer.Typer(help="Generate videos with Seedance 2.0.")


@app.callback(invoke_without_command=True)
def generate(
    ctx: typer.Context,
    prompt: str = typer.Option(..., "--prompt", "-p", help="Scene/motion description."),
    image: str = typer.Option("", "--image", "-i", help="Reference image URL (auto-uploaded to asset library)."),
    first_frame: str = typer.Option("", "--first-frame", help="URL of the exact starting frame."),
    last_frame: str = typer.Option("", "--last-frame", help="URL of the exact ending frame (requires --first-frame)."),
    ratio: str = typer.Option("16:9", "--ratio", "-r", help="Aspect ratio (e.g. 9:16, 1:1, 16:9)."),
    duration: int = typer.Option(5, "--duration", "-d", help="Length in seconds (4–15)."),
    resolution: str = typer.Option("720p", "--resolution", help="Output quality: 480p | 720p | 1080p."),
    audio: bool = typer.Option(False, "--audio", help="Generate a matching audio track."),
    fast: bool = typer.Option(False, "--fast", help="Use the faster/cheaper model variant."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for reproducibility."),
    camerafixed: bool = typer.Option(False, "--camerafixed", help="Fix camera — no panning or zooming."),
    asset_group: str = typer.Option("", "--asset-group", help="Reuse an existing asset group ID."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Auto-poll until the video is ready."),
    poll_interval: int = typer.Option(10, "--poll-interval", help="Seconds between status checks (--watch mode)."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Submit a Seedance video generation job.

    Handles the full pipeline automatically:
      • Plain HTTPS image_url → uploaded to asset library before generation
      • asset:// ref → used directly, no upload
      • No image → text-to-video

    Use --watch to stream progress until the video is ready.
    Without --watch, prints the task_id and exits immediately.
    """
    if ctx.invoked_subcommand is not None:
        return

    client = SeedanceClient(profile=profile)
    steps_seen: list[tuple[str, str]] = []

    def on_progress(step: str, detail: str) -> None:
        steps_seen.append((step, detail))

    console.print()

    # --- Run the composite generate pipeline with a live spinner ---
    with Live(
        Text("  Starting…", style="dim"),
        console=console,
        refresh_per_second=8,
        transient=True,
    ) as live:
        def _update(msg: str) -> None:
            live.update(Spinner("dots", text=f"  {msg}", style="cyan"))

        original_progress = on_progress

        def on_progress(step: str, detail: str) -> None:  # noqa: F811
            original_progress(step, detail)
            labels = {
                "create_asset_group": f"Creating asset group…",
                "reuse_asset_group": f"Reusing asset group {detail}",
                "asset_poll": f"Uploading image — asset status: {detail.split(':')[-1]}",
                "upload_asset": f"Asset ready: {detail}",
                "submit_job": f"Job submitted: {detail}",
            }
            _update(labels.get(step, step))

        _update("Preparing…")
        try:
            result = client.generate(
                prompt,
                image_url=image,
                first_frame_url=first_frame,
                last_frame_url=last_frame,
                ratio=ratio,
                duration=duration,
                resolution=resolution,
                generate_audio=audio,
                fast_mode=fast,
                seed=seed,
                camerafixed=camerafixed,
                asset_group_id=asset_group,
                on_progress=on_progress,
            )
        except SeedanceError as exc:
            err(str(exc))
            raise typer.Exit(1)

    # --- Print pipeline steps ---
    steps_panel(result.steps)
    console.print()
    ok(f"Job submitted  [task_id=[task_id]{result.task_id}[/task_id]  mode={result.mode}]")

    if not watch:
        console.print(
            f"\n  Poll status:  [cyan]seedance status {result.task_id}[/cyan]\n"
            f"  Watch live:   [cyan]seedance watch {result.task_id}[/cyan]\n"
        )
        return

    # --- --watch mode: poll until done ---
    _watch_task(client, result.task_id, poll_interval)


def _watch_task(client: SeedanceClient, task_id: str, poll_interval: int) -> None:
    """Poll task_id until terminal, streaming progress."""
    console.print(f"\n  Watching [task_id]{task_id}[/task_id] (polling every {poll_interval}s)…\n")
    elapsed = 0

    with Live(console=console, refresh_per_second=4, transient=True) as live:
        while True:
            live.update(
                Spinner("dots", text=f"  Generating… [{elapsed}s elapsed]", style="cyan")
            )
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                status = client.check_task(task_id)
            except SeedanceError as exc:
                err(f"Poll error: {exc}")
                continue

            if status.succeeded:
                live.stop()
                console.print()
                ok(f"Video ready!  [{elapsed}s]")
                console.print(f"\n  [url]{status.video_url}[/url]\n")
                return

            if status.terminal:
                live.stop()
                err(f"Task ended with status '{status.status}'.")
                if status.error:
                    info(f"Error details: {status.error}")
                raise typer.Exit(1)
