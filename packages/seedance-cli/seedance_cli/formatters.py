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
    table.add_column("Model ID", style="blue", no_wrap=True)
    table.add_column("Label")
    table.add_column("Alias")
    table.add_column("Resolutions")
    table.add_column("Ratios")
    table.add_column("Duration")
    table.add_column("Features")

    for m in data.get("models", []):
        features = ", ".join(
            k for k, v in m.get("features", {}).items() if v
        ) or "—"
        dur = m["duration_range"]
        table.add_row(
            m["model_id"],
            m["label"],
            m["alias"],
            ", ".join(m["resolutions"]),
            ", ".join(m["ratios"]),
            f"{dur[0]}–{dur[1]}s",
            features,
        )

    console.print(table)
    console.print(f"\n  Default: [blue]{data['default_model']}[/blue]")
    console.print(f"  Fast:    [blue]{data['fast_model']}[/blue]")


def steps_panel(steps: list[dict]) -> None:
    """Print pipeline steps from generate()."""
    for step in steps:
        name = step.get("step", "")
        outcome = step.get("outcome", "")
        detail = step.get("group_id") or step.get("asset_id") or step.get("task_id") or ""
        label = {
            "create_asset_group": "Created asset group",
            "reuse_asset_group": "Reusing asset group",
            "upload_asset": "Asset uploaded",
            "submit_job": "Job submitted",
        }.get(name, name)
        console.print(f"  [success]✔[/success]  {label}  [dim]{detail}[/dim]")
