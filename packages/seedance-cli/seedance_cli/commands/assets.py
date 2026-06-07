"""seedance asset — asset library management commands."""
from __future__ import annotations

import typer
from rich.live import Live
from rich.spinner import Spinner

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..console import console, err, info, ok

app = typer.Typer(help="Manage the BytePlus asset library.")


@app.command("upload")
def upload(
    url: str = typer.Argument(..., help="Publicly accessible HTTPS image URL (JPEG/PNG/WebP)."),
    group: str = typer.Option(..., "--group", "-g", help="Asset group ID (from 'seedance asset group create')."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Upload an image to the asset library and wait until Active.

    Returns an asset:// reference to use in generation commands.
    Required for portrait/sensitive images that are rejected as plain URLs.
    """
    client = SeedanceClient(profile=profile)

    def on_poll(asset_id: str, status: str) -> None:
        pass  # live spinner handles display

    console.print()
    with Live(
        Spinner("dots", text="  Uploading image…", style="cyan"),
        console=console,
        refresh_per_second=4,
        transient=True,
    ) as live:
        def on_poll(asset_id: str, status: str) -> None:  # noqa: F811
            live.update(Spinner("dots", text=f"  Asset {asset_id} — {status}…", style="cyan"))

        try:
            result = client.upload_asset(url, group, on_poll=on_poll)
        except SeedanceError as exc:
            err(str(exc))
            raise typer.Exit(1)

    ok(f"Asset ready  status=Active")
    console.print(f"\n  asset_id:  [blue]{result.asset_id}[/blue]")
    console.print(f"  asset_ref: [cyan]{result.asset_ref}[/cyan]")
    console.print(
        f"\n  Use [cyan]--image {result.asset_ref}[/cyan] in [cyan]seedance generate[/cyan]\n"
    )


@app.command("status")
def asset_status(
    asset_id: str = typer.Argument(..., help="Asset ID to check."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Check the status of an asset in the library."""
    client = SeedanceClient(profile=profile)
    try:
        result = client.get_asset(asset_id)
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1)

    console.print()
    if result.active:
        ok(f"[blue]{asset_id}[/blue]  status=[green]Active[/green]")
        console.print(f"  asset_ref: [cyan]{result.asset_ref}[/cyan]\n")
    elif result.error:
        err(f"[blue]{asset_id}[/blue]  status=[red]{result.status}[/red]")
        info(f"Error: {result.error}")
        raise typer.Exit(1)
    else:
        info(f"[blue]{asset_id}[/blue]  status=[yellow]{result.status}[/yellow]")
        console.print("  Poll again in a few seconds.\n")


# --- Asset group sub-group ---
group_app = typer.Typer(help="Manage asset groups.")
app.add_typer(group_app, name="group")


@group_app.command("create")
def group_create(
    name: str = typer.Argument(..., help="Short descriptive name for the group."),
    description: str = typer.Option("", "--desc", help="Optional description."),
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """Create a new asset group. One-time setup per project."""
    client = SeedanceClient(profile=profile)
    try:
        result = client.create_asset_group(name, description)
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1)

    ok(f"Asset group created")
    console.print(f"\n  group_id: [blue]{result.group_id}[/blue]")
    console.print(
        f"\n  Pass to uploads:  [cyan]seedance asset upload <url> --group {result.group_id}[/cyan]\n"
        f"  Or reuse in generate:  [cyan]seedance generate --asset-group {result.group_id} …[/cyan]\n"
    )
