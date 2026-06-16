"""SeedanceClient — the primary entry point for the Seedance SDK."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from .asset import AssetClient
from .config import (
    BASE_URL, DEFAULT_MODEL, FAST_MODEL, INCLUDE_RAW,
    MAX_REFERENCE_AUDIO, MAX_REFERENCE_IMAGES, MAX_REFERENCE_VIDEOS,
    MODELS, PAGE_SIZE_MAX, POLL_TIMEOUT, SUBMIT_TIMEOUT, TERMINAL_STATUSES,
    __version__, model_caps,
)
from .credentials import load_api_key, load_asset_credentials, load_mediakit_api_key
from .exceptions import ValidationError
from .http import extract_nested, extract_video_url, request_with_retry
from .mediakit import MediaKitClient
from .types import (
    AssetGroupResult, AssetResult, GenerateResult, TaskResult, UpscaleResult,
)

logger = logging.getLogger("seedance")


class SeedanceClient:
    """Client for BytePlus Seedance 2.0 video generation.

    Credentials are resolved in priority order: explicit args → env vars →
    ~/.seedance/credentials file → legacy ark_api_key.txt.

    Usage:
        client = SeedanceClient()   # picks up creds automatically
        result = client.generate(prompt="A sunrise over mountains", ratio="16:9")
        print(result.task_id)
    """

    def __init__(
        self,
        api_key: str | None = None,
        ak: str | None = None,
        sk: str | None = None,
        *,
        mediakit_api_key: str | None = None,
        profile: str = "default",
    ) -> None:
        self._api_key_override = api_key
        self._ak_override = ak
        self._sk_override = sk
        self._mediakit_key_override = mediakit_api_key
        self._profile = profile

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _api_key(self) -> str:
        return load_api_key(self._api_key_override, profile=self._profile)

    def _asset_client(self) -> AssetClient:
        ak, sk = load_asset_credentials(self._ak_override, self._sk_override, profile=self._profile)
        return AssetClient(ak, sk)

    def _mediakit_client(self) -> MediaKitClient:
        return MediaKitClient(load_mediakit_api_key(self._mediakit_key_override, profile=self._profile))

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _http(
        self,
        path: str,
        *,
        method: str,
        payload: dict | None = None,
        timeout: int = POLL_TIMEOUT,
        correlation_id: str = "",
    ) -> dict[str, Any]:
        return request_with_retry(
            f"{BASE_URL}{path}",
            method=method,
            headers=self._auth_headers(),
            payload=payload,
            timeout=timeout,
            correlation_id=correlation_id,
        )

    @staticmethod
    def _cid() -> str:
        return str(uuid.uuid4())[:8]

    @staticmethod
    def _maybe_raw(resp: dict) -> dict:
        return {"raw": resp} if INCLUDE_RAW else {}

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(
        ratio: str,
        duration: int,
        resolution: str,
        model: str,
    ) -> None:
        caps = model_caps(model)
        if ratio not in caps["ratios"]:
            raise ValidationError(
                f"Invalid ratio {ratio!r}. Must be one of: {', '.join(sorted(caps['ratios']))}"
            )
        dur_min, dur_max = caps["duration_range"]
        if not dur_min <= duration <= dur_max:
            raise ValidationError(
                f"Invalid duration {duration}. Must be {dur_min}–{dur_max}s for model {model}."
            )
        if resolution not in caps["resolutions"]:
            raise ValidationError(
                f"Invalid resolution {resolution!r}. "
                f"Must be one of: {', '.join(sorted(caps['resolutions']))}"
            )

    # ------------------------------------------------------------------
    # Payload builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_content(
        prompt: str,
        image_urls: list[str] | None = None,
        first_frame_url: str | None = None,
        last_frame_url: str | None = None,
        video_urls: list[str] | None = None,
        audio_urls: list[str] | None = None,
    ) -> list[dict]:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if first_frame_url:
            content.append({"type": "image_url", "image_url": {"url": first_frame_url}, "role": "first_frame"})
        if last_frame_url:
            content.append({"type": "image_url", "image_url": {"url": last_frame_url}, "role": "last_frame"})
        for u in image_urls or []:
            content.append({"type": "image_url", "image_url": {"url": u}, "role": "reference_image"})
        for u in video_urls or []:
            content.append({"type": "video_url", "video_url": {"url": u}, "role": "reference_video"})
        for u in audio_urls or []:
            content.append({"type": "audio_url", "audio_url": {"url": u}, "role": "reference_audio"})
        return content

    @staticmethod
    def _validate_refs(
        image_urls: list[str] | None,
        video_urls: list[str] | None,
        audio_urls: list[str] | None,
    ) -> None:
        """Enforce Seedance 2.0 all-round-reference budgets and reject empty
        entries. Reference videos and audio are URL-only (no asset upload)."""
        for label, urls, limit in (
            ("image_urls", image_urls, MAX_REFERENCE_IMAGES),
            ("video_urls", video_urls, MAX_REFERENCE_VIDEOS),
            ("audio_urls", audio_urls, MAX_REFERENCE_AUDIO),
        ):
            if not urls:
                continue
            if not all(urls):
                raise ValidationError(f"{label} contains an empty entry.")
            if len(urls) > limit:
                raise ValidationError(
                    f"Too many {label}: {len(urls)} (max {limit} for Seedance 2.0)."
                )

    @staticmethod
    def _extra_params(seed: int | None, camerafixed: bool) -> dict:
        params: dict = {}
        if seed is not None:
            params["seed"] = seed
        if camerafixed:
            params["camerafixed"] = True
        return params

    # ------------------------------------------------------------------
    # Video generation
    # ------------------------------------------------------------------

    def submit_text_to_video(
        self,
        prompt: str,
        *,
        ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        generate_audio: bool = False,
        fast_mode: bool = False,
        seed: int | None = None,
        camerafixed: bool = False,
    ) -> TaskResult:
        """Submit a text-to-video job. Returns immediately with task_id."""
        cid = self._cid()
        model = FAST_MODEL if fast_mode else DEFAULT_MODEL
        self._validate(ratio, duration, resolution, model)

        payload = {
            "model": model,
            "content": self._build_content(prompt),
            "ratio": ratio,
            "duration": duration,
            "resolution": resolution,
            "generate_audio": generate_audio,
            "watermark": False,
            **self._extra_params(seed, camerafixed),
        }
        logger.info("[%s] T2V | ratio=%s dur=%ss res=%s", cid, ratio, duration, resolution)
        resp = self._http(
            "/contents/generations/tasks",
            method="POST",
            payload=payload,
            timeout=SUBMIT_TIMEOUT,
            correlation_id=cid,
        )
        return TaskResult(
            task_id=resp.get("id") or resp.get("task_id", ""),
            status=resp.get("status", "queued"),
            mode="T2V",
            raw=resp,
        )

    def submit_image_to_video(
        self,
        prompt: str,
        *,
        image_urls: list[str] | None = None,
        first_frame_url: str = "",
        last_frame_url: str = "",
        video_urls: list[str] | None = None,
        audio_urls: list[str] | None = None,
        ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        generate_audio: bool = False,
        fast_mode: bool = False,
        seed: int | None = None,
        camerafixed: bool = False,
    ) -> TaskResult:
        """Submit a reference-to-video job (image / video / audio references).

        Returns immediately with task_id. Video and audio references are bound
        by their content[] role; to *extend* an existing clip, pass that clip
        as a reference_video and describe the continuation in the prompt.
        """
        cid = self._cid()
        model = FAST_MODEL if fast_mode else DEFAULT_MODEL
        self._validate(ratio, duration, resolution, model)

        if not image_urls and not first_frame_url and not last_frame_url and not video_urls:
            raise ValidationError(
                "Provide at least one of: image_urls, first_frame_url, "
                "first_frame_url+last_frame_url, or video_urls."
            )
        if last_frame_url and not first_frame_url:
            raise ValidationError(
                "last_frame_url requires first_frame_url. The API does not support last-frame-only mode."
            )
        self._validate_refs(image_urls, video_urls, audio_urls)

        has_first = bool(first_frame_url)
        has_last = bool(last_frame_url)
        n = len(image_urls or [])
        nv = len(video_urls or [])
        na = len(audio_urls or [])
        mode = (
            "I2V-FirstLastFrame" if has_first and has_last
            else "I2V-FirstFrame" if has_first
            else f"R2V-Reference(img={n},vid={nv},aud={na})"
        )

        payload = {
            "model": model,
            "content": self._build_content(
                prompt,
                image_urls=image_urls,
                first_frame_url=first_frame_url or None,
                last_frame_url=last_frame_url or None,
                video_urls=video_urls,
                audio_urls=audio_urls,
            ),
            "ratio": ratio,
            "duration": duration,
            "resolution": resolution,
            "generate_audio": generate_audio,
            "watermark": False,
            **self._extra_params(seed, camerafixed),
        }
        logger.info("[%s] I2V | mode=%s ratio=%s dur=%ss res=%s", cid, mode, ratio, duration, resolution)
        resp = self._http(
            "/contents/generations/tasks",
            method="POST",
            payload=payload,
            timeout=SUBMIT_TIMEOUT,
            correlation_id=cid,
        )
        return TaskResult(
            task_id=resp.get("id") or resp.get("task_id", ""),
            status=resp.get("status", "queued"),
            mode=mode,
            raw=resp,
        )

    def generate(
        self,
        prompt: str,
        *,
        image_url: str = "",
        first_frame_url: str = "",
        last_frame_url: str = "",
        video_urls: list[str] | None = None,
        audio_urls: list[str] | None = None,
        ratio: str = "16:9",
        duration: int = 5,
        resolution: str = "720p",
        generate_audio: bool = False,
        fast_mode: bool = False,
        seed: int | None = None,
        camerafixed: bool = False,
        asset_group_id: str = "",
        on_progress: Any = None,   # optional callback(step, detail) for CLI progress reporting
    ) -> GenerateResult:
        """High-level composite generate: auto-uploads portrait images to the asset
        library before submitting the generation job.

        Pipeline:
          1. If image_url is a plain HTTPS URL:
               a. Create asset group (or reuse asset_group_id)
               b. Upload image and poll until Active
          2. If image_url already starts with "asset://", skip upload.
          3. Submit generation job.
          4. Return GenerateResult with task_id — poll check_task() to get video_url.

        The optional on_progress callback receives (step: str, detail: str) after
        each pipeline stage — used by the CLI to drive a progress display without
        coupling the SDK to Rich or any output library.
        """
        cid = self._cid()
        model = FAST_MODEL if fast_mode else DEFAULT_MODEL
        self._validate(ratio, duration, resolution, model)

        if last_frame_url and not first_frame_url:
            raise ValidationError(
                "last_frame_url requires first_frame_url. The API does not support last-frame-only mode."
            )
        self._validate_refs(None, video_urls, audio_urls)

        steps: list[dict] = []
        resolved_image_url = image_url
        asset_id_used = ""

        # --- Asset upload pipeline (only for plain HTTPS image_urls) ---
        if image_url and not image_url.startswith("asset://"):
            ac = self._asset_client()
            group_id = asset_group_id

            if not group_id:
                group_name = f"seedance-{cid}"
                logger.info("[%s] Creating asset group: %s", cid, group_name)
                group_id = ac.create_group(group_name, correlation_id=cid)
                steps.append({"step": "create_asset_group", "group_id": group_id, "outcome": "ok"})
                if on_progress:
                    on_progress("create_asset_group", group_id)
            else:
                steps.append({"step": "reuse_asset_group", "group_id": group_id, "outcome": "ok"})
                if on_progress:
                    on_progress("reuse_asset_group", group_id)

            def _asset_poll_cb(aid: str, status: str) -> None:
                if on_progress:
                    on_progress("asset_poll", f"{aid}:{status}")

            asset_id_used = ac.upload_and_wait(
                image_url, group_id,
                correlation_id=cid,
                on_poll=_asset_poll_cb,
            )
            resolved_image_url = f"asset://{asset_id_used}"
            steps.append({"step": "upload_asset", "asset_id": asset_id_used, "outcome": "Active"})
            if on_progress:
                on_progress("upload_asset", asset_id_used)

        # --- Determine mode and submit ---
        has_image = bool(resolved_image_url)
        has_first = bool(first_frame_url)
        has_last = bool(last_frame_url)
        has_av = bool(video_urls or audio_urls)

        if has_image or has_first or has_last or has_av:
            mode = (
                "I2V-FirstLastFrame" if has_first and has_last
                else "I2V-FirstFrame" if has_first
                else "R2V-Reference" if has_av
                else "I2V-Reference"
            )
            image_urls_payload = [resolved_image_url] if has_image else None
        else:
            mode = "T2V"
            image_urls_payload = None

        payload = {
            "model": model,
            "content": self._build_content(
                prompt,
                image_urls=image_urls_payload,
                first_frame_url=first_frame_url or None,
                last_frame_url=last_frame_url or None,
                video_urls=video_urls,
                audio_urls=audio_urls,
            ),
            "ratio": ratio,
            "duration": duration,
            "resolution": resolution,
            "generate_audio": generate_audio,
            "watermark": False,
            **self._extra_params(seed, camerafixed),
        }

        logger.info("[%s] Submitting | mode=%s ratio=%s dur=%ss res=%s", cid, mode, ratio, duration, resolution)
        resp = self._http(
            "/contents/generations/tasks",
            method="POST",
            payload=payload,
            timeout=SUBMIT_TIMEOUT,
            correlation_id=cid,
        )
        task_id = resp.get("id") or resp.get("task_id", "")
        steps.append({"step": "submit_job", "task_id": task_id, "outcome": "queued"})
        if on_progress:
            on_progress("submit_job", task_id)

        return GenerateResult(
            task_id=task_id,
            status=resp.get("status", "queued"),
            mode=mode,
            steps=steps,
            asset_id=asset_id_used,
            raw=resp,
        )

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def check_task(self, task_id: str) -> TaskResult:
        """Fetch current status of a task. Returns TaskResult with video_url when succeeded."""
        if not task_id:
            raise ValidationError("task_id is required.")
        cid = self._cid()
        resp = self._http(
            f"/contents/generations/tasks/{task_id}",
            method="GET",
            correlation_id=cid,
        )
        status = resp.get("status", "unknown")
        return TaskResult(
            task_id=task_id,
            status=status,
            video_url=extract_video_url(resp),
            error=resp.get("error") if status in TERMINAL_STATUSES else None,
            raw=resp,
        )

    def list_tasks(
        self,
        page_num: int = 1,
        page_size: int = 10,
        status_filter: str = "",
    ) -> dict[str, Any]:
        """List recent tasks with optional status filter."""
        page_size = min(max(1, page_size), PAGE_SIZE_MAX)
        cid = self._cid()
        qs = f"page_num={page_num}&page_size={page_size}"
        if status_filter:
            qs += f"&filter.status={status_filter}"

        resp = self._http(
            f"/contents/generations/tasks?{qs}",
            method="GET",
            correlation_id=cid,
        )
        tasks = resp.get("items") or resp.get("data") or []
        return {
            "total": resp.get("total", len(tasks)),
            "page_num": page_num,
            "page_size": page_size,
            "tasks": [
                TaskResult(
                    task_id=t.get("id", ""),
                    status=t.get("status", ""),
                    video_url=extract_video_url(t),
                )
                for t in tasks
            ],
        }

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        """Cancel a queued or running task."""
        if not task_id:
            raise ValidationError("task_id is required.")
        cid = self._cid()
        resp = self._http(
            f"/contents/generations/tasks/{task_id}",
            method="DELETE",
            correlation_id=cid,
        )
        return {"task_id": task_id, "cancelled": True, **self._maybe_raw(resp)}

    # ------------------------------------------------------------------
    # Video upscaling / enhancement (AI MediaKit)
    # ------------------------------------------------------------------

    def submit_video_enhance(
        self,
        video_url: str,
        *,
        tool_version: str = "standard",
        scene: str | None = None,
        resolution: str | None = None,
        resolution_limit: int | None = None,
        bitrate_level: str | None = None,
        fps: float | None = None,
        client_token: str | None = None,
        callback_args: str | None = None,
        force_new: bool = False,
    ) -> UpscaleResult:
        """Submit a video-enhancement (upscale) task. Returns immediately with task_id.

        Idempotent by default: identical parameters reuse the same task within 24h
        (via a deterministic client_token + local cache). Pass force_new=True or a
        distinct client_token to force a brand-new task.
        """
        cid = self._cid()
        resp = self._mediakit_client().submit_enhance(
            video_url,
            tool_version=tool_version,
            scene=scene,
            resolution=resolution,
            resolution_limit=resolution_limit,
            bitrate_level=bitrate_level,
            fps=fps,
            client_token=client_token,
            callback_args=callback_args,
            force_new=force_new,
            correlation_id=cid,
        )
        return UpscaleResult(
            task_id=resp.get("task_id", ""),
            status="submitted",
            request_id=resp.get("request_id", ""),
            idempotent_hit=bool(resp.get("idempotent_hit")),
            raw=resp if INCLUDE_RAW else {},
        )

    def check_enhance_task(self, task_id: str) -> UpscaleResult:
        """Fetch current status of an upscale task. Includes video_url when completed."""
        if not task_id:
            raise ValidationError("task_id is required.")
        cid = self._cid()
        resp = self._mediakit_client().get_task(task_id, correlation_id=cid)
        status = resp.get("status", "unknown")
        result = resp.get("result") or {}
        return UpscaleResult(
            task_id=resp.get("task_id", task_id),
            status=status,
            video_url=result.get("video_url") or extract_video_url(resp) or None,
            error=resp.get("error") if status == "failed" else None,
            request_id=resp.get("request_id", ""),
            duration=result.get("duration"),
            resolution=result.get("resolution"),
            fps=result.get("fps"),
            tool_version=result.get("tool_version"),
            raw=resp if INCLUDE_RAW else {},
        )

    # ------------------------------------------------------------------
    # Asset library
    # ------------------------------------------------------------------

    def create_asset_group(self, name: str, description: str = "") -> AssetGroupResult:
        if not name:
            raise ValidationError("name is required.")
        ac = self._asset_client()
        group_id = ac.create_group(name, description)
        return AssetGroupResult(group_id=group_id, name=name)

    def upload_asset(
        self,
        image_url: str,
        group_id: str,
        *,
        on_poll: Any = None,
    ) -> AssetResult:
        """Upload an image and poll until Active. Returns AssetResult."""
        if not image_url:
            raise ValidationError("image_url is required.")
        if not group_id:
            raise ValidationError("group_id is required. Call create_asset_group() first.")
        ac = self._asset_client()
        cid = self._cid()
        asset_id = ac.upload_and_wait(image_url, group_id, correlation_id=cid, on_poll=on_poll)
        return AssetResult(
            asset_id=asset_id,
            asset_ref=f"asset://{asset_id}",
            status="Active",
        )

    def get_asset(self, asset_id: str) -> AssetResult:
        """Check the status of an existing asset."""
        if not asset_id:
            raise ValidationError("asset_id is required.")
        ac = self._asset_client()
        status, resp = ac.get_asset_status(asset_id)
        error_msg = ""
        if status == "Failed":
            error_msg = (
                extract_nested(resp, "Result", "Error")
                or extract_nested(resp, "Error")
                or "unknown error"
            )
        return AssetResult(
            asset_id=asset_id,
            asset_ref=f"asset://{asset_id}",
            status=status,
            error=error_msg,
            raw=resp,
        )

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------

    def list_models(self) -> dict[str, Any]:
        return {
            "default_model": DEFAULT_MODEL,
            "fast_model": FAST_MODEL,
            "models": [
                {
                    "model_id": mid,
                    "label": caps["label"],
                    "alias": caps["alias"],
                    "resolutions": caps["resolutions"],
                    "ratios": caps["ratios"],
                    "duration_range": caps["duration_range"],
                    "features": {
                        "first_frame": caps.get("supports_first_frame", False),
                        "last_frame": caps.get("supports_last_frame", False),
                        "camerafixed": caps.get("supports_camerafixed", False),
                        "seed": caps.get("supports_seed", False),
                    },
                }
                for mid, caps in MODELS.items()
            ],
        }

    def ping(self) -> dict[str, Any]:
        from .credentials import credentials_configured
        status = credentials_configured(profile=self._profile)
        return {
            "status": "ok",
            "version": __version__,
            "default_model": DEFAULT_MODEL,
            "fast_model": FAST_MODEL,
            "base_url": BASE_URL,
            "credentials": status,
        }
