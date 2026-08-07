"""CLI command tests using Typer's test runner."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from seedance.types import GenerateResult, TaskResult, UpscaleResult
from seedance_cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test-key")
    monkeypatch.setenv("ARK_AK", "test-ak")
    monkeypatch.setenv("ARK_SK", "test-sk")
    monkeypatch.setenv("MEDIAKIT_API_KEY", "test-mediakit-key")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def test_generate_t2v_prints_task_id():
    mock_result = GenerateResult(
        task_id="task-abc",
        status="queued",
        mode="T2V",
        steps=[{"step": "submit_job", "task_id": "task-abc", "outcome": "queued"}],
    )
    with patch("seedance_cli.commands.generate.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = runner.invoke(app, ["generate", "--prompt", "A sunset"])
    assert result.exit_code == 0
    assert "task-abc" in result.output


def test_generate_missing_prompt_fails():
    result = runner.invoke(app, ["generate"])
    assert result.exit_code != 0


def test_generate_forwards_video_and_audio_refs():
    mock_result = GenerateResult(
        task_id="task-r2v",
        status="queued",
        mode="R2V-Reference",
        steps=[{"step": "submit_job", "task_id": "task-r2v", "outcome": "queued"}],
    )
    with patch("seedance_cli.commands.generate.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = runner.invoke(app, [
            "generate", "--prompt", "Extend [video1], sync [audio1]",
            "--video", "https://example.com/clip.mp4",
            "--audio-ref", "https://example.com/voice.mp3",
        ])
    assert result.exit_code == 0
    kwargs = MockClient.return_value.generate.call_args.kwargs
    assert kwargs["video_urls"] == ["https://example.com/clip.mp4"]
    assert kwargs["audio_urls"] == ["https://example.com/voice.mp3"]


def test_generate_forwards_model_and_output_format():
    mock_result = GenerateResult(task_id="task-25", status="queued", mode="T2V", steps=[])
    with patch("seedance_cli.commands.generate.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = runner.invoke(app, [
            "generate", "--prompt", "A sunset",
            "--model", "2.5", "--output-format", "mov",
        ])
    assert result.exit_code == 0
    kwargs = MockClient.return_value.generate.call_args.kwargs
    assert kwargs["model"] == "2.5"
    assert kwargs["output_format"] == "mov"


def test_generate_accepts_repeated_image_flags():
    mock_result = GenerateResult(task_id="task-multi", status="queued", mode="I2V-Reference", steps=[])
    with patch("seedance_cli.commands.generate.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = runner.invoke(app, [
            "generate", "--prompt", "@Image1 meets @Image2",
            "-i", "https://example.com/a.jpg",
            "-i", "https://example.com/b.jpg",
        ])
    assert result.exit_code == 0
    kwargs = MockClient.return_value.generate.call_args.kwargs
    assert kwargs["image_urls"] == ["https://example.com/a.jpg", "https://example.com/b.jpg"]


def test_generate_accepts_auto_duration():
    mock_result = GenerateResult(task_id="task-auto", status="queued", mode="T2V", steps=[])
    with patch("seedance_cli.commands.generate.SeedanceClient") as MockClient:
        MockClient.return_value.generate.return_value = mock_result
        result = runner.invoke(app, ["generate", "--prompt", "A sunset", "--duration=-1"])
    assert result.exit_code == 0
    assert MockClient.return_value.generate.call_args.kwargs["duration"] == -1


# ---------------------------------------------------------------------------
# edit / extend
# ---------------------------------------------------------------------------

def test_edit_submits_and_prints_task_id():
    mock_result = TaskResult(task_id="task-edit", status="queued", mode="V2V-Edit(vid=1)")
    with patch("seedance_cli.commands.edit.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_edit.return_value = mock_result
        result = runner.invoke(app, [
            "edit", "--prompt", "Video edit: remove the crowd in @Video1.",
            "--video", "https://example.com/scene.mov",
        ])
    assert result.exit_code == 0
    assert "task-edit" in result.output
    kwargs = MockClient.return_value.submit_video_edit.call_args.kwargs
    assert kwargs["output_format"] == "mov"


def test_edit_requires_video():
    result = runner.invoke(app, ["edit", "--prompt", "Video edit: drop the crowd."])
    assert result.exit_code != 0


def test_extend_forwards_duration():
    mock_result = TaskResult(task_id="task-ext", status="queued", mode="V2V-Extend(vid=1)")
    with patch("seedance_cli.commands.edit.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_extend.return_value = mock_result
        result = runner.invoke(app, [
            "extend", "--prompt", "Extend @Video1.",
            "--video", "https://example.com/v.mov", "--duration", "11",
        ])
    assert result.exit_code == 0
    assert MockClient.return_value.submit_video_extend.call_args.kwargs["duration"] == 11


def test_extend_defaults_to_auto_duration():
    mock_result = TaskResult(task_id="task-ext", status="queued", mode="V2V-Extend(vid=1)")
    with patch("seedance_cli.commands.edit.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_extend.return_value = mock_result
        result = runner.invoke(app, [
            "extend", "--prompt", "Extend @Video1.", "--video", "https://example.com/v.mov",
        ])
    assert result.exit_code == 0
    assert MockClient.return_value.submit_video_extend.call_args.kwargs["duration"] == -1


def test_edit_surfaces_sdk_validation_error():
    from seedance.exceptions import ValidationError
    with patch("seedance_cli.commands.edit.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_edit.side_effect = ValidationError(
            "Video editing requires Seedance 2.5"
        )
        result = runner.invoke(app, [
            "edit", "--prompt", "Video edit: drop the crowd.",
            "--video", "https://example.com/v.mov",
        ])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# upscale
# ---------------------------------------------------------------------------

def test_upscale_prints_task_id():
    mock_result = UpscaleResult(task_id="amk-abc", status="submitted")
    with patch("seedance_cli.commands.upscale.SeedanceClient") as MockClient:
        MockClient.return_value.submit_video_enhance.return_value = mock_result
        result = runner.invoke(app, ["upscale", "https://example.com/v.mp4", "--resolution", "1080p"])
    assert result.exit_code == 0
    assert "amk-abc" in result.output


def test_upscale_missing_url_fails():
    result = runner.invoke(app, ["upscale"])
    assert result.exit_code != 0


def test_upscale_status_completed_shows_url():
    mock_result = UpscaleResult(
        task_id="amk-abc", status="completed", video_url="https://cdn.example.com/out.mp4",
    )
    with patch("seedance_cli.commands.upscale.SeedanceClient") as MockClient:
        MockClient.return_value.check_enhance_task.return_value = mock_result
        result = runner.invoke(app, ["upscale-status", "amk-abc"])
    assert result.exit_code == 0
    assert "https://cdn.example.com/out.mp4" in result.output


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_succeeded_shows_url():
    mock_result = TaskResult(
        task_id="task-123",
        status="succeeded",
        video_url="https://cdn.example.com/video.mp4",
    )
    with patch("seedance_cli.commands.tasks.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = runner.invoke(app, ["status", "task-123"])
    assert result.exit_code == 0
    assert "succeeded" in result.output
    assert "https://cdn.example.com/video.mp4" in result.output


def test_status_failed_exits_nonzero():
    mock_result = TaskResult(task_id="task-bad", status="failed", error={"msg": "out of memory"})
    with patch("seedance_cli.commands.tasks.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = runner.invoke(app, ["status", "task-bad"])
    assert result.exit_code != 0


def test_status_succeeded_shows_output_metadata():
    mock_result = TaskResult(
        task_id="task-123",
        status="succeeded",
        video_url="https://cdn.example.com/video.mov",
        duration=11,
        ratio="9:16",
        resolution="720p",
        output_format="mov",
    )
    with patch("seedance_cli.commands.tasks.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = runner.invoke(app, ["status", "task-123"])
    assert result.exit_code == 0
    assert "mov" in result.output
    assert "9:16" in result.output


def test_status_explains_task_type_constraint_failure():
    mock_result = TaskResult(
        task_id="task-bad",
        status="failed",
        error={"code": "InvalidParameter.TaskTypeConstraint", "message": "ratio must be adaptive"},
    )
    with patch("seedance_cli.commands.tasks.SeedanceClient") as MockClient:
        MockClient.return_value.check_task.return_value = mock_result
        result = runner.invoke(app, ["status", "task-bad"])
    assert result.exit_code != 0
    assert "seedance edit" in result.output


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def test_list_prints_table():
    mock_tasks = [
        TaskResult(task_id="t1", status="succeeded", video_url="https://example.com/1.mp4"),
        TaskResult(task_id="t2", status="running"),
    ]
    with patch("seedance_cli.commands.tasks.SeedanceClient") as MockClient:
        MockClient.return_value.list_tasks.return_value = {
            "total": 2, "page_num": 1, "page_size": 10, "tasks": mock_tasks,
        }
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "t1" in result.output
    assert "t2" in result.output


def test_list_forwards_model_filter():
    with patch("seedance_cli.commands.tasks.SeedanceClient") as MockClient:
        MockClient.return_value.list_tasks.return_value = {
            "total": 0, "page_num": 1, "page_size": 10, "tasks": [],
        }
        result = runner.invoke(app, ["list", "--model", "2.5"])
    assert result.exit_code == 0
    assert MockClient.return_value.list_tasks.call_args.args[3] == "2.5"


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

def test_models_table_lists_seedance_25():
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "2-5-260628" in result.output.replace("\n", "")


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

def test_ping_ok(tmp_path, monkeypatch):
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", tmp_path / "credentials")
    # ping() imports SeedanceClient inline; patch at the definition site
    with patch("seedance.client.SeedanceClient") as MockClient:
        MockClient.return_value.ping.return_value = {
            "status": "ok",
            "version": "2.0.0",
            "credentials": {"api_key": True, "ak": True, "sk": True},
        }
        result = runner.invoke(app, ["ping"])
    assert result.exit_code == 0
    assert "Connected" in result.output


# ---------------------------------------------------------------------------
# auth check
# ---------------------------------------------------------------------------

def test_auth_check_all_configured(tmp_path, monkeypatch):
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", tmp_path / "credentials")
    # Credentials come from env vars (set by autouse fixture)
    result = runner.invoke(app, ["auth", "check"])
    assert result.exit_code == 0
    assert "configured" in result.output


def test_auth_check_missing_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_AK", raising=False)
    monkeypatch.delenv("ARK_SK", raising=False)
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", tmp_path / "credentials")
    result = runner.invoke(app, ["auth", "check"])
    assert result.exit_code != 0
