"""BytePlus Asset Library — HMAC-SHA256 auth and API calls."""
from __future__ import annotations

import datetime
import hashlib
import hmac as hmac_lib
import json
import logging
import os
import random
import time
from typing import Any
from urllib import error, parse, request

from .config import (
    ASSET_HOST, ASSET_POLL_INTERVAL, ASSET_POLL_TIMEOUT, ASSET_REGION,
    ASSET_SERVICE, ASSET_VERSION, MAX_RETRIES, POLL_TIMEOUT,
)

logger = logging.getLogger("seedance_mcp")

_cached_ak: str | None = None
_cached_sk: str | None = None


def _asset_credentials() -> tuple[str, str]:
    global _cached_ak, _cached_sk
    if _cached_ak and _cached_sk:
        return _cached_ak, _cached_sk
    ak = os.getenv("ARK_AK", "").strip()
    sk = os.getenv("ARK_SK", "").strip()
    if not ak or not sk:
        raise RuntimeError(
            "ARK_AK and ARK_SK are required for asset library operations. "
            "Pass them as -e ARK_AK=<key> -e ARK_SK=<secret> when registering the server."
        )
    _cached_ak, _cached_sk = ak, sk
    return ak, sk


def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac_lib.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _norm_query(params: dict) -> str:
    """Sort and URL-encode query params per BytePlus signing spec."""
    parts = []
    for key in sorted(params.keys()):
        values = params[key] if isinstance(params[key], list) else [params[key]]
        for v in values:
            parts.append(
                parse.quote(key, safe="-_.~") + "=" + parse.quote(str(v), safe="-_.~")
            )
    return "&".join(parts)


def _asset_api(action: str, body: dict, timeout: int = POLL_TIMEOUT) -> dict[str, Any]:
    """Call a BytePlus Asset Library OpenAPI action with HMAC-SHA256 signing."""
    ak, sk = _asset_credentials()
    body_str = json.dumps(body)
    now = datetime.datetime.utcnow()
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    content_sha256 = _sha256_hex(body_str)

    query_params = {"Action": action, "Version": ASSET_VERSION}
    canonical_query = _norm_query(query_params)

    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{ASSET_HOST}\n"
        f"x-content-sha256:{content_sha256}\n"
        f"x-date:{x_date}\n"
    )
    signed_headers = "content-type;host;x-content-sha256;x-date"

    canonical_request = "\n".join([
        "POST", "/", canonical_query, canonical_headers, signed_headers, content_sha256,
    ])

    credential_scope = f"{short_date}/{ASSET_REGION}/{ASSET_SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256", x_date, credential_scope, _sha256_hex(canonical_request),
    ])

    k_date    = _hmac_sha256(sk.encode("utf-8"), short_date)
    k_region  = _hmac_sha256(k_date, ASSET_REGION)
    k_service = _hmac_sha256(k_region, ASSET_SERVICE)
    k_signing = _hmac_sha256(k_service, "request")
    signature = _hmac_sha256(k_signing, string_to_sign).hex()

    authorization = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    url = f"https://{ASSET_HOST}/?{canonical_query}"
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "X-Content-Sha256": content_sha256,
        "X-Date": x_date,
        "Host": ASSET_HOST,
    }
    req = request.Request(url, data=body_str.encode(), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as exc:
        detail = exc.read().decode(errors="ignore")
        raise RuntimeError(f"Asset API HTTP {exc.code}: {detail}") from exc


def _asset_api_with_retry(action: str, body: dict, correlation_id: str = "") -> dict[str, Any]:
    tag = f"[{correlation_id}] " if correlation_id else ""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return _asset_api(action, body)
        except RuntimeError as exc:
            last_exc = exc
            msg = str(exc)
            if "HTTP 4" in msg or "ARK_AK" in msg or "ARK_SK" in msg:
                raise
            wait = (2 ** attempt) + random.random()
            logger.warning("%sAsset API retry in %.1fs (attempt %d/%d): %s", tag, wait, attempt + 1, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
        except error.URLError as exc:
            last_exc = exc
            wait = (2 ** attempt) + random.random()
            logger.warning("%sAsset API network error, retrying in %.1fs: %s", tag, wait, exc)
            if attempt < MAX_RETRIES - 1:
                time.sleep(wait)
    raise RuntimeError(f"Asset API request failed after {MAX_RETRIES} attempts: {last_exc}") from last_exc


def extract_nested(data: dict, *keys: str) -> str:
    """Safely extract a string value from a nested dict."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    if current is None:
        return ""
    return str(current)


def upload_image_as_asset(image_url: str, group_id: str, cid: str) -> tuple[str, str, dict | None]:
    """Upload image_url to the asset library and poll until Active.

    Returns (asset_id, asset_ref, error_dict).
    On success error_dict is None; on failure asset_ref is "" and error_dict has details.
    """
    logger.info("[%s] Creating asset | group=%s url=%.60s", cid, group_id, image_url)
    create_body = {"GroupId": group_id, "URL": image_url, "AssetType": "Image"}
    try:
        create_resp = _asset_api_with_retry("CreateAsset", create_body, correlation_id=cid)
    except RuntimeError as exc:
        return "", "", {"status": "error", "error": str(exc)}

    asset_id = (
        extract_nested(create_resp, "Result", "Id")
        or extract_nested(create_resp, "Result", "AssetId")
        or extract_nested(create_resp, "Id")
        or extract_nested(create_resp, "AssetId")
    )
    if not asset_id:
        return "", "", {"status": "error", "error": "CreateAsset did not return an asset_id."}

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
            return asset_id, f"asset://{asset_id}", None
        if status == "Failed":
            err = (
                extract_nested(get_resp, "Result", "Error")
                or extract_nested(get_resp, "Error")
                or "unknown error"
            )
            return asset_id, "", {"status": "Failed", "error": f"Asset processing failed: {err}"}

    return asset_id, f"asset://{asset_id}", {
        "status": "timeout",
        "error": (
            f"Asset did not become Active within {ASSET_POLL_TIMEOUT}s. "
            f"Use seedance_get_asset(asset_id='{asset_id}') to continue polling."
        ),
    }
