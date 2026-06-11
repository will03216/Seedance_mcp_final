"""Smoke tests for MCP tool contracts — verify shape of returned dicts."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from seedance.types import GenerateResult, TaskResult, UpscaleResult


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_AK", "test-ak")
    monkeypatch.setenv("ARK_SK", "test-sk")
    monkeypatch.setenv("MEDIAKIT_API_KEY", "test-mediakit-key")


def _import_tools():
    from seedance_mcp.server import (
        seedance_check_task,
        seedance_generate,
        seedance_list_models,
        seedance_ping,
        seedance_text_to_video,
    )
    return seedance_text_to_video, seedance_check_task, seedance_generate, seedance_list_models, seedance_ping


def test_text_to_video_returns_task_id():
    t2v, *_ = _import_tools()
    mock_result = TaskResult(task_id="task-123", status="queued", mode="T2V")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_text_to_video.return_value = mock_result
        result = t2v("A sunrise over mountains")
    assert result["task_id"] == "task-123"
    assert result["status"] == "queued"
    assert "message" in result


def test_check_task_succeeded_has_video_url():
    _, check, *_ = _import_tools()
    mock_result = TaskResult(
        task_id="task-123",
        status="succeeded",
        video_url="https://cdn.example.com/video.mp4",
    )
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = check("task-123")
    assert result["video_url"] == "https://cdn.example.com/video.mp4"
    assert "ready" in result["message"].lower()


def test_check_task_running_has_poll_message():
    _, check, *_ = _import_tools()
    mock_result = TaskResult(task_id="task-123", status="running")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = check("task-123")
    assert "poll" in result["message"].lower()


def test_generate_returns_steps():
    _, _, gen, *_ = _import_tools()
    mock_result = GenerateResult(
        task_id="task-999",
        status="queued",
        mode="T2V",
        steps=[{"step": "submit_job", "task_id": "task-999", "outcome": "queued"}],
    )
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = gen("A test prompt")
    assert result["task_id"] == "task-999"
    assert len(result["steps"]) == 1


def test_error_from_sdk_returns_error_dict():
    from seedance.exceptions import ValidationError
    t2v, *_ = _import_tools()
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_text_to_video.side_effect = ValidationError("bad ratio")
        result = t2v("test")
    assert result["status"] == "error"
    assert "bad ratio" in result["error"]


def test_upscale_video_returns_task_id():
    from seedance_mcp.server import byteplus_upscale_video
    mock_result = UpscaleResult(task_id="amk-123", status="submitted")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_enhance.return_value = mock_result
        result = byteplus_upscale_video("https://example.com/v.mp4", resolution="1080p")
    assert result["task_id"] == "amk-123"
    assert result["status"] == "submitted"
    assert "byteplus_check_upscale_task" in result["message"]


def test_upscale_idempotent_hit_message():
    from seedance_mcp.server import byteplus_upscale_video
    mock_result = UpscaleResult(task_id="amk-123", status="submitted", idempotent_hit=True)
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_enhance.return_value = mock_result
        result = byteplus_upscale_video("https://example.com/v.mp4")
    assert result["idempotent_hit"] is True
    assert "idempotent" in result["message"].lower()


def test_check_upscale_completed_has_video_url():
    from seedance_mcp.server import byteplus_check_upscale_task
    mock_result = UpscaleResult(
        task_id="amk-123", status="completed", video_url="https://cdn/out.mp4",
    )
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.check_enhance_task.return_value = mock_result
        result = byteplus_check_upscale_task("amk-123")
    assert result["video_url"] == "https://cdn/out.mp4"
    assert "ready" in result["message"].lower()


def test_check_upscale_running_has_poll_message():
    from seedance_mcp.server import byteplus_check_upscale_task
    mock_result = UpscaleResult(task_id="amk-123", status="running")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.check_enhance_task.return_value = mock_result
        result = byteplus_check_upscale_task("amk-123")
    assert "processing" in result["message"].lower()


def test_upscale_error_returns_error_dict():
    from seedance.exceptions import ValidationError
    from seedance_mcp.server import byteplus_upscale_video
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_enhance.side_effect = ValidationError("bad fps")
        result = byteplus_upscale_video("https://example.com/v.mp4", fps=999)
    assert result["status"] == "error"
    assert "bad fps" in result["error"]


def test_ping_returns_ok():
    *_, ping = _import_tools()
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.ping.return_value = {
            "status": "ok",
            "version": "2.0.0",
            "credentials": {"api_key": True, "ak": True, "sk": True},
        }
        result = ping()
    assert result["status"] == "ok"
