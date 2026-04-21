"""
MCP Slice 4 — hosted-mode tests.

Covers three new behaviors added for the hosted HTTP deployment:
- AVP_MCP_READONLY=1 gates write tools at REGISTRATION, not call-time. The
  four write tools must not appear in the FastMCP tool registry.
- The HTTP ASGI app enforces Authorization: Bearer <AVP_MCP_TOKEN> on every
  path except /healthz, which returns 200 unauthenticated.
- main() with --http and an empty AVP_MCP_TOKEN refuses to start
  (fail-closed), raising SystemExit(2).

All tests skip when the optional `mcp` runtime isn't installed.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from typing import Iterable

import pytest


def _mcp_runtime_available() -> bool:
    try:
        import mcp.server.fastmcp  # noqa: F401
        return True
    except ImportError:
        return False


requires_mcp = pytest.mark.skipif(
    not _mcp_runtime_available(),
    reason="MCP runtime not installed; install with pip install 'agentveil[mcp]'",
)


WRITE_TOOLS = {"register_agent", "submit_attestation", "publish_agent_card", "get_my_agent_info"}
READ_TOOLS = {
    "check_reputation", "check_trust", "get_agent_info", "search_agents",
    "get_attestations_received", "get_protocol_stats", "verify_audit_chain",
    "get_audit_trail",
}
ALL_TOOLS = WRITE_TOOLS | READ_TOOLS


def _reload_server_with_env(env_overrides: dict) -> object:
    """Reload agentveil_mcp.server with the given env overrides applied.

    Restores the prior env after returning. Returns the reloaded module.
    """
    prior = {k: os.environ.get(k) for k in env_overrides}
    try:
        for k, v in env_overrides.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # Drop cached module so module-level flags are re-evaluated.
        for mod_name in ("agentveil_mcp.server", "agentveil_mcp"):
            sys.modules.pop(mod_name, None)
        import agentveil_mcp.server as s
        return s
    finally:
        for k, old in prior.items():
            if old is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def _tool_names(server_mod) -> set[str]:
    """Ask the FastMCP instance for its registered tool names."""
    tools = asyncio.run(server_mod.mcp.list_tools())
    return {t.name for t in tools}


# ------------------------------------------------------------------
# Readonly tool-registration gate
# ------------------------------------------------------------------

@requires_mcp
def test_full_mode_registers_all_12_tools():
    s = _reload_server_with_env({"AVP_MCP_READONLY": None})
    try:
        names = _tool_names(s)
        assert names == ALL_TOOLS, f"expected all 12 tools, got {names}"
    finally:
        # Leave module state fresh-ish for next test by clearing it.
        sys.modules.pop("agentveil_mcp.server", None)
        sys.modules.pop("agentveil_mcp", None)


@requires_mcp
def test_readonly_mode_registers_only_read_tools():
    s = _reload_server_with_env({"AVP_MCP_READONLY": "1"})
    try:
        names = _tool_names(s)
        assert names == READ_TOOLS, f"expected 8 read tools, got {names}"
        # Bright-line check: none of the four write names must be present.
        for w in WRITE_TOOLS:
            assert w not in names, f"write tool {w!r} leaked into readonly mode"
    finally:
        sys.modules.pop("agentveil_mcp.server", None)
        sys.modules.pop("agentveil_mcp", None)


@requires_mcp
def test_readonly_write_callables_still_exist_as_plain_python():
    """Write tool functions remain module attributes, just not registered with FastMCP.

    This is intentional: it keeps the module importable and lets unit tests
    exercise the functions directly if needed. The registration gate is the
    protocol-surface contract, not Python reachability.
    """
    s = _reload_server_with_env({"AVP_MCP_READONLY": "1"})
    try:
        for name in WRITE_TOOLS:
            assert callable(getattr(s, name, None)), f"{name} missing as module attr"
    finally:
        sys.modules.pop("agentveil_mcp.server", None)
        sys.modules.pop("agentveil_mcp", None)


# ------------------------------------------------------------------
# HTTP ASGI app: bearer-token middleware + health
# ------------------------------------------------------------------

@pytest.fixture
def http_app():
    s = _reload_server_with_env({"AVP_MCP_READONLY": "1"})
    app = s._build_http_app(token="test-token-123")
    try:
        yield app
    finally:
        sys.modules.pop("agentveil_mcp.server", None)
        sys.modules.pop("agentveil_mcp", None)


@requires_mcp
def test_healthz_is_unauthenticated_and_returns_200(http_app):
    from starlette.testclient import TestClient

    with TestClient(http_app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


@requires_mcp
def test_mcp_path_without_token_returns_401(http_app):
    from starlette.testclient import TestClient

    with TestClient(http_app) as client:
        r = client.get("/mcp/")
        assert r.status_code == 401
        body = r.json()
        assert "unauthorized" in body.get("error", "").lower()
        # Standard challenge header so clients can prompt for credentials.
        assert "Bearer" in r.headers.get("WWW-Authenticate", "")


@requires_mcp
def test_mcp_path_with_wrong_token_returns_401(http_app):
    from starlette.testclient import TestClient

    with TestClient(http_app) as client:
        r = client.get("/mcp/", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401


@requires_mcp
def test_mcp_path_with_correct_token_passes_middleware(http_app):
    """With a valid token, middleware forwards to the MCP ASGI app.

    We don't care what MCP returns (could be 404/405/500-from-missing-lifespan,
    depending on the transport's internal state); we only care that the middleware
    did NOT short-circuit to 401 — i.e., the gate let the request through.

    The real MCP app needs a full ASGI lifespan to initialize its session
    manager; TestClient without `raise_server_exceptions=False` surfaces that
    lifecycle gap as a raised exception. We set it False so we observe the
    HTTP status the middleware produced, which is what this test is about.
    """
    from starlette.testclient import TestClient

    with TestClient(http_app, raise_server_exceptions=False) as client:
        r = client.get("/mcp/", headers={"Authorization": "Bearer test-token-123"})
        assert r.status_code != 401, f"valid token rejected; body: {r.text}"


# ------------------------------------------------------------------
# Fail-closed on empty token
# ------------------------------------------------------------------

@requires_mcp
def test_http_mode_with_empty_token_exits_nonzero(monkeypatch):
    """main() must refuse to start an HTTP server if AVP_MCP_TOKEN is empty."""
    monkeypatch.setenv("AVP_MCP_READONLY", "1")
    monkeypatch.setenv("AVP_MCP_TOKEN", "")
    monkeypatch.setattr(sys, "argv", ["agentveil-mcp", "--http", "--port", "0"])

    s = _reload_server_with_env({"AVP_MCP_READONLY": "1", "AVP_MCP_TOKEN": ""})
    try:
        with pytest.raises(SystemExit) as excinfo:
            s.main()
        assert excinfo.value.code == 2
    finally:
        sys.modules.pop("agentveil_mcp.server", None)
        sys.modules.pop("agentveil_mcp", None)
