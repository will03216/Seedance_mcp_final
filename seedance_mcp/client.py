"""BytePlus ModelArk video generation — HTTP client and payload helpers."""
from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any
from urllib import error, request

from .config import (
    BASE_URL, INCLUDE_RAW, MAX_RETRIES, POLL_TIMEOUT,
    SUBMIT_TIMEOUT, TERMINAL, _model_caps,
)

logger = logging.getLogger("seedance_mcp")

_cached_key: str | None = None


def _api_key() -> str:
    global _cached_key
    if _cached_key:
        return _cached_key
    key = os.getenv("ARK_API_KEY", "").strip()
    if not key:
        fallback = Path(__file__).parent / "ark_api_key.txt"
        if fallback.exists():
            key = fallback.read_text().strip()
    if not key:
        raise RuntimeError(
            "ARK_API_KEY is not set. "
            "Export it as an environment variable or create ark_api_key.txt next to server.py."
        )
    _cached_key = key
    return key


def _http(
    url: str,
    *,
    method: str,
    payload: dict | None = None,
    timeout: int = POLL_TIMEOUT,
) -> dict[str, Any]:
    key = _api_key()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(payload).encode() if payload else None
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _http_with_retry(
    url: str,
    *,
    method: str,
    payload: dict | None = None,
    timeout: int = POLL_TIMEOUT,
    correlation_id: str = "",
) -> dict[str, Any]:
    tag = f"[{correlation_id}] " if correlation_id else ""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return _http(url, method=method, payload=payload, timeout=timeout)
        except RuntimeError as exc:
            last_exc = exc
            if "HTTP 4" in str(exc):
                raise
            wait = (2 ** attempt) + random.random()
            logger.warning(
                "%sRetrying in %.1fs (attempt %d/%d): %s",
                tag, wait, attempt + 1, MAX_RETRIES, exc,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
        except error.URLError as exc:
            last_exc = exc
            wait = (2 ** attempt) + random.random()
            logger.warning("%sNetwork error, retrying in %.1fs: %s", tag, wait, exc)
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
    raise RuntimeError(f"Request failed after {MAX_RETRIES} attempts: {last_exc}") from last_exc


def _submit(payload: dict, correlation_id: str = "") -> dict:
    return _http_with_retry(
        f"{BASE_URL}/contents/generations/tasks",
        method="POST",
        payload=payload,
        timeout=SUBMIT_TIMEOUT,
        correlation_id=correlation_id,
    )


def _get(task_id: str, correlation_id: str = "") -> dict:
    return _http_with_retry(
        f"{BASE_URL}/contents/generations/tasks/{task_id}",
        method="GET",
        timeout=POLL_TIMEOUT,
        correlation_id=correlation_id,
    )


def _cancel(task_id: str, correlation_id: str = "") -> dict:
    return _http_with_retry(
        f"{BASE_URL}/contents/generations/tasks/{task_id}",
        method="DELETE",
        timeout=POLL_TIMEOUT,
        correlation_id=correlation_id,
    )


def _extract_video_url(task: dict) -> str | None:
    for extractor in [
        lambda t: t["content"]["video_url"],
        lambda t: t["result"]["video_url"],
        lambda t: t["output"]["video_url"],
    ]:
        try:
            url = extractor(task)
            if url:
                return url
        except (KeyError, TypeError):
            pass
    if task.get("status") == "succeeded":
        logger.warning(
            "Task succeeded but video_url could not be extracted. Response keys: %s",
            list(task.keys()),
        )
    return None


def _maybe_raw(resp: dict) -> dict:
    return {"raw": resp} if INCLUDE_RAW else {}


def _error_result(exc: Exception, context: str = "") -> dict[str, Any]:
    msg = str(exc)
    logger.error("Error%s: %s", f" ({context})" if context else "", msg)
    return {"status": "error", "error": msg}


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


def _extra_params(seed: int | None, camerafixed: bool, draft: bool) -> dict:
    params: dict = {}
    if seed is not None:
        params["seed"] = seed
    if camerafixed:
        params["camerafixed"] = True
    if draft:
        params["draft"] = True
    return params


def _validate_common(ratio: str, duration: int, resolution: str, model: str) -> None:
    caps = _model_caps(model)
    valid_ratios = set(caps["ratios"])
    valid_resolutions = set(caps["resolutions"])
    dur_min, dur_max = caps["duration_range"]

    if ratio not in valid_ratios:
        raise ValueError(
            f"Invalid ratio {ratio!r}. Must be one of: {', '.join(sorted(valid_ratios))}"
        )
    if not dur_min <= duration <= dur_max:
        raise ValueError(
            f"Invalid duration {duration}. Must be between {dur_min} and {dur_max} seconds for {model}."
        )
    if resolution not in valid_resolutions:
        raise ValueError(
            f"Invalid resolution {resolution!r}. Must be one of: {', '.join(sorted(valid_resolutions))}"
        )
