"""Seedance 2.0 MCP Server

Exposes BytePlus ModelArk Seedance 2.0 video generation as MCP tools so any
MCP-compatible AI client (Claude Desktop, Cursor, etc.) can submit and track
video generation jobs without custom integration code.

Tools exposed:
    seedance_text_to_video        – generate a video from a text prompt
    seedance_image_to_video       – generate a video from an image + prompt
    seedance_check_task           – poll an existing task for status / video URL
    seedance_list_tasks           – list recent tasks with optional status filter
    seedance_cancel_task          – cancel a queued or running task
    seedance_auto_generate        – submit + poll in one call, returns video URL directly
    seedance_generate             – recommended: upload + submit in one call
    seedance_ping                 – liveness / config check

    seedance_create_asset_group   – create an asset group (one-time setup for portrait images)
    seedance_upload_asset         – upload an image URL to the asset library, poll until Active
    seedance_get_asset            – check the status of an existing asset by ID

Usage:
    ARK_API_KEY=<key> ARK_AK=<ak> ARK_SK=<sk> python server.py

    Or set the keys in a .env file / system environment before launching.

Environment variables:
    ARK_API_KEY                 Required. BytePlus ModelArk bearer token (video generation).
    ARK_AK                      Required for asset tools. IAM Access Key ID.
    ARK_SK                      Required for asset tools. IAM Secret Access Key.
    SEEDANCE_SUBMIT_TIMEOUT     HTTP timeout (s) for job submission. Default: 30.
    SEEDANCE_POLL_TIMEOUT       HTTP timeout (s) for status polls. Default: 15.
    SEEDANCE_MAX_RETRIES        Max retry attempts on 5xx / network errors. Default: 3.
    SEEDANCE_DEBUG_RAW          Set to "1" to include raw API responses in tool output.
    SEEDANCE_ASSET_POLL_INTERVAL  Seconds between asset status checks. Default: 3.
    SEEDANCE_ASSET_POLL_TIMEOUT   Max seconds to wait for asset to become Active. Default: 120.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Optional .env support for local development
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# MCP SDK import
# ---------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError as exc:
    raise SystemExit(
        "mcp package not found. Install it with:\n"
        "  pip install mcp\n"
        "Then re-run this server."
    ) from exc

from .config import (
    __version__,
    ASSET_POLL_TIMEOUT, ASSET_POLL_INTERVAL,
    DEFAULT_MODEL, FAST_MODEL, INCLUDE_RAW, MODELS,
    PAGE_SIZE_MAX, POLL_TIMEOUT, SUBMIT_TIMEOUT, TERMINAL,
)
from .auth import (
    _asset_api_with_retry, extract_nested, upload_image_as_asset,
)
from .client import (
    _build_content, _cancel, _error_result, _extra_params,
    _extract_video_url, _get, _maybe_raw, _submit,
    _http_with_retry, _validate_common,
)
from .config import BASE_URL

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("seedance_mcp")

# ---------------------------------------------------------------------------
# MCP app
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="seedance",
    instructions=(
        "Tools for generating videos with BytePlus Seedance 2.0. "
        "PREFERRED: use seedance_generate for most tasks — it handles asset upload "
        "and job submission in one call, then poll seedance_check_task "
        "every 10–15 seconds until status == 'succeeded'. "
        "Use seedance_text_to_video or seedance_image_to_video only when you need fine-grained "
        "control (e.g. multiple reference images, explicit asset:// refs). "
        "Do NOT use seedance_auto_generate — it blocks for minutes and causes MCP timeout errors."
    ),
    # Disable the SDK's built-in DNS-rebinding guard — we enforce access
    # control via a bearer token in the ASGI gateway instead.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


# ---------------------------------------------------------------------------
# MCP Tools — Video generation
# ---------------------------------------------------------------------------

@mcp.tool()
def seedance_text_to_video(
    prompt: str,
    ratio: str = "16:9",
    duration: int = 5,
    resolution: str = "720p",
    generate_audio: bool = False,
    fast_mode: bool = False,
    seed: int | None = None,
    camerafixed: bool = False,
    draft: bool = False,
) -> dict:
    """Submit a text-to-video generation job on Seedance 2.0.

    Args:
        prompt: Detailed scene description. Include subject, action, camera
                movement, lighting, and style for best results.
                Example: "A silver espresso machine on a modern kitchen counter.
                Morning light cuts in, steam rises slowly, camera slowly pushes
                in to a close-up of coffee flowing into a glass cup."
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15).
        resolution: Output quality. One of: 480p | 720p | 1080p
        generate_audio: Whether to generate a matching audio track.
        fast_mode: Use the faster/cheaper model variant (lower quality).
        seed: Random seed for reproducible results. Same seed + prompt = same video.
        camerafixed: Fix the camera in place — no panning, zooming, or movement.
                     Useful for product shots and static scene reveals.
        draft: Force 480p regardless of resolution setting. Faster and cheaper
               for composition checks before a full-quality render.

    Returns:
        dict with task_id, status, and queue info. Use seedance_check_task to poll
        for the video URL once status reaches 'succeeded'.
    """
    cid = str(uuid.uuid4())[:8]
    model = FAST_MODEL if fast_mode else DEFAULT_MODEL
    try:
        _validate_common(ratio, duration, resolution, model)
    except ValueError as exc:
        return _error_result(exc, "validation")

    if draft:
        resolution = "480p"

    payload = {
        "model": model,
        "content": _build_content(prompt),
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "generate_audio": generate_audio,
        "watermark": False,
        **_extra_params(seed, camerafixed, draft),
    }
    logger.info("[%s] Submitting T2V | ratio=%s dur=%ss res=%s seed=%s", cid, ratio, duration, resolution, seed)

    try:
        resp = _submit(payload, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    task_id = resp.get("id") or resp.get("task_id", "")
    return {
        "task_id": task_id,
        "status": resp.get("status", "queued"),
        "message": (
            f"Task submitted. Poll with seedance_check_task(task_id='{task_id}') "
            "every 10–15 seconds until status == 'succeeded'."
        ),
        **_maybe_raw(resp),
    }


@mcp.tool()
def seedance_image_to_video(
    prompt: str,
    image_urls: list[str] | None = None,
    first_frame_url: str = "",
    last_frame_url: str = "",
    ratio: str = "16:9",
    duration: int = 5,
    resolution: str = "720p",
    generate_audio: bool = False,
    fast_mode: bool = False,
    seed: int | None = None,
    camerafixed: bool = False,
    draft: bool = False,
) -> dict:
    """Submit an image-to-video generation job on Seedance 2.0.

    Supports three image input modes — use whichever fits your use case:

    1. Reference images (image_urls): character/object identity references.
       The model animates a scene containing those subjects. Tag as [image1], [image2].

    2. First frame (first_frame_url): pins the exact starting frame of the video.
       The model animates forward from that frame.

    3. Last frame (last_frame_url): pins the exact ending frame.

    4. First + Last frame together: creates a transition between two images.

    Args:
        prompt: Motion and camera description. Tag reference images as [image1], etc.
        image_urls: Reference image URLs (HTTPS or asset://). Used for character/object
                    identity. Order matches [image1], [image2], ... tags in the prompt.
        first_frame_url: URL of the exact frame the video must START from.
        last_frame_url: URL of the exact frame the video must END at.
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15).
        resolution: Output quality. One of: 480p | 720p | 1080p
        generate_audio: Whether to generate a matching audio track.
        fast_mode: Use the faster/cheaper model variant (lower quality).
        seed: Random seed for reproducible results.
        camerafixed: Fix the camera in place — no movement.
        draft: Force 480p for a fast composition check.

    Returns:
        dict with task_id, status, and queue info. Use seedance_check_task to poll.
    """
    cid = str(uuid.uuid4())[:8]
    model = FAST_MODEL if fast_mode else DEFAULT_MODEL
    try:
        _validate_common(ratio, duration, resolution, model)
        if not image_urls and not first_frame_url and not last_frame_url:
            raise ValueError(
                "Provide at least one of: image_urls, first_frame_url, or last_frame_url."
            )
        if image_urls and not all(image_urls):
            raise ValueError("image_urls contains an empty entry.")
    except ValueError as exc:
        return _error_result(exc, "validation")

    if draft:
        resolution = "480p"

    n_images = len(image_urls or [])
    has_first = bool(first_frame_url)
    has_last = bool(last_frame_url)
    mode = (
        "First+Last Frame" if has_first and has_last
        else "First Frame" if has_first
        else "Last Frame" if has_last
        else f"Reference ({n_images} images)"
    )

    payload = {
        "model": model,
        "content": _build_content(
            prompt,
            image_urls=image_urls,
            first_frame_url=first_frame_url or None,
            last_frame_url=last_frame_url or None,
        ),
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "generate_audio": generate_audio,
        "watermark": False,
        **_extra_params(seed, camerafixed, draft),
    }
    logger.info("[%s] Submitting I2V | mode=%s ratio=%s dur=%ss res=%s seed=%s",
                cid, mode, ratio, duration, resolution, seed)

    try:
        resp = _submit(payload, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    task_id = resp.get("id") or resp.get("task_id", "")
    return {
        "task_id": task_id,
        "status": resp.get("status", "queued"),
        "mode": mode,
        "message": (
            f"Task submitted. Poll with seedance_check_task(task_id='{task_id}') "
            "every 10–15 seconds until status == 'succeeded'."
        ),
        **_maybe_raw(resp),
    }


@mcp.tool()
def seedance_check_task(task_id: str) -> dict:
    """Check the status of a Seedance video generation task.

    Poll this every 10–15 seconds after submitting a job. When
    status == 'succeeded' the response includes the video_url to download
    or display the generated video.

    Args:
        task_id: The task ID returned by seedance_text_to_video or
                 seedance_image_to_video.

    Returns:
        dict with:
            status    – queued | running | succeeded | failed | cancelled
            video_url – present when status == 'succeeded'
            error     – present when status is terminal and failed
    """
    cid = str(uuid.uuid4())[:8]
    if not task_id:
        return _error_result(ValueError("task_id is required."), "validation")

    try:
        task = _get(task_id, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    status = task.get("status", "unknown")
    video_url = _extract_video_url(task)
    result: dict[str, Any] = {"task_id": task_id, "status": status}

    if video_url:
        result["video_url"] = video_url
        result["message"] = "Video is ready. Download or display the video_url."
    elif status in TERMINAL:
        result["error"] = task.get("error", {})
        result["message"] = f"Task ended with status '{status}'."
    else:
        result["message"] = f"Still processing (status='{status}'). Poll again in 10–15 seconds."

    result.update(_maybe_raw(task))
    return result


@mcp.tool()
def seedance_list_tasks(
    page_num: int = 1,
    page_size: int = 10,
    status_filter: str = "",
) -> dict:
    """List recent Seedance video generation tasks.

    Args:
        page_num: Page number (1-indexed).
        page_size: Results per page (max 50).
        status_filter: Optional. Filter by status: queued | running | succeeded | failed | cancelled

    Returns:
        dict with a list of tasks and pagination info.
    """
    cid = str(uuid.uuid4())[:8]
    page_size = min(max(1, page_size), PAGE_SIZE_MAX)

    if status_filter and status_filter not in TERMINAL | {"queued", "running"}:
        return _error_result(
            ValueError(f"Invalid status_filter {status_filter!r}."),
            "validation",
        )

    qs = f"page_num={page_num}&page_size={page_size}"
    if status_filter:
        qs += f"&filter.status={status_filter}"

    try:
        resp = _http_with_retry(
            f"{BASE_URL}/contents/generations/tasks?{qs}",
            method="GET",
            correlation_id=cid,
        )
    except RuntimeError as exc:
        return _error_result(exc, cid)

    tasks = resp.get("items") or resp.get("data") or []
    if not tasks and resp:
        logger.warning("[%s] Unexpected list response shape. Keys: %s", cid, list(resp.keys()))

    return {
        "total": resp.get("total", len(tasks)),
        "page_num": page_num,
        "page_size": page_size,
        "tasks": [
            {
                "task_id": t.get("id"),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
                "video_url": _extract_video_url(t),
            }
            for t in tasks
        ],
    }


@mcp.tool()
def seedance_cancel_task(task_id: str) -> dict:
    """Cancel a queued or running Seedance video generation task.

    Args:
        task_id: The task ID to cancel.

    Returns:
        dict confirming cancellation or describing the error.
    """
    cid = str(uuid.uuid4())[:8]
    if not task_id:
        return _error_result(ValueError("task_id is required."), "validation")

    logger.info("[%s] Cancelling task %s", cid, task_id)
    try:
        resp = _cancel(task_id, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    return {
        "task_id": task_id,
        "cancelled": True,
        "message": f"Task {task_id} cancellation requested.",
        **_maybe_raw(resp),
    }


@mcp.tool()
def seedance_auto_generate(
    prompt: str,
    image_urls: list[str] | None = None,
    first_frame_url: str = "",
    last_frame_url: str = "",
    ratio: str = "16:9",
    duration: int = 5,
    resolution: str = "720p",
    generate_audio: bool = False,
    fast_mode: bool = False,
    seed: int | None = None,
    camerafixed: bool = False,
    draft: bool = False,
    poll_interval: int = 10,
    poll_timeout: int = 300,
) -> dict:
    """Submit a Seedance video job and wait for it to complete in a single call.

    WARNING: Video generation takes 1–3 minutes. MCP clients time out after ~60s,
    so this tool will hit MCP error -32001 (Request timed out) in most cases.
    PREFER the two-step pattern instead:
        1. seedance_text_to_video or seedance_image_to_video  (returns task_id immediately)
        2. seedance_check_task polled every 10s until status == 'succeeded'

    Only use seedance_auto_generate for very short draft clips where generation
    is likely to finish within 55 seconds (draft=True, duration=4, fast_mode=True).

    Args:
        prompt: Scene description (T2V) or motion description tagging images as
                [image1], [image2], etc. (I2V).
        image_urls: Optional reference image URLs (HTTPS or asset://).
        first_frame_url: Pin the exact starting frame of the video.
        last_frame_url: Pin the exact ending frame of the video.
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15).
        resolution: Output quality. One of: 480p | 720p | 1080p
        generate_audio: Whether to generate a matching audio track.
        fast_mode: Use the faster/cheaper model variant.
        seed: Random seed for reproducible results.
        camerafixed: Fix the camera in place — no movement.
        draft: Force 480p for a fast composition check.
        poll_interval: Seconds between status checks. Default: 10.
        poll_timeout: Maximum seconds to wait for completion. Default: 300 (5 min).

    Returns:
        dict with status, video_url (when succeeded), or error details.
    """
    cid = str(uuid.uuid4())[:8]
    model = FAST_MODEL if fast_mode else DEFAULT_MODEL
    try:
        _validate_common(ratio, duration, resolution, model)
        poll_interval = max(5, poll_interval)
        poll_timeout = max(30, poll_timeout)
        if image_urls and not all(image_urls):
            raise ValueError("image_urls contains an empty entry.")
    except ValueError as exc:
        return _error_result(exc, "validation")

    if draft:
        resolution = "480p"

    has_images = bool(image_urls or first_frame_url or last_frame_url)
    mode = "T2V" if not has_images else (
        "First+Last" if first_frame_url and last_frame_url
        else "First Frame" if first_frame_url
        else "Last Frame" if last_frame_url
        else f"I2V({len(image_urls or [])} refs)"
    )

    content = _build_content(
        prompt,
        image_urls=image_urls or None,
        first_frame_url=first_frame_url or None,
        last_frame_url=last_frame_url or None,
    )
    payload = {
        "model": model,
        "content": content,
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "generate_audio": generate_audio,
        "watermark": False,
        **_extra_params(seed, camerafixed, draft),
    }
    logger.info("[%s] Auto-generate %s | ratio=%s dur=%ss res=%s seed=%s", cid, mode, ratio, duration, resolution, seed)

    try:
        resp = _submit(payload, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    task_id = resp.get("id") or resp.get("task_id", "")
    if not task_id:
        return {"status": "error", "error": "API did not return a task_id.", **_maybe_raw(resp)}

    logger.info("[%s] Task submitted: %s — polling every %ds (max %ds)", cid, task_id, poll_interval, poll_timeout)
    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        try:
            task = _get(task_id, correlation_id=cid)
        except RuntimeError as exc:
            logger.warning("[%s] Poll error (will retry): %s", cid, exc)
            continue

        status = task.get("status", "unknown")
        logger.info("[%s] Task %s status: %s", cid, task_id, status)

        if status == "succeeded":
            video_url = _extract_video_url(task)
            return {
                "task_id": task_id,
                "status": "succeeded",
                "video_url": video_url,
                "message": "Video is ready.",
                **_maybe_raw(task),
            }
        if status in TERMINAL:
            return {
                "task_id": task_id,
                "status": status,
                "error": task.get("error", {}),
                "message": f"Task ended with status '{status}'.",
                **_maybe_raw(task),
            }

    return {
        "task_id": task_id,
        "status": "timeout",
        "error": f"Video did not complete within {poll_timeout}s. Use seedance_check_task('{task_id}') to continue polling.",
    }


@mcp.tool()
def seedance_generate(
    prompt: str,
    image_url: str = "",
    first_frame_url: str = "",
    last_frame_url: str = "",
    ratio: str = "16:9",
    duration: int = 5,
    resolution: str = "720p",
    generate_audio: bool = False,
    fast_mode: bool = False,
    seed: int | None = None,
    camerafixed: bool = False,
    draft: bool = False,
    asset_group_id: str = "",
) -> dict:
    """High-level tool: generate a Seedance video with automatic asset-library upload
    when an image reference is provided.

    Prefer this over seedance_text_to_video / seedance_image_to_video for most use
    cases. It handles the full pre-generation pipeline in a single call:

      1. If image_url is a plain HTTPS URL (not already an asset:// reference):
           a. Create a new asset group (or reuse asset_group_id if provided).
           b. Upload the image and wait until status == Active.
      2. If image_url is already an asset:// reference, skip upload.
      3. If no image is given, submit a text-to-video job directly.
      4. Return task_id immediately — poll with seedance_check_task until succeeded.

    Args:
        prompt: Scene/motion description. Tag the reference image as [image1].
        image_url: Reference image — plain HTTPS URL (auto-uploaded to asset library)
                   or existing asset:// ref (skips upload).
        first_frame_url: Pin the exact starting frame (HTTPS or asset://).
        last_frame_url: Pin the exact ending frame (HTTPS or asset://).
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15). Default: 5.
        resolution: Output quality. One of: 480p | 720p | 1080p. Default: 720p.
        generate_audio: Whether to generate a matching audio track. Default: false.
        fast_mode: Use the faster/cheaper model variant. Default: false.
        seed: Random seed for reproducible results.
        camerafixed: Fix the camera — no panning or zooming. Default: false.
        draft: Force 480p for a quick composition check. Default: false.
        asset_group_id: Reuse an existing asset group instead of creating a new one.

    Returns:
        dict with:
            task_id      – poll with seedance_check_task every 10–15s
            status       – "queued" on success
            mode         – T2V | I2V-Reference | I2V-FirstFrame | I2V-LastFrame | I2V-FirstLastFrame
            steps        – list of pipeline steps taken with outcomes
            asset_id     – populated when image_url was uploaded via asset library
    """
    cid = str(uuid.uuid4())[:8]
    model = FAST_MODEL if fast_mode else DEFAULT_MODEL
    try:
        _validate_common(ratio, duration, resolution, model)
    except ValueError as exc:
        return _error_result(exc, "validation")

    if draft:
        resolution = "480p"

    steps: list[dict] = []
    resolved_image_url = image_url
    asset_id: str = ""

    if image_url and not image_url.startswith("asset://"):
        group_id = asset_group_id
        if not group_id:
            group_name = f"seedance-generate-{cid}"
            logger.info("[%s] Creating asset group: %s", cid, group_name)
            try:
                grp_resp = _asset_api_with_retry(
                    "CreateAssetGroup",
                    {"Name": group_name, "Description": "Auto-created by seedance_generate", "GroupType": "AIGC"},
                    correlation_id=cid,
                )
            except RuntimeError as exc:
                return _error_result(exc, cid)

            group_id = (
                extract_nested(grp_resp, "Result", "Id")
                or extract_nested(grp_resp, "Result", "GroupId")
                or extract_nested(grp_resp, "Id")
                or extract_nested(grp_resp, "GroupId")
            )
            if not group_id:
                return {"status": "error", "error": "Failed to create asset group — group_id not returned.", "steps": steps}
            steps.append({"step": "create_asset_group", "group_id": group_id, "outcome": "ok"})
        else:
            steps.append({"step": "reuse_asset_group", "group_id": group_id, "outcome": "ok"})

        asset_id, asset_ref, upload_err = upload_image_as_asset(image_url, group_id, cid)
        if upload_err:
            upload_err["steps"] = steps
            return upload_err
        steps.append({"step": "upload_asset", "asset_id": asset_id, "outcome": "Active"})
        resolved_image_url = asset_ref

    has_image = bool(resolved_image_url)
    has_first = bool(first_frame_url)
    has_last = bool(last_frame_url)

    if has_image or has_first or has_last:
        image_urls = [resolved_image_url] if has_image else None
        mode = (
            "I2V-FirstLastFrame" if has_first and has_last
            else "I2V-FirstFrame" if has_first
            else "I2V-LastFrame" if has_last
            else "I2V-Reference"
        )
    else:
        image_urls = None
        mode = "T2V"

    payload = {
        "model": model,
        "content": _build_content(
            prompt,
            image_urls=image_urls,
            first_frame_url=first_frame_url or None,
            last_frame_url=last_frame_url or None,
        ),
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "generate_audio": generate_audio,
        "watermark": False,
        **_extra_params(seed, camerafixed, draft),
    }

    logger.info("[%s] Submitting seedance_generate | mode=%s ratio=%s dur=%ss res=%s", cid, mode, ratio, duration, resolution)
    try:
        resp = _submit(payload, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    task_id = resp.get("id") or resp.get("task_id", "")
    steps.append({"step": "submit_job", "task_id": task_id, "outcome": "queued"})

    result: dict[str, Any] = {
        "task_id": task_id,
        "status": resp.get("status", "queued"),
        "mode": mode,
        "steps": steps,
        "message": (
            f"Job submitted. Poll with seedance_check_task(task_id='{task_id}') "
            "every 10–15 seconds until status == 'succeeded'."
        ),
    }
    if asset_id:
        result["asset_id"] = asset_id
    result.update(_maybe_raw(resp))
    return result


# ---------------------------------------------------------------------------
# MCP Tools — Asset library
# ---------------------------------------------------------------------------

@mcp.tool()
def seedance_create_asset_group(
    name: str,
    description: str = "",
) -> dict:
    """Create an asset group in the BytePlus asset library.

    Asset groups are a one-time setup. Create one group per project or use-case,
    then reuse the returned group_id for all seedance_upload_asset calls.

    Args:
        name: A short, descriptive name for the group (e.g. "my-portraits").
        description: Optional description.

    Returns:
        dict with group_id to pass to seedance_upload_asset.
    """
    cid = str(uuid.uuid4())[:8]
    if not name:
        return _error_result(ValueError("name is required."), "validation")

    logger.info("[%s] Creating asset group: %s", cid, name)
    body = {"Name": name, "Description": description, "GroupType": "AIGC"}
    try:
        resp = _asset_api_with_retry("CreateAssetGroup", body, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    group_id = (
        extract_nested(resp, "Result", "Id")
        or extract_nested(resp, "Result", "GroupId")
        or extract_nested(resp, "Id")
        or extract_nested(resp, "GroupId")
    )
    if not group_id:
        logger.warning("[%s] Could not extract group_id. Response keys: %s", cid, list(resp.keys()))

    return {
        "group_id": group_id,
        "name": name,
        "message": (
            f"Asset group created. Use group_id='{group_id}' in seedance_upload_asset."
            if group_id else "Group created but group_id could not be extracted — check raw response."
        ),
        **_maybe_raw(resp),
    }


@mcp.tool()
def seedance_upload_asset(
    image_url: str,
    group_id: str,
    asset_type: str = "Image",
) -> dict:
    """Upload an image to the BytePlus asset library and wait until it is Active.

    Use this for portrait or sensitive images before passing them to
    seedance_image_to_video — the asset:// reference is required for human faces
    and other sensitive images that are rejected when passed as plain URLs.

    Workflow:
        1. Call seedance_create_asset_group once to get a group_id.
        2. Call this tool to upload each image — returns asset_id and asset_ref.
        3. Pass asset_ref (e.g. "asset://asset-xxxx") as one of the image_urls
           in seedance_image_to_video.

    Args:
        image_url: Publicly accessible HTTPS URL of the image to upload (JPEG/PNG/WebP).
        group_id: The group ID returned by seedance_create_asset_group.
        asset_type: Asset type. Use "Image" (default) for still images.

    Returns:
        dict with:
            asset_id   – the raw asset ID (e.g. "asset-20260225023032-gnzwk")
            asset_ref  – the asset:// URL to pass to seedance_image_to_video
            status     – "Active" when ready
    """
    cid = str(uuid.uuid4())[:8]
    if not image_url:
        return _error_result(ValueError("image_url is required."), "validation")
    if not group_id:
        return _error_result(ValueError("group_id is required. Call seedance_create_asset_group first."), "validation")

    logger.info("[%s] Creating asset | group=%s url=%.60s", cid, group_id, image_url)
    create_body = {"GroupId": group_id, "URL": image_url, "AssetType": asset_type}
    try:
        create_resp = _asset_api_with_retry("CreateAsset", create_body, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    asset_id = (
        extract_nested(create_resp, "Result", "Id")
        or extract_nested(create_resp, "Result", "AssetId")
        or extract_nested(create_resp, "Id")
        or extract_nested(create_resp, "AssetId")
    )
    if not asset_id:
        return {
            "status": "error",
            "error": "CreateAsset did not return an asset_id.",
            **_maybe_raw(create_resp),
        }

    logger.info("[%s] Asset created: %s — polling until Active (max %ds)", cid, asset_id, ASSET_POLL_TIMEOUT)
    deadline = time.monotonic() + ASSET_POLL_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(ASSET_POLL_INTERVAL)
        try:
            get_resp = _asset_api_with_retry("GetAsset", {"Id": asset_id}, correlation_id=cid)
        except RuntimeError as exc:
            logger.warning("[%s] GetAsset poll error (will retry): %s", cid, exc)
            continue

        status = (
            extract_nested(get_resp, "Result", "Status")
            or extract_nested(get_resp, "Status")
        )
        logger.info("[%s] Asset %s status: %s", cid, asset_id, status)

        if status == "Active":
            asset_ref = f"asset://{asset_id}"
            return {
                "asset_id": asset_id,
                "asset_ref": asset_ref,
                "status": "Active",
                "message": (
                    f"Asset is ready. Pass asset_ref '{asset_ref}' as one of the "
                    "image_urls in seedance_image_to_video."
                ),
                **_maybe_raw(get_resp),
            }

        if status == "Failed":
            err = (
                extract_nested(get_resp, "Result", "Error")
                or extract_nested(get_resp, "Error")
                or "unknown error"
            )
            return {
                "asset_id": asset_id,
                "status": "Failed",
                "error": f"Asset processing failed: {err}",
                **_maybe_raw(get_resp),
            }

    return {
        "asset_id": asset_id,
        "asset_ref": f"asset://{asset_id}",
        "status": "timeout",
        "error": (
            f"Asset did not become Active within {ASSET_POLL_TIMEOUT}s. "
            f"Use seedance_get_asset(asset_id='{asset_id}') to continue polling."
        ),
    }


@mcp.tool()
def seedance_get_asset(asset_id: str) -> dict:
    """Check the status of an asset in the BytePlus asset library.

    Args:
        asset_id: The asset ID returned by seedance_upload_asset.

    Returns:
        dict with asset_id, status (Processing | Active | Failed), and asset_url when Active.
    """
    cid = str(uuid.uuid4())[:8]
    if not asset_id:
        return _error_result(ValueError("asset_id is required."), "validation")

    try:
        resp = _asset_api_with_retry("GetAsset", {"Id": asset_id}, correlation_id=cid)
    except RuntimeError as exc:
        return _error_result(exc, cid)

    status = (
        extract_nested(resp, "Result", "Status")
        or extract_nested(resp, "Status")
    )
    result: dict[str, Any] = {
        "asset_id": asset_id,
        "asset_ref": f"asset://{asset_id}",
        "status": status,
    }
    if status == "Active":
        result["message"] = (
            f"Asset is ready. Pass asset_ref 'asset://{asset_id}' as one of the "
            "image_urls in seedance_image_to_video."
        )
    elif status == "Failed":
        result["error"] = (
            extract_nested(resp, "Result", "Error")
            or extract_nested(resp, "Error")
            or "unknown error"
        )
        result["message"] = "Asset processing failed."
    else:
        result["message"] = f"Asset status is '{status}'. Poll again in a few seconds."

    result.update(_maybe_raw(resp))
    return result


@mcp.tool()
def seedance_list_models() -> dict:
    """List available Seedance models and their capabilities.

    Returns:
        dict with all supported models, their aliases, resolution/ratio/duration
        support, and which optional features each model supports.
    """
    return {
        "default_model": DEFAULT_MODEL,
        "fast_model": FAST_MODEL,
        "models": [
            {
                "model_id": model_id,
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
                    "draft": caps.get("supports_draft", False),
                },
            }
            for model_id, caps in MODELS.items()
        ],
    }


@mcp.tool()
def seedance_ping() -> dict:
    """Check server liveness and current configuration.

    Returns:
        dict with server version, configured models, base URL, and API key status.
    """
    from pathlib import Path
    return {
        "status": "ok",
        "version": __version__,
        "default_model": DEFAULT_MODEL,
        "fast_model": FAST_MODEL,
        "base_url": BASE_URL,
        "api_key_configured": bool(os.getenv("ARK_API_KEY") or (Path(__file__).parent / "ark_api_key.txt").exists()),
        "asset_credentials_configured": bool(os.getenv("ARK_AK") and os.getenv("ARK_SK")),
        "submit_timeout": SUBMIT_TIMEOUT,
        "poll_timeout": POLL_TIMEOUT,
        "asset_poll_interval": ASSET_POLL_INTERVAL,
        "asset_poll_timeout": ASSET_POLL_TIMEOUT,
        "debug_raw": INCLUDE_RAW,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _main() -> None:
    _transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    _port = int(os.getenv("PORT", "8000"))
    _auth_token = os.getenv("MCP_AUTH_TOKEN", "").strip()

    if _transport == "sse":
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit("SSE transport requires uvicorn: pip install uvicorn") from exc

        _mcp_app = mcp.streamable_http_app()

        class _Gateway:
            """ASGI gateway: health check, bearer-token auth, host-header rewrite.

            The MCP SDK validates the Host header to prevent DNS-rebinding attacks.
            It only accepts 'localhost', but Render's proxy forwards the public
            hostname. We rewrite Host → localhost before the MCP SDK sees it.
            """

            def __init__(self, app):
                self._app = app

            async def __call__(self, scope, receive, send):
                if scope["type"] != "http":
                    await self._app(scope, receive, send)
                    return

                path = scope.get("path", "")

                if path == "/health":
                    body = json.dumps({"status": "ok", "version": __version__}).encode()
                    await send({"type": "http.response.start", "status": 200,
                                "headers": [(b"content-type", b"application/json")]})
                    await send({"type": "http.response.body", "body": body})
                    return

                if _auth_token:
                    hdrs = {k.lower(): v for k, v in scope.get("headers", [])}
                    auth = hdrs.get(b"authorization", b"").decode()
                    if auth != f"Bearer {_auth_token}":
                        body = json.dumps({"error": "Unauthorized"}).encode()
                        await send({"type": "http.response.start", "status": 401,
                                    "headers": [(b"content-type", b"application/json")]})
                        await send({"type": "http.response.body", "body": body})
                        return

                new_hdrs = [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"host"]
                new_hdrs.append((b"host", b"localhost"))
                await self._app({**scope, "headers": new_hdrs}, receive, send)

        logger.info("Starting Seedance MCP server v%s on :%d (streamable-http, auth=%s)",
                    __version__, _port, bool(_auth_token))
        uvicorn.run(_Gateway(_mcp_app), host="0.0.0.0", port=_port)
    else:
        logger.info("Starting Seedance 2.0 MCP server v%s (stdio transport)...", __version__)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    _main()
