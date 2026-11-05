"""Live-session isolation (package 2F): an anonymous cookie must not select a signed-in user's
session. Signed-in sessions are keyed by the Cognito subject, anonymous ones by the
``ts_session`` cookie, in one shared dict (src/live/sessions.py)."""

from __future__ import annotations

from typing import Any, Iterator, List

import pytest
from fastapi.testclient import TestClient

import src.live.sessions as sessions
from src.main import app


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "s.db"))
    yield TestClient(app, raise_server_exceptions=False)


@pytest.mark.xfail(
    strict=True,
    reason="S-03: the middleware uses the raw ts_session cookie as the session key "
    "(src/live/sessions.py:241-242) and signed-in users are keyed by their Cognito sub in the "
    "same dict (:247), so an anonymous client that knows a sub can adopt that user's session",
)
def test_anonymous_cookie_cannot_adopt_a_signed_in_users_session(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim_key = "cognito-sub-1234-victim"
    victim = sessions.get_or_create_session(victim_key)
    seen: List[Any] = []
    real = sessions.get_or_create_session

    def spy(key: str) -> Any:
        found = real(key)
        seen.append(found)
        return found

    monkeypatch.setattr(sessions, "get_or_create_session", spy)
    try:
        res = client.get("/api/simulation/status", cookies={"ts_session": victim_key})
        assert res.status_code == 200
        assert seen, "middleware did not resolve a session"
        assert all(s is not victim for s in seen)
    finally:
        with sessions.live_sessions_lock:
            sessions.live_sessions.pop(victim_key, None)
