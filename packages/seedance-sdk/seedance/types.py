"""Typed result dataclasses returned by SeedanceClient methods."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import MEDIAKIT_TERMINAL_STATUSES, TERMINAL_STATUSES


@dataclass
class TaskResult:
    task_id: str
    status: str
    video_url: str | None = None
    error: dict[str, Any] | None = None
    mode: str = ""
    model: str = ""
    # Properties of the finished video, present once the task succeeds.
    # `duration` is the API's approximation (total frames // 24) and can differ
    # from the true length by up to a second; `output_format` is 2.5-only.
    duration: int | None = None
    ratio: str | None = None
    resolution: str | None = None
    output_format: str | None = None
    # PNG of the final frame, present only when return_last_frame was set.
    # Chain it as the first_frame_url of the next clip for continuous sequences.
    last_frame_url: str | None = None
    # `frames` is the exact frame count; `duration` is frames // 24 rounded down,
    # so frames is the precise figure when the output has fractional seconds.
    frames: int | None = None
    fps: float | None = None
    seed: int | None = None
    priority: int | None = None
    service_tier: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    # Non-fatal advisory raised at submission — e.g. an edit prompt with no
    # trigger word, which Seedance will silently treat as a new generation.
    warning: str = ""
    raw: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"task_id": self.task_id, "status": self.status}
        if self.video_url:
            out["video_url"] = self.video_url
        if self.error:
            out["error"] = self.error
        if self.mode:
            out["mode"] = self.mode
        if self.model:
            out["model"] = self.model
        if self.duration is not None:
            out["duration"] = self.duration
        if self.ratio:
            out["ratio"] = self.ratio
        if self.resolution:
            out["resolution"] = self.resolution
        if self.output_format:
            out["output_format"] = self.output_format
        if self.last_frame_url:
            out["last_frame_url"] = self.last_frame_url
        for name in ("frames", "fps", "seed", "priority", "service_tier",
                     "created_at", "updated_at", "completion_tokens", "total_tokens"):
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        if self.warning:
            out["warning"] = self.warning
        return out

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def expired(self) -> bool:
        """True when the task outlived execution_expires_after and was killed."""
        return self.status == "expired"

    @property
    def task_type_constraint_error(self) -> bool:
        """True when the task failed because parameters clashed with the task
        type the model inferred from the prompt (Seedance 2.5, async error)."""
        code = (self.error or {}).get("code", "")
        return str(code) == "InvalidParameter.TaskTypeConstraint"


@dataclass
class GenerateResult:
    task_id: str
    status: str
    mode: str
    model: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    # asset_id is the first uploaded asset, kept for backward compatibility;
    # asset_ids holds all of them when several reference images were uploaded.
    asset_id: str = ""
    asset_ids: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict[str, Any])

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
        if self.model:
            out["model"] = self.model
        if self.asset_id:
            out["asset_id"] = self.asset_id
        if len(self.asset_ids) > 1:
            out["asset_ids"] = self.asset_ids
        return out


@dataclass
class UpscaleResult:
    """Result of an AI MediaKit video-enhancement (upscale) task.

    Status uses the MediaKit enum (running | processing | completed | failed),
    plus 'submitted' for a fresh submission — distinct from TaskResult's
    succeeded/failed/cancelled, hence a separate type.
    """
    task_id: str
    status: str
    video_url: str | None = None
    error: dict[str, Any] | None = None
    request_id: str = ""
    duration: float | None = None
    resolution: str | None = None
    fps: float | None = None
    tool_version: str | None = None
    idempotent_hit: bool = False
    raw: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"task_id": self.task_id, "status": self.status}
        if self.video_url:
            out["video_url"] = self.video_url
        if self.error:
            out["error"] = self.error
        if self.request_id:
            out["request_id"] = self.request_id
        if self.duration is not None:
            out["duration"] = self.duration
        if self.resolution:
            out["resolution"] = self.resolution
        if self.fps is not None:
            out["fps"] = self.fps
        if self.tool_version:
            out["tool_version"] = self.tool_version
        if self.idempotent_hit:
            out["idempotent_hit"] = True
        return out

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"

    @property
    def terminal(self) -> bool:
        return self.status in MEDIAKIT_TERMINAL_STATUSES


@dataclass
class AssetGroupResult:
    group_id: str
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"group_id": self.group_id, "name": self.name}


@dataclass
class TOSUploadResult:
    """Result of uploading a local file to a TOS bucket."""
    bucket: str
    key: str
    url: str
    region: str = ""
    size: int = 0
    content_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "bucket": self.bucket,
            "key": self.key,
            "url": self.url,
        }
        if self.region:
            out["region"] = self.region
        if self.size:
            out["size"] = self.size
        if self.content_type:
            out["content_type"] = self.content_type
        return out


@dataclass
class AssetResult:
    asset_id: str
    asset_ref: str
    status: str
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict[str, Any])

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
