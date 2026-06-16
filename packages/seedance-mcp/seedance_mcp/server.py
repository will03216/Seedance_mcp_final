"""Seedance MCP Server — thin MCP adapter over seedance-sdk.

Each tool is a minimal wrapper: validate inputs, call SeedanceClient, return dict.
All business logic (retry, signing, asset pipeline) lives in seedance-sdk.

Environment variables (all optional if ~/.seedance/credentials is configured):
    ARK_API_KEY      BytePlus ModelArk bearer token
    ARK_AK           IAM Access Key ID  (required for asset tools)
    ARK_SK           IAM Secret Key     (required for asset tools)
    MEDIAKIT_API_KEY AI MediaKit bearer token (required for upscale tools)
    MCP_TRANSPORT    "stdio" (default) | "sse"
    MCP_AUTH_TOKEN   Bearer token for SSE transport auth (optional)
    PORT             HTTP port for SSE transport (default: 8000)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError as exc:
    raise SystemExit(
        "mcp package not found. Install it: pip install mcp"
    ) from exc

from seedance import SeedanceClient
from seedance.config import __version__
from seedance.exceptions import SeedanceError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("seedance_mcp")

mcp = FastMCP(
    name="seedance",
    instructions=(
        "Tools for generating videos with BytePlus Seedance 2.0. "
        "PREFERRED: use seedance_generate for most tasks — it handles asset upload "
        "and job submission in one call, then poll seedance_check_task every 10–15 seconds "
        "until status == 'succeeded'. "
        "Use seedance_text_to_video or seedance_image_to_video only when you need fine-grained "
        "control (e.g. multiple reference images, explicit asset:// refs). "
        "To upscale/enhance an EXISTING video (e.g. a generated output URL) up to 4K, use "
        "byteplus_upscale_video, then poll byteplus_check_upscale_task until status == 'completed'. "
        "When the user has a LOCAL image file (a filesystem path) and needs a public URL — e.g. to "
        "share it or to feed it into generation — use seedance_upload_image_to_tos. If the user has "
        "not said which bucket, first call seedance_list_tos_buckets and ASK them which bucket to use. "
        "Do NOT use seedance_auto_generate — it blocks for minutes and causes MCP timeout errors."
    ),
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _client() -> SeedanceClient:
    return SeedanceClient()


def _err(exc: Exception) -> dict[str, Any]:
    logger.error("Tool error: %s", exc)
    return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Video generation tools
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
) -> dict:
    """Submit a text-to-video generation job on Seedance 2.0.

    Args:
        prompt: Detailed scene description. Include subject, action, camera movement,
                lighting, and style for best results.
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15).
        resolution: Output quality. One of: 480p | 720p | 1080p
        generate_audio: Whether to generate a matching audio track.
        fast_mode: Use the faster/cheaper model variant (lower quality).
        seed: Random seed for reproducible results.
        camerafixed: Fix the camera — no panning or zooming.

    Returns:
        dict with task_id and status. Poll seedance_check_task every 10–15s.
    """
    try:
        result = _client().submit_text_to_video(
            prompt,
            ratio=ratio,
            duration=duration,
            resolution=resolution,
            generate_audio=generate_audio,
            fast_mode=fast_mode,
            seed=seed,
            camerafixed=camerafixed,
        )
    except SeedanceError as exc:
        return _err(exc)

    return {
        **result.to_dict(),
        "message": (
            f"Task submitted. Poll with seedance_check_task(task_id='{result.task_id}') "
            "every 10–15 seconds until status == 'succeeded'."
        ),
    }


@mcp.tool()
def seedance_image_to_video(
    prompt: str,
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
) -> dict:
    """Submit a reference-to-video generation job on Seedance 2.0.

    Supports the full all-round-reference set, bound by content[] role:
      1. image_urls: character/object/scene reference images (tag as [image1], [image2])
      2. first_frame_url: pin the exact starting frame
      3. first_frame_url + last_frame_url: transition between two images
      4. video_urls: reference videos for motion/camera rhythm (tag as [video1], ...)
      5. audio_urls: reference audio for lip-sync / beat / pacing (tag as [audio1], ...)

    Video extension: pass the previous clip as a video_url and describe the
    continuation in the prompt (e.g. "extend [video1] backward by N seconds,
    keeping character, background, and lighting consistent").

    Limits: ≤9 images, ≤3 videos, ≤3 audio. Video and audio references are
    URL-only (not auto-uploaded to the asset library).

    Args:
        prompt: Motion and camera description. Tag references as [image1], [video1], [audio1], etc.
        image_urls: Reference image URLs (HTTPS or asset://). Matched to [image1], [image2], ...
        first_frame_url: URL of the exact frame the video must START from.
        last_frame_url: URL of the exact frame the video must END at (requires first_frame_url).
        video_urls: Reference video URLs. Matched to [video1], [video2], ... (max 3).
        audio_urls: Reference audio URLs (MP3/WAV). Matched to [audio1], ... (max 3).
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15).
        resolution: Output quality. One of: 480p | 720p | 1080p
        generate_audio: Whether to generate a matching audio track (separate from audio_urls).
        fast_mode: Use the faster/cheaper model variant.
        seed: Random seed for reproducible results.
        camerafixed: Fix the camera — no movement.

    Returns:
        dict with task_id and status. Poll seedance_check_task every 10–15s.
    """
    try:
        result = _client().submit_image_to_video(
            prompt,
            image_urls=image_urls,
            first_frame_url=first_frame_url,
            last_frame_url=last_frame_url,
            video_urls=video_urls,
            audio_urls=audio_urls,
            ratio=ratio,
            duration=duration,
            resolution=resolution,
            generate_audio=generate_audio,
            fast_mode=fast_mode,
            seed=seed,
            camerafixed=camerafixed,
        )
    except SeedanceError as exc:
        return _err(exc)

    return {
        **result.to_dict(),
        "message": (
            f"Task submitted. Poll with seedance_check_task(task_id='{result.task_id}') "
            "every 10–15 seconds until status == 'succeeded'."
        ),
    }


@mcp.tool()
def seedance_generate(
    prompt: str,
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
) -> dict:
    """High-level tool: generate a Seedance video with automatic asset-library upload.

    Preferred over seedance_text_to_video / seedance_image_to_video for most use cases.
    Handles the full pipeline in one call:
      1. If image_url is a plain HTTPS URL: auto-creates asset group + uploads image.
      2. If image_url is already an asset:// ref: skips upload.
      3. video_urls / audio_urls are passed through as references (URL-only, not uploaded).
      4. If no references: submits text-to-video directly.
      5. Returns task_id — poll seedance_check_task until succeeded.

    Args:
        prompt: Scene/motion description. Tag references as [image1], [video1], [audio1].
        image_url: Reference image — plain HTTPS URL (auto-uploaded) or existing asset:// ref.
        first_frame_url: Pin the exact starting frame (HTTPS or asset://).
        last_frame_url: Pin the exact ending frame (requires first_frame_url).
        video_urls: Reference video URLs (motion/camera rhythm, or a clip to extend). Max 3.
        audio_urls: Reference audio URLs (lip-sync / beat / pacing, MP3/WAV). Max 3.
        ratio: Aspect ratio. One of: 21:9 | 16:9 | 4:3 | 1:1 | 3:4 | 9:16 | adaptive
        duration: Video length in seconds (4–15).
        resolution: Output quality. One of: 480p | 720p | 1080p
        generate_audio: Whether to generate a matching audio track (separate from audio_urls).
        fast_mode: Use the faster/cheaper model variant.
        seed: Random seed for reproducible results.
        camerafixed: Fix the camera — no panning or zooming.
        asset_group_id: Reuse an existing asset group (skips group creation).

    Returns:
        dict with task_id, status, mode, steps, and optional asset_id.
    """
    try:
        result = _client().generate(
            prompt,
            image_url=image_url,
            first_frame_url=first_frame_url,
            last_frame_url=last_frame_url,
            video_urls=video_urls,
            audio_urls=audio_urls,
            ratio=ratio,
            duration=duration,
            resolution=resolution,
            generate_audio=generate_audio,
            fast_mode=fast_mode,
            seed=seed,
            camerafixed=camerafixed,
            asset_group_id=asset_group_id,
        )
    except SeedanceError as exc:
        return _err(exc)

    return result.to_dict()


@mcp.tool()
def seedance_check_task(task_id: str) -> dict:
    """Check the status of a Seedance video generation task.

    Poll every 10–15 seconds after submitting a job. When status == 'succeeded'
    the response includes video_url.

    Args:
        task_id: The task ID returned by any generation tool.

    Returns:
        dict with status, and video_url when succeeded.
    """
    try:
        result = _client().check_task(task_id)
    except SeedanceError as exc:
        return _err(exc)

    out = result.to_dict()
    if result.video_url:
        out["message"] = "Video is ready. Download or display the video_url."
    elif result.terminal:
        out["message"] = f"Task ended with status '{result.status}'."
    else:
        out["message"] = f"Still processing (status='{result.status}'). Poll again in 10–15 seconds."
    return out


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
        status_filter: Optional. Filter by: queued | running | succeeded | failed | cancelled

    Returns:
        dict with tasks list and pagination info.
    """
    try:
        data = _client().list_tasks(page_num, page_size, status_filter)
    except SeedanceError as exc:
        return _err(exc)

    return {
        "total": data["total"],
        "page_num": data["page_num"],
        "page_size": data["page_size"],
        "tasks": [
            {
                "task_id": t.task_id,
                "status": t.status,
                "video_url": t.video_url,
            }
            for t in data["tasks"]
        ],
    }


@mcp.tool()
def seedance_cancel_task(task_id: str) -> dict:
    """Cancel a queued or running Seedance video generation task.

    Args:
        task_id: The task ID to cancel.
    """
    try:
        return _client().cancel_task(task_id)
    except SeedanceError as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Video upscaling / enhancement (AI MediaKit)
# ---------------------------------------------------------------------------

@mcp.tool()
def byteplus_upscale_video(
    video_url: str,
    tool_version: str = "standard",
    scene: str = "",
    resolution: str = "",
    resolution_limit: int = 0,
    bitrate_level: str = "",
    fps: float = 0,
    client_token: str = "",
    force_new: bool = False,
) -> dict:
    """Upscale / enhance an EXISTING video via BytePlus AI MediaKit.

    Standalone tool — independent of seedance_generate. Takes a publicly accessible
    video URL (e.g. a Seedance output URL) and runs AI enhancement: denoising, color
    enhancement, artifact removal, and super-resolution up to 4K. Asynchronous:
    returns a task_id; poll byteplus_check_upscale_task until status == 'completed'.

    Requires MEDIAKIT_API_KEY (separate from ARK_API_KEY; created in the AI MediaKit console).

    Idempotency: identical parameters reuse the same task for 24h (deterministic
    client_token + local cache). To force a fresh task on identical input, set
    force_new=True or pass a distinct client_token.

    Args:
        video_url: Publicly accessible HTTP/HTTPS URL of the source video
                   (mp4/flv/ts/avi/mov/wmv/mkv; input up to 2K, ≤10 GB recommended).
        tool_version: 'standard' (default, ~10 algorithms, fast) or 'professional'
                      (~30 algorithms, cinema-grade 4K).
        scene: Only for tool_version='standard'. One of:
               common | ugc | short_series | aigc | old_film
        resolution: Target resolution. One of:
                    240p | 360p | 480p | 540p | 720p | 1080p | 2k | 4k
                    (mutually exclusive with resolution_limit).
        resolution_limit: Short-side pixel cap [128, 2160], preserving aspect ratio
                          (mutually exclusive with resolution).
        bitrate_level: low | medium | high (default medium; may be ignored if fps is set).
        fps: Target frame rate [15, 120]. Omitted (0) keeps the source frame rate.
        client_token: Optional explicit idempotency token (≤64 printable ASCII).
        force_new: Force a brand-new task even for identical parameters.

    Returns:
        dict with task_id and status='submitted'. Poll byteplus_check_upscale_task.
    """
    try:
        result = _client().submit_video_enhance(
            video_url,
            tool_version=tool_version,
            scene=scene or None,
            resolution=resolution or None,
            resolution_limit=resolution_limit or None,
            bitrate_level=bitrate_level or None,
            fps=fps or None,
            client_token=client_token or None,
            force_new=force_new,
        )
    except SeedanceError as exc:
        return _err(exc)

    out = result.to_dict()
    if result.idempotent_hit:
        out["message"] = (
            f"Idempotent hit — reused existing task '{result.task_id}'. "
            f"Poll byteplus_check_upscale_task(task_id='{result.task_id}')."
        )
    else:
        out["message"] = (
            f"Upscale task submitted. Poll with "
            f"byteplus_check_upscale_task(task_id='{result.task_id}') "
            "every 10–15 seconds until status == 'completed'."
        )
    return out


@mcp.tool()
def byteplus_check_upscale_task(task_id: str) -> dict:
    """Check the status of an AI MediaKit video upscale/enhancement task.

    Poll every 10–15 seconds after submitting. When status == 'completed' the
    response includes video_url (valid for 24 hours — download promptly).

    Args:
        task_id: The task ID returned by byteplus_upscale_video.

    Returns:
        dict with status (running | processing | completed | failed) and, when
        completed, video_url plus duration/resolution/fps/tool_version.
    """
    try:
        result = _client().check_enhance_task(task_id)
    except SeedanceError as exc:
        return _err(exc)

    out = result.to_dict()
    if result.video_url:
        out["message"] = "Enhanced video is ready. Download the video_url within 24 hours."
    elif result.status == "failed":
        out["message"] = f"Upscale task failed: {result.error or 'unknown error'}."
    else:
        out["message"] = (
            f"Still processing (status='{result.status}'). Poll again in 10–15 seconds."
        )
    return out


# ---------------------------------------------------------------------------
# Asset library tools
# ---------------------------------------------------------------------------

@mcp.tool()
def seedance_create_asset_group(name: str, description: str = "") -> dict:
    """Create an asset group in the BytePlus asset library.

    One-time setup per project. Reuse the returned group_id across all uploads.

    Args:
        name: Short descriptive name (e.g. "my-portraits").
        description: Optional description.

    Returns:
        dict with group_id to pass to seedance_upload_asset.
    """
    try:
        result = _client().create_asset_group(name, description)
    except SeedanceError as exc:
        return _err(exc)

    return {
        **result.to_dict(),
        "message": f"Asset group created. Use group_id='{result.group_id}' in seedance_upload_asset.",
    }


@mcp.tool()
def seedance_upload_asset(image_url: str, group_id: str) -> dict:
    """Upload an image to the BytePlus asset library and wait until Active.

    Required for portrait/sensitive images that are rejected as plain URLs.

    Args:
        image_url: Publicly accessible HTTPS URL (JPEG/PNG/WebP).
        group_id: Group ID from seedance_create_asset_group.

    Returns:
        dict with asset_id, asset_ref ("asset://..."), and status.
    """
    try:
        result = _client().upload_asset(image_url, group_id)
    except SeedanceError as exc:
        return _err(exc)

    return {
        **result.to_dict(),
        "message": (
            f"Asset ready. Pass asset_ref '{result.asset_ref}' as one of the "
            "image_urls in seedance_image_to_video."
        ),
    }


@mcp.tool()
def seedance_get_asset(asset_id: str) -> dict:
    """Check the status of an asset in the BytePlus asset library.

    Args:
        asset_id: The asset ID returned by seedance_upload_asset.

    Returns:
        dict with asset_id, status (Processing | Active | Failed), and asset_ref.
    """
    try:
        result = _client().get_asset(asset_id)
    except SeedanceError as exc:
        return _err(exc)

    out = result.to_dict()
    if result.active:
        out["message"] = f"Asset is ready. Pass '{result.asset_ref}' to seedance_image_to_video."
    elif result.error:
        out["message"] = "Asset processing failed."
    else:
        out["message"] = f"Asset status is '{result.status}'. Poll again in a few seconds."
    return out


# ---------------------------------------------------------------------------
# TOS object storage tools
# ---------------------------------------------------------------------------

@mcp.tool()
def seedance_list_tos_buckets() -> dict:
    """List the TOS (object storage) buckets available to your AK/SK.

    Call this first when the user wants to upload a local image but has not said
    which bucket — show the list and ask which bucket to use, then pass that
    bucket to seedance_upload_image_to_tos.

    Returns:
        dict with a `buckets` list (name, location, creation_date).
    """
    try:
        buckets = _client().list_tos_buckets()
    except SeedanceError as exc:
        return _err(exc)

    return {
        "status": "ok",
        "count": len(buckets),
        "buckets": buckets,
        "message": (
            "Ask the user which bucket to upload to, then call "
            "seedance_upload_image_to_tos(file_path=..., bucket=...)."
            if buckets else "No buckets found for these credentials."
        ),
    }


@mcp.tool()
def seedance_upload_image_to_tos(file_path: str, bucket: str = "", key: str = "") -> dict:
    """Upload a LOCAL image file to a TOS bucket and return its public URL.

    Reads the file from the local filesystem (this server runs locally), uploads
    it to the bucket with a public-read ACL, and returns a directly fetchable URL
    that can be shared or passed to seedance_generate / seedance_image_to_video.

    If `bucket` is empty and no default (SEEDANCE_TOS_BUCKET) is configured, call
    seedance_list_tos_buckets first and ask the user which bucket to use.

    Args:
        file_path: Absolute path to a local image (e.g. /Users/you/photo.png).
        bucket: Target TOS bucket. Optional if SEEDANCE_TOS_BUCKET is set.
        key: Object key within the bucket. Defaults to the filename.

    Returns:
        dict with bucket, key, and the public url.
    """
    try:
        result = _client().upload_to_tos(file_path, bucket, key)
    except SeedanceError as exc:
        return _err(exc)

    return {
        **result.to_dict(),
        "message": (
            f"Uploaded. Public URL: {result.url}\n"
            "Share this URL, or pass it as image_url to seedance_generate."
        ),
    }


@mcp.tool()
def seedance_list_models() -> dict:
    """List available Seedance models and their capabilities."""
    return _client().list_models()


@mcp.tool()
def seedance_ping() -> dict:
    """Check server liveness and current configuration."""
    return _client().ping()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    port = int(os.getenv("PORT", "8000"))
    auth_token = os.getenv("MCP_AUTH_TOKEN", "").strip()

    if transport == "sse":
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit("SSE transport requires uvicorn: pip install uvicorn") from exc

        mcp_app = mcp.streamable_http_app()

        class _Gateway:
            """ASGI middleware: health check, bearer-token auth, host-header rewrite."""

            def __init__(self, app: Any) -> None:
                self._app = app

            async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
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

                if auth_token:
                    hdrs = {k.lower(): v for k, v in scope.get("headers", [])}
                    auth = hdrs.get(b"authorization", b"").decode()
                    if auth != f"Bearer {auth_token}":
                        body = json.dumps({"error": "Unauthorized"}).encode()
                        await send({"type": "http.response.start", "status": 401,
                                    "headers": [(b"content-type", b"application/json")]})
                        await send({"type": "http.response.body", "body": body})
                        return

                new_hdrs = [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"host"]
                new_hdrs.append((b"host", b"localhost"))
                await self._app({**scope, "headers": new_hdrs}, receive, send)

        logger.info("Starting Seedance MCP server v%s on :%d (streamable-http, auth=%s)",
                    __version__, port, bool(auth_token))
        uvicorn.run(_Gateway(mcp_app), host="0.0.0.0", port=port)
    else:
        logger.info("Starting Seedance MCP server v%s (stdio)...", __version__)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    _main()
