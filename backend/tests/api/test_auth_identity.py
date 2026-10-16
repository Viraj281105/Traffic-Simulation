"""Identity resolution in src/api/auth.py.

* a verified token without a ``sub`` is refused (an empty id would match
  every unowned record in an owner comparison);
* admin status needs a *verified* email in ADMIN_EMAILS;
* the optional dependencies treat a missing token as anonymous but a
  presented bad token as a 401, never as anonymous.
"""

from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

import src.api.auth as auth
from src.main import app


def test_token_without_a_subject_is_refused() -> None:
    for claims in ({}, {"sub": ""}, {"sub": "   "}, {"sub": None}):
        with pytest.raises(HTTPException) as err:
            auth.get_current_user_id(claims)
        assert err.value.status_code == 401
    assert auth.get_current_user_id({"sub": "abc"}) == "abc"


def test_admin_needs_a_verified_listed_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "ADMIN_EMAILS", frozenset({"boss@example.com"}))
    assert auth.is_admin({"email": "Boss@Example.com", "email_verified": True})
    assert auth.is_admin({"email": "boss@example.com", "email_verified": "true"})
    assert not auth.is_admin({"email": "boss@example.com"})
    assert not auth.is_admin({"email": "boss@example.com", "email_verified": False})
    assert not auth.is_admin({"email": "boss@example.com", "email_verified": "false"})
    assert not auth.is_admin({"email": "other@example.com", "email_verified": True})
    assert not auth.is_admin({"email": "", "email_verified": True})


def test_optional_identity_is_anonymous_only_without_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert auth.get_optional_claims(None) is None
    assert auth.get_optional_user_id(None) is None
    assert auth.get_optional_user_is_admin(None) is False

    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    bad = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    with pytest.raises(HTTPException) as err:
        auth.get_optional_claims(bad)
    assert err.value.status_code in (401, 500)  # 500 only when no pool is set


def test_history_routes_reject_a_bad_token_instead_of_going_anonymous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The run list is readable anonymously, but a request that presents a
    token is judged by that token: a forged one is a 401, not a fallback."""
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    client = TestClient(app)
    assert client.get("/api/v1/study/history/runs").status_code == 200
    forged = {"Authorization": "Bearer " + auth.DEV_AUTH_TOKEN}
    res = client.get("/api/v1/study/history/runs", headers=forged)
    assert res.status_code == 401


def test_dev_token_signs_in_on_optional_routes_only_with_the_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    creds: Any = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=auth.DEV_AUTH_TOKEN
    )
    claims = auth.get_optional_claims(creds)
    assert claims is not None
    assert auth.get_optional_user_id(claims) == "local-dev"
    assert auth.get_optional_user_is_admin(claims) is False
