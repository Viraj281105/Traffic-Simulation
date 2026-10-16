"""Per-client isolation for the live/dual dashboard simulation state.

current_live_config, live_sim_data, and dual_sim_orchestrator used to be
bare process-global singletons, so one client's /api/simulation/config or
/api/simulation/dual/reset call would silently reset what every other
connected client was watching. There is no existing session/user concept
in this API to key off of, so the smallest practical, dependency-free
(no Redis/DB) mechanism is a browser cookie — the closest thing to a
built-in "connection identifier" HTTP already provides. A signed-in user's
Cognito subject is used instead when a token is presented.

Live-session registry bounds: the registry mints a session per client
cookie, and any request arriving without one (a crawler, a health probe,
curl, a browser that rejects cookies) mints a fresh key that nothing will
ever present again. Left unbounded that is a memory and thread leak that a
public deployment would hit within hours: each session can own a live
SimulationEngine, and each running engine owns a background thread.

Two bounds, deliberately both present: a TTL reclaims the common case of
abandoned single-use sessions, and a hard cap is the backstop for a burst
that arrives faster than the TTL can expire. Neither ever evicts a session
whose simulation is still running or paused (see LiveSession.is_active).
"""

import contextvars
import copy
import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from src.api.security import bearer_value, is_api_key
from src.auth import verify_token
from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import SimulationStatus
from src.live.dashboard_config import DEFAULT_CONFIG, generate_random_seed
from src.metrics.collector import MetricCollector
from src.snapshot.builder import SnapshotBuilder
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator

logger = logging.getLogger(__name__)

LIVE_SESSION_COOKIE = "ts_session"
DEFAULT_SESSION_KEY = "default"
LIVE_SESSION_PATH_PREFIX = "/api/simulation"

MAX_LIVE_SESSIONS = 100
LIVE_SESSION_IDLE_TTL_SECONDS = 30 * 60


def _empty_live_sim_data() -> Dict[str, Any]:
    return {
        "engine": None,
        "collector": None,
        "controller": None,
        "builder": None,
        "config_id": None,
    }


class LiveSession:
    """Per-client container for what used to be the three global variables."""

    def __init__(self) -> None:
        self.current_live_config: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.is_user_defined_seed: bool = False
        self.live_sim_data: Dict[str, Any] = _empty_live_sim_data()
        self.dual_sim_orchestrator: Optional[DualSimulationOrchestrator] = None
        self.last_seen: float = time.time()

    def touch(self) -> None:
        self.last_seen = time.time()

    def is_active(self) -> bool:
        """True while this session still owns a live engine or orchestrator.

        An active session is never evicted, so a visitor watching a running
        simulation cannot have it pulled out from under them just because the
        registry filled up.
        """
        engine = self.live_sim_data.get("engine")
        if engine is not None and engine.status in (
            SimulationStatus.RUNNING,
            SimulationStatus.PAUSED,
        ):
            return True
        orch = self.dual_sim_orchestrator
        if orch is not None and orch.get_status() in ("running", "paused"):
            return True
        return False

    def shutdown(self) -> None:
        """Stop and drop this session's engines so its threads can exit.

        Called on eviction. Every step is best-effort and independently
        guarded: reclaiming a session must never raise into a request that
        merely happened to trigger the sweep.
        """
        engine = self.live_sim_data.get("engine")
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                logger.exception("Failed to stop live engine during eviction")
        orch = self.dual_sim_orchestrator
        if orch is not None:
            try:
                orch.stop()
            except Exception:
                logger.exception("Failed to stop dual orchestrator during eviction")
        self.live_sim_data = _empty_live_sim_data()
        self.dual_sim_orchestrator = None


live_sessions: Dict[str, LiveSession] = {DEFAULT_SESSION_KEY: LiveSession()}
live_sessions_lock: threading.RLock = threading.RLock()
live_session_var: "contextvars.ContextVar[Optional[LiveSession]]" = (
    contextvars.ContextVar("live_session", default=None)
)


def evict_stale_sessions(now: Optional[float] = None) -> int:
    """Reclaim idle sessions. Returns how many were evicted.

    The shared default session is never evicted — it is the fallback every
    non-cookie caller (WebSocket handlers, tests, direct calls) resolves to.
    """
    current = time.time() if now is None else now
    evicted = 0

    with live_sessions_lock:
        # Pass 1 — anything idle for longer than the TTL.
        for key in list(live_sessions.keys()):
            if key == DEFAULT_SESSION_KEY:
                continue
            session = live_sessions[key]
            if session.is_active():
                continue
            if current - session.last_seen >= LIVE_SESSION_IDLE_TTL_SECONDS:
                session.shutdown()
                del live_sessions[key]
                evicted += 1

        # Pass 2 — still over the cap, so drop the least recently used
        # inactive sessions until it fits.
        if len(live_sessions) > MAX_LIVE_SESSIONS:
            candidates = [
                (session.last_seen, key)
                for key, session in live_sessions.items()
                if key != DEFAULT_SESSION_KEY and not session.is_active()
            ]
            candidates.sort()
            overflow = len(live_sessions) - MAX_LIVE_SESSIONS
            for _, key in candidates[:overflow]:
                live_sessions[key].shutdown()
                del live_sessions[key]
                evicted += 1

    return evicted


