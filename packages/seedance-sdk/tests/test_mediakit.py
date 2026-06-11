"""Tests for the AI MediaKit upscale path — HTTP mocked at the request boundary."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from seedance import SeedanceClient
from seedance.exceptions import ValidationError
from seedance.mediakit import MediaKitClient, TaskCache, make_client_token


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIAKIT_API_KEY", "test-mediakit-key")
    # Isolate the idempotency cache so deterministic tokens never hit the real ~/.seedance file.
    monkeypatch.setattr("seedance.mediakit.MEDIAKIT_CACHE_PATH", tmp_path / "upscale_cache.json")
    return SeedanceClient()


def _mock_http(response: dict):
    """Patch request_with_retry as imported in mediakit.py."""
    return patch("seedance.mediakit.request_with_retry", return_value=response)


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

def test_submit_enhance_returns_task_id(client):
    with _mock_http({"success": True, "task_id": "amk-123", "request_id": "req-1"}):
        result = client.submit_video_enhance("https://example.com/v.mp4", resolution="1080p")
    assert result.task_id == "amk-123"
    assert result.status == "submitted"
    assert result.request_id == "req-1"
    assert result.idempotent_hit is False


def test_submit_sends_client_token_and_params(client):
    with _mock_http({"success": True, "task_id": "amk-1"}) as mock:
        client.submit_video_enhance(
            "https://example.com/v.mp4",
            tool_version="professional", resolution="4k", fps=60,
        )
    payload = mock.call_args.kwargs["payload"]
    assert payload["video_url"] == "https://example.com/v.mp4"
    assert payload["tool_version"] == "professional"
    assert payload["resolution"] == "4k"
    assert payload["fps"] == 60
    assert payload["client_token"].startswith("amk-")
    assert len(payload["client_token"]) <= 64


# ---------------------------------------------------------------------------
# Idempotency token + local cache
# ---------------------------------------------------------------------------

def test_make_client_token_deterministic_and_order_independent():
    a = make_client_token({"video_url": "u", "resolution": "1080p", "fps": 30})
    b = make_client_token({"fps": 30, "resolution": "1080p", "video_url": "u"})
    c = make_client_token({"video_url": "u", "resolution": "720p", "fps": 30})
    assert a == b
    assert a != c
    assert a.startswith("amk-") and len(a) <= 64


def test_make_client_token_ignores_none():
    a = make_client_token({"video_url": "u", "scene": None})
    b = make_client_token({"video_url": "u"})
    assert a == b


def test_cache_short_circuits_duplicate_submit(tmp_path):
    cache = TaskCache(path=tmp_path / "cache.json")
    mk = MediaKitClient("test-key", cache=cache)
    with patch(
        "seedance.mediakit.request_with_retry",
        return_value={"success": True, "task_id": "amk-cached"},
    ) as mock:
        first = mk.submit_enhance("https://example.com/v.mp4", resolution="1080p")
        second = mk.submit_enhance("https://example.com/v.mp4", resolution="1080p")
    assert mock.call_count == 1                 # second submit was a cache hit
    assert first["task_id"] == "amk-cached"
    assert second["task_id"] == "amk-cached"
    assert second["idempotent_hit"] is True


def test_force_new_bypasses_cache(tmp_path):
    cache = TaskCache(path=tmp_path / "cache.json")
    mk = MediaKitClient("test-key", cache=cache)
    with patch(
        "seedance.mediakit.request_with_retry",
        return_value={"success": True, "task_id": "amk-x"},
    ) as mock:
        mk.submit_enhance("https://example.com/v.mp4", resolution="1080p")
        mk.submit_enhance("https://example.com/v.mp4", resolution="1080p", force_new=True)
    assert mock.call_count == 2                 # force_new always hits the API


def test_explicit_client_token_used_verbatim(tmp_path):
    cache = TaskCache(path=tmp_path / "cache.json")
    mk = MediaKitClient("test-key", cache=cache)
    with patch(
        "seedance.mediakit.request_with_retry",
        return_value={"success": True, "task_id": "amk-y"},
    ) as mock:
        mk.submit_enhance("https://example.com/v.mp4", client_token="my-token-123")
    assert mock.call_args.kwargs["payload"]["client_token"] == "my-token-123"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_resolution_and_limit_mutually_exclusive(client):
    with pytest.raises(ValidationError, match="mutually exclusive"):
        client.submit_video_enhance("https://e.com/v.mp4", resolution="1080p", resolution_limit=1920)


def test_invalid_fps_raises(client):
    with pytest.raises(ValidationError, match="fps"):
        client.submit_video_enhance("https://e.com/v.mp4", fps=240)


def test_invalid_tool_version_raises(client):
    with pytest.raises(ValidationError, match="tool_version"):
        client.submit_video_enhance("https://e.com/v.mp4", tool_version="ultra")


def test_scene_with_professional_raises(client):
    with pytest.raises(ValidationError, match="scene only applies"):
        client.submit_video_enhance("https://e.com/v.mp4", tool_version="professional", scene="ugc")


def test_invalid_resolution_raises(client):
    with pytest.raises(ValidationError, match="resolution"):
        client.submit_video_enhance("https://e.com/v.mp4", resolution="8k")


def test_client_token_too_long_raises(client):
    with pytest.raises(ValidationError, match="client_token"):
        client.submit_video_enhance("https://e.com/v.mp4", client_token="x" * 65)


def test_missing_video_url_raises(client):
    with pytest.raises(ValidationError, match="video_url"):
        client.submit_video_enhance("")


# ---------------------------------------------------------------------------
# Check task
# ---------------------------------------------------------------------------

def test_check_enhance_running(client):
    with _mock_http({"success": True, "task_id": "amk-1", "status": "running"}):
        result = client.check_enhance_task("amk-1")
    assert result.status == "running"
    assert not result.terminal
    assert result.video_url is None


def test_check_enhance_completed(client):
    with _mock_http({
        "success": True, "task_id": "amk-1", "status": "completed",
        "result": {"video_url": "https://cdn/out.mp4", "resolution": "1080p", "fps": 60, "duration": 12.5},
    }):
        result = client.check_enhance_task("amk-1")
    assert result.succeeded
    assert result.video_url == "https://cdn/out.mp4"
    assert result.resolution == "1080p"
    assert result.fps == 60
    assert result.duration == 12.5


def test_check_enhance_failed(client):
    with _mock_http({
        "success": True, "task_id": "amk-1", "status": "failed",
        "error": {"code": "DownloadFailed", "message": "bad url", "type": "TaskError"},
    }):
        result = client.check_enhance_task("amk-1")
    assert result.status == "failed"
    assert result.terminal
    assert result.error["code"] == "DownloadFailed"


def test_check_enhance_requires_id(client):
    with pytest.raises(ValidationError, match="task_id"):
        client.check_enhance_task("")
