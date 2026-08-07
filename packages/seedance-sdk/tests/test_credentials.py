"""Tests for credential loading priority chain."""
from __future__ import annotations

import configparser

import pytest

from seedance.credentials import (
    clear_credentials,
    credentials_configured,
    load_api_key,
    load_asset_credentials,
    write_credentials,
)
from seedance.exceptions import AuthError


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Remove real credential env vars and redirect credentials file to tmp."""
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_AK", raising=False)
    monkeypatch.delenv("ARK_SK", raising=False)
    monkeypatch.setattr(
        "seedance.credentials.CREDENTIALS_PATH",
        tmp_path / "credentials",
    )
    yield


def test_load_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "test-key-from-env")
    assert load_api_key() == "test-key-from-env"


def test_load_api_key_explicit_wins_over_env(monkeypatch):
    monkeypatch.setenv("ARK_API_KEY", "env-key")
    assert load_api_key("explicit-key") == "explicit-key"


def test_load_api_key_from_credentials_file(tmp_path, monkeypatch):
    creds = tmp_path / "credentials"
    parser = configparser.ConfigParser()
    parser.add_section("default")
    parser.set("default", "ark_api_key", "file-key")
    with creds.open("w") as f:
        parser.write(f)
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", creds)
    assert load_api_key() == "file-key"


def test_load_api_key_raises_when_missing():
    with pytest.raises(AuthError, match="ARK_API_KEY"):
        load_api_key()


def test_load_asset_credentials_from_env(monkeypatch):
    monkeypatch.setenv("ARK_AK", "my-ak")
    monkeypatch.setenv("ARK_SK", "my-sk")
    ak, sk = load_asset_credentials()
    assert ak == "my-ak"
    assert sk == "my-sk"


def test_load_asset_credentials_raises_when_missing():
    with pytest.raises(AuthError, match="missing"):
        load_asset_credentials()


def test_write_and_read_credentials(tmp_path, monkeypatch):
    creds_path = tmp_path / "credentials"
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", creds_path)
    write_credentials("api-key", "ak-value", "sk-value")
    assert load_api_key() == "api-key"
    ak, sk = load_asset_credentials()
    assert ak == "ak-value"
    assert sk == "sk-value"


def test_credentials_file_is_chmod_600(tmp_path, monkeypatch):
    creds_path = tmp_path / "credentials"
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", creds_path)
    write_credentials("k", "a", "s")
    mode = oct(creds_path.stat().st_mode)[-3:]
    assert mode == "600"


def test_clear_credentials(tmp_path, monkeypatch):
    creds_path = tmp_path / "credentials"
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", creds_path)
    write_credentials("k", "a", "s")
    clear_credentials()
    with pytest.raises(AuthError):
        load_api_key()


def test_credentials_configured(tmp_path, monkeypatch):
    creds_path = tmp_path / "credentials"
    monkeypatch.setattr("seedance.credentials.CREDENTIALS_PATH", creds_path)
    status = credentials_configured()
    assert not any(status.values())

    # Core creds only — mediakit is a separate, optional credential.
    write_credentials("k", "a", "s")
    status = credentials_configured()
    assert status["api_key"] and status["ak"] and status["sk"]
    assert not status["mediakit"]

    # Writing the mediakit key flips it on.
    write_credentials("k", "a", "s", mediakit_api_key="m")
    status = credentials_configured()
    assert all(status.values())
