"""Shared Rich console instance and formatting helpers."""
from __future__ import annotations

from rich.console import Console
from rich.theme import Theme

_theme = Theme({
    "success": "bold green",
    "error": "bold red",
    "warning": "yellow",
    "info": "cyan",
    "dim": "dim white",
    "task_id": "bold blue",
    "url": "underline cyan",
})

console = Console(theme=_theme)


def ok(msg: str) -> None:
    console.print(f"[success]✔[/success]  {msg}")


def err(msg: str) -> None:
    console.print(f"[error]✖[/error]  {msg}")


def warn(msg: str) -> None:
    console.print(f"[warning]⚠[/warning]  {msg}")


def info(msg: str) -> None:
    console.print(f"[info]·[/info]  {msg}")


def spinner_text(msg: str) -> str:
    return f"[dim]{msg}[/dim]"
