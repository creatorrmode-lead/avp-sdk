"""
Universal @avp_tracked decorator — one line = full AVP integration.

Usage:
    from agentveil import avp_tracked

    @avp_tracked("https://agentveil.dev", name="my_agent", capabilities=["code_review"])
    def review_code(pr_url: str) -> str:
        # Your logic here
        return analysis

    # That's it. The decorator handles:
    # - Auto-registration on first call
    # - Positive attestation on success
    # - Negative attestation with evidence on failure
    # - Agent card publishing with capabilities

Works with sync and async functions, any framework.
"""

import asyncio
import functools
import hashlib
import inspect
import logging
import traceback
from typing import Optional

from agentveil.agent import AVPAgent
from agentveil.exceptions import AVPError

log = logging.getLogger("agentveil.tracked")

# Cache of initialized agents (by name) to avoid re-registration
_agent_cache: dict[str, AVPAgent] = {}


def _get_or_create_agent(
    base_url: str,
    name: str,
    capabilities: list[str],
    provider: Optional[str],
) -> AVPAgent:
    """Get cached agent or create+register a new one."""
    if name in _agent_cache:
        return _agent_cache[name]

    # Try loading existing agent
    try:
        agent = AVPAgent.load(base_url, name=name)
        if agent.is_verified:
            _agent_cache[name] = agent
            log.info(f"Loaded existing agent: {name}")
            return agent
    except FileNotFoundError:
        pass

    # Create and register new agent
    agent = AVPAgent.create(base_url, name=name, save=True)
    try:
        agent.register(display_name=name)
        log.info(f"Auto-registered agent: {name} ({agent.did[:40]}...)")
    except AVPError as e:
        # Already registered (409) — load state and continue
        if e.status_code == 409:
            log.info(f"Agent already registered: {name}")
            agent._is_registered = True
            agent._is_verified = True
            agent.save()
        else:
            log.warning(f"Registration failed: {e}")
            raise

    # Publish capabilities card
    if capabilities:
        try:
            agent.publish_card(capabilities=capabilities, provider=provider)
            log.info(f"Published card: {capabilities}")
        except AVPError as e:
            log.warning(f"Card publish failed (non-fatal): {e}")

    # Auto-handle onboarding challenge if pipeline generated one
    _auto_handle_challenge(agent)

    _agent_cache[name] = agent
    return agent


def _auto_handle_challenge(agent: AVPAgent, max_wait: float = 10.0) -> None:
    """
    Poll for an onboarding challenge and auto-submit an answer.
    Non-blocking best-effort: if anything fails, the agent continues without challenge.
    Max wait time prevents blocking the decorator for too long.
    """
    import time
    deadline = time.monotonic() + max_wait

    try:
        # Poll for challenge (pipeline may still be generating it)
        challenge = None
        for _ in range(5):
            challenge = agent.get_onboarding_challenge()
            if challenge and challenge.get("status") == "awaiting_response":
                break
            if time.monotonic() > deadline:
                return
            time.sleep(1.0)

        if not challenge or challenge.get("status") != "awaiting_response":
            return

        challenge_id = challenge.get("challenge_id", "")
        challenge_text = challenge.get("challenge_text", "")

        if not challenge_id or not challenge_text:
            return

        # Generate a basic answer describing what the agent can do
        # (real LLM-powered agents should override this with their own logic)
        answer = (
            f"Responding to challenge: {challenge_text[:200]}\n\n"
            f"I am an AI agent with capabilities in this domain. "
            f"This is an automated response from the AVP SDK tracked decorator. "
            f"My capabilities are registered in my agent card."
        )

        result = agent.submit_challenge_answer(challenge_id, answer)
        log.info(
            f"Auto-submitted challenge answer: score={result.get('score', '?')}, "
            f"passed={result.get('passed', '?')}"
        )
    except Exception as e:
        log.debug(f"Auto-challenge handling skipped: {e}")


def _make_evidence_hash(exc: Exception) -> str:
    """Create SHA256 hash of exception traceback for evidence."""
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    tb_text = "".join(tb)
    return hashlib.sha256(tb_text.encode()).hexdigest()


def _derive_context(func_name: str) -> str:
    """Derive attestation context from function name."""
    # Sanitize: only alphanumeric, underscore, hyphen, dot (AVP context rules)
    clean = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in func_name)
    return clean[:100]


def avp_tracked(
    base_url: str,
    *,
    name: str = "agent",
    to_did: Optional[str] = None,
    capabilities: Optional[list[str]] = None,
    provider: Optional[str] = None,
    weight: float = 0.8,
    attest_self: bool = False,
):
    """
    Decorator that integrates any function with Agent Veil Protocol.

    On first call: auto-registers agent (if not registered).
    On success: submits positive attestation.
    On exception: submits negative attestation with stack trace hash as evidence.

    Args:
        base_url: AVP server URL (e.g. "https://agentveil.dev")
        name: Agent name (used for key storage and display)
        to_did: DID of agent to attest (required unless attest_self=True)
        capabilities: Agent capabilities for card (defaults to [function_name])
        provider: LLM provider for card (e.g. "anthropic")
        weight: Attestation weight 0.0-1.0 (default 0.8)
        attest_self: If True and to_did is None, skip attestation (no self-attest)

    Usage:
        @avp_tracked("https://agentveil.dev", name="reviewer", to_did="did:key:z6Mk...")
        def review_code(code: str) -> str:
            return "LGTM"

        @avp_tracked("https://agentveil.dev", name="reviewer", capabilities=["code_review"])
        async def review_code(code: str) -> str:
            return "LGTM"
    """

    def decorator(func):
        func_name = func.__name__
        caps = capabilities if capabilities is not None else [func_name]
        context = _derive_context(func_name)

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                agent = _get_or_create_agent(base_url, name, caps, provider)
                target_did = to_did

                try:
                    result = await func(*args, **kwargs)

                    # Positive attestation on success
                    if target_did:
                        try:
                            agent.attest(
                                to_did=target_did,
                                outcome="positive",
                                weight=weight,
                                context=context,
                            )
                        except AVPError as e:
                            log.warning(f"Positive attestation failed (non-fatal): {e}")

                    return result

                except Exception as exc:
                    # Negative attestation on failure
                    if target_did:
                        evidence = _make_evidence_hash(exc)
                        try:
                            agent.attest(
                                to_did=target_did,
                                outcome="negative",
                                weight=weight,
                                context=context,
                                evidence_hash=evidence,
                            )
                        except AVPError as e:
                            log.warning(f"Negative attestation failed (non-fatal): {e}")
                    raise

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                agent = _get_or_create_agent(base_url, name, caps, provider)
                target_did = to_did

                try:
                    result = func(*args, **kwargs)

                    # Positive attestation on success
                    if target_did:
                        try:
                            agent.attest(
                                to_did=target_did,
                                outcome="positive",
                                weight=weight,
                                context=context,
                            )
                        except AVPError as e:
                            log.warning(f"Positive attestation failed (non-fatal): {e}")

                    return result

                except Exception as exc:
                    # Negative attestation on failure
                    if target_did:
                        evidence = _make_evidence_hash(exc)
                        try:
                            agent.attest(
                                to_did=target_did,
                                outcome="negative",
                                weight=weight,
                                context=context,
                                evidence_hash=evidence,
                            )
                        except AVPError as e:
                            log.warning(f"Negative attestation failed (non-fatal): {e}")
                    raise

            return sync_wrapper

    return decorator


def clear_agent_cache():
    """Clear the cached agents. Useful for testing."""
    _agent_cache.clear()
