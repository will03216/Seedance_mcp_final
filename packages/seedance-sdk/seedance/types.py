"""Typed result dataclasses returned by SeedanceClient methods."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskResult:
    task_id: str
    status: str
    video_url: str | None = None
    error: dict | None = None
    mode: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"task_id": self.task_id, "status": self.status}
        if self.video_url:
            out["video_url"] = self.video_url
        if self.error:
            out["error"] = self.error
        if self.mode:
            out["mode"] = self.mode
        return out

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    @property
    def terminal(self) -> bool:
        return self.status in {"succeeded", "failed", "cancelled"}


@dataclass
class GenerateResult:
    task_id: str
    status: str
    mode: str
    steps: list[dict] = field(default_factory=list)
    asset_id: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "task_id": self.task_id,
            "status": self.status,
            "mode": self.mode,
            "steps": self.steps,
            "message": (
                f"Job submitted. Poll with seedance_check_task(task_id='{self.task_id}') "
                "every 10–15 seconds until status == 'succeeded'."
            ),
        }
        if self.asset_id:
            out["asset_id"] = self.asset_id
        return out


@dataclass
class AssetGroupResult:
    group_id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"group_id": self.group_id, "name": self.name}


@dataclass
class AssetResult:
    asset_id: str
    asset_ref: str
    status: str
    error: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "asset_id": self.asset_id,
            "asset_ref": self.asset_ref,
            "status": self.status,
        }
        if self.error:
            out["error"] = self.error
        return out

    @property
    def active(self) -> bool:
        return self.status == "Active"
