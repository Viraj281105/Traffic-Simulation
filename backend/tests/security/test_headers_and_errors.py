"""Error responses and headers (package 2F).

Asserts what the app does today and nothing aspirational. What the API process does not set
itself (X-Content-Type-Options, HSTS, a CSP on API responses) is reported in
docs/security/review-v5.3.md: the deployed nginx (frontend/templates/default.conf.template) sets
the first and the CSP; HSTS is set by neither.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.auth import get_current_user_id
from src.main import app

NGINX = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "templates"
    / "default.conf.template"
)

LEAK = re.compile(
    r"(Traceback \(most recent call last\)|File \"[^\"]+\", line \d+|[A-Za-z]:\\\\|"
    r"[A-Za-z]:\\|site-packages|/usr/lib/python|/app/src/|\bsrc[\\/][a-z_]+[\\/][a-z_]+\.py)"
)
SECRET_PATH = r"C:\Users\secret-user\backend\src\hidden_module.py"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "e.db"))
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    yield TestClient(app, raise_server_exceptions=False)


def _assert_clean(body: str, where: str) -> None:
    assert not LEAK.search(body), f"{where} leaks internals: {body[:300]}"


def test_unknown_route_and_wrong_method_do_not_leak(client: TestClient) -> None:
    for res in (client.get("/no/such/route"), client.delete("/health")):
        assert res.status_code in (404, 405)
        _assert_clean(res.text, "routing error")


def test_unauthenticated_error_uses_the_envelope_and_challenges(
    client: TestClient,
) -> None:
    res = client.get("/api/v2/twin/compare")
    assert res.status_code in (401, 405)
    res = client.post("/api/v2/twin/compare", json={})
    assert res.status_code == 401
    assert res.headers.get("www-authenticate", "").lower().startswith("bearer")
    assert res.json()["error"]["code"]
    _assert_clean(res.text, "401")


def test_validation_error_names_fields_but_not_files(client: TestClient) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: "u"
    try:
        res = client.post("/api/v2/netmetrics-does-not-exist", json={})
        res = client.post("/api/v2/network-metrics/simulate", json={"duration": "x"})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert res.status_code == 422
    _assert_clean(res.text, "422")


def test_unexpected_exception_is_a_bare_500_without_traceback(
    client: TestClient,
) -> None:
    def boom() -> str:
        raise RuntimeError(f"cannot open {SECRET_PATH}")

    app.dependency_overrides[get_current_user_id] = boom
    try:
        res = client.post("/api/v2/network-metrics/simulate", json={})
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
    assert res.status_code == 500
    assert "hidden_module" not in res.text and "secret-user" not in res.text
    _assert_clean(res.text, "500")
    assert "RuntimeError" not in res.text


def test_bad_token_error_does_not_echo_the_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.api.auth as auth

    monkeypatch.setattr(auth, "USER_POOL_ID", "eu-west-1_TESTPOOL")
    monkeypatch.setattr(auth, "get_jwks", lambda: [])
    token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2ln-marker-value"
    res = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code in (401, 403)
    assert token not in res.text and "marker-value" not in res.text


@pytest.mark.xfail(
    strict=True,
    reason="S-07: with COGNITO_USER_POOL_ID unset, a presented token gets 500 and the message "
    "'Cognito User Pool ID not configured on server' (src/api/auth.py:365); fail-closed, but "
    "a 503 with a generic body would not disclose server configuration",
)
def test_unconfigured_identity_provider_is_not_a_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.api.auth as auth

    monkeypatch.setattr(auth, "USER_POOL_ID", "")
    res = client.get("/api/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert res.status_code in (401, 403, 503)
    assert "Pool ID" not in res.text


def test_every_response_carries_a_request_id_and_echoes_a_safe_one(
    client: TestClient,
) -> None:
    res = client.get("/health")
    assert res.headers.get("x-request-id")
    sent = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert sent.headers.get("x-request-id") == "abc-123"
    hostile = client.get("/health", headers={"X-Request-ID": "x" * 5000})
    assert len(hostile.headers.get("x-request-id", "")) < 200


def test_cors_does_not_reflect_an_unlisted_origin(client: TestClient) -> None:
    res = client.options(
        "/api/v2/twin/compare",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    allowed: Dict[str, Any] = {k.lower(): v for k, v in res.headers.items()}
    assert allowed.get("access-control-allow-origin") not in (
        "https://evil.example",
        "*",
    ) or (allowed.get("access-control-allow-credentials") != "true")


def test_websocket_from_a_foreign_origin_is_refused(client: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/simulation/live", headers={"Origin": "https://evil.example"}
        ):
            pass


def test_nginx_template_sets_the_baseline_headers_on_both_locations() -> None:
    text = NGINX.read_text(encoding="utf-8")
    for header in (
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Content-Security-Policy",
    ):
        assert text.count(f"add_header {header}") >= 2, header
    assert "server_tokens off" in text
    assert "frame-ancestors 'none'" in text and "object-src 'none'" in text
    assert (
        "script-src 'self';" in text
        and "unsafe-inline" not in text.split("script-src", 1)[1].split(";", 1)[0]
    )


def test_nginx_template_does_not_proxy_metrics() -> None:
    text = NGINX.read_text(encoding="utf-8")
    assert not re.search(r"location\s+[^\n{]*/metrics", text)
