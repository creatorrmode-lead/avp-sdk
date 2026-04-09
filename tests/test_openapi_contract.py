"""
Contract test: verify SDK endpoint assumptions match live OpenAPI schema.

Run: pytest tests/test_openapi_contract.py -v
Requires: production or local server running.
"""

import os
import httpx
import pytest

BASE_URL = os.environ.get("AVP_BASE_URL", "https://agentveil.dev")

# SDK endpoint expectations: (method, path, description)
SDK_ENDPOINTS = [
    ("POST", "/v1/agents/register", "agent registration"),
    ("POST", "/v1/agents/verify", "agent verification"),
    ("GET", "/v1/agents/{did}", "get agent info"),
    ("POST", "/v1/cards", "publish card"),
    ("GET", "/v1/cards", "search cards"),
    ("POST", "/v1/attestations", "submit attestation"),
    ("POST", "/v1/attestations/batch", "batch attestation"),
    ("GET", "/v1/reputation/{did}", "get reputation"),
    ("GET", "/v1/reputation/{did}/trust-check", "can_trust advisory"),
    ("GET", "/v1/reputation/bulk", "bulk reputation"),
    ("GET", "/v1/reputation/{did}/tracks", "reputation tracks"),
    ("GET", "/v1/reputation/{did}/velocity", "reputation velocity"),
    ("GET", "/v1/reputation/{did}/credential", "verifiable credential"),
    ("POST", "/v1/alerts", "create alert"),
    ("DELETE", "/v1/alerts/{alert_id}", "delete alert"),
    ("GET", "/v1/alerts", "list alerts"),
    ("POST", "/v1/verify/email", "email verification"),
    ("POST", "/v1/verify/email/confirm", "email confirm"),
    ("POST", "/v1/verify/moltbook", "moltbook verification"),
    ("GET", "/v1/verify/status/{did}", "verification status"),
    ("GET", "/v1/onboarding/{did}/challenge", "get onboarding challenge"),
    ("POST", "/v1/onboarding/{did}/challenge", "submit challenge response"),
    ("GET", "/v1/onboarding/{did}", "get onboarding status"),
    ("GET", "/v1/health", "health check"),
]

# Required response fields per endpoint (the ones SDK accesses directly)
REQUIRED_RESPONSE_FIELDS = {
    "POST /v1/agents/register": ["challenge", "pow_challenge", "pow_difficulty"],
    "GET /v1/reputation/{did}": ["score", "confidence", "interpretation"],
}


@pytest.fixture(scope="module")
def openapi_schema():
    """Fetch live OpenAPI schema."""
    try:
        r = httpx.get(f"{BASE_URL}/openapi.json", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        pytest.skip(f"Cannot fetch OpenAPI schema from {BASE_URL}: {e}")


class TestEndpointExistence:
    """Verify every endpoint the SDK calls actually exists in the server."""

    @pytest.mark.parametrize(
        "method,path,desc", SDK_ENDPOINTS, ids=[f"{m} {p}" for m, p, _ in SDK_ENDPOINTS]
    )
    def test_endpoint_exists(self, openapi_schema, method, path, desc):
        paths = openapi_schema.get("paths", {})
        assert path in paths, (
            f"SDK expects {method} {path} ({desc}) but server OpenAPI "
            f"does not list it. Available: {sorted(paths.keys())}"
        )
        methods = paths[path]
        assert method.lower() in methods, (
            f"Path {path} exists but method {method} not found. "
            f"Available methods: {list(methods.keys())}"
        )


class TestResponseSchemas:
    """Verify required response fields are declared in OpenAPI schema."""

    @pytest.mark.parametrize(
        "endpoint,fields",
        REQUIRED_RESPONSE_FIELDS.items(),
        ids=REQUIRED_RESPONSE_FIELDS.keys(),
    )
    def test_response_has_required_fields(self, openapi_schema, endpoint, fields):
        method, path = endpoint.split(" ", 1)
        path_spec = openapi_schema.get("paths", {}).get(path, {})
        method_spec = path_spec.get(method.lower(), {})

        # Navigate to 200 response schema
        resp_200 = method_spec.get("responses", {}).get("200", {})
        content = resp_200.get("content", {}).get("application/json", {})
        schema = content.get("schema", {})

        # Resolve $ref if present
        if "$ref" in schema:
            ref_path = schema["$ref"].replace("#/", "").split("/")
            resolved = openapi_schema
            for part in ref_path:
                resolved = resolved.get(part, {})
            schema = resolved

        properties = schema.get("properties", {})
        for field in fields:
            assert field in properties, (
                f"{endpoint} response missing field '{field}'. "
                f"SDK depends on it. Available: {sorted(properties.keys())}"
            )
