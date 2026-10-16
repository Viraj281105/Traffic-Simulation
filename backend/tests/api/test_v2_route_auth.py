"""Every mounted ``/api/v2`` route needs the API key and a signed-in user.

nginx attaches ``X-API-Key`` to every browser request, so the key identifies
the proxy, not a person: a route guarded by the key alone is public. The
routes are read from the app itself, not listed by hand, so a route added
later without the guards fails here.
"""

import re
from typing import List, Tuple

import pytest
from fastapi.testclient import TestClient

import src.api.security as security
import src.auth as auth
from src.auth import DEV_AUTH_TOKEN
from src.main import app

KEY = "test-gate-key"


def _v2_routes() -> List[Tuple[str, str]]:
    # From the app's own OpenAPI document: this FastAPI nests included
    # routers, so ``app.routes`` does not list their routes directly.
    found = []
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/v2/"):
            for method in operations:
                found.append((method.upper(), re.sub(r"\{[^}]+\}", "x", path)))
    return sorted(found)


V2_ROUTES = _v2_routes()


def test_every_v2_family_is_mounted() -> None:
    families = {path.split("/")[3] for _, path in V2_ROUTES}
    assert families == {"calibration", "networks", "planning"}
    assert len(V2_ROUTES) >= 20


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setattr(security, "API_KEY", KEY)
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    return TestClient(app)


def _call(client: TestClient, method: str, path: str, headers: dict) -> int:
    body = None if method in ("GET", "DELETE") else {}
    return client.request(method, path, json=body, headers=headers).status_code


@pytest.mark.parametrize(("method", "path"), V2_ROUTES)
def test_no_api_key_is_401(client: TestClient, method: str, path: str) -> None:
    headers = {"Authorization": f"Bearer {DEV_AUTH_TOKEN}"}
    assert _call(client, method, path, headers) == 401


@pytest.mark.parametrize(("method", "path"), V2_ROUTES)
def test_api_key_without_a_user_is_401(
    client: TestClient, method: str, path: str
) -> None:
    assert _call(client, method, path, {"X-API-Key": KEY}) == 401


@pytest.mark.parametrize(("method", "path"), V2_ROUTES)
def test_api_key_with_an_invalid_user_token_is_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, method: str, path: str
) -> None:
    # A configured pool whose key set does not contain the token's key id:
    # the token is refused as unverifiable.
    monkeypatch.setattr(auth, "USER_POOL_ID", "eu-west-1_TESTPOOL")
    monkeypatch.setattr(auth, "get_jwks", lambda: [])
    forged = (
        "eyJhbGciOiJSUzI1NiIsImtpZCI6Im5vcGUifQ.eyJzdWIiOiJtYWxsb3J5In0.c2lnbmF0dXJl"
    )
    headers = {"X-API-Key": KEY, "Authorization": f"Bearer {forged}"}
    assert _call(client, method, path, headers) == 401


@pytest.mark.parametrize(("method", "path"), V2_ROUTES)
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
    res = client.get("/api/v2/calibration/thresholds", headers=headers)
    assert res.status_code == 200 and res.json()["thresholds"]
    res = client.post(
        "/api/v2/networks/validate", json={"network": {}}, headers=headers
    )
    assert res.status_code == 200 and res.json()["valid"] is False
