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
