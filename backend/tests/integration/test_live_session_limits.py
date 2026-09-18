"""Bounds on the per-client live-session registry.

The registry mints a session per client cookie and a throwaway one for every
cookie-less request, so without bounds a public deployment leaks memory and
engine threads. These tests pin the two bounds (idle TTL and hard cap) and,
just as importantly, the guarantee that a session with a running simulation is
never reclaimed.
"""

import time
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

import src.main as main
from src.core.enums import SimulationStatus
from src.main import (
    _DEFAULT_SESSION_KEY,
    LIVE_SESSION_IDLE_TTL_SECONDS,
    MAX_LIVE_SESSIONS,
    _evict_stale_sessions,
    _get_or_create_session,
    _live_sessions,
    app,
)


@pytest.fixture(autouse=True)
def clean_registry() -> Iterator[None]:
    """Isolate each test from the module-level registry."""
    saved = dict(_live_sessions)
    _live_sessions.clear()
    _live_sessions[_DEFAULT_SESSION_KEY] = main._LiveSession()
    yield
    _live_sessions.clear()
    _live_sessions.update(saved)


def test_cookieless_requests_do_not_grow_registry_without_bound() -> None:
    """A crawler hitting the demo must not mint unbounded sessions."""
    client = TestClient(app)
    for _ in range(MAX_LIVE_SESSIONS + 40):
        client.cookies.clear()
        assert client.get("/api/simulation/status").status_code == 200

    assert len(_live_sessions) <= MAX_LIVE_SESSIONS + 1


def test_idle_sessions_are_evicted_after_ttl() -> None:
    session = _get_or_create_session("idle-client")
    assert "idle-client" in _live_sessions

    # Backdate past the TTL rather than sleeping through it.
    session.last_seen = time.time() - LIVE_SESSION_IDLE_TTL_SECONDS - 1

    assert _evict_stale_sessions() == 1
    assert "idle-client" not in _live_sessions


def test_recently_seen_session_survives_eviction() -> None:
    _get_or_create_session("fresh-client")
    assert _evict_stale_sessions() == 0
    assert "fresh-client" in _live_sessions


def test_default_session_is_never_evicted() -> None:
    _live_sessions[_DEFAULT_SESSION_KEY].last_seen = 0.0
    _evict_stale_sessions()
    assert _DEFAULT_SESSION_KEY in _live_sessions


def test_running_session_is_never_evicted_even_when_stale() -> None:
    """The core safety property: an active viewer keeps their simulation."""
    session = _get_or_create_session("watching-client")
    session.last_seen = 0.0  # ancient

    class _RunningEngine:
        status = SimulationStatus.RUNNING

        def stop(self) -> None:  # pragma: no cover - must never be called
            raise AssertionError("an active session must not be shut down")

    session.live_sim_data["engine"] = _RunningEngine()

    assert _evict_stale_sessions() == 0
    assert "watching-client" in _live_sessions


def test_paused_session_is_never_evicted() -> None:
    session = _get_or_create_session("paused-client")
    session.last_seen = 0.0

    class _PausedEngine:
        status = SimulationStatus.PAUSED

        def stop(self) -> None:  # pragma: no cover - must never be called
            raise AssertionError("an active session must not be shut down")

    session.live_sim_data["engine"] = _PausedEngine()

    assert _evict_stale_sessions() == 0
    assert "paused-client" in _live_sessions


def test_eviction_stops_engine_and_releases_references() -> None:
    """Evicting must actually reclaim the thread, not just drop the dict key."""
    session = _get_or_create_session("done-client")
    session.last_seen = time.time() - LIVE_SESSION_IDLE_TTL_SECONDS - 1

    stopped: list[bool] = []

    class _CompletedEngine:
        status = SimulationStatus.COMPLETED

        def stop(self) -> None:
            stopped.append(True)

    session.live_sim_data["engine"] = _CompletedEngine()

    assert _evict_stale_sessions() == 1
    assert stopped == [True]
    assert session.live_sim_data["engine"] is None
    assert "done-client" not in _live_sessions


def test_hard_cap_evicts_least_recently_used_first() -> None:
    now = time.time()
    for i in range(MAX_LIVE_SESSIONS + 10):
        session = _get_or_create_session(f"client-{i}")
        # All well inside the TTL, so only the hard cap can act here.
        session.last_seen = now - (MAX_LIVE_SESSIONS + 10 - i)

    assert len(_live_sessions) <= MAX_LIVE_SESSIONS + 1
    # The oldest keys went first; the newest are still resident.
    assert "client-0" not in _live_sessions
    assert f"client-{MAX_LIVE_SESSIONS + 9}" in _live_sessions


def test_shutdown_survives_a_failing_engine() -> None:
    """Reclaiming a session must never raise into the triggering request."""
    session = _get_or_create_session("broken-client")
    session.last_seen = time.time() - LIVE_SESSION_IDLE_TTL_SECONDS - 1

    class _ExplodingEngine:
        status = SimulationStatus.COMPLETED

        def stop(self) -> None:
            raise RuntimeError("engine refused to stop")

    session.live_sim_data["engine"] = _ExplodingEngine()

    assert _evict_stale_sessions() == 1
    assert "broken-client" not in _live_sessions


def test_session_isolation_still_holds() -> None:
    """Bounding the registry must not regress per-client isolation."""
    a = _get_or_create_session("client-a")
    b = _get_or_create_session("client-b")

    assert a is not b
    a.is_user_defined_seed = True
    assert b.is_user_defined_seed is False
    assert _get_or_create_session("client-a") is a
