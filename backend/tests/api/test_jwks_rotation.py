"""The Cognito key set is refetched after a key rotation (F-22).

``get_jwks`` cached the pool's keys for the life of the process, so after a
Cognito signing-key rotation every new token was refused with "Public key not
found" until a restart. A token whose ``kid`` is not in the cached set now
triggers one refetch, at most once per ``JWKS_REFRESH_COOLDOWN_SECONDS`` (so
tokens with made-up ``kid``s cannot turn the server into a fetch amplifier),
and a failed refetch keeps the keys already held.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Iterator, List

import pytest
import requests
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import src.api.auth as auth
from tests.api.test_cognito_token_verification import (
    CLIENT,
    _claims,
    _jwk,
    _key,
    _sign,
)

OLD_KEY = _key()
NEW_KEY = _key()


class _Response:
    def __init__(self, keys: List[Dict[str, str]]) -> None:
        self._keys = keys

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return {"keys": self._keys}


class _Pool:
    """Stands in for the user pool's jwks.json endpoint."""

    def __init__(self) -> None:
        self.keys = [_jwk(OLD_KEY, "old")]
        self.fetches = 0
        self.down = False

    def get(self, url: str, timeout: float) -> _Response:
        assert url.endswith("/eu-west-1_TESTPOOL/.well-known/jwks.json")
        self.fetches += 1
        if self.down:
            raise requests.ConnectionError("pool unreachable")
        return _Response(list(self.keys))


@pytest.fixture
def pool(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Pool]:
    fake = _Pool()
    monkeypatch.setattr(auth, "USER_POOL_ID", "eu-west-1_TESTPOOL")
    monkeypatch.setattr(auth, "REGION", "eu-west-1")
    monkeypatch.setattr(auth, "CLIENT_ID", CLIENT)
    monkeypatch.setattr(auth.requests, "get", fake.get)
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    auth.reset_jwks_cache()
    yield fake
    auth.reset_jwks_cache()


def _verify(token: str) -> Dict[str, Any]:
    return auth.verify_token(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )


def _age_cache(seconds: float) -> None:
    auth._JWKS_FETCHED_AT = time.monotonic() - seconds


def test_keys_are_fetched_once_and_cached(pool: _Pool) -> None:
    token = _sign(_claims(), OLD_KEY, "old")
    assert _verify(token)["sub"] == "user-123"
    assert _verify(token)["sub"] == "user-123"
    assert pool.fetches == 1


def test_a_rotated_key_is_picked_up_after_the_cooldown(pool: _Pool) -> None:
    assert _verify(_sign(_claims(), OLD_KEY, "old"))["sub"] == "user-123"
    pool.keys = [_jwk(OLD_KEY, "old"), _jwk(NEW_KEY, "new")]
    _age_cache(auth.JWKS_REFRESH_COOLDOWN_SECONDS + 1)
    assert _verify(_sign(_claims(), NEW_KEY, "new"))["sub"] == "user-123"
    assert pool.fetches == 2
    # Both keys are now held; nothing more is fetched.
    _verify(_sign(_claims(), OLD_KEY, "old"))
    _verify(_sign(_claims(), NEW_KEY, "new"))
    assert pool.fetches == 2


def test_unknown_kids_refetch_at_most_once_per_cooldown(pool: _Pool) -> None:
    _verify(_sign(_claims(), OLD_KEY, "old"))
    for i in range(20):
        with pytest.raises(HTTPException) as err:
            _verify(_sign(_claims(), NEW_KEY, f"made-up-{i}"))
        assert err.value.status_code == 401
    # Inside the cooldown of the first fetch: no refetch at all.
    assert pool.fetches == 1
    _age_cache(auth.JWKS_REFRESH_COOLDOWN_SECONDS + 1)
    for i in range(20):
        with pytest.raises(HTTPException):
            _verify(_sign(_claims(), NEW_KEY, f"made-up-again-{i}"))
    # One refetch for the twenty, then the cooldown applies again.
    assert pool.fetches == 2


