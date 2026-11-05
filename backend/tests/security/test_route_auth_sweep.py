"""Authz sweep (package 2F): every route of the real app, found by walking the app itself.

Rule: a request with no API key and no token gets 401 or 403 and never 200 or 5xx, unless the
route is in ``PUBLIC_ROUTES`` below. That list is reviewed by hand: every entry names why the
route is reachable anonymously. A route that is neither rejected nor listed fails this file by
name, so a new unguarded route cannot ship silently.

Only the rejection path runs (the guards fire before any handler), so no simulation starts.
Deployed configuration is simulated by setting API_KEY, so the key guard is active too.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Tuple

import pytest
from fastapi.testclient import TestClient

import src.api.security as security
from src.main import app

from .route_inventory import RouteInfo, all_routes, assert_inventory_sane

REJECTED = (401, 403)

_HISTORY = "public by design: unowned study runs are readable by anyone (src/access.py)"
_DOCS = "FastAPI documentation endpoints; expose only the schema"
_LIVE_READ = (
    "anonymous read of the caller's cookie-scoped live session (src/live/sessions.py)"
)
_VALIDATE = "stateless validation of a posted document; no storage, no long compute"
_SIM_READ = (
    "read of a registered simulation by uuid; no owner check (review finding S-06)"
)
_STUDY_READ = (
    "read of a study job or sweep result; no owner check (review finding S-06)"
)
_WS = "browser WebSocket; origin check only, no key or token (review finding S-02)"

# (METHOD, path template) -> reason it may be reached with no credentials at all.
PUBLIC_ROUTES: Dict[Tuple[str, str], str] = {
    ("GET", "/openapi.json"): _DOCS,
    ("GET", "/docs"): _DOCS,
    ("GET", "/docs/oauth2-redirect"): _DOCS,
    ("GET", "/redoc"): _DOCS,
    ("GET", "/health"): "liveness probe for the load balancer",
    ("GET", "/api/version"): "public build metadata (engine version, commit)",
    (
        "GET",
        "/api/strategies",
    ): "public catalogue of signal strategies for the landing UI",
    (
        "GET",
        "/api/v1/study/sensitivity/inputs",
    ): "public catalogue of sensitivity inputs",
    ("GET", "/api/v1/study/history/runs"): _HISTORY,
    ("GET", "/api/v1/study/history/runs/{run_id}"): _HISTORY,
    ("GET", "/api/v1/study/history/runs/{run_id}/reproducibility"): _HISTORY,
    ("GET", "/api/v1/study/history/runs/{run_id}/export"): _HISTORY,
    ("POST", "/api/v1/study/history/runs/compare"): _HISTORY + " (read-only compare)",
    ("GET", "/api/simulation/status"): _LIVE_READ,
    ("GET", "/api/simulation/single-vehicle"): _LIVE_READ,
    ("GET", "/api/simulation/active-vehicles"): _LIVE_READ,
    ("GET", "/api/simulation/dual/status"): _LIVE_READ,
    ("GET", "/api/simulation/comparison/status"): _LIVE_READ,
    ("POST", "/api/v1/configs/validate"): _VALIDATE,
    ("POST", "/api/v1/scenarios/validate"): _VALIDATE,
    ("POST", "/api/v1/scenarios/compile"): _VALIDATE + " (compiles, does not run)",
    ("GET", "/api/v1/simulations/{sim_id}"): _SIM_READ,
    ("GET", "/api/v1/simulations/{sim_id}/metrics"): _SIM_READ,
    ("GET", "/api/v1/simulations/{sim_id}/history"): _SIM_READ,
    ("GET", "/api/v1/simulations/{sim_id}/history/{tick}"): _SIM_READ,
    ("GET", "/api/v1/simulations/{sim_id}/report"): _SIM_READ,
    ("GET", "/api/v1/study/jobs/{job_id}"): _STUDY_READ,
    ("GET", "/api/v1/study/sweeps"): _STUDY_READ,
    ("GET", "/api/v1/study/sweeps/{sweep_id}"): _STUDY_READ,
    ("WS", "/ws/simulation/live"): _WS,
    ("WS", "/ws/simulation/dual"): _WS,
    ("WS", "/ws/simulation/comparison"): _WS,
    ("WS", "/ws/v1/stream"): _WS,
}

# Rejected with 403 by their own check rather than by the API-key/user guards; not public.
SELF_PROTECTED = {
    ("GET", "/metrics"): "METRICS_TOKEN or loopback only (src/observability/router.py)",
    ("GET", "/metrics/prom"): "METRICS_TOKEN or loopback only (prom_router.py)",
}

ROUTES: List[RouteInfo] = all_routes()
HTTP_ROUTES = [r for r in ROUTES if r.kind == "http"]
GUARDED = [r for r in HTTP_ROUTES if r.key not in PUBLIC_ROUTES]
PUBLIC_HTTP = [r for r in HTTP_ROUTES if r.key in PUBLIC_ROUTES]
WS_ROUTES = [r for r in ROUTES if r.kind == "websocket"]


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    mp = pytest.MonkeyPatch()
    db_path = str(tmp_path_factory.mktemp("sweep") / "s.db")
    mp.setattr("src.database.db.DB_PATH", db_path)
    mp.setattr(security, "API_KEY", "sweep-test-key")
    mp.delenv("DEV_AUTH_BYPASS", raising=False)
    mp.delenv("METRICS_TOKEN", raising=False)
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        mp.undo()


def _call(client: TestClient, route: RouteInfo) -> int:
    body = None if route.method in ("GET", "DELETE") else {}
    return client.request(route.method, route.concrete_path, json=body).status_code


def test_the_walker_sees_the_whole_app() -> None:
    assert_inventory_sane(ROUTES)
    paths = {r.path for r in ROUTES}
    # Spot checks across nested routers: one per mounted family.
    for expected in (
        "/api/v2/twin/compare",
        "/api/v2/v2x/experiment",
        "/api/v2/jobs/enqueue-dry-run",
        "/api/v2/tenancy/me",
        "/api/v3/tokens",
        "/api/suites",
        "/api/ai/chat",
        "/ws/simulation/live",
    ):
        assert expected in paths, f"{expected} missing from the walked route table"


def test_the_allow_list_is_explicit_and_not_stale() -> None:
    known = {r.key for r in ROUTES}
    stale = sorted(set(PUBLIC_ROUTES) - known)
    assert not stale, f"allow-list entries that match no route (remove them): {stale}"
    assert all(len(reason) >= 15 for reason in PUBLIC_ROUTES.values())
    stale = sorted(set(SELF_PROTECTED) - known)
    assert not stale, f"self-protected entries that match no route: {stale}"


@pytest.mark.parametrize("route", GUARDED, ids=lambda r: r.label)
def test_unauthenticated_request_is_rejected(
    client: TestClient, route: RouteInfo
) -> None:
    status = _call(client, route)
    assert status in REJECTED, (
        f"{route.label} answered {status} to a request with no API key and no token. "
        "Guard it with require_api_key and a user dependency, or add it to PUBLIC_ROUTES "
        "in tests/security/test_route_auth_sweep.py with a reason."
    )


@pytest.mark.parametrize("route", PUBLIC_HTTP, ids=lambda r: r.label)
def test_public_routes_never_fail_with_a_server_error(
    client: TestClient, route: RouteInfo
) -> None:
    assert _call(client, route) < 500, route.label


def test_self_protected_routes_refuse_a_stranger(client: TestClient) -> None:
    for (method, path), _why in SELF_PROTECTED.items():
        # A TestClient peer is not a loopback address, so the 403 is the token/loopback rule.
        assert client.request(method, path).status_code in REJECTED, path


def test_no_public_route_can_mutate_server_state_without_a_key() -> None:
    """Public entries may read or validate; none may create, change or delete."""
    read_only_posts = ("validate", "compile", "compare")
    mutating = [
        r.label
        for r in PUBLIC_HTTP
        if r.method in ("PUT", "PATCH", "DELETE")
        or (r.method == "POST" and not any(w in r.path for w in read_only_posts))
    ]
    assert not mutating, f"public routes that look state-changing: {mutating}"


def test_every_websocket_is_classified() -> None:
    unlisted = [r.label for r in WS_ROUTES if r.key not in PUBLIC_ROUTES]
    assert not unlisted, f"websocket routes not reviewed in PUBLIC_ROUTES: {unlisted}"


@pytest.mark.xfail(
    strict=True,
    reason="S-02: the simulation WebSockets accept any client without an API key or "
    "token; only the Origin header is checked (src/api/origins.py:refuse_foreign_origin)",
)
@pytest.mark.parametrize("route", WS_ROUTES, ids=lambda r: r.label)
def test_websockets_require_credentials(route: RouteInfo) -> None:
    deps = getattr(route.dependant, "dependencies", None) or []
    assert deps, f"{route.label} resolves no auth dependency before accept()"
