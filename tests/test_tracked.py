"""Tests for @avp_tracked decorator — auto-registration and attestation."""

import pytest

from agentveil.tracked import avp_tracked, clear_agent_cache, _derive_context, _make_evidence_hash


class TestDeriveContext:
    """Context string sanitization."""

    def test_simple_name(self):
        assert _derive_context("review_code") == "review_code"

    def test_special_chars_replaced(self):
        result = _derive_context("my func!@#$%")
        assert all(c.isalnum() or c in ("_", "-", ".") for c in result)

    def test_truncated_to_100(self):
        long_name = "a" * 200
        assert len(_derive_context(long_name)) == 100

    def test_dots_and_hyphens_preserved(self):
        assert _derive_context("my-func.v2") == "my-func.v2"


class TestMakeEvidenceHash:
    """Evidence hash from exceptions."""

    def test_returns_sha256_hex(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            h = _make_evidence_hash(e)
            assert len(h) == 64
            int(h, 16)  # valid hex

    def test_different_errors_different_hashes(self):
        hashes = []
        for msg in ("error 1", "error 2"):
            try:
                raise ValueError(msg)
            except ValueError as e:
                hashes.append(_make_evidence_hash(e))
        assert hashes[0] != hashes[1]


class TestClearAgentCache:
    """Cache clearing for test isolation."""

    def test_clear_does_not_raise(self):
        clear_agent_cache()  # should not raise even when empty

    def test_clear_empties_cache(self):
        from agentveil.tracked import _agent_cache
        _agent_cache["test_key"] = "dummy"
        clear_agent_cache()
        assert len(_agent_cache) == 0


class TestAvpTrackedDecorator:
    """Decorator wrapping sync and async functions."""

    def setup_method(self):
        clear_agent_cache()

    def test_sync_function_returns_result(self):
        @avp_tracked("mock://test", name="test_sync")
        def my_func(x):
            return x * 2

        # Without a server, _get_or_create_agent will fail trying to connect.
        # We test the decorator structure, not the full flow.
        # Full e2e requires a server or mocking httpx.
        assert my_func.__name__ == "my_func"
        assert my_func.__wrapped__  # functools.wraps applied

    def test_async_function_is_coroutine(self):
        import asyncio

        @avp_tracked("mock://test", name="test_async")
        async def my_async_func(x):
            return x * 2

        assert asyncio.iscoroutinefunction(my_async_func)
        assert my_async_func.__name__ == "my_async_func"

    def test_decorator_preserves_docstring(self):
        @avp_tracked("mock://test", name="test_doc")
        def documented():
            """My docstring."""
            pass

        assert documented.__doc__ == "My docstring."
