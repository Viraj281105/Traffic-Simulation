"""The local development auth bypass (src/auth.py DEV_AUTH_BYPASS).

The Vite dev server sends a fixed development marker as its bearer token
until Cognito is connected. The backend accepts it only when started with
DEV_AUTH_BYPASS=1; otherwise it is refused like any invalid token, and every
other token keeps the Cognito path.
"""

import pytest
from fastapi.testclient import TestClient

import src.database.db as db_module
from src.auth import DEV_AUTH_CLAIMS, DEV_AUTH_TOKEN
from src.database.db import init_db
from src.main import app

client = TestClient(app)

DEV_HEADERS = {"Authorization": f"Bearer {DEV_AUTH_TOKEN}"}
PAYLOAD = {
    "name": "Dev replay",
    "config": {"simulation": {"duration": 10.0}},
    "metrics": {"throughput": 20},
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "replays.db"))
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)
    init_db()


def test_dev_token_is_rejected_unless_the_bypass_is_enabled() -> None:
    response = client.get("/api/v1/replays", headers=DEV_HEADERS)
    assert response.status_code == 401
    assert "DEV_AUTH_BYPASS" in response.text


@pytest.mark.parametrize("value", ["0", "false", "", "no"])
def test_only_an_explicit_flag_enables_the_bypass(monkeypatch, value) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", value)
    assert client.get("/api/v1/replays", headers=DEV_HEADERS).status_code == 401


def test_bypass_serves_saved_runs_as_the_local_dev_user(monkeypatch) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")

    saved = client.post("/api/v1/replays", json=PAYLOAD, headers=DEV_HEADERS)
    assert saved.status_code == 200
    replay_id = saved.json()["replay_id"]

    listed = client.get("/api/v1/replays", headers=DEV_HEADERS)
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [replay_id]
    assert (
        client.get(f"/api/v1/replays/{replay_id}", headers=DEV_HEADERS).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/replays/{replay_id}", headers=DEV_HEADERS).status_code
        == 200
    )
    assert DEV_AUTH_CLAIMS["sub"] == "local-dev"


def test_bypass_does_not_change_cognito_handling_of_other_tokens(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    # No token at all is still refused.
    assert client.get("/api/v1/replays").status_code == 401
    # Any other bearer token still goes through Cognito verification, which
    # cannot succeed here (no user pool): it is never treated as the dev user.
    other = client.get(
        "/api/v1/replays", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert other.status_code in (401, 500)
