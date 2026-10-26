"""Tests for Personal Access Tokens (PATs), scopes, revocation, and audit persistence.

W7 Stage 1 / ADR-013 / ADR-018 validation suite.
"""

from __future__ import annotations

import datetime
import hashlib
from datetime import timedelta, timezone
from typing import Any, Iterator, List

import pytest
from fastapi.testclient import TestClient

import src.api.auth as auth
import src.api.security as security
from src.api.auth import DEV_AUTH_TOKEN, reset_auth_failures
from src.api.token_store import AuditStore, TokenStore, ensure_tables
from src.database.db import get_db_connection
from src.main import app

KEY = "test-gate-key"


def error_message(res: Any) -> str:
    """Extract error message whether in {"error": {"message": ...}} envelope or {"detail": ...}."""
    body = res.json()
    if isinstance(body, dict):
        if (
            "error" in body
            and isinstance(body["error"], dict)
            and "message" in body["error"]
        ):
            return str(body["error"]["message"])
        return str(body.get("detail", ""))
    return str(body)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[None]:
    db_file = str(tmp_path / "test_pat.db")
    monkeypatch.setattr("src.database.db.DB_PATH", db_file)
    monkeypatch.setattr(security, "API_KEY", KEY)
    reset_auth_failures()
    with get_db_connection() as conn:
        ensure_tables(conn)
    try:
        yield
    finally:
        reset_auth_failures()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_token_creation_dev_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dev browser session creates a PAT; 256-bit secret returned once; SHA-256 stored."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    headers = {
        "X-API-Key": KEY,
        "Authorization": f"Bearer {DEV_AUTH_TOKEN}",
    }
    payload = {
        "name": "Integration Test Token",
        "scopes": ["experiments:read", "experiments:run"],
        "expiresInDays": 30,
    }
    res = client.post("/api/v3/tokens", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Integration Test Token"
    assert data["id"].startswith("pat_")
    raw_token = data["token"]
    assert raw_token.startswith("uf_pat_")
    assert len(raw_token) > 40
    assert set(data["scopes"]) == {"experiments:read", "experiments:run"}

    # Verify only SHA-256 hash is in SQLite, not raw secret
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sha256_hash, user_id FROM uf_pats WHERE id = ?;", (data["id"],)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["user_id"] == "local-dev"
        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        assert row["sha256_hash"] == expected_hash


def test_token_creation_rejected_for_pat(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request presenting a PAT cannot create another PAT (HTTP 403)."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}
    create_res = client.post(
        "/api/v3/tokens",
        json={"name": "First PAT", "scopes": ["experiments:read", "experiments:run"]},
        headers=headers,
    )
    assert create_res.status_code == 201
    pat_token = create_res.json()["token"]

    # Now attempt to create a second PAT using the first PAT
    pat_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {pat_token}"}
    res = client.post(
        "/api/v3/tokens",
        json={"name": "Recursive PAT", "scopes": ["experiments:read"]},
        headers=pat_headers,
    )
    assert res.status_code == 403
    assert error_message(res) == "A PAT cannot create a PAT"


def test_token_creation_scope_validation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid or empty scopes fail with HTTP 422."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}

    # Empty scopes
    res = client.post(
        "/api/v3/tokens",
        json={"name": "Bad Token", "scopes": []},
        headers=headers,
    )
    assert res.status_code == 422

    # Invalid scope string
    res = client.post(
        "/api/v3/tokens",
        json={"name": "Bad Token", "scopes": ["admin:super", "experiments:read"]},
        headers=headers,
    )
    assert res.status_code == 422


def test_active_token_limit_and_quota_audit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At most 10 active tokens per user; 11th yields 429 and records quota_rejected audit."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}

    created_ids: List[str] = []
    for i in range(10):
        res = client.post(
            "/api/v3/tokens",
            json={"name": f"Token {i}", "scopes": ["experiments:read"]},
            headers=headers,
        )
        assert res.status_code == 201
        created_ids.append(res.json()["id"])

    # 11th creation attempt should be refused
    res11 = client.post(
        "/api/v3/tokens",
        json={"name": "Token 11", "scopes": ["experiments:read"]},
        headers=headers,
    )
    assert res11.status_code == 429
    assert "Active PAT limit exceeded" in error_message(res11)

    # Check audit log for quota_rejected event
    events = AuditStore.list_events(user_id="local-dev")
    quota_events = [e for e in events if e.eventType == "quota_rejected"]
    assert len(quota_events) >= 1
    assert quota_events[0].details.get("quota") == "active_pats"

    # Revoke one token; creation should now succeed
    del_res = client.delete(f"/api/v3/tokens/{created_ids[0]}", headers=headers)
    assert del_res.status_code == 200

    retry_res = client.post(
        "/api/v3/tokens",
        json={"name": "Token 11 replacement", "scopes": ["experiments:read"]},
        headers=headers,
    )
    assert retry_res.status_code == 201


def test_token_listing_and_ownership(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/v3/tokens lists caller's active tokens without secrets, respecting ownership."""
    # Alice creates 2 tokens directly via TokenStore
    meta1, _ = TokenStore.create_token("alice", "Alice Token 1", ["experiments:read"])
    meta2, _ = TokenStore.create_token("alice", "Alice Token 2", ["experiments:run"])
    # Bob creates 1 token
    TokenStore.create_token("bob", "Bob Token 1", ["experiments:read"])

    # List as alice
    monkeypatch.setattr(
        auth,
        "verify_cognito_jwt",
        lambda token: {"sub": "alice", "email": "alice@example.com"},
    )
    headers_alice = {"X-API-Key": KEY, "Authorization": "Bearer alice-jwt"}
    res = client.get("/api/v3/tokens", headers=headers_alice)
    assert res.status_code == 200
    tokens = res.json()["tokens"]
    assert len(tokens) == 2
    ids = {t["id"] for t in tokens}
    assert ids == {meta1["id"], meta2["id"]}
    # Verify no raw secret in listing
    for t in tokens:
        assert "token" not in t

    # List as bob
    monkeypatch.setattr(
        auth,
        "verify_cognito_jwt",
        lambda token: {"sub": "bob", "email": "bob@example.com"},
    )
    headers_bob = {"X-API-Key": KEY, "Authorization": "Bearer bob-jwt"}
    res_bob = client.get("/api/v3/tokens", headers=headers_bob)
    assert res_bob.status_code == 200
    assert len(res_bob.json()["tokens"]) == 1


def test_token_revocation_and_immediate_effect(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Revoking a token immediately invalidates authentication with HTTP 401."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    dev_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}

    create_res = client.post(
        "/api/v3/tokens",
        json={"name": "Ephemeral", "scopes": ["experiments:read"]},
        headers=dev_headers,
    )
    token_id = create_res.json()["id"]
    raw_pat = create_res.json()["token"]

    # Use PAT to access capabilities
    pat_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {raw_pat}"}
    cap_res = client.get("/api/v3/capabilities", headers=pat_headers)
    assert cap_res.status_code == 200

    # Verify last_used_at was updated
    tok_row = TokenStore.get_by_id(token_id)
    assert tok_row is not None
    assert tok_row["last_used_at"] is not None

    # Revoke token
    del_res = client.delete(f"/api/v3/tokens/{token_id}", headers=dev_headers)
    assert del_res.status_code == 200
    assert del_res.json() == {"id": token_id, "revoked": True}

    # Attempt to use revoked token -> 401
    cap_after = client.get("/api/v3/capabilities", headers=pat_headers)
    assert cap_after.status_code == 401
    assert "revoked" in error_message(cap_after).lower()


def test_token_revocation_ownership(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting another user's token returns HTTP 404 (ADR-013)."""
    meta, _ = TokenStore.create_token("alice", "Alice Token", ["experiments:read"])

    # Bob attempts to delete Alice's token
    monkeypatch.setattr(
        auth,
        "verify_cognito_jwt",
        lambda token: {"sub": "bob", "email": "bob@example.com"},
    )
    headers = {"X-API-Key": KEY, "Authorization": "Bearer bob-jwt"}
    del_res = client.delete(f"/api/v3/tokens/{meta['id']}", headers=headers)
    assert del_res.status_code == 404
    assert error_message(del_res) == "Token not found"


def test_token_expiry(client: TestClient) -> None:
    """An expired token is rejected with HTTP 401."""
    meta, raw_pat = TokenStore.create_token(
        "alice", "Expired Token", ["experiments:read"], expires_in_days=1
    )
    # Set expires_at in the past
    past = (datetime.datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE uf_pats SET expires_at = ? WHERE id = ?;", (past, meta["id"])
        )
        conn.commit()

    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {raw_pat}"}
    res = client.get("/api/v3/capabilities", headers=headers)
    assert res.status_code == 401
    assert "expired" in error_message(res).lower()


def test_scope_enforcement(client: TestClient) -> None:
    """PAT scopes are strictly enforced per route."""
    # Token 1: experiments:read only
    _, read_token = TokenStore.create_token("alice", "Reader", ["experiments:read"])
    read_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {read_token}"}

    # Allowed: capabilities and validate
    assert client.get("/api/v3/capabilities", headers=read_headers).status_code == 200
    assert (
        client.post(
            "/api/v3/experiments/validate", json={}, headers=read_headers
        ).status_code
        == 200
    )

    # Denied: submit (requires experiments:run)
    submit_res = client.post("/api/v3/experiments", json={}, headers=read_headers)
    assert submit_res.status_code == 403
    assert error_message(submit_res) == "Insufficient token scope"

    # Token 2: experiments:run only
    _, run_token = TokenStore.create_token("alice", "Runner", ["experiments:run"])
    run_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {run_token}"}

    # Denied: capabilities (requires experiments:read)
    assert client.get("/api/v3/capabilities", headers=run_headers).status_code == 403

    # Token with unrelated scope: packages:read only
    _, pkg_token = TokenStore.create_token("alice", "Packager", ["packages:read"])
    pkg_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {pkg_token}"}
    assert client.get("/api/v3/capabilities", headers=pkg_headers).status_code == 403


def test_audit_persistence_and_secret_redaction(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit table is append-only and strictly redacts tokens, secrets, and payloads."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    dev_headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}

    # Perform token creation and revocation
    res = client.post(
        "/api/v3/tokens",
        json={"name": "Audit Sample", "scopes": ["experiments:read"]},
        headers=dev_headers,
    )
    assert res.status_code == 201
    token_id = res.json()["id"]
    raw_secret = res.json()["token"]

    client.delete(f"/api/v3/tokens/{token_id}", headers=dev_headers)

    events = AuditStore.list_events(user_id="local-dev")
    event_types = [e.eventType for e in events]
    assert "token_created" in event_types
    assert "token_revoked" in event_types

    # Read raw SQLite audit log to verify zero secret leakage
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT details_json FROM uf_audit_log;")
        rows = cursor.fetchall()
        for row in rows:
            json_text = row["details_json"]
            assert raw_secret not in json_text, "Raw secret leaked into audit log!"
            assert "uf_pat_" not in json_text, "PAT prefix found in audit log!"


def test_failed_auth_rate_limiting(client: TestClient) -> None:
    """10 failed authentication attempts from same IP result in HTTP 429."""
    forged_token = "uf_pat_nonexistent_token_12345"
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {forged_token}"}

    for _ in range(10):
        res = client.get("/api/v3/capabilities", headers=headers)
        assert res.status_code == 401

    # 11th attempt is rate-limited
    res11 = client.get("/api/v3/capabilities", headers=headers)
    assert res11.status_code == 429
    assert "Too many invalid authentication attempts" in error_message(res11)

    # Resetting restores access
    reset_auth_failures()
    res_after_reset = client.get("/api/v3/capabilities", headers=headers)
    assert res_after_reset.status_code == 401


def test_concurrent_creation_cannot_exceed_active_token_limit() -> None:
    """Simultaneous creators for one user are serialized: exactly the limit succeeds."""
    import threading

    from src.api.token_store import MAX_ACTIVE_TOKENS_PER_USER

    attempts = MAX_ACTIVE_TOKENS_PER_USER + 6
    barrier = threading.Barrier(attempts)
    outcomes: List[str] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        barrier.wait()
        try:
            TokenStore.create_token("racer", f"t{i}", ["experiments:read"])
            result = "ok"
        except RuntimeError:
            result = "quota"
        except Exception as err:  # pragma: no cover - surfaced by the assertions
            result = f"error:{err!r}"
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert outcomes.count("ok") == MAX_ACTIVE_TOKENS_PER_USER, outcomes
    assert outcomes.count("quota") == attempts - MAX_ACTIVE_TOKENS_PER_USER, outcomes
    assert TokenStore.count_active("racer") == MAX_ACTIVE_TOKENS_PER_USER
