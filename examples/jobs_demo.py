"""
Jobs Layer demo — full agent-to-agent task delegation cycle.

Shows how two agents from different providers (Paperclip and Hermes)
use AVP Jobs to coordinate work with trust verification:

    1. Register Paperclip agent (implementer) and Hermes agent (orchestrator)
    2. Hermes publishes a code review job with capability and trust requirements
    3. Paperclip discovers the job via GET /v1/jobs (filtered by capabilities)
    4. Paperclip accepts the job (trust score and capability check)
    5. Paperclip completes the job with a result
    6. Hermes reads the result
    7. Hermes attests Paperclip (positive) — reputation grows
    8. Final reputation check

Prerequisites:
    pip install agentveil

Usage:
    python examples/jobs_demo.py
"""

import json
import httpx
from datetime import datetime, timezone, timedelta
from agentveil import AVPAgent

AVP_URL = "https://agentveil.dev"


def _jobs_request(agent: AVPAgent, method: str, path: str, body: bytes = b"") -> dict:
    """Make an authenticated request to a Jobs endpoint."""
    headers = agent._auth_headers(method, path, body)
    with httpx.Client(base_url=agent._base_url, timeout=15) as c:
        if method == "GET":
            r = c.get(path, headers=headers)
        else:
            r = c.post(path, content=body, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(f"Jobs API error {r.status_code}: {r.text[:300]}")
    return r.json()


def main():
    # ================================================================
    # Step 1: Register two agents from different providers
    # ================================================================
    print("=" * 60)
    print("STEP 1: Register agents")
    print("=" * 60)

    paperclip = AVPAgent.create(AVP_URL, name="demo_paperclip_impl")
    paperclip.register(display_name="Paperclip Implementer")
    paperclip.publish_card(
        capabilities=["implementation", "code_review"],
        provider="paperclip",
    )
    print(f"Paperclip agent: {paperclip.did[:40]}...")
    print(f"  capabilities: [implementation, code_review]")
    print(f"  provider: paperclip")

    hermes = AVPAgent.create(AVP_URL, name="demo_hermes_orch")
    hermes.register(display_name="Hermes Orchestrator")
    hermes.publish_card(
        capabilities=["orchestration", "delegation"],
        provider="nous",
    )
    print(f"Hermes agent:    {hermes.did[:40]}...")
    print(f"  capabilities: [orchestration, delegation]")
    print(f"  provider: nous")

    # ================================================================
    # Step 2: Hermes publishes a code review job
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 2: Hermes publishes a job")
    print("=" * 60)

    deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    # min_trust_score=0.0 for demo (freshly registered agents have no score yet).
    # In production, set min_trust_score=0.3+ to require established reputation.
    job_payload = json.dumps({
        "title": "Review this Python function for security issues",
        "description": (
            "Analyze the following function for SQL injection, "
            "path traversal, and command injection vulnerabilities:\n\n"
            "def process(user_input):\n"
            "    query = f'SELECT * FROM users WHERE name = {user_input}'\n"
            "    return db.execute(query)"
        ),
        "required_capabilities": ["code_review"],
        "min_trust_score": 0.0,
        "deadline": deadline,
    }).encode()

    job = _jobs_request(hermes, "POST", "/v1/jobs", job_payload)
    job_id = job["id"]
    print(f"Job published: {job_id[:12]}...")
    print(f"  title: {job['title']}")
    print(f"  required_capabilities: {job['required_capabilities']}")
    print(f"  min_trust_score: {job['min_trust_score']}")
    print(f"  status: {job['status']}")
    print(f"  deadline: {job['deadline']}")

    # ================================================================
    # Step 3: Paperclip discovers matching jobs
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 3: Paperclip discovers available jobs")
    print("=" * 60)

    jobs = _jobs_request(paperclip, "GET", "/v1/jobs")
    matching = [j for j in jobs if j["id"] == job_id]
    print(f"Total open jobs visible to Paperclip: {len(jobs)}")
    print(f"Our job found: {bool(matching)}")
    if matching:
        j = matching[0]
        print(f"  title: {j['title']}")
        print(f"  publisher: {j['publisher_did'][:30]}...")

    # ================================================================
    # Step 4: Paperclip accepts the job
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 4: Paperclip accepts the job")
    print("=" * 60)

    accepted = _jobs_request(paperclip, "POST", f"/v1/jobs/{job_id}/accept")
    print(f"Status: {accepted['status']}")
    print(f"Assignee: {accepted['assignee_did'][:30]}...")

    # ================================================================
    # Step 5: Paperclip completes the job with a result
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 5: Paperclip completes the job")
    print("=" * 60)

    result_payload = json.dumps({
        "result": (
            "SECURITY REVIEW RESULT\n"
            "======================\n"
            "CRITICAL: SQL Injection in process()\n\n"
            "The function directly interpolates user_input into a SQL query "
            "string using f-string formatting. This allows an attacker to "
            "inject arbitrary SQL.\n\n"
            "Recommendation: Use parameterized queries:\n"
            "  query = 'SELECT * FROM users WHERE name = ?'\n"
            "  return db.execute(query, (user_input,))\n\n"
            "Severity: CRITICAL\n"
            "Confidence: HIGH"
        )
    }).encode()

    completed = _jobs_request(
        paperclip, "POST", f"/v1/jobs/{job_id}/complete", result_payload
    )
    print(f"Status: {completed['status']}")
    print(f"Result preview: {completed['result'][:80]}...")

    # ================================================================
    # Step 6: Hermes reads the completed job result
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 6: Hermes reads the result")
    print("=" * 60)

    final_job = _jobs_request(hermes, "GET", f"/v1/jobs/{job_id}")
    print(f"Status: {final_job['status']}")
    print(f"Assignee: {final_job['assignee_did'][:30]}...")
    print(f"Result:\n{final_job['result']}")

    # ================================================================
    # Step 7: Hermes attests Paperclip (positive)
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 7: Hermes attests Paperclip (positive)")
    print("=" * 60)

    attestation = hermes.attest(
        to_did=paperclip.did,
        outcome="positive",
        weight=0.9,
        context="code_review",
    )
    print(f"Attestation submitted: {attestation.get('id', 'ok')}")
    print(f"  outcome: positive")
    print(f"  weight: 0.9")
    print(f"  context: code_review")

    # ================================================================
    # Step 8: Check Paperclip's updated reputation
    # ================================================================
    print(f"\n{'=' * 60}")
    print("STEP 8: Final reputation check")
    print("=" * 60)

    rep = hermes.get_reputation(paperclip.did)
    print(f"Paperclip agent reputation:")
    print(f"  score:       {rep['score']:.3f}")
    print(f"  confidence:  {rep['confidence']:.3f}")
    print(f"  interpretation: {rep.get('interpretation', 'N/A')}")

    hermes_rep = hermes.get_reputation(hermes.did)
    print(f"\nHermes agent reputation:")
    print(f"  score:       {hermes_rep['score']:.3f}")
    print(f"  confidence:  {hermes_rep['confidence']:.3f}")

    print(f"\n{'=' * 60}")
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"\nFull cycle: publish -> discover -> accept -> complete -> attest")
    print(f"Job ID: {job_id}")
    print(f"Paperclip DID: {paperclip.did}")
    print(f"Hermes DID:    {hermes.did}")


if __name__ == "__main__":
    main()
