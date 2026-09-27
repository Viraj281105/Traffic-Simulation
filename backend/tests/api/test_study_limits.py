"""Workload bounds on the study endpoints.

These endpoints run whole simulations synchronously inside the request, and
their cost is the product of their parameters. Unbounded, a single request
could pin a worker for hours — a denial of service needing no exploit. The
caps sit well above every documented workflow, so these tests pin both halves
of that: abusive requests are rejected, legitimate ones still run.
"""

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.main import (
    MAX_MONTE_CARLO_SEEDS,
    MAX_STUDY_DURATION_SECONDS,
    MAX_SWEEP_ARRIVAL_RATES,
    app,
)

client = TestClient(app)


def _error_code(payload: Dict[str, Any]) -> Any:
    return payload.get("error", {}).get("code")


# ── Volume sweep ──────────────────────────────────────────────────────────


def test_sweep_rejects_duration_above_cap() -> None:
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={"duration": MAX_STUDY_DURATION_SECONDS + 1, "arrivalRates": [0.3]},
    )
    assert response.status_code == 422


def test_sweep_rejects_too_many_arrival_rates() -> None:
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={
            "duration": 5,
            "arrivalRates": [0.3] * (MAX_SWEEP_ARRIVAL_RATES + 1),
        },
    )
    assert response.status_code == 422


def test_sweep_rejects_out_of_range_arrival_rate() -> None:
    """A rate the scenario config itself would reject must not sneak in here."""
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={"duration": 5, "arrivalRates": [0.3, 999.0]},
    )
    assert response.status_code == 422


def test_sweep_rejects_non_positive_arrival_rate() -> None:
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={"duration": 5, "arrivalRates": [0.0]},
    )
    assert response.status_code == 422


def test_sweep_rejects_zero_duration() -> None:
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={"duration": 0, "arrivalRates": [0.3]},
    )
    assert response.status_code == 422


def test_sweep_accepts_a_legitimate_request() -> None:
    """The cap must not break real use: a small sweep still runs."""
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={"duration": 5, "arrivalRates": [0.2, 0.4], "randomSeed": 7},
    )
    assert response.status_code == 200
    assert "sessionId" in response.json() or "runs" in response.json()


def test_sweep_accepts_the_maximum_allowed_rate_count() -> None:
    """The boundary itself is legitimate, not rejected off-by-one."""
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={
            "duration": 2,
            "arrivalRates": [0.1] * MAX_SWEEP_ARRIVAL_RATES,
            "randomSeed": 3,
        },
    )
    assert response.status_code == 200


# ── Monte Carlo validation ────────────────────────────────────────────────


def test_monte_carlo_rejects_too_many_seeds() -> None:
    response = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"numSeeds": MAX_MONTE_CARLO_SEEDS + 1, "duration": 5},
    )
    assert response.status_code == 422


def test_monte_carlo_rejects_zero_seeds() -> None:
    response = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"numSeeds": 0, "duration": 5},
    )
    assert response.status_code == 422


def test_monte_carlo_rejects_duration_above_cap() -> None:
    response = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"numSeeds": 2, "duration": MAX_STUDY_DURATION_SECONDS + 1},
    )
    assert response.status_code == 422


def test_monte_carlo_accepts_a_legitimate_request() -> None:
    response = client.post(
        "/api/v1/study/validate/monte-carlo",
        json={"numSeeds": 2, "duration": 5},
    )
    assert response.status_code == 200


# ── Repeatability validation ──────────────────────────────────────────────


def test_repeatability_rejects_duration_above_cap() -> None:
    response = client.post(
        "/api/v1/study/validate/repeatability",
        json={"duration": MAX_STUDY_DURATION_SECONDS + 1, "randomSeed": 5},
    )
    assert response.status_code == 422


def test_repeatability_accepts_a_legitimate_request() -> None:
    response = client.post(
        "/api/v1/study/validate/repeatability",
        json={"duration": 5, "randomSeed": 5},
    )
    assert response.status_code == 200


def test_defaults_still_work_with_no_payload() -> None:
    """Every study endpoint keeps its documented no-body default behaviour."""
    response = client.post("/api/v1/study/validate/repeatability")
    assert response.status_code == 200


def test_sweep_honours_custom_time_step() -> None:
    """Regression: the orchestrator hard-coded a 0.1 s clock, so the
    dashboards' Δt choice was silently ignored (recorded timeStep 0.1)."""
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={
            "duration": 4,
            "arrivalRates": [0.3],
            "customConfig": {"simulation": {"timeStep": 0.2}},
        },
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["runs"][0]["signal"]["runId"]
    record = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert record["timing"]["timeStep"] == 0.2
    assert record["timing"]["elapsed"] == pytest.approx(4.0)


def test_sweep_custom_duration_mismatch_is_not_a_500() -> None:
    """Regression: customConfig.simulation.duration shorter than the request's
    duration completed the engine mid-loop and the next step raised (500)."""
    response = client.post(
        "/api/v1/study/sweeps/run",
        json={
            "duration": 6,
            "arrivalRates": [0.3],
            "customConfig": {"simulation": {"duration": 3}},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["runs"][0]["signal"]["metrics"] is not None


@pytest.mark.parametrize("step", [0.001, 0.0, -0.1, 5.0, "fast"])
def test_study_time_step_is_bounded(step: object) -> None:
    for route, body in (
        ("/api/v1/study/sweeps/run", {"duration": 5, "arrivalRates": [0.3]}),
        ("/api/v1/study/validate/monte-carlo", {"numSeeds": 2, "duration": 5}),
    ):
        response = client.post(
            route, json={**body, "customConfig": {"simulation": {"timeStep": step}}}
        )
        assert response.status_code == 422, (route, step, response.text)


@pytest.mark.parametrize(
    "path",
    ["/api/v1/study/history/runs", "/api/v1/study/sweeps", "/api/v1/replays"],
)
@pytest.mark.parametrize("query", ["limit=-1", "limit=0", "limit=100000", "offset=-5"])
def test_listing_pagination_is_bounded(path: str, query: str) -> None:
    """Regression: limit went straight into SQL LIMIT, where SQLite treats a
    negative value as "no limit", so ?limit=-1 dumped the whole table."""
    response = client.get(f"{path}?{query}")
    assert response.status_code == 422, (path, query, response.status_code)
