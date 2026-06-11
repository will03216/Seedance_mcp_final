"""SDK-wide constants and model capability registry."""
from __future__ import annotations

import os
from pathlib import Path

__version__ = "2.0.0"

# Video generation API
BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
DEFAULT_MODEL = "dreamina-seedance-2-0-260128"
FAST_MODEL = "dreamina-seedance-2-0-fast-260128"

SUBMIT_TIMEOUT = int(os.getenv("SEEDANCE_SUBMIT_TIMEOUT", "30"))
POLL_TIMEOUT = int(os.getenv("SEEDANCE_POLL_TIMEOUT", "15"))
MAX_RETRIES = int(os.getenv("SEEDANCE_MAX_RETRIES", "3"))
INCLUDE_RAW = os.getenv("SEEDANCE_DEBUG_RAW", "").lower() in ("1", "true", "yes")

TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "failed", "cancelled"})
PAGE_SIZE_MAX = 50

MODELS: dict[str, dict] = {
    "dreamina-seedance-2-0-260128": {
        "label": "Seedance 2.0 Standard",
        "alias": "standard",
        "resolutions": ["480p", "720p", "1080p"],
        "ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"],
        "duration_range": [4, 15],
        "supports_first_frame": True,
        "supports_last_frame": False,
        "supports_camerafixed": True,
        "supports_seed": True,
    },
    "dreamina-seedance-2-0-fast-260128": {
        "label": "Seedance 2.0 Fast",
        "alias": "fast",
        "resolutions": ["480p", "720p", "1080p"],
        "ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"],
        "duration_range": [4, 15],
        "supports_first_frame": True,
        "supports_last_frame": False,
        "supports_camerafixed": True,
        "supports_seed": True,
    },
}


def model_caps(model: str) -> dict:
    return MODELS.get(model, MODELS[DEFAULT_MODEL])


# Asset library API (HMAC-SHA256 AK/SK auth)
# Host matches the byteplus-go-sdk-v2 default endpoint (open.* prefix, not ark.*)
ASSET_HOST = "open.ap-southeast-1.byteplusapi.com"
ASSET_CONTENT_TYPE = "application/json; charset=utf-8"
ASSET_SERVICE = "ark"
ASSET_REGION = "ap-southeast-1"
ASSET_VERSION = "2024-01-01"
ASSET_POLL_INTERVAL = int(os.getenv("SEEDANCE_ASSET_POLL_INTERVAL", "10"))
ASSET_POLL_TIMEOUT = int(os.getenv("SEEDANCE_ASSET_POLL_TIMEOUT", "120"))


# AI MediaKit video-enhancement API (Bearer auth, separate host + API key)
# Docs: https://docs.byteplus.com/en/docs/byteplus-vod/ai-mediakit-create-a-video-enhancement-task
MEDIAKIT_BASE_URL = os.getenv(
    "SEEDANCE_MEDIAKIT_BASE_URL",
    "https://mediakit.ap-southeast-1.bytepluses.com/api/v1",
)
MEDIAKIT_TOOL_VERSIONS = frozenset({"standard", "professional"})
MEDIAKIT_SCENES = frozenset({"common", "ugc", "short_series", "aigc", "old_film"})
MEDIAKIT_RESOLUTIONS = frozenset({"240p", "360p", "480p", "540p", "720p", "1080p", "2k", "4k"})
MEDIAKIT_BITRATE_LEVELS = frozenset({"low", "medium", "high"})
MEDIAKIT_RESOLUTION_LIMIT_RANGE = (128, 2160)
MEDIAKIT_FPS_RANGE = (15, 120)
MEDIAKIT_CLIENT_TOKEN_MAXLEN = 64
# In-progress statuses vary across docs (running / processing); terminal is fixed.
MEDIAKIT_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed"})

# Local idempotency cache (token -> task_id); TTL matches the server's 24h dedup window.
MEDIAKIT_CACHE_PATH = Path.home() / ".seedance" / "upscale_cache.json"
MEDIAKIT_CACHE_TTL = int(os.getenv("SEEDANCE_MEDIAKIT_CACHE_TTL", str(24 * 3600)))
