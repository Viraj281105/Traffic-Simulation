"""Bounds on how much simulation one request may cause.

* ``compute_slot`` (src/request_limits.py): at most
  MAX_SYNC_COMPUTE_REQUESTS synchronous simulations at once, and at most
  MAX_SYNC_COMPUTE_PER_CLIENT per client; the next request is refused with 429
  at once instead of holding a worker thread;
* the step ceiling (src/core/limits.py MAX_SIMULATION_TICKS): duration divided
  by the time step, checked by the shared validator and by the engine itself,
  because the schema accepts any positive time step.
"""

import threading
from typing import Any, List

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import src.request_limits as limits
from src.core.clock import Clock
from src.core.config_validation import semantic_config_errors
from src.core.engine import SimulationEngine
from src.core.limits import MAX_SIMULATION_TICKS
from src.main import app

SYNC_ROUTES = [
    ("/api/v1/study/sweeps/run", {"arrivalRates": [0.2], "duration": 2.0}),
    ("/api/v1/study/validate/repeatability", {"duration": 2.0}),
    ("/api/v1/study/validate/monte-carlo", {"numSeeds": 2, "duration": 2.0}),
    ("/api/v1/study/control-comparison/run", {"duration": 2.0}),
    ("/api/v1/study/history/runs/anything/reproduce", None),
    ("/api/v2/calibration/runs", {}),
    ("/api/v2/planning/run", {}),
    ("/api/v2/planning/anything/reproduce", None),
]


def _request(ip: str, forwarded: bool = True) -> Request:
    headers = [(b"x-real-ip", ip.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (ip, 1234)})


def _slot(ip: str = "198.51.100.1") -> Any:
    return limits.compute_slot(_request(ip))


def _hold_all_slots() -> List[Any]:
    """Every slot, each held by a different client (none is the test client)."""
    held = []
    for i in range(limits.MAX_SYNC_COMPUTE_REQUESTS):
        gen = _slot(f"203.0.113.{i + 1}")
        next(gen)
        held.append(gen)
    return held


def _release(held: List[Any]) -> None:
    for gen in held:
        with pytest.raises(StopIteration):
            next(gen)


def test_slots_are_bounded_and_released() -> None:
    held = _hold_all_slots()
    try:
        with pytest.raises(HTTPException) as err:
            next(_slot("198.51.100.99"))
        assert err.value.status_code == 429
    finally:
        _release(held)
    # Released, including after an exception inside the request.
    gen = _slot()
    next(gen)
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("request failed"))
    held = _hold_all_slots()
    _release(held)


def test_slots_are_safe_across_threads() -> None:
    acquired: List[bool] = []
    barrier = threading.Barrier(8)

    def worker(i: int) -> None:
        barrier.wait()
        gen = _slot(f"192.0.2.{i}")
        try:
            next(gen)
        except HTTPException:
            acquired.append(False)
            return
        acquired.append(True)
        barrier_done.wait()
        with pytest.raises(StopIteration):
            next(gen)

    barrier_done = threading.Event()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    # Wait until every thread has either got a slot or been refused.
    while len(acquired) < 8:
        threading.Event().wait(0.01)
    barrier_done.set()
    for t in threads:
        t.join(timeout=10)
    assert acquired.count(True) == limits.MAX_SYNC_COMPUTE_REQUESTS


@pytest.mark.parametrize("path,body", SYNC_ROUTES)
def test_every_synchronous_simulation_route_is_gated(
    path: str, body: Any, signed_in_user: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    held = _hold_all_slots()
    try:
        res = TestClient(app).post(path, json=body)
        if path == SYNC_ROUTES[0][0]:
            # The report route runs a sweep and a Monte Carlo study on a GET.
            report = TestClient(app).get("/api/v1/study/export")
            assert report.status_code == 429, report.text[:200]
    finally:
        _release(held)
    assert res.status_code == 429, (path, res.status_code, res.text[:200])
    assert res.json()["error"]["code"] == "SIMULATION_LIMIT_REACHED"


def test_step_ceiling_in_the_validator() -> None:
    ok = {"simulation": {"duration": 3600, "timeStep": 0.05}}
    assert semantic_config_errors(ok) == []
    too_fine = {"simulation": {"duration": 3600, "timeStep": 0.001}}
    (message,) = semantic_config_errors(too_fine)
    assert "3,600,000 steps" in message and f"{MAX_SIMULATION_TICKS:,}" in message


def test_scenario_endpoints_reject_a_tiny_time_step() -> None:
    from tests.api.test_scenarios_api import SCENARIO

    client = TestClient(app)
    scenario = {
        **SCENARIO,
        "simulation": {"duration": 3600, "warmup": 10, "seed": 1, "timeStep": 1e-4},
    }
    body = client.post("/api/v1/scenarios/validate", json={"scenario": scenario}).json()
    assert body["valid"] is False
    assert any("steps" in e for e in body["errors"]), body["errors"]

    fine = {**scenario, "simulation": {**scenario["simulation"], "timeStep": 0.1}}
    body = client.post("/api/v1/scenarios/validate", json={"scenario": fine}).json()
    assert body["valid"], body["errors"]


def test_step_ceiling_in_the_engine() -> None:
    SimulationEngine(Clock(0.05), duration=3600.0)  # the documented maximum
    with pytest.raises(ValueError):
        SimulationEngine(Clock(1e-6), duration=10.0)


def test_one_client_cannot_take_every_slot() -> None:
    first = _slot("198.51.100.7")
    next(first)
    try:
        with pytest.raises(HTTPException) as err:
            next(_slot("198.51.100.7"))
        assert err.value.status_code == 429
        assert "you started" in str(err.value.detail)
        other = _slot("198.51.100.8")  # another client still gets the free slot
        next(other)
        with pytest.raises(StopIteration):
            next(other)
    finally:
        with pytest.raises(StopIteration):
            next(first)
    again = _slot("198.51.100.7")  # released: the same client may start again
    next(again)
    with pytest.raises(StopIteration):
        next(again)
    assert limits._running_per_client == {}


def test_the_client_is_nginxs_x_real_ip_else_the_peer() -> None:
    assert limits.client_key(_request("203.0.113.9")) == "203.0.113.9"
    assert limits.client_key(_request("203.0.113.9", forwarded=False)) == "203.0.113.9"
