"""Every mounted ``/api/v3`` route needs the API key and a signed-in user (same rule as ``/api/v2``).

The routes are read from the app's own OpenAPI document, so a route added later without the guards fails
here."""

import re
from typing import List, Tuple

import pytest
from fastapi.testclient import TestClient

import src.api.auth as auth
import src.api.security as security
from src.api.auth import DEV_AUTH_TOKEN
from src.api.request_limits import MAX_V2_BODY_BYTES
from src.main import app

KEY = "test-gate-key"


def _v3_routes() -> List[Tuple[str, str]]:
    found = []
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/v3/"):
            for method in operations:
                found.append((method.upper(), re.sub(r"\{[^}]+\}", "x", path)))
    return sorted(found)


V3_ROUTES = _v3_routes()


def test_the_v3_family_is_mounted() -> None:
    families = {path.split("/")[3] for _, path in V3_ROUTES}
    assert families == {"capabilities", "copilot", "experiments", "packages", "tokens"}
    assert len(V3_ROUTES) >= 20


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setattr(security, "API_KEY", KEY)
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    auth.reset_auth_failures()
    return TestClient(app)


def _call(client: TestClient, method: str, path: str, headers: dict) -> int:
    body = None if method in ("GET", "DELETE") else {}
    return client.request(method, path, json=body, headers=headers).status_code


@pytest.mark.parametrize(("method", "path"), V3_ROUTES)
def test_no_api_key_is_401(client: TestClient, method: str, path: str) -> None:
    headers = {"Authorization": f"Bearer {DEV_AUTH_TOKEN}"}
    assert _call(client, method, path, headers) == 401


@pytest.mark.parametrize(("method", "path"), V3_ROUTES)
def test_api_key_without_a_user_is_401(
    client: TestClient, method: str, path: str
) -> None:
    assert _call(client, method, path, {"X-API-Key": KEY}) == 401


@pytest.mark.parametrize(("method", "path"), V3_ROUTES)
def test_api_key_with_an_invalid_user_token_is_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    monkeypatch.setattr(auth, "USER_POOL_ID", "eu-west-1_TESTPOOL")
    monkeypatch.setattr(auth, "get_jwks", lambda: [])
    forged = (
        "eyJhbGciOiJSUzI1NiIsImtpZCI6Im5vcGUifQ.eyJzdWIiOiJtYWxsb3J5In0.c2lnbmF0dXJl"
    )
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {forged}"}
    assert _call(client, method, path, headers) == 401


@pytest.mark.parametrize(("method", "path"), V3_ROUTES)
def test_dev_token_is_refused_without_the_bypass(
    client: TestClient, method: str, path: str
) -> None:
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}
    assert _call(client, method, path, headers) == 401


def test_key_and_user_together_reach_the_route(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {DEV_AUTH_TOKEN}"}
    res = client.get("/api/v3/capabilities", headers=headers)
    assert res.status_code == 200 and res.json()["apiVersion"] == 3
    res = client.post("/api/v3/experiments/validate", json={}, headers=headers)
    assert res.status_code == 200 and res.json()["valid"] is False


def test_oversized_experiment_body_is_413(signed_in_user: str) -> None:
    client = TestClient(app)
    huge = '{"name": "' + "x" * (MAX_V2_BODY_BYTES + 10) + '"}'
    for path in ("/api/v3/experiments", "/api/v3/experiments/validate"):
        res = client.post(
            path, content=huge, headers={"Content-Type": "application/json"}
        )
        assert res.status_code == 413, path
        assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
