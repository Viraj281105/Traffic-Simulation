"""Workload bounds on the study endpoints.

These endpoints run whole simulations synchronously inside the request, and
their cost is the product of their parameters. Unbounded, a single request
could pin a worker for hours — a denial of service needing no exploit. The
caps sit well above every documented workflow, so these tests pin both halves
of that: abusive requests are rejected, legitimate ones still run.
"""

from typing import Any, Dict

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
