"""seedance auth — credential management commands."""
from __future__ import annotations

import typer
from rich.prompt import Prompt

from seedance import SeedanceClient
from seedance.credentials import (
    clear_credentials,
    credentials_configured,
    write_credentials,
)
from seedance.exceptions import SeedanceError

from ..console import console, err, info, ok, warn

app = typer.Typer(help="Manage BytePlus credentials.")


@app.command("login")
def login(
    profile: str = typer.Option("default", help="Credentials profile name."),
) -> None:
    """Interactively store ARK_API_KEY, ARK_AK, and ARK_SK in ~/.seedance/credentials."""
    console.print("\n[bold]Seedance — credential setup[/bold]")
    console.print("Credentials are stored in [cyan]~/.seedance/credentials[/cyan] (chmod 600).\n")
    console.print("Find your keys at: [url]https://console.byteplus.com/iam/[/url]\n")

    api_key  = Prompt.ask("  ARK_API_KEY      (ModelArk bearer token)", password=True)
    ak       = Prompt.ask("  ARK_AK           (IAM Access Key ID)")
    sk       = Prompt.ask("  ARK_SK           (IAM Secret Key)", password=True)
    mediakit = Prompt.ask(
        "  MEDIAKIT_API_KEY (AI MediaKit key for upscaling — optional)",
        password=True, default="", show_default=False,
    )

    if not api_key or not ak or not sk:
        err("ARK_API_KEY, ARK_AK, and ARK_SK are required. Aborting.")
        raise typer.Exit(1)

    write_credentials(
        api_key.strip(), ak.strip(), sk.strip(),
        mediakit_api_key=mediakit.strip(), profile=profile,
    )
    ok(f"Credentials saved to ~/.seedance/credentials  [profile: {profile}]")

    # Quick liveness check
    info("Verifying credentials with seedance ping…")
    try:
        result = SeedanceClient(api_key=api_key.strip(), ak=ak.strip(), sk=sk.strip()).ping()
        ok(f"Connection OK  (server v{result['version']})")
    except SeedanceError as exc:
        warn(f"Saved, but ping failed: {exc}")
        warn("Your credentials are stored — check ARK_API_KEY if generation fails.")


@app.command("check")
def check(
    profile: str = typer.Option("default", help="Credentials profile name."),
) -> None:
    """Check which credentials are currently configured."""
    status = credentials_configured(profile=profile)
    console.print(f"\n[bold]Credential status[/bold]  (profile: [cyan]{profile}[/cyan])\n")

    for key, label in [
        ("api_key",  "ARK_API_KEY      (video generation)"),
        ("ak",       "ARK_AK           (asset library)   "),
        ("sk",       "ARK_SK           (asset library)   "),
        ("mediakit", "MEDIAKIT_API_KEY (upscaling, optional)"),
    ]:
        mark = "[success]✔[/success]" if status[key] else "[error]✖[/error]"
        state = "configured" if status[key] else "missing"
        console.print(f"  {mark}  {label}  [dim]{state}[/dim]")

    # MEDIAKIT_API_KEY is optional — only the three core credentials are required.
    required = ("api_key", "ak", "sk")
    if all(status[k] for k in required):
        console.print("\n  [success]All required credentials are configured.[/success]")
        if not status["mediakit"]:
            console.print(
                "  [dim]MEDIAKIT_API_KEY is unset — needed only for seedance upscale.[/dim]\n"
            )
    else:
        missing = [k for k in required if not status[k]]
        console.print(f"\n  [error]Missing:[/error] {', '.join(missing)}")
        console.print("  Run [cyan]seedance auth login[/cyan] to configure.\n")
        raise typer.Exit(1)


@app.command("logout")
def logout(
    profile: str = typer.Option("default", help="Credentials profile to remove."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Remove stored credentials for a profile."""
    if not yes:
        typer.confirm(
            f"Remove credentials for profile '{profile}'?",
            abort=True,
        )
    existed = clear_credentials(profile=profile)
    if existed:
        ok(f"Credentials removed for profile '{profile}'.")
    else:
        warn("No credentials file found — nothing to remove.")
