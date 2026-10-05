"""The server API key and per-user tokens must coexist.

nginx used to inject the API key as ``Authorization: Bearer <API_KEY>``. That
overwrote the signed-in user's Cognito token, and the live-session middleware
then tried to verify the key itself as a JWT, answering ``401 Invalid token``
to every ``/api/simulation/*`` call — so enabling API_KEY broke the guided
comparison, and saved runs never saw the user. The key now travels in
``X-API-Key`` and ``Authorization`` is left for the user.
"""

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import src.database.db as db_module
import src.main as main
from src.auth import DEV_AUTH_TOKEN
from src.database.db import init_db
from src.main import app

KEY = "test-secret-key-0123456789"
KEY_HEADER = {"X-API-Key": KEY}
DEV_USER = {"Authorization": f"Bearer {DEV_AUTH_TOKEN}"}

SCENARIO = {
    "intersectionType": "fixed_time_signal",
    "duration": 60,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.2,
    "randomSeed": 7,
}

REPLAY = {
    "name": "Key + user",
    "config": {"simulation": {"duration": 10.0}},
    "metrics": {"throughput": 20},
}


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "keyed.db"))
    monkeypatch.setattr(main, "API_KEY", KEY)
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    init_db()
    yield TestClient(app)


def test_live_dashboard_works_with_the_key_header(client: TestClient) -> None:
    """What the browser sends through nginx when it is not signed in."""
    config = client.post("/api/simulation/config", json=SCENARIO, headers=KEY_HEADER)
    assert config.status_code == 200, config.text
    status = client.get("/api/simulation/dual/status", headers=KEY_HEADER)
    assert status.status_code == 200, status.text


def test_live_dashboard_treats_the_key_as_a_bearer_token_as_anonymous(
    client: TestClient,
) -> None:
    """A proxy still configured the old way must not be rejected as an
    invalid user token: the key is not a user, so the cookie session applies."""
    headers = {"Authorization": f"Bearer {KEY}"}
    config = client.post("/api/simulation/config", json=SCENARIO, headers=headers)
    assert config.status_code == 200, config.text
    assert client.get("/api/simulation/dual/status", headers=headers).status_code == 200


def test_live_dashboard_still_requires_the_key(client: TestClient) -> None:
    response = client.post("/api/simulation/config", json=SCENARIO)
    assert response.status_code == 401


def test_live_dashboard_still_rejects_an_invalid_user_token(
    client: TestClient,
) -> None:
    headers = {**KEY_HEADER, "Authorization": "Bearer not-a-real-jwt"}
    response = client.post("/api/simulation/config", json=SCENARIO, headers=headers)
    assert response.status_code == 401


def test_signed_in_user_and_api_key_together(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The request nginx forwards for a signed-in user: its own key header plus
    the user's untouched bearer token. Saving, listing and deleting work, and
    the live session is the user's."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    headers = {**KEY_HEADER, **DEV_USER}

    config = client.post("/api/simulation/config", json=SCENARIO, headers=headers)
    assert config.status_code == 200, config.text

    saved = client.post("/api/v1/replays", json=REPLAY, headers=headers)
    assert saved.status_code == 200, saved.text
    replay_id = saved.json()["replay_id"]

    listed = client.get("/api/v1/replays", headers=headers)
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [replay_id]

    deleted = client.delete(f"/api/v1/replays/{replay_id}", headers=headers)
    assert deleted.status_code == 200


def test_saving_needs_the_key_even_for_a_signed_in_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    response = client.post("/api/v1/replays", json=REPLAY, headers=DEV_USER)
    assert response.status_code == 401
