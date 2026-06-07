"""Tests for SeedanceClient — HTTP calls mocked at the urllib boundary."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from seedance import SeedanceClient
from seedance.exceptions import ValidationError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_AK", "test-ak")
    monkeypatch.setenv("ARK_SK", "test-sk")
    return SeedanceClient()


def _mock_http(response: dict):
    """Return a context manager that makes request_with_retry return response.

    Must patch the name as imported in client.py, not the definition site.
    """
    return patch(
        "seedance.client.request_with_retry",
        return_value=response,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_invalid_ratio_raises(client):
    with pytest.raises(ValidationError, match="ratio"):
        client.submit_text_to_video("test", ratio="99:1")


def test_invalid_duration_raises(client):
    with pytest.raises(ValidationError, match="duration"):
        client.submit_text_to_video("test", duration=99)


def test_invalid_resolution_raises(client):
    with pytest.raises(ValidationError, match="resolution"):
        client.submit_text_to_video("test", resolution="4K")


def test_image_to_video_requires_image(client):
    with pytest.raises(ValidationError, match="at least one"):
        client.submit_image_to_video("test")


def test_last_frame_without_first_raises(client):
    with pytest.raises(ValidationError, match="last_frame_url requires"):
        client.submit_image_to_video("test", last_frame_url="https://example.com/frame.jpg")


# ---------------------------------------------------------------------------
# Text-to-video
# ---------------------------------------------------------------------------

def test_submit_text_to_video_returns_task_id(client):
    with _mock_http({"id": "task-abc123", "status": "queued"}):
        result = client.submit_text_to_video("A sunrise over mountains")
    assert result.task_id == "task-abc123"
    assert result.status == "queued"
    assert result.mode == "T2V"


def test_submit_t2v_fast_mode(client):
    with _mock_http({"id": "task-fast", "status": "queued"}) as mock:
        client.submit_text_to_video("test", fast_mode=True)
        call_kwargs = mock.call_args
        payload = call_kwargs.kwargs.get("payload") or call_kwargs[1].get("payload")
        from seedance.config import FAST_MODEL
        assert payload["model"] == FAST_MODEL


# ---------------------------------------------------------------------------
# Check task
# ---------------------------------------------------------------------------

def test_check_task_succeeded(client):
    with _mock_http({
        "status": "succeeded",
        "content": {"video_url": "https://cdn.example.com/video.mp4"},
    }):
        result = client.check_task("task-abc123")
    assert result.succeeded
    assert result.video_url == "https://cdn.example.com/video.mp4"


def test_check_task_running(client):
    with _mock_http({"status": "running"}):
        result = client.check_task("task-running")
    assert not result.terminal
    assert result.video_url is None


def test_check_task_requires_id(client):
    with pytest.raises(ValidationError, match="task_id"):
        client.check_task("")


# ---------------------------------------------------------------------------
# List tasks
# ---------------------------------------------------------------------------

def test_list_tasks_returns_task_objects(client):
    with _mock_http({
        "total": 2,
        "items": [
            {"id": "t1", "status": "succeeded", "content": {"video_url": "https://example.com/1.mp4"}},
            {"id": "t2", "status": "running"},
        ],
    }):
        data = client.list_tasks()

    assert data["total"] == 2
    assert len(data["tasks"]) == 2
    assert data["tasks"][0].task_id == "t1"
    assert data["tasks"][0].video_url == "https://example.com/1.mp4"


# ---------------------------------------------------------------------------
# Ping / models
# ---------------------------------------------------------------------------

def test_ping_returns_version(client, monkeypatch, tmp_path):
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", tmp_path / "credentials")
    result = client.ping()
    assert result["status"] == "ok"
    assert "version" in result


def test_list_models_returns_known_models(client):
    data = client.list_models()
    model_ids = [m["model_id"] for m in data["models"]]
    assert "dreamina-seedance-2-0-260128" in model_ids
    assert "dreamina-seedance-2-0-fast-260128" in model_ids
