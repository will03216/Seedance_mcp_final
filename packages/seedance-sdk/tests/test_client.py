"""Tests for SeedanceClient — HTTP calls mocked at the urllib boundary."""
from __future__ import annotations

from unittest.mock import patch

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
# Multi-reference (image / video / audio) content shape
# ---------------------------------------------------------------------------

def _payload_of(mock):
    call = mock.call_args
    return call.kwargs.get("payload") or call[1].get("payload")


def test_video_ref_builds_video_url_content(client):
    with _mock_http({"id": "t-vid", "status": "queued"}) as mock:
        result = client.submit_image_to_video(
            "Extend [video1] backward by 5 seconds.",
            video_urls=["https://example.com/clip.mp4"],
        )
    assert result.mode.startswith("R2V")
    content = _payload_of(mock)["content"]
    vid = [c for c in content if c["type"] == "video_url"]
    assert vid == [{"type": "video_url", "video_url": {"url": "https://example.com/clip.mp4"}, "role": "reference_video"}]


def test_audio_ref_builds_audio_url_content(client):
    with _mock_http({"id": "t-aud", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "She [image1] lip-syncs to [audio1].",
            image_urls=["https://example.com/face.jpg"],
            audio_urls=["https://example.com/voice.mp3"],
        )
    content = _payload_of(mock)["content"]
    aud = [c for c in content if c["type"] == "audio_url"]
    assert aud == [{"type": "audio_url", "audio_url": {"url": "https://example.com/voice.mp3"}, "role": "reference_audio"}]


def test_video_only_reference_is_valid(client):
    # A video reference alone satisfies the "at least one reference" rule.
    with _mock_http({"id": "t-vonly", "status": "queued"}):
        result = client.submit_image_to_video("test", video_urls=["https://example.com/v.mp4"])
    assert result.task_id == "t-vonly"


def test_too_many_video_refs_raises(client):
    with pytest.raises(ValidationError, match="Too many video_urls"):
        client.submit_image_to_video(
            "test",
            video_urls=[f"https://example.com/{i}.mp4" for i in range(11)],
        )


def test_too_many_audio_refs_raises(client):
    with pytest.raises(ValidationError, match="Too many audio_urls"):
        client.submit_image_to_video(
            "test",
            image_urls=["https://example.com/face.jpg"],
            audio_urls=[f"https://example.com/{i}.mp3" for i in range(11)],
        )


def test_seedance_20_keeps_its_tighter_ref_limits(client):
    with pytest.raises(ValidationError, match="max 3 for Seedance 2.0"):
        client.submit_image_to_video(
            "test",
            model="2.0",
            video_urls=[f"https://example.com/{i}.mp4" for i in range(4)],
        )


def test_empty_video_ref_entry_raises(client):
    with pytest.raises(ValidationError, match="video_urls contains an empty entry"):
        client.submit_image_to_video("test", video_urls=[""])


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
    assert "dreamina-seedance-2-5-260628" in model_ids
    assert "dreamina-seedance-2-0-260128" in model_ids
    assert "dreamina-seedance-2-0-fast-260128" in model_ids


def test_list_models_reports_25_capabilities(client):
    data = client.list_models()
    m25 = next(m for m in data["models"] if m["model_id"] == "dreamina-seedance-2-5-260628")
    assert m25["duration_range"] == [4, 30]
    assert m25["resolutions"] == ["480p", "720p"]
    assert m25["reference_limits"]["images"] == 30
    assert m25["output_formats"] == ["mov", "mp4"]
    assert m25["features"]["audio_only_input"] is True


# ---------------------------------------------------------------------------
# Seedance 2.5: model selection
# ---------------------------------------------------------------------------

def test_default_model_is_seedance_25(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        result = client.submit_text_to_video("test")
    assert _payload_of(mock)["model"] == "dreamina-seedance-2-5-260628"
    assert result.model == "dreamina-seedance-2-5-260628"


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("2.5", "dreamina-seedance-2-5-260628"),
        ("2.0", "dreamina-seedance-2-0-260128"),
        ("2.0-fast", "dreamina-seedance-2-0-fast-260128"),
        ("dreamina-seedance-2-0-260128", "dreamina-seedance-2-0-260128"),
    ],
)
def test_model_aliases_resolve(client, alias, expected):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", model=alias, resolution="480p")
    assert _payload_of(mock)["model"] == expected