def test_a_failed_refetch_keeps_the_keys_already_held(pool: _Pool) -> None:
    _verify(_sign(_claims(), OLD_KEY, "old"))
    pool.down = True
    _age_cache(auth.JWKS_REFRESH_COOLDOWN_SECONDS + 1)
    with pytest.raises(HTTPException) as err:
        _verify(_sign(_claims(), NEW_KEY, "new"))
    assert err.value.status_code == 401
    assert pool.fetches == 2
    # The existing key still verifies, without another fetch.
    assert _verify(_sign(_claims(), OLD_KEY, "old"))["sub"] == "user-123"
    assert pool.fetches == 2


def test_a_withdrawn_key_stops_verifying_once_the_set_is_old(pool: _Pool) -> None:
    """A key the pool removes must not stay trusted for the life of the
    process just because no unknown kid ever triggers a refresh."""
    token = _sign(_claims(), OLD_KEY, "old")
    assert _verify(token)["sub"] == "user-123"
    pool.keys = [_jwk(NEW_KEY, "new")]  # "old" withdrawn
    _age_cache(auth.JWKS_REFRESH_COOLDOWN_SECONDS + 1)
    # Younger than the max age: still the cached set.
    assert _verify(token)["sub"] == "user-123"
    assert pool.fetches == 1
    _age_cache(auth.JWKS_MAX_AGE_SECONDS + 1)
    with pytest.raises(HTTPException) as err:
        _verify(token)
    assert err.value.status_code == 401
    assert pool.fetches == 2
    assert _verify(_sign(_claims(), NEW_KEY, "new"))["sub"] == "user-123"


def test_an_unreachable_pool_at_max_age_keeps_the_published_keys(pool: _Pool) -> None:
    _verify(_sign(_claims(), OLD_KEY, "old"))
    pool.down = True
    _age_cache(auth.JWKS_MAX_AGE_SECONDS + 1)
    assert _verify(_sign(_claims(), OLD_KEY, "old"))["sub"] == "user-123"
    assert pool.fetches == 2
    # The failed attempt restarted the clock: no retry on the next request.
    _verify(_sign(_claims(), OLD_KEY, "old"))
    assert pool.fetches == 2
    # A forged token is still refused while the pool is down.
    with pytest.raises(HTTPException):
        _verify(_sign(_claims(), NEW_KEY, "old"))


def test_concurrent_unknown_kids_cause_one_fetch(pool: _Pool) -> None:
    _verify(_sign(_claims(), OLD_KEY, "old"))
    _age_cache(auth.JWKS_REFRESH_COOLDOWN_SECONDS + 1)
    start = threading.Barrier(16)
    statuses: List[int] = []

    def attempt(i: int) -> None:
        token = _sign(_claims(), NEW_KEY, f"made-up-{i}")
        start.wait()
        try:
            _verify(token)
            statuses.append(200)
        except HTTPException as err:
            statuses.append(err.status_code)

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert statuses == [401] * 16
    assert pool.fetches == 2


def test_a_cold_start_outage_backs_off_and_recovers(pool: _Pool) -> None:
    """With no keys held, a failed fetch is not retried for a short backoff:
    tokens are refused either way (fail closed), and requests no longer each
    wait behind their own fetch. After the backoff the next request fetches
    again and, once the pool is back, verifies normally."""
    pool.down = True
    token = _sign(_claims(), OLD_KEY, "old")
    for _ in range(10):
        with pytest.raises(HTTPException) as err:
            _verify(token)
        assert err.value.status_code == 401
        assert err.value.detail == "Invalid token"
    assert pool.fetches == 1
    pool.down = False
    # Still inside the backoff: refused without a fetch.
    with pytest.raises(HTTPException):
        _verify(token)
    assert pool.fetches == 1
    auth._JWKS_FAILED_AT = (
        time.monotonic() - auth.JWKS_INITIAL_FAILURE_BACKOFF_SECONDS - 1
    )
    assert _verify(token)["sub"] == "user-123"
    assert pool.fetches == 2
    assert auth._JWKS_FAILED_AT is None
