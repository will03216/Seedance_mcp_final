"""seedance models — list available models."""
from __future__ import annotations

import typer

from seedance import SeedanceClient
from seedance.exceptions import SeedanceError

from ..console import console, err
from ..formatters import models_table

app = typer.Typer(help="List available Seedance models.")


@app.callback(invoke_without_command=True)
def models(
    ctx: typer.Context,
    profile: str = typer.Option("default", "--profile", help="Credentials profile."),
) -> None:
    """List all available Seedance models and their capabilities."""
    if ctx.invoked_subcommand is not None:
        return

    client = SeedanceClient(profile=profile)
    try:
        data = client.list_models()
    except SeedanceError as exc:
        err(str(exc))
        raise typer.Exit(1) from exc

    console.print()
    models_table(data)
    console.print()
