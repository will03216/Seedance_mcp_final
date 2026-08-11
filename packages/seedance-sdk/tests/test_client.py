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


# ---------------------------------------------------------------------------
# Seedance 2.5: prompt-inferred task type (edit / extend detection)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "prompt",
    [
        "Remove the background music from @Video1.",
        "Add small animals to @Video1.",
        "Replace the character in @Video1 with the character in @Image1.",
        "Delete the logo in the corner.",
        "Please modify the sky in @Video1.",
        "Change the jacket to red.",
        "编辑视频：删除背景音乐。",
    ],
)
def test_edit_wording_with_video_ref_is_blocked_when_params_clash(client, prompt):
    # Default duration=5 violates the edit constraint (must be -1).
    with pytest.raises(ValidationError, match="reads as a video edit task"):
        client.submit_image_to_video(prompt, video_urls=["https://e.com/v.mov"])


@pytest.mark.parametrize(
    "prompt",
    [
        "Extend @Video1 backward.",
        "Continue the story of @Video1.",
        "Please continue this shot for another 5 seconds.",
        "延长 @Video1，让镜头继续推进。",
    ],
)
def test_extend_wording_with_video_ref_is_blocked_when_ratio_clashes(client, prompt):
    with pytest.raises(ValidationError, match="reads as a video extend task"):
        client.submit_image_to_video(prompt, video_urls=["https://e.com/v.mov"], ratio="16:9")


def test_guard_names_the_dedicated_entrypoint(client):
    with pytest.raises(ValidationError) as exc:
        client.submit_image_to_video(
            "Remove the crowd from @Video1.", video_urls=["https://e.com/v.mov"], ratio="16:9",
        )
    msg = str(exc.value)
    assert "submit_video_edit()" in msg and "seedance_edit_video" in msg
    # ...and tells the caller how to proceed if it really was a plain generation.
    assert "reword the prompt" in msg


def test_guard_is_advisory_not_a_hard_block(client):
    # Edit wording, but the parameters already satisfy the edit constraints,
    # so there is nothing to fail on and the request goes through.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "Remove the crowd from @Video1.",
            video_urls=["https://e.com/v.mov"], ratio="adaptive", duration=-1,
        )
    assert _payload_of(mock)["ratio"] == "adaptive"


def test_innocent_reference_prompt_is_not_blocked(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "A woman walks through neon rain; camera rhythm follows @Video1.",
            video_urls=["https://e.com/v.mov"], ratio="16:9", duration=8,
        )
    assert _payload_of(mock)["ratio"] == "16:9"


def test_edit_wording_without_video_ref_is_not_blocked(client):
    # Editing requires a reference_* role; with no video there is nothing to
    # edit, so "add" in a text-to-video prompt must not trip the guard.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("Add a splash of colour to the scene.", duration=5)
    assert _payload_of(mock)["ratio"] == "16:9"


def test_declaring_task_type_bypasses_the_guard(client):
    # An explicit task_type means the caller already knows; the dedicated
    # methods rely on this to pass their own edit-worded prompts through.
    with _mock_http({"id": "t", "status": "queued"}):
        client.submit_image_to_video(
            "Remove the crowd from @Video1.",
            video_urls=["https://e.com/v.mov"],
            ratio="adaptive", duration=-1, task_type="edit",
        )


def test_guard_does_not_apply_to_seedance_20(client):
    # 2.0 has no task-type constraints at all.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "Remove the crowd from @Video1.",
            model="2.0", video_urls=["https://e.com/v.mov"], ratio="16:9", duration=5,
        )
    assert _payload_of(mock)["ratio"] == "16:9"


# ---------------------------------------------------------------------------
# Seedance 2.5: ratio default when the task type is not yet knowable
# ---------------------------------------------------------------------------

def test_ratio_auto_defaults_to_adaptive_when_video_refs_present(client):
    # The model may classify this as reference/edit/extend from the prompt.
    # 'adaptive' is the only value legal under all three (and the API default),
    # so defaulting to 16:9 here would manufacture an async failure.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "Camera rhythm follows @Video1.", video_urls=["https://e.com/v.mov"],
        )
    assert _payload_of(mock)["ratio"] == "adaptive"