def test_fast_mode_overrides_explicit_25_model(client):
    # There is no Seedance 2.5 fast variant, so fast_mode falls back to 2.0 fast.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", model="2.5", fast_mode=True)
    assert _payload_of(mock)["model"] == "dreamina-seedance-2-0-fast-260128"


# ---------------------------------------------------------------------------
# Seedance 2.5: duration and resolution envelope
# ---------------------------------------------------------------------------

def test_duration_up_to_30_allowed_on_25(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", duration=30)
    assert _payload_of(mock)["duration"] == 30


def test_duration_31_rejected_on_25(client):
    with pytest.raises(ValidationError, match="4–30s"):
        client.submit_text_to_video("test", duration=31)


def test_duration_20_rejected_on_20(client):
    with pytest.raises(ValidationError, match="4–15s"):
        client.submit_text_to_video("test", model="2.0", duration=20)


def test_duration_auto_sentinel_allowed(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", duration=-1)
    assert _payload_of(mock)["duration"] == -1


def test_1080p_rejected_on_25(client):
    with pytest.raises(ValidationError, match="Invalid resolution"):
        client.submit_text_to_video("test", resolution="1080p")


def test_1080p_still_allowed_on_20(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", model="2.0", resolution="1080p")
    assert _payload_of(mock)["resolution"] == "1080p"


# ---------------------------------------------------------------------------
# Seedance 2.5: ratio resolution and task-type constraints
# ---------------------------------------------------------------------------

def test_ratio_auto_defaults_to_16_9_for_plain_generation(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test")
    assert _payload_of(mock)["ratio"] == "16:9"


def test_ratio_auto_resolves_to_adaptive_for_first_frame(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video("test", first_frame_url="https://example.com/f.jpg")
    assert _payload_of(mock)["ratio"] == "adaptive"


def test_explicit_ratio_rejected_for_first_frame_on_25(client):
    with pytest.raises(ValidationError, match="must be 'adaptive' for first_frame"):
        client.submit_image_to_video(
            "test", first_frame_url="https://example.com/f.jpg", ratio="16:9",
        )


def test_explicit_ratio_still_allowed_for_first_frame_on_20(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "test", model="2.0", first_frame_url="https://example.com/f.jpg", ratio="16:9",
        )
    assert _payload_of(mock)["ratio"] == "16:9"


def test_explicit_ratio_rejected_for_edit_task(client):
    with pytest.raises(ValidationError, match="must be 'adaptive' for edit"):
        client.submit_image_to_video(
            "Video edit: remove the crowd from @Video1.",
            video_urls=["https://example.com/v.mov"],
            task_type="edit",
            ratio="16:9",
        )


def test_explicit_duration_rejected_for_edit_task(client):
    with pytest.raises(ValidationError, match="duration must be -1 for edit"):
        client.submit_image_to_video(
            "Video edit: remove the crowd from @Video1.",
            video_urls=["https://example.com/v.mov"],
            task_type="edit",
            duration=10,
        )


def test_invalid_task_type_raises(client):
    with pytest.raises(ValidationError, match="Invalid task_type"):
        client.submit_image_to_video(
            "test", video_urls=["https://example.com/v.mp4"], task_type="remix",
        )


# ---------------------------------------------------------------------------
# Seedance 2.5: audio-only input
# ---------------------------------------------------------------------------

def test_audio_only_input_allowed_on_25(client):
    with _mock_http({"id": "t-aud", "status": "queued"}) as mock:
        result = client.submit_image_to_video(
            "Generate a video driven by @Audio1.",
            audio_urls=["https://example.com/track.mp3"],
        )
    assert result.task_id == "t-aud"
    content = _payload_of(mock)["content"]
    assert [c["type"] for c in content] == ["text", "audio_url"]


def test_audio_only_input_rejected_on_20(client):
    with pytest.raises(ValidationError, match="does not support audio-only"):
        client.submit_image_to_video(
            "test", model="2.0", audio_urls=["https://example.com/track.mp3"],
        )


def test_no_references_at_all_still_raises(client):
    with pytest.raises(ValidationError, match="at least one"):
        client.submit_image_to_video("test")


# ---------------------------------------------------------------------------
# Seedance 2.5: output_format
# ---------------------------------------------------------------------------

def test_output_format_omitted_when_unset(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test")
    assert "output_format" not in _payload_of(mock)


def test_output_format_mov_sent_on_25(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", output_format="mov")
    assert _payload_of(mock)["output_format"] == "mov"


def test_invalid_output_format_raises(client):
    with pytest.raises(ValidationError, match="Invalid output_format"):
        client.submit_text_to_video("test", output_format="webm")


def test_output_format_rejected_on_20(client):
    with pytest.raises(ValidationError, match="not supported by"):
        client.submit_text_to_video("test", model="2.0", output_format="mov")


# ---------------------------------------------------------------------------
# Seedance 2.5: video edit and extend
# ---------------------------------------------------------------------------

def test_video_edit_locks_ratio_and_duration(client):
    with _mock_http({"id": "t-edit", "status": "queued"}) as mock:
        result = client.submit_video_edit(
            "Video edit: remove everyone in @Video1 except the protagonist.",
            ["https://example.com/scene.mov"],
        )
    payload = _payload_of(mock)
    assert payload["ratio"] == "adaptive"
    assert payload["duration"] == -1
    assert payload["output_format"] == "mov"
    assert result.mode == "V2V-Edit(vid=1)"


def test_video_edit_requires_video_urls(client):
    with pytest.raises(ValidationError, match="video_urls is required"):
        client.submit_video_edit("Video edit: drop the crowd.", [])


def test_video_edit_rejected_on_20(client):
    with pytest.raises(ValidationError, match="requires Seedance 2.5"):
        client.submit_video_edit(
            "Video edit: drop the crowd.",
            ["https://example.com/scene.mov"],
            model="2.0",
        )


def test_video_extend_locks_ratio_but_allows_duration(client):
    with _mock_http({"id": "t-ext", "status": "queued"}) as mock:
        result = client.submit_video_extend(
            "Extend @Video1 down the corridor.",
            ["https://example.com/corridor.mov"],
            duration=11,
        )
    payload = _payload_of(mock)
    assert payload["ratio"] == "adaptive"
    assert payload["duration"] == 11
    assert result.mode == "V2V-Extend(vid=1)"


def test_video_extend_defaults_to_auto_duration(client):
    with _mock_http({"id": "t-ext", "status": "queued"}) as mock:
        client.submit_video_extend("Extend @Video1.", ["https://example.com/v.mov"])
    assert _payload_of(mock)["duration"] == -1


def test_video_extend_rejects_out_of_range_duration(client):
    with pytest.raises(ValidationError, match="4–30s"):
        client.submit_video_extend(
            "Extend @Video1.", ["https://example.com/v.mov"], duration=45,
        )


# ---------------------------------------------------------------------------
# Seedance 2.5: response fields
# ---------------------------------------------------------------------------

def test_check_task_parses_output_metadata(client):
    with _mock_http({
        "status": "succeeded",
        "model": "dreamina-seedance-2-5-260628",
        "output": {
            "video_url": "https://cdn.example.com/v.mov",
            "duration": 5,
            "ratio": "16:9",
            "resolution": "720p",
            "output_format": "mov",
        },
    }):
        result = client.check_task("task-1")
    assert result.output_format == "mov"
    assert result.duration == 5
    assert result.ratio == "16:9"
    assert result.resolution == "720p"
    assert result.model == "dreamina-seedance-2-5-260628"
    assert result.to_dict()["output_format"] == "mov"


def test_check_task_flags_task_type_constraint_failure(client):
    with _mock_http({
        "status": "failed",
        "error": {
            "code": "InvalidParameter.TaskTypeConstraint",
            "message": "ratio must be adaptive. Issues: [0] ratio is not adaptive.",
        },
    }):
        result = client.check_task("task-bad")
    assert result.task_type_constraint_error


def test_check_task_without_output_metadata_is_none(client):
    with _mock_http({"status": "running"}):
        result = client.check_task("task-2")
    assert result.output_format is None
    assert result.duration is None


def test_list_tasks_accepts_model_filter(client):
    with _mock_http({"total": 0, "items": []}) as mock:
        client.list_tasks(model_filter="2.5")
    url = mock.call_args.args[0] if mock.call_args.args else mock.call_args.kwargs["url"]
    assert "filter.model=dreamina-seedance-2-5-260628" in url
