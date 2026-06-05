from __future__ import annotations
import os

__version__ = "1.5.0"

# Video generation API
BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
DEFAULT_MODEL = "dreamina-seedance-2-0-260128"
FAST_MODEL = "dreamina-seedance-2-0-fast-260128"

SUBMIT_TIMEOUT = int(os.getenv("SEEDANCE_SUBMIT_TIMEOUT", "30"))
POLL_TIMEOUT = int(os.getenv("SEEDANCE_POLL_TIMEOUT", "15"))
MAX_RETRIES = int(os.getenv("SEEDANCE_MAX_RETRIES", "3"))
INCLUDE_RAW = os.getenv("SEEDANCE_DEBUG_RAW", "").lower() in ("1", "true", "yes")

TERMINAL = {"succeeded", "failed", "cancelled"}
VALID_RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"}
VALID_RESOLUTIONS = {"480p", "720p", "1080p"}
PAGE_SIZE_MAX = 50

MODELS: dict[str, dict] = {
    "dreamina-seedance-2-0-260128": {
        "label": "Seedance 2.0 Standard",
        "alias": "standard",
        "resolutions": ["480p", "720p", "1080p"],
        "ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"],
        "duration_range": [4, 15],
        "supports_first_frame": True,
        "supports_last_frame": True,
        "supports_camerafixed": True,
        "supports_seed": True,
        "supports_draft": True,
    },
    "dreamina-seedance-2-0-fast-260128": {
        "label": "Seedance 2.0 Fast",
        "alias": "fast",
        "resolutions": ["480p", "720p", "1080p"],
        "ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "adaptive"],
        "duration_range": [4, 15],
        "supports_first_frame": True,
        "supports_last_frame": True,
        "supports_camerafixed": True,
        "supports_seed": True,
        "supports_draft": True,
    },
}


def _model_caps(model: str) -> dict:
    return MODELS.get(model, MODELS[DEFAULT_MODEL])


DURATION_MIN = _model_caps(DEFAULT_MODEL)["duration_range"][0]
DURATION_MAX = _model_caps(DEFAULT_MODEL)["duration_range"][1]

# Asset library API (HMAC-SHA256 AK/SK auth)
ASSET_HOST = "ark.ap-southeast-1.byteplusapi.com"
ASSET_SERVICE = "ark"
ASSET_REGION = "ap-southeast-1"
ASSET_VERSION = "2024-01-01"
ASSET_POLL_INTERVAL = int(os.getenv("SEEDANCE_ASSET_POLL_INTERVAL", "10"))
ASSET_POLL_TIMEOUT = int(os.getenv("SEEDANCE_ASSET_POLL_TIMEOUT", "120"))
ASSET_TERMINAL = {"Active", "Failed"}
