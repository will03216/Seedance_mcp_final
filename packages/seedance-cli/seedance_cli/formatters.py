"""Rich table/output formatters for CLI commands."""
from __future__ import annotations

from typing import Any

from rich.table import Table

from .console import console


def tasks_table(tasks: list[Any], title: str = "Tasks") -> None:
    table = Table(title=title, show_lines=False, header_style="bold cyan")
    table.add_column("Task ID", style="blue", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Video URL", overflow="fold")

    status_styles = {
        "succeeded": "[green]succeeded[/green]",
        "running": "[yellow]running[/yellow]",
        "queued": "[cyan]queued[/cyan]",
        "failed": "[red]failed[/red]",
        "cancelled": "[dim]cancelled[/dim]",
    }

    for t in tasks:
        status = t.status if hasattr(t, "status") else t.get("status", "")
        task_id = t.task_id if hasattr(t, "task_id") else t.get("task_id", "")
        video_url = t.video_url if hasattr(t, "video_url") else t.get("video_url") or ""
        table.add_row(
            task_id,
            status_styles.get(status, status),
            video_url or "[dim]—[/dim]",
        )

    console.print(table)


def models_table(data: dict) -> None:
    table = Table(title="Available Models", show_lines=True, header_style="bold cyan")
    # The model ID is long, so the label rides under it rather than in its own
    # column — eight columns will not fit an 80-column terminal.
    table.add_column("Model", style="blue")
    table.add_column("Alias", no_wrap=True)
    table.add_column("Res.")
    table.add_column("Dur.", no_wrap=True)
    table.add_column("Refs\nimg/vid/aud", no_wrap=True)
    table.add_column("Fmt")
    table.add_column("Features")

    # Long capability keys crowd the table; abbreviate to the distinguishing part.
    short_feature = {
        "first_frame": "first-frame",
        "last_frame": "last-frame",
        "camerafixed": "camera-fixed",
        "seed": "seed",
        "auto_duration": "auto-dur",
        "audio_only_input": "audio-only",
        "output_format": "mov",
        "video_edit": "edit",
        "video_extend": "extend",
    }

    for m in data.get("models", []):
        features = ", ".join(
            short_feature.get(k, k) for k, v in m.get("features", {}).items() if v
        ) or "—"
        dur = m["duration_range"]
        limits = m.get("reference_limits", {})
        refs = "{}/{}/{}".format(
            limits.get("images", "—"),
            limits.get("videos", "—"),
            limits.get("audio", "—"),
        )
        table.add_row(
            f"{m['model_id']}\n[dim]{m['label']}[/dim]",
            m["alias"],
            ", ".join(m["resolutions"]),
            f"{dur[0]}–{dur[1]}s",
            refs,
            ", ".join(m.get("output_formats", ["mp4"])),
            features,
        )

    console.print(table)
    console.print(f"\n  Default: [blue]{data['default_model']}[/blue]")
    console.print(f"  Fast:    [blue]{data['fast_model']}[/blue]")
    if data.get("legacy_model"):
        console.print(f"  Legacy:  [blue]{data['legacy_model']}[/blue]")
    console.print(
        "\n  [dim]Ratios: 21:9, 16:9, 4:3, 1:1, 3:4, 9:16, adaptive on every model.[/dim]"
    )


def steps_panel(steps: list[dict]) -> None:
    """Print pipeline steps from generate()."""
    for step in steps:
        name = step.get("step", "")
        detail = step.get("group_id") or step.get("asset_id") or step.get("task_id") or ""
        label = {
            "create_asset_group": "Created asset group",
            "reuse_asset_group": "Reusing asset group",
            "upload_asset": "Asset uploaded",
            "submit_job": "Job submitted",
        }.get(name, name)
        console.print(f"  [success]✔[/success]  {label}  [dim]{detail}[/dim]")
