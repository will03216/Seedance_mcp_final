"""Tests for the TOS client — signing and URL construction, no network."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from seedance import SeedanceClient
from seedance.exceptions import ValidationError
from seedance.tos import TOSClient, _sign

_LIST_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ListAllMyBucketsResult xmlns="http://tos.bytepluses.com/doc/2020-04-01/">
  <Owner><ID>123</ID></Owner>
  <Buckets>
    <Bucket><Name>my-images</Name><Location>ap-southeast-1</Location>
      <CreationDate>2024-01-01T00:00:00Z</CreationDate></Bucket>
    <Bucket><Name>my-videos</Name><Location>ap-southeast-1</Location>
      <CreationDate>2024-02-01T00:00:00Z</CreationDate></Bucket>
  </Buckets>
</ListAllMyBucketsResult>"""


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ARK_AK", "test-ak")
    monkeypatch.setenv("ARK_SK", "test-sk")
    return SeedanceClient()


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------

def test_sign_produces_tos4_authorization():
    headers = _sign(
        "AKxxx", "SKxxx",
        method="PUT",
        host="bucket.tos-ap-southeast-1.bytepluses.com",
        path="/photo.png",
        payload_sha256="abc123",
        headers={"Content-Type": "image/png", "X-Tos-Acl": "public-read"},
    )
    auth = headers["Authorization"]
    assert auth.startswith("TOS4-HMAC-SHA256 Credential=AKxxx/")
    assert "/ap-southeast-1/tos/request" in auth
    # All signed headers must be present and ordered.
    assert "SignedHeaders=content-type;host;x-tos-acl;x-tos-content-sha256;x-tos-date" in auth
    assert headers["X-Tos-Content-Sha256"] == "abc123"
    assert headers["Host"] == "bucket.tos-ap-southeast-1.bytepluses.com"


def test_sign_is_deterministic_for_fixed_time():
    kwargs = dict(
        method="GET", host="tos-ap-southeast-1.bytepluses.com", path="/",
        payload_sha256="x", headers={},
    )
    import datetime

    class _FixedDT(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2024, 6, 16, 12, 0, 0, tzinfo=tz)

    with patch("seedance.tos.datetime") as dt:
        dt.datetime = _FixedDT
        # The module is fully mocked, so hand back the real timezone — _sign
        # passes datetime.timezone.utc into now() and needs a valid tzinfo.
        dt.timezone = datetime.timezone
        a = _sign("AK", "SK", **kwargs)["Authorization"]
        b = _sign("AK", "SK", **kwargs)["Authorization"]
    assert a == b


# ---------------------------------------------------------------------------
# list_buckets / upload_to_tos
# ---------------------------------------------------------------------------

_LIST_JSON = (
    b'{"Buckets":[{"CreationDate":"2025-05-20T14:04:12.000Z","Name":"2321312",'
    b'"Location":"ap-southeast-1","ExtranetEndpoint":"tos-ap-southeast-1.bytepluses.com"}],'
    b'"Owner":{"ID":"123"}}'
)


def test_list_buckets_parses_json():
    tos = TOSClient("ak", "sk")
    with patch.object(tos, "_request", return_value=_LIST_JSON):
        buckets = tos.list_buckets()
    assert [b["name"] for b in buckets] == ["2321312"]
    assert buckets[0]["location"] == "ap-southeast-1"


def test_list_buckets_parses_xml():
    tos = TOSClient("ak", "sk")
    with patch.object(tos, "_request", return_value=_LIST_XML):
        buckets = tos.list_buckets()
    assert [b["name"] for b in buckets] == ["my-images", "my-videos"]
    assert buckets[0]["location"] == "ap-southeast-1"


def test_upload_to_tos_builds_public_url(client, tmp_path):
    f = tmp_path / "photo.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n fake")

    captured = {}

    def fake_put(bucket, key, data, *, content_type, public):
        captured.update(bucket=bucket, key=key, content_type=content_type, public=public)
        return f"https://{bucket}.tos-ap-southeast-1.bytepluses.com/{key}"

    with patch("seedance.tos.TOSClient.put_object", side_effect=fake_put):
        result = client.upload_to_tos(str(f), bucket="my-images")

    assert captured["bucket"] == "my-images"
    assert captured["key"] == "photo.png"
    assert captured["content_type"] == "image/png"
    assert captured["public"] is True
    assert result.url == "https://my-images.tos-ap-southeast-1.bytepluses.com/photo.png"
    assert result.size == len(b"\x89PNG\r\n\x1a\n fake")


def test_upload_requires_bucket(client, tmp_path):
    f = tmp_path / "x.jpg"
    f.write_bytes(b"data")
    with pytest.raises(ValidationError, match="bucket"):
        client.upload_to_tos(str(f))


def test_upload_missing_file_raises(client):
    with pytest.raises(ValidationError, match="not found"):
        client.upload_to_tos("/nope/missing.png", bucket="my-images")
