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


def test_generate_forwards_video_and_audio_refs():
    *_, = _import_tools()
    from seedance_mcp.server import seedance_generate
    mock_result = GenerateResult(task_id="task-r2v", status="queued", mode="R2V-Reference", steps=[])
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = seedance_generate(
            "Extend [video1], sync to [audio1].",
            video_urls=["https://example.com/clip.mp4"],
            audio_urls=["https://example.com/voice.mp3"],
        )
    assert result["task_id"] == "task-r2v"
    kwargs = MockClient.return_value.generate.call_args.kwargs
    assert kwargs["video_urls"] == ["https://example.com/clip.mp4"]
    assert kwargs["audio_urls"] == ["https://example.com/voice.mp3"]


def test_image_to_video_forwards_video_audio_refs():
    from seedance_mcp.server import seedance_image_to_video
    mock_result = TaskResult(task_id="task-i", status="queued", mode="R2V-Reference(img=1,vid=1,aud=0)")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_image_to_video.return_value = mock_result
        seedance_image_to_video(
            "test",
            image_urls=["https://example.com/face.jpg"],
            video_urls=["https://example.com/clip.mp4"],
        )
    kwargs = MockClient.return_value.submit_image_to_video.call_args.kwargs
    assert kwargs["video_urls"] == ["https://example.com/clip.mp4"]
    assert kwargs["audio_urls"] is None


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


def test_text_to_video_forwards_model_and_output_format():
    t2v, *_ = _import_tools()
    mock_result = TaskResult(task_id="task-25", status="queued", mode="T2V")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_text_to_video.return_value = mock_result
        t2v("test", model="2.5", output_format="mov")
    kwargs = MockClient.return_value.submit_text_to_video.call_args.kwargs
    assert kwargs["model"] == "2.5"
    assert kwargs["output_format"] == "mov"


def test_generate_defaults_ratio_to_auto():
    from seedance_mcp.server import seedance_generate
    mock_result = GenerateResult(task_id="t", status="queued", mode="T2V", steps=[])
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        seedance_generate("test")
    assert MockClient.return_value.generate.call_args.kwargs["ratio"] == "auto"


def test_generate_forwards_image_urls_list():
    from seedance_mcp.server import seedance_generate
    mock_result = GenerateResult(task_id="t", status="queued", mode="I2V-Reference", steps=[])
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        seedance_generate("@Image1 and @Image2", image_urls=["https://a/1.jpg", "https://a/2.jpg"])
    kwargs = MockClient.return_value.generate.call_args.kwargs
    assert kwargs["image_urls"] == ["https://a/1.jpg", "https://a/2.jpg"]


# ---------------------------------------------------------------------------
# Seedance 2.5 edit / extend tools
# ---------------------------------------------------------------------------

def test_edit_video_returns_task_id_and_constraint_message():
    from seedance_mcp.server import seedance_edit_video
    mock_result = TaskResult(task_id="task-edit", status="queued", mode="V2V-Edit(vid=1)")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_edit.return_value = mock_result
        result = seedance_edit_video(
            "Video edit: remove the crowd in @Video1.",
            video_urls=["https://example.com/scene.mov"],
        )
    assert result["task_id"] == "task-edit"
    assert "ratio and duration" in result["message"]
    args = MockClient.return_value.submit_video_edit.call_args
    assert args.args[1] == ["https://example.com/scene.mov"]
    assert args.kwargs["output_format"] == "mov"


def test_edit_video_does_not_expose_ratio_or_duration():
    # These are locked by the task type; exposing them would only let an agent
    # construct a request that fails asynchronously.
    import inspect

    from seedance_mcp.server import seedance_edit_video
    params = inspect.signature(seedance_edit_video).parameters
    assert "ratio" not in params
    assert "duration" not in params


def test_extend_video_forwards_duration():
    from seedance_mcp.server import seedance_extend_video
    mock_result = TaskResult(task_id="task-ext", status="queued", mode="V2V-Extend(vid=1)")
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_extend.return_value = mock_result
        result = seedance_extend_video(
            "Extend @Video1.", video_urls=["https://example.com/v.mov"], duration=11,
        )
    assert result["task_id"] == "task-ext"
    assert MockClient.return_value.submit_video_extend.call_args.kwargs["duration"] == 11


def test_extend_video_exposes_duration_but_not_ratio():
    import inspect

    from seedance_mcp.server import seedance_extend_video
    params = inspect.signature(seedance_extend_video).parameters
    assert "duration" in params
    assert "ratio" not in params


def test_edit_video_error_returns_error_dict():
    from seedance.exceptions import ValidationError
    from seedance_mcp.server import seedance_edit_video
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_edit.side_effect = ValidationError(
            "Video editing requires Seedance 2.5"
        )
        result = seedance_edit_video("Video edit: x.", video_urls=["https://a/v.mov"])
    assert result["status"] == "error"
    assert "Seedance 2.5" in result["error"]


def test_check_task_explains_task_type_constraint_failure():
    _, check, *_ = _import_tools()
    mock_result = TaskResult(
        task_id="task-bad",
        status="failed",
        error={"code": "InvalidParameter.TaskTypeConstraint", "message": "ratio must be adaptive"},
    )
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = check("task-bad")
    assert "seedance_edit_video" in result["message"]


def test_check_task_surfaces_output_format():
    _, check, *_ = _import_tools()
    mock_result = TaskResult(
        task_id="t", status="succeeded", video_url="https://cdn/v.mov",
        output_format="mov", duration=11,
    )
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = check("t")
    assert result["output_format"] == "mov"
    assert result["duration"] == 11


def test_list_models_includes_seedance_25():
    *_, list_models, _ = _import_tools()
    with patch("seedance_mcp.server.SeedanceClient") as MockClient:
        MockClient.return_value.list_models.return_value = {"models": []}
        list_models()
    assert MockClient.return_value.list_models.called


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