def test_ratio_auto_still_defaults_to_16_9_without_video_refs(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video("A portrait.", image_urls=["https://e.com/a.jpg"])
    assert _payload_of(mock)["ratio"] == "16:9"


def test_ratio_auto_defaults_to_16_9_with_video_refs_on_20(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "Camera follows the clip.", model="2.0", video_urls=["https://e.com/v.mp4"],
        )
    assert _payload_of(mock)["ratio"] == "16:9"


# ---------------------------------------------------------------------------
# Seedance 2.5: missing trigger word on the dedicated methods
# ---------------------------------------------------------------------------

def test_edit_without_trigger_word_warns(client):
    with _mock_http({"id": "t", "status": "queued"}):
        result = client.submit_video_edit(
            "Make it look more cinematic.", ["https://e.com/v.mov"],
        )
    assert "no edit trigger word" in result.warning
    assert result.to_dict()["warning"]


def test_edit_with_trigger_word_does_not_warn(client):
    with _mock_http({"id": "t", "status": "queued"}):
        result = client.submit_video_edit(
            "Remove the crowd from @Video1.", ["https://e.com/v.mov"],
        )
    assert result.warning == ""


def test_extend_without_trigger_word_warns(client):
    with _mock_http({"id": "t", "status": "queued"}):
        result = client.submit_video_extend(
            "The camera drifts across the map.", ["https://e.com/v.mov"],
        )
    assert "no extend trigger word" in result.warning


def test_extend_with_trigger_word_does_not_warn(client):
    with _mock_http({"id": "t", "status": "queued"}):
        result = client.submit_video_extend(
            "Continue @Video1 for another 5 seconds.", ["https://e.com/v.mov"],
        )
    assert result.warning == ""


# ---------------------------------------------------------------------------
# Seedance 2.5: response ratio is not restricted to the request enum
# ---------------------------------------------------------------------------

def test_adaptive_output_ratio_may_be_non_standard(client):
    # Observed live: an edit of a 269x215-ish source returned ratio="269:215".
    # 'adaptive' inherits the source's exact aspect ratio, so the response value
    # is NOT one of the seven values the request accepts.
    with _mock_http({
        "status": "succeeded",
        "output": {
            "video_url": "https://cdn/v.mov", "duration": 16,
            "ratio": "269:215", "resolution": "720p", "output_format": "mov",
        },
    }):
        result = client.check_task("t")
    assert result.ratio == "269:215"
    assert result.duration == 16
    assert result.output_format == "mov"


def test_list_tasks_accepts_model_filter(client):
    with _mock_http({"total": 0, "items": []}) as mock:
        client.list_tasks(model_filter="2.5")
    url = mock.call_args.args[0] if mock.call_args.args else mock.call_args.kwargs["url"]
    assert "filter.model=dreamina-seedance-2-5-260628" in url


# ---------------------------------------------------------------------------
# API parity: terminal statuses
# ---------------------------------------------------------------------------

def test_expired_is_terminal(client):
    # A task that outlives execution_expires_after is killed and marked expired.
    # Treating it as non-terminal makes watchers poll forever.
    with _mock_http({"status": "expired", "error": {"code": "TaskExpired"}}):
        result = client.check_task("t-exp")
    assert result.terminal
    assert result.expired
    assert not result.succeeded
    assert result.error is not None, "error must surface on a terminal status"


def test_running_is_not_terminal(client):
    with _mock_http({"status": "running"}):
        assert not client.check_task("t").terminal


# ---------------------------------------------------------------------------
# API parity: camera_fixed
# ---------------------------------------------------------------------------

def test_camerafixed_rejected_on_25(client):
    # Documented for Seedance 1.5 pro / 1.0 pro only.
    with pytest.raises(ValidationError, match="1.5 pro"):
        client.submit_text_to_video("test", camerafixed=True)


def test_camerafixed_rejected_on_20(client):
    with pytest.raises(ValidationError, match="not supported"):
        client.submit_text_to_video("test", model="2.0", camerafixed=True)


def test_camerafixed_omitted_when_false(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test")
    payload = _payload_of(mock)
    assert "camera_fixed" not in payload and "camerafixed" not in payload


# ---------------------------------------------------------------------------
# API parity: omni_reference_task_type
# ---------------------------------------------------------------------------

def test_omni_task_type_sent_for_edit(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_video_edit("Remove the crowd from @Video1.", ["https://e/v.mov"])
    assert _payload_of(mock)["omni_reference_task_type"] == "edit"


def test_omni_task_type_sent_for_extend(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_video_extend("Extend @Video1.", ["https://e/v.mov"], duration=11)
    assert _payload_of(mock)["omni_reference_task_type"] == "extend"


def test_omni_task_type_sent_when_declared_reference(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "Rhythm follows @Video1.", video_urls=["https://e/v.mov"],
            task_type="reference", ratio="16:9",
        )
    assert _payload_of(mock)["omni_reference_task_type"] == "reference"


def test_omni_task_type_omitted_when_auto(client):
    # "auto" is the API default; omitting it is equivalent and keeps payloads lean.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video("A dancer.", video_urls=["https://e/v.mov"])
    assert "omni_reference_task_type" not in _payload_of(mock)


def test_omni_task_type_omitted_for_first_frame(client):
    # First-frame is a separate task family, classified by content.role.
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video("She turns.", first_frame_url="https://e/f.jpg")
    assert "omni_reference_task_type" not in _payload_of(mock)


def test_omni_task_type_omitted_for_text_to_video(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("A city at dusk.")
    assert "omni_reference_task_type" not in _payload_of(mock)


def test_omni_task_type_omitted_on_seedance_20(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_image_to_video(
            "Remove the crowd.", model="2.0", video_urls=["https://e/v.mp4"],
            task_type="edit", ratio="adaptive", duration=-1,
        )
    assert "omni_reference_task_type" not in _payload_of(mock)


# ---------------------------------------------------------------------------
# API parity: newly supported request parameters
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [0, 5, 9])
def test_priority_accepted_in_range(client, value):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", priority=value)
    assert _payload_of(mock)["priority"] == value


@pytest.mark.parametrize("value", [-1, 10, 99])
def test_priority_rejected_out_of_range(client, value):
    with pytest.raises(ValidationError, match="Invalid priority"):
        client.submit_text_to_video("test", priority=value)


def test_callback_url_sent(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", callback_url="https://cb.example.com/hook")
    assert _payload_of(mock)["callback_url"] == "https://cb.example.com/hook"


def test_non_http_callback_url_rejected(client):
    with pytest.raises(ValidationError, match="http\\(s\\) URL"):
        client.submit_text_to_video("test", callback_url="ftp://example.com")


def test_return_last_frame_sent(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", return_last_frame=True)
    assert _payload_of(mock)["return_last_frame"] is True


@pytest.mark.parametrize("value", [3600, 172800, 259200])
def test_execution_expires_after_accepted(client, value):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", execution_expires_after=value)
    assert _payload_of(mock)["execution_expires_after"] == value


@pytest.mark.parametrize("value", [3599, 259201])
def test_execution_expires_after_rejected(client, value):
    with pytest.raises(ValidationError, match="execution_expires_after"):
        client.submit_text_to_video("test", execution_expires_after=value)


def test_safety_identifier_sent(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", safety_identifier="u_abc123")
    assert _payload_of(mock)["safety_identifier"] == "u_abc123"


def test_over_long_safety_identifier_rejected(client):
    with pytest.raises(ValidationError, match="maximum is 64"):
        client.submit_text_to_video("test", safety_identifier="x" * 65)


def test_frames_rejected_on_25(client):
    # frames is documented as unsupported on the 2.5 and 2.0 series.
    with pytest.raises(ValidationError, match="frames is not supported"):
        client.submit_text_to_video("test", frames=33)


def test_service_tier_default_accepted(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test", service_tier="default")
    assert _payload_of(mock)["service_tier"] == "default"


def test_service_tier_flex_rejected_on_25(client):
    with pytest.raises(ValidationError, match="flex"):
        client.submit_text_to_video("test", service_tier="flex")


def test_invalid_service_tier_rejected(client):
    with pytest.raises(ValidationError, match="Invalid service_tier"):
        client.submit_text_to_video("test", service_tier="turbo")


def test_optional_params_omitted_by_default(client):
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_text_to_video("test")
    payload = _payload_of(mock)
    for key in ("priority", "callback_url", "return_last_frame",
                "execution_expires_after", "safety_identifier", "frames",
                "service_tier", "omni_reference_task_type"):
        assert key not in payload, f"{key} should be omitted so the API default applies"


# ---------------------------------------------------------------------------
# API parity: newly parsed response fields
# ---------------------------------------------------------------------------

def test_check_task_parses_full_response(client):
    with _mock_http({
        "status": "succeeded",
        "model": "dreamina-seedance-2-5-260628",
        "created_at": 1700000000,
        "updated_at": 1700000123,
        "priority": 5,
        "service_tier": "default",
        "seed": 42,
        "usage": {"completion_tokens": 12345, "total_tokens": 12400},
        "content": {
            "video_url": "https://cdn/v.mov",
            "last_frame_url": "https://cdn/last.png",
            "duration": 5,
            "frames": 133,
            "framespersecond": 24,
            "ratio": "269:215",
            "resolution": "720p",
            "output_format": "mov",
        },
    }):
        r = client.check_task("t")
    assert r.last_frame_url == "https://cdn/last.png"
    assert r.frames == 133
    assert r.fps == 24
    assert r.seed == 42
    assert r.priority == 5
    assert r.service_tier == "default"
    assert r.created_at == 1700000000 and r.updated_at == 1700000123
    assert r.completion_tokens == 12345 and r.total_tokens == 12400
    d = r.to_dict()
    assert d["last_frame_url"] == "https://cdn/last.png" and d["frames"] == 133


def test_missing_optional_response_fields_stay_none(client):
    with _mock_http({"status": "running"}):
        r = client.check_task("t")
    assert r.last_frame_url is None and r.frames is None and r.total_tokens is None
    assert "frames" not in r.to_dict()


def test_video_edit_requires_exactly_one_reference_video(client):
    # Verified live: the API returns "must include exactly one reference video
    # to be edited", which is stricter than the prose docs' "at least one".
    with pytest.raises(ValidationError, match="exactly one reference video"):
        client.submit_video_edit(
            "Video edit: remove the crowd.",
            ["https://e/a.mov", "https://e/b.mov"],
        )


def test_video_extend_still_accepts_multiple_reference_videos(client):
    # Extension genuinely does take several sources (the docs' own sample uses 3).
    with _mock_http({"id": "t", "status": "queued"}) as mock:
        client.submit_video_extend(
            "Extend @Video1 into @Video2, then @Video3.",
            ["https://e/1.mov", "https://e/2.mp4", "https://e/3.mp4"],
            duration=11,
        )
    vids = [c for c in _payload_of(mock)["content"] if c["type"] == "video_url"]
    assert len(vids) == 3
