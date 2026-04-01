"""Tests for HTTP response handling in AVPAgent._handle_response."""

import pytest
from unittest.mock import MagicMock

from agentveil.agent import AVPAgent
from agentveil.exceptions import (
    AVPAuthError,
    AVPNotFoundError,
    AVPRateLimitError,
    AVPValidationError,
    AVPServerError,
    AVPError,
)


def _make_response(status_code: int, json_data=None, text=""):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("no json")
    return resp


class TestHandleResponse:
    """Response parsing and exception mapping."""

    def setup_method(self):
        self.agent = AVPAgent.create("https://example.com", name="test", save=False)

    def test_200_returns_json(self):
        resp = _make_response(200, {"status": "ok"})
        result = self.agent._handle_response(resp)
        assert result == {"status": "ok"}

    def test_401_raises_auth_error(self):
        resp = _make_response(401, {"detail": "bad signature"})
        with pytest.raises(AVPAuthError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 401

    def test_403_raises_auth_error(self):
        resp = _make_response(403, {"detail": "forbidden"})
        with pytest.raises(AVPAuthError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 403

    def test_404_raises_not_found(self):
        resp = _make_response(404, {"detail": "agent not found"})
        with pytest.raises(AVPNotFoundError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 404

    def test_409_raises_validation_error(self):
        resp = _make_response(409, {"detail": "already registered"})
        with pytest.raises(AVPValidationError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 409

    def test_429_raises_rate_limit(self):
        resp = _make_response(429, {"detail": "too many requests"})
        with pytest.raises(AVPRateLimitError):
            self.agent._handle_response(resp)

    def test_400_raises_validation_error(self):
        resp = _make_response(400, {"detail": "invalid input"})
        with pytest.raises(AVPValidationError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 400

    def test_500_raises_server_error(self):
        resp = _make_response(500, {"detail": "internal error"})
        with pytest.raises(AVPServerError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 500

    def test_502_raises_server_error(self):
        resp = _make_response(502, {"detail": "bad gateway"})
        with pytest.raises(AVPServerError):
            self.agent._handle_response(resp)

    def test_unexpected_status_raises_avp_error(self):
        resp = _make_response(418, {"detail": "teapot"})
        with pytest.raises(AVPError) as exc_info:
            self.agent._handle_response(resp)
        assert exc_info.value.status_code == 418

    def test_non_json_error_response(self):
        resp = _make_response(500, json_data=None, text="nginx error")
        with pytest.raises(AVPServerError):
            self.agent._handle_response(resp)
