"""The /api/v2/priority endpoints: shapes, bounds and errors. Runs are kept
short (light traffic, 120 s, two seeds) so the file stays fast; the statistical
claims live in test_emergency_runs.py."""

from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.priority.router import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

QUICK_SCENARIO: Dict[str, Any] = {
    "durationSeconds": 120,
    "arrivalRate": 0.3,
    "lanesPerApproach": 1,
}


@pytest.fixture(scope="module")
def emergency_body() -> Dict[str, Any]:
    return {
        "scenario": QUICK_SCENARIO,
        "emergencyVehicles": [
            {
                "kind": "ambulance",
                "approach": "east",
                "turn": "straight",
                "timeSeconds": 10,
            }
        ],
        "numSeeds": 2,
        "baseSeed": 3,
    }


@pytest.fixture(scope="module")
def emergency_response(emergency_body: Dict[str, Any]) -> Dict[str, Any]:
    response = client.post("/api/v2/priority/emergency-comparison", json=emergency_body)
    assert response.status_code == 200, response.text
    body: Dict[str, Any] = response.json()
    return body


def test_catalogue_lists_kinds_defaults_and_limits() -> None:
    response = client.get("/api/v2/priority/catalogue")
    assert response.status_code == 200
    body = response.json()
    assert body["inModelOnly"] is True
    assert {k["id"] for k in body["emergencyKinds"]} == {"ambulance", "fire_truck"}
    assert all(k["priority"] for k in body["emergencyKinds"])
    assert body["limits"]["seeds"] == [2, 20]
    assert body["defaults"]["preemption"]["minGreenSeconds"] == 7.0
    assert "paired_t" in body["methods"]


def test_emergency_comparison_shape(emergency_response: Dict[str, Any]) -> None:
    body = emergency_response
    assert body["kind"] == "emergency-comparison"
    assert body["inModelOnly"] is True and "In-model only" in body["label"]
    assert body["seeds"] == [3, 4]
    for arm in ("withPreemption", "baseline"):
        per_seed = body["perSeed"][arm]
        assert set(per_seed) == {"travelTime", "delay", "waitTime", "collateralDelay"}
        assert all(len(values) == 2 for values in per_seed.values())
        assert body["safety"][arm]["vehiclesConserved"] is True
    travel = body["comparison"]["emergencyTravelTime"]
    assert travel["method"] == "paired_t" and travel["n_pairs"] == 2
    assert {"ci_lower", "ci_upper", "p_value", "verdict", "difference"} <= set(travel)
    assert "collateralDelay" in body["comparison"]
    assert body["safety"]["withPreemption"]["signalAuditOk"] is True


def test_emergency_comparison_is_deterministic(
    emergency_body: Dict[str, Any], emergency_response: Dict[str, Any]
) -> None:
    again = client.post("/api/v2/priority/emergency-comparison", json=emergency_body)
    assert again.status_code == 200
    assert again.json() == emergency_response


def test_transit_comparison_shape() -> None:
    response = client.post(
        "/api/v2/priority/transit-comparison",
        json={
            "scenario": QUICK_SCENARIO,
            "lines": [
                {
                    "lineId": "L7",
                    "approach": "north",
                    "turn": "straight",
                    "headwaySeconds": 40,
                    "firstDepartureSeconds": 0,
                    "trips": 2,
                    "dwellSeconds": 5,
                }
            ],
            "numSeeds": 2,
            "method": "paired_bootstrap",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "transit-comparison" and body["inModelOnly"] is True
    assert set(body["perSeed"]) == {"withPriority", "baseline"}
    assert {"busScheduleLateness", "personDelayPerPerson", "vehicleDelay"} <= set(
        body["perSeed"]["baseline"]
    )
    assert body["comparison"]["personDelayPerPerson"]["method"] == "paired_bootstrap"
    assert body["safety"]["withPriority"]["signalAuditOk"] is True


@pytest.mark.parametrize(
    "patch",
    [
        {"numSeeds": 1},
        {"numSeeds": 21},
        {"scenario": {"durationSeconds": 5000}},
        {"scenario": {"durationSeconds": 10}},
        {"scenario": {"arrivalRate": 50}},
        {"scenario": {"lanesPerApproach": 9}},
        {"method": "ouija"},
        {"emergencyVehicles": []},
        {"emergencyVehicles": [{"kind": "tank"}]},
        {"emergencyVehicles": [{"approach": "up"}]},
        {"preemption": {"minGreenSeconds": 0}},
        {"preemption": {"detectionDistance": 5}},
        {"yielding": {"headwayFactor": 0}},
    ],
)
def test_inputs_are_bounded_by_validation(patch: Dict[str, Any]) -> None:
    body = {"scenario": QUICK_SCENARIO, "numSeeds": 2}
    body.update(patch)
    response = client.post("/api/v2/priority/emergency-comparison", json=body)
    assert response.status_code == 422


def test_seed_times_duration_budget_is_enforced() -> None:
    response = client.post(
        "/api/v2/priority/emergency-comparison",
        json={"scenario": {"durationSeconds": 900}, "numSeeds": 20},
    )
    assert response.status_code == 422
    assert "must not exceed" in str(response.json()["detail"])


def test_emergency_after_the_end_of_the_run_is_rejected() -> None:
    response = client.post(
        "/api/v2/priority/emergency-comparison",
        json={
            "scenario": QUICK_SCENARIO,
            "emergencyVehicles": [{"timeSeconds": 110}],
            "numSeeds": 2,
        },
    )
    assert response.status_code == 422


def test_transit_inputs_are_bounded() -> None:
    for line in (
        {"headwaySeconds": 1},
        {"trips": 500},
        {"dwellSeconds": 600},
        {"approach": "up"},
    ):
        response = client.post(
            "/api/v2/priority/transit-comparison",
            json={"scenario": QUICK_SCENARIO, "lines": [line], "numSeeds": 2},
        )
        assert response.status_code == 422
    too_many = client.post(
        "/api/v2/priority/transit-comparison",
        json={"scenario": QUICK_SCENARIO, "lines": [{}] * 9, "numSeeds": 2},
    )
    assert too_many.status_code == 422
