"""seedance edit / seedance extend — Seedance 2.5 video-to-video tasks.

Both wrap an existing clip: `edit` changes what is in it, `extend` continues it.
Each task type locks parameters that the generic `generate` path cannot check —
ratio for both, plus duration for edits — so these commands set them and reject
overrides up front rather than letting the API fail the task minutes later.
"""
from __future__ import annotations

import typer

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..console import console, err, ok
from .generate import _watch_task

app = typer.Typer(help="Edit or extend an existing video with Seedance 2.5.")


def _submit(
    *,
    kind: str,
    prompt: str,
    video: list[str],
    image: list[str] | None,
    audio_ref: list[str] | None,
    duration: int | None,
    resolution: str,
    audio: bool,
    output_format: str,
    seed: int | None,
    watch: bool,
    poll_interval: int,
    profile: str,
) -> None:
    client = SeedanceClient(profile=profile)
    console.print()

    try:
        if kind == "edit":
            result = client.submit_video_edit(
                prompt,
                list(video),
                image_urls=image or None,
                audio_urls=audio_ref or None,
                resolution=resolution,
                generate_audio=audio,
                output_format=output_format,
                seed=seed,
            )
        else:
            result = client.submit_video_extend(
                prompt,
                list(video),
                duration=duration if duration is not None else -1,
                image_urls=image or None,
                audio_urls=audio_ref or None,
                resolution=resolution,
                generate_audio=audio,
                output_format=output_format,
                seed=seed,
            )
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1)

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

    _watch_task(client, result.task_id, poll_interval)


def edit(
    prompt: str = typer.Option(..., "--prompt", "-p", help="The edit to perform, e.g. \"Video edit: remove everyone in @Video1 except the protagonist.\""),
    video: list[str] = typer.Option(..., "--video", help="Reference video URL. Repeatable, up to 10. The one to edit is chosen from the prompt."),
    image: list[str] | None = typer.Option(None, "--image", "-i", help="Reference image for anything being added. Repeatable, up to 30. Tag as @Image1…"),
    audio_ref: list[str] | None = typer.Option(None, "--audio-ref", help="Reference audio URL. Repeatable, up to 10. Tag as @Audio1…"),
    resolution: str = typer.Option("720p", "--resolution", help="Output quality: 480p | 720p."),
    audio: bool = typer.Option(True, "--audio/--no-audio", help="Generate a matching audio track."),
    output_format: str = typer.Option("mov", "--output-format", help="Container format: mov (default, best A/V sync) | mp4 (wider playback)."),
    seed: int | None = typer.Option(None, "--seed", help="Random seed for reproducibility."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Auto-poll until the video is ready."),
    poll_interval: int = typer.Option(10, "--poll-interval", help="Seconds between status checks (--watch mode)."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Edit an existing video — add, remove, or replace visual or audio elements.

    The output keeps the source video's aspect ratio AND duration; neither is
    settable. The source clip must itself be 4–30 seconds long. Seedance 2.5 only.

    Example:
      seedance edit -p "Video edit: remove everyone in @Video1 except the protagonist." \\
        --video https://example.com/scene.mov --watch
    """
    _submit(
        kind="edit",
        prompt=prompt,
        video=video,
        image=image,
        audio_ref=audio_ref,
        duration=None,
        resolution=resolution,
        audio=audio,
        output_format=output_format,
        seed=seed,
        watch=watch,
        poll_interval=poll_interval,
        profile=profile,
    )


def extend(
    prompt: str = typer.Option(..., "--prompt", "-p", help="The continuation, e.g. \"Extend @Video1, then move into the gallery interior of @Video2.\""),
    video: list[str] = typer.Option(..., "--video", help="Reference video URL. Repeatable, up to 10. The one to extend is chosen from the prompt."),
    duration: int = typer.Option(-1, "--duration", "-d", help="Length in seconds (4–30), or -1 to let the model choose."),
    image: list[str] | None = typer.Option(None, "--image", "-i", help="Reference image for anything introduced. Repeatable, up to 30. Tag as @Image1…"),
    audio_ref: list[str] | None = typer.Option(None, "--audio-ref", help="Reference audio URL. Repeatable, up to 10. Tag as @Audio1…"),
    resolution: str = typer.Option("720p", "--resolution", help="Output quality: 480p | 720p."),
    audio: bool = typer.Option(True, "--audio/--no-audio", help="Generate a matching audio track."),
    output_format: str = typer.Option("mov", "--output-format", help="Container format: mov (default, best A/V sync) | mp4 (wider playback)."),
    seed: int | None = typer.Option(None, "--seed", help="Random seed for reproducibility."),
    watch: bool = typer.Option(False, "--watch", "-w", help="Auto-poll until the video is ready."),
    poll_interval: int = typer.Option(10, "--poll-interval", help="Seconds between status checks (--watch mode)."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Extend an existing video forwards or backwards.

    The output keeps the source video's aspect ratio, which is not settable.
    Unlike `seedance edit`, the duration IS settable here. Seedance 2.5 only.

    Example:
      seedance extend -p "Extend @Video1 — the camera keeps pushing down the corridor." \\
        --video https://example.com/corridor.mov --duration 11 --watch
    """
    _submit(
        kind="extend",
        prompt=prompt,
        video=video,
        image=image,
        audio_ref=audio_ref,
        duration=duration,
        resolution=resolution,
        audio=audio,
        output_format=output_format,
        seed=seed,
        watch=watch,
        poll_interval=poll_interval,
        profile=profile,
    )
