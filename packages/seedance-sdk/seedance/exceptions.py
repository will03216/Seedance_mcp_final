"""Typed exceptions for the Seedance SDK."""
from __future__ import annotations


class SeedanceError(Exception):
    """Base exception for all Seedance SDK errors."""


class AuthError(SeedanceError):
    """Raised when credentials are missing or invalid."""


class ValidationError(SeedanceError):
    """Raised when request parameters fail validation."""


class APIError(SeedanceError):
    """Raised when the BytePlus API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AssetError(SeedanceError):
    """Raised when an asset library operation fails."""


class TimeoutError(SeedanceError):
    """Raised when polling exceeds the configured deadline."""
