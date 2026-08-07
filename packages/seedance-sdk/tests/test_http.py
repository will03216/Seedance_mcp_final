"""Tests for HTTP error mapping and response-field extraction."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from seedance.exceptions import APIError, TaskTypeConstraintError
from seedance.http import (
    _do_request,
    error_for_body,
    extract_output_field,
    extract_video_url,
    parse_issues,
)

CONSTRAINT_BODY = (
    '{"error": {"type": "BadRequest", '
    '"code": "InvalidParameter.TaskTypeConstraint", '
    '"message": "The parameter(s) ratio and duration specified in the request are not '
    'valid. This is a video edit task. Issues: [0] ratio must be adaptive. '
    '[1] duration must be -1. Request id: 021786"}}'
)


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

def test_task_type_constraint_body_maps_to_specific_error():
    exc = error_for_body(CONSTRAINT_BODY, 400)
    assert isinstance(exc, TaskTypeConstraintError)
    assert exc.status_code == 400
    assert exc.issues == ["ratio must be adaptive.", "duration must be -1."]


def test_task_type_constraint_error_is_an_api_error():
    # Callers catching APIError (or SeedanceError) must keep working.
    assert isinstance(error_for_body(CONSTRAINT_BODY, 400), APIError)


def test_other_error_codes_map_to_plain_api_error():
    body = '{"error": {"code": "AuthenticationError", "message": "bad key"}}'
    exc = error_for_body(body, 401)
    assert type(exc) is APIError
    assert exc.status_code == 401


def test_non_json_error_body_still_raises_api_error():
    exc = error_for_body("<html>502 Bad Gateway</html>", 502)
    assert type(exc) is APIError
    assert "502" in str(exc)


def test_parse_issues_returns_empty_without_issues_section():
    assert parse_issues("Something went wrong. Request id: 1") == []


# ---------------------------------------------------------------------------
# Response body validation
# ---------------------------------------------------------------------------

def _urlopen_returning(body: str):
    """Patch urlopen so the request layer sees `body` as the response."""
    resp = MagicMock()
    resp.read.return_value = body.encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    return patch("seedance.http.request.urlopen", return_value=resp)


def test_non_object_json_response_raises_api_error():
    # A proxy or error page can return valid JSON that is not an object.
    with _urlopen_returning('["not", "an", "object"]'), pytest.raises(APIError, match="got list"):
        _do_request("https://example.com/x", method="GET", headers={})


def test_malformed_json_response_raises_api_error():
    with _urlopen_returning("<html>oops</html>"), pytest.raises(APIError, match="Malformed JSON"):
        _do_request("https://example.com/x", method="GET", headers={})


def test_object_json_response_passes_through():
    with _urlopen_returning('{"id": "t-1", "status": "queued"}'):
        assert _do_request("https://example.com/x", method="GET", headers={}) == {
            "id": "t-1", "status": "queued",
        }


# ---------------------------------------------------------------------------
# Output field extraction
# ---------------------------------------------------------------------------

def test_extract_reads_from_output_container():
    task = {"output": {"video_url": "https://cdn/v.mov", "output_format": "mov"}}
    assert extract_video_url(task) == "https://cdn/v.mov"
    assert extract_output_field(task, "output_format") == "mov"


def test_extract_reads_from_legacy_content_container():
    assert extract_video_url({"content": {"video_url": "https://cdn/v.mp4"}}) == "https://cdn/v.mp4"


def test_extract_falls_back_to_top_level():
    assert extract_output_field({"ratio": "9:16"}, "ratio") == "9:16"


def test_extract_missing_field_is_none():
    assert extract_output_field({"output": {}}, "output_format") is None
    assert extract_video_url({"status": "running"}) is None


def test_extract_skips_empty_container_value():
    task = {"output": {"video_url": ""}, "result": {"video_url": "https://cdn/v.mp4"}}
    assert extract_video_url(task) == "https://cdn/v.mp4"