def get_or_create_session(key: str) -> LiveSession:
    with live_sessions_lock:
        session = live_sessions.get(key)
        if session is None:
            # Reclaim before admitting a new session, so the registry is
            # bounded at the moment of growth rather than after the fact.
            evict_stale_sessions()
            session = LiveSession()
            live_sessions[key] = session
        session.touch()
        return session


def current_session() -> LiveSession:
    """Returns the live session for the current request context.

    Falls back to one shared "default" session for anything that isn't a
    request routed through `live_session_middleware` with a valid cookie —
    notably the two WebSocket handlers (which resolve their own session
    explicitly from `websocket.cookies`) and any direct/test call outside of
    request handling. That fallback exactly matches this application's
    previous single-shared-state behavior.
    """
    session = live_session_var.get()
    if session is not None:
        return session
    return get_or_create_session(DEFAULT_SESSION_KEY)


def find_live_session(request: Request) -> Optional[LiveSession]:
    """The caller's existing live session, looked up (never created) from
    its session cookie, for routes outside the live-session middleware's
    prefix. No cookie -> None: never guess at another client's (or the
    shared default) session."""
    key = request.cookies.get(LIVE_SESSION_COOKIE)
    if not key:
        return None
    with live_sessions_lock:
        return live_sessions.get(key)


async def live_session_middleware(request: Request, call_next: Any) -> Any:
    """Resolves a per-client live-simulation session from a Cognito JWT."""
    if not request.url.path.startswith(LIVE_SESSION_PATH_PREFIX):
        return await call_next(request)

    # A bearer value identifies a user only when it is not the server's own
    # API key: a proxy (or script) authenticating with the key is not a
    # user, and must get the anonymous cookie session rather than a 401.
    token = bearer_value(request.headers.get("Authorization"))
    if token is None or is_api_key(token):
        incoming = request.cookies.get(LIVE_SESSION_COOKIE)
        key = incoming or str(uuid.uuid4())
    else:
        try:
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            claims = verify_token(creds)
            key = str(claims.get("sub", ""))
        except Exception as e:
            # A client presenting a bad token is a client error: logged on the
            # module logger at warning level, not as a server error on root.
            logger.warning("JWT verification failed: %s", e)
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    ctx_token = live_session_var.set(get_or_create_session(key))
    try:
        response = await call_next(request)
    finally:
        live_session_var.reset(ctx_token)

    if request.cookies.get(LIVE_SESSION_COOKIE) != key:
        response.set_cookie(
            LIVE_SESSION_COOKIE,
            key,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24,
        )
    return response


def get_or_create_live_simulation() -> Dict[str, Any]:
    session = current_session()
    if session.live_sim_data["engine"] is None:
        clock = Clock(time_step=0.1)
        duration = session.current_live_config.get("simulation", {}).get(
            "duration", 300
        )
        engine = SimulationEngine(
            clock, duration=duration, config=session.current_live_config
        )
        controller = create_controller(session.current_live_config, engine.network)
        engine.controller = controller

        collector = MetricCollector(session.current_live_config)
        config_id = str(uuid.uuid4())
        builder = SnapshotBuilder("live_sim", config_id, engine, collector, controller)

        engine.register_tick_callback(
            build_tick_callback(controller, clock, engine, collector)
        )
        session.live_sim_data["engine"] = engine
        session.live_sim_data["collector"] = collector
        session.live_sim_data["controller"] = controller
        session.live_sim_data["builder"] = builder
        session.live_sim_data["config_id"] = config_id
    return session.live_sim_data


def get_or_create_dual_orchestrator() -> DualSimulationOrchestrator:
    session = current_session()
    if session.dual_sim_orchestrator is None:
        session.dual_sim_orchestrator = DualSimulationOrchestrator(
            session.current_live_config
        )
    return session.dual_sim_orchestrator


def reseed_unless_user_pinned(session: LiveSession) -> None:
    """Draw a fresh seed for the next live/dual run, unless the user pinned one.

    The rule is the same at all three call sites that restart a run — live
    play after completion, dual play after completion, and dual reset — and
    it was written out at each of them. Stating it once keeps the three from
    drifting: a seed the user supplied explicitly must survive a restart, or
    the run they asked to reproduce is not the run they get.
    """
    if session.is_user_defined_seed:
        return
    session.current_live_config["simulation"]["randomSeed"] = generate_random_seed()
