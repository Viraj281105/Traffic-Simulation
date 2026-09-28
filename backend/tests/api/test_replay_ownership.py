"""Saved replays belong to the user who saved them.

The replay endpoints resolve the caller from a verified Cognito token
(``src.auth``): without one they refuse, and a signed-in user cannot read or
delete another user's replay, nor see it in their list.
"""

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import src.database.db as db_module
from src.auth import get_current_user_email, get_current_user_id
from src.database.db import init_db
from src.main import app

client = TestClient(app)

PAYLOAD = {
    "name": "Owned replay",
    "config": {"simulation": {"duration": 10.0}},
    "metrics": {"throughput": 20},
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "replays.db"))
    init_db()


@pytest.fixture
def act_as() -> Iterator[object]:
    """Switch the signed-in user between requests."""

    def sign_in(user_id: str) -> None:
        app.dependency_overrides[get_current_user_id] = lambda: user_id
        app.dependency_overrides[get_current_user_email] = lambda: (
            f"{user_id}@example.com"
        )

    try:
        yield sign_in
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
        app.dependency_overrides.pop(get_current_user_email, None)


def test_replay_endpoints_require_a_signed_in_user() -> None:
    assert client.post("/api/v1/replays", json=PAYLOAD).status_code == 401
    assert client.get("/api/v1/replays").status_code == 401
    assert client.get("/api/v1/replays/any-id").status_code == 401
    assert client.delete("/api/v1/replays/any-id").status_code == 401


def test_another_users_replay_is_forbidden_and_unlisted(act_as) -> None:
    act_as("alice")
    replay_id = client.post("/api/v1/replays", json=PAYLOAD).json()["replay_id"]
    assert client.get(f"/api/v1/replays/{replay_id}").status_code == 200

    act_as("bob")
    assert client.get(f"/api/v1/replays/{replay_id}").status_code == 403
    assert client.delete(f"/api/v1/replays/{replay_id}").status_code == 403
    assert all(r["id"] != replay_id for r in client.get("/api/v1/replays").json())

    act_as("alice")
    assert any(r["id"] == replay_id for r in client.get("/api/v1/replays").json())
    assert client.delete(f"/api/v1/replays/{replay_id}").status_code == 200
