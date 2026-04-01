"""Tests for AVP exception hierarchy."""

import pytest

from agentveil.exceptions import (
    AVPError,
    AVPAuthError,
    AVPNotFoundError,
    AVPRateLimitError,
    AVPValidationError,
    AVPServerError,
)


class TestExceptionHierarchy:
    """All exceptions inherit from AVPError."""

    def test_auth_error_is_avp_error(self):
        assert issubclass(AVPAuthError, AVPError)

    def test_not_found_is_avp_error(self):
        assert issubclass(AVPNotFoundError, AVPError)

    def test_rate_limit_is_avp_error(self):
        assert issubclass(AVPRateLimitError, AVPError)

    def test_validation_is_avp_error(self):
        assert issubclass(AVPValidationError, AVPError)

    def test_server_error_is_avp_error(self):
        assert issubclass(AVPServerError, AVPError)


class TestExceptionAttributes:
    """Exception objects carry structured data."""

    def test_avp_error_attributes(self):
        e = AVPError("test message", status_code=418, detail="teapot")
        assert e.message == "test message"
        assert e.status_code == 418
        assert e.detail == "teapot"
        assert str(e) == "test message"

    def test_rate_limit_has_retry_after(self):
        e = AVPRateLimitError("slow down", retry_after=30)
        assert e.retry_after == 30
        assert e.status_code == 429

    def test_rate_limit_default_retry(self):
        e = AVPRateLimitError()
        assert e.retry_after == 60

    def test_error_defaults(self):
        e = AVPError("msg")
        assert e.status_code == 0
        assert e.detail == ""


class TestExceptionCatching:
    """Exceptions can be caught by parent class."""

    def test_catch_auth_as_avp_error(self):
        with pytest.raises(AVPError):
            raise AVPAuthError("bad sig", 401)

    def test_catch_not_found_as_avp_error(self):
        with pytest.raises(AVPError):
            raise AVPNotFoundError("no agent", 404)

    def test_catch_rate_limit_as_avp_error(self):
        with pytest.raises(AVPError):
            raise AVPRateLimitError("wait")
