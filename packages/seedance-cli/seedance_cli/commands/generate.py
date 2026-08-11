"""seedance generate — submit video generation jobs."""
from __future__ import annotations

import time

import typer
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..console import console, err, info, ok
from ..formatters import steps_panel

app = typer.Typer(help="Generate videos with Seedance.")


@app.callback(invoke_without_command=True)
def generate(
    ctx: typer.Context,
    prompt: str = typer.Option(..., "--prompt", "-p", help="Scene/motion description."),
    image: list[str] | None = typer.Option(None, "--image", "-i", help="Reference image URL (auto-uploaded to asset library). Repeatable, up to 30 on 2.5. Tag as @Image1…"),
    video: list[str] | None = typer.Option(None, "--video", help="Reference video URL (motion/camera rhythm). Repeatable, up to 10 on 2.5. Tag as @Video1…"),
    audio_ref: list[str] | None = typer.Option(None, "--audio-ref", help="Reference audio URL (lip-sync/beat, MP3/WAV). Repeatable, up to 10 on 2.5. Tag as @Audio1…"),
    first_frame: str = typer.Option("", "--first-frame", help="URL of the exact starting frame."),
    last_frame: str = typer.Option("", "--last-frame", help="URL of the exact ending frame (requires --first-frame)."),
    ratio: str = typer.Option("auto", "--ratio", "-r", help="Aspect ratio (e.g. 9:16, 1:1, 16:9), or 'auto'. First-frame jobs on 2.5 require 'adaptive'."),
    duration: int = typer.Option(5, "--duration", "-d", help="Length in seconds: 4–30 on 2.5, 4–15 on 2.0. Use --duration=-1 to let the model choose."),
    resolution: str = typer.Option("720p", "--resolution", help="Output quality: 480p | 720p (2.0 also allows 1080p)."),
    audio: bool = typer.Option(False, "--audio", help="Generate a matching audio track."),
    fast: bool = typer.Option(False, "--fast", help="Use the faster/cheaper variant (always Seedance 2.0 Fast)."),
    model: str = typer.Option("", "--model", "-m", help="Model: 2.5 (default) | 2.0 | 2.0-fast. Use 2.0 for 1080p."),
    output_format: str = typer.Option("", "--output-format", help="Container format: mp4 (default) | mov. Seedance 2.5 only."),
    seed: int | None = typer.Option(None, "--seed", help="Random seed for reproducibility."),
    camerafixed: bool = typer.Option(False, "--camerafixed", help="Fix camera — no panning or zooming (Seedance 1.5/1.0 pro only)."),
    task_type: str = typer.Option("auto", "--task-type", help="Declare the omni-reference subtask: auto (default) | reference | edit | extend. Declaring it validates at submit time, so a violation fails immediately and no task is created."),
    priority: int = typer.Option(0, "--priority", help="Queue priority 0–9; higher jumps ahead of lower-priority queued tasks."),
    callback_url: str = typer.Option("", "--callback-url", help="URL to POST task status changes to, instead of polling."),
    return_last_frame: bool = typer.Option(False, "--return-last-frame", help="Also return the final frame as a PNG, for chaining into the next clip."),
    execution_expires_after: int = typer.Option(0, "--expires-after", help="Task timeout in seconds (3600–259200). Default 48h; expired tasks end with status 'expired'."),
    safety_identifier: str = typer.Option("", "--safety-identifier", help="Opaque end-user identifier for policy enforcement (max 64 chars)."),
    asset_group: str = typer.Option("", "--asset-group", help="Reuse an existing asset group ID."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Auto-poll until the video is ready."),
    poll_interval: int = typer.Option(10, "--poll-interval", help="Seconds between status checks (--watch mode)."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Submit a Seedance video generation job.

    Handles the full pipeline automatically:
      • Plain HTTPS --image URLs → uploaded to asset library before generation
      • asset:// refs → used directly, no upload
      • No image → text-to-video

    To modify an existing clip, use `seedance edit` or `seedance extend` instead.

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
                "create_asset_group": "Creating asset group…",
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
                image_urls=image or None,
                first_frame_url=first_frame,
                last_frame_url=last_frame,
                video_urls=video or None,
                audio_urls=audio_ref or None,
                ratio=ratio,
                duration=duration,
                resolution=resolution,
                generate_audio=audio,
                fast_mode=fast,
                model=model,
                output_format=output_format,
                seed=seed,
                camerafixed=camerafixed,
                task_type=task_type,
                priority=priority or None,
                callback_url=callback_url,
                return_last_frame=return_last_frame,
                execution_expires_after=execution_expires_after or None,
                safety_identifier=safety_identifier,
                asset_group_id=asset_group,
                on_progress=on_progress,
            )
        except SeedanceError as exc:
            err(str(exc))
            raise typer.Exit(1) from exc

    # --- Print pipeline steps ---
    steps_panel(result.steps)
    console.print()
    ok(
        f"Job submitted  [task_id=[task_id]{result.task_id}[/task_id]  "
        f"mode={result.mode}  model={result.model}]"
    )

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
