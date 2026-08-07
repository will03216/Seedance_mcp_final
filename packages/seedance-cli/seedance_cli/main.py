"""Seedance CLI — entry point.

Usage:
    seedance auth login
    seedance generate --prompt "..." --image "https://..." --watch
    seedance edit --prompt "..." --video "https://..." --watch
    seedance extend --prompt "..." --video "https://..." --duration 11 --watch
    seedance upscale <video_url> --resolution 1080p --watch
    seedance upscale-status <task_id>
    seedance status <task_id>
    seedance watch <task_id>
    seedance list
    seedance cancel <task_id>
    seedance asset upload <url> --group <id>
    seedance asset status <asset_id>
    seedance asset group create <name>
    seedance models
    seedance skill install
    seedance skill check
"""
from __future__ import annotations

import typer

from .commands import auth, assets, edit, generate, models, skill, tasks, tos, upscale

app = typer.Typer(
    name="seedance",
    help="BytePlus Seedance video generation CLI (2.5 by default).",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

# Top-level command groups
app.add_typer(auth.app,     name="auth",     help="Manage BytePlus credentials.")
app.add_typer(generate.app, name="generate", help="Submit video generation jobs.")
app.add_typer(tasks.app,    name="tasks",    help="Manage generation tasks.")
app.add_typer(assets.app,   name="asset",    help="Manage the BytePlus asset library.")
app.add_typer(tos.app,      name="tos",      help="Upload local files to TOS object storage.")
app.add_typer(models.app,   name="models",   help="List available Seedance models.")
app.add_typer(skill.app,    name="skill",    help="Install/manage the Claude Code skill.")

# Convenience shortcuts at the top level (avoids `seedance tasks status`)
app.command("status", help="Check the status of a task.")(tasks.status)
app.command("watch",  help="Stream live progress for a task.")(tasks.watch)
app.command("list",   help="List recent tasks.")(tasks.list_tasks)
app.command("cancel", help="Cancel a running task.")(tasks.cancel)
app.command("edit",   help="Edit an existing video (Seedance 2.5).")(edit.edit)
app.command("extend", help="Extend an existing video (Seedance 2.5).")(edit.extend)
app.command("upscale", help="Upscale/enhance an existing video (AI MediaKit).")(upscale.upscale)
app.command("upscale-status", help="Check an upscale task's status.")(upscale.upscale_status)


@app.command("ping")
def ping(
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Verify server connectivity and credential configuration."""
    from seedance import SeedanceClient
    from seedance.exceptions import SeedanceError
    from .console import console, err, ok, info

    client = SeedanceClient(profile=profile)
    try:
        result = client.ping()
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1)

    console.print()
    ok(f"Connected  (SDK v{result['version']})")
    creds = result.get("credentials", {})
    for key, label in [
        ("api_key",  "ARK_API_KEY     "),
        ("ak",       "ARK_AK          "),
        ("sk",       "ARK_SK          "),
        ("mediakit", "MEDIAKIT_API_KEY"),
    ]:
        mark = "[success]✔[/success]" if creds.get(key) else "[error]✖[/error]"
        info(f"{mark}  {label}  {'configured' if creds.get(key) else 'missing'}")
    console.print()


if __name__ == "__main__":
    app()
