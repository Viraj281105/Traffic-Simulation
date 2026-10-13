"""Scenario-suite batch experiments, end to end through the API (V1.7).

The dashboard's batch button posts its flat scenario payload as
``baseConfig``. The batch runner used to receive that payload uncompiled and
index ``config["traffic"]``, so every batch it started failed inside the
background job while the POST had already answered 200 with a job id.
"""

import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import src.main as main
from src.auth import DEV_AUTH_TOKEN
from src.main import MAX_BATCH_SIMULATIONS, app

# Suites belong to signed-in users; the development bypass token stands in
# for a Cognito session (see test_dev_auth_bypass.py).
client = TestClient(app, headers={"Authorization": f"Bearer {DEV_AUTH_TOKEN}"})


@pytest.fixture(autouse=True)
def suite_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.database import db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "suites.db"))
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    monkeypatch.delenv("API_KEY", raising=False)
    db.init_db()


def _dashboard_payload(**overrides: Any) -> Dict[str, Any]:
    """The body App.tsx sends as baseConfig (dashboardPayload())."""
    payload: Dict[str, Any] = {
        "intersectionType": "fixed_time_signal",
        "intersectionSize": 11.0,
        "laneWidth": 3.5,
        "lanesNorth": 1,
        "lanesSouth": 1,
        "lanesEast": 1,
        "lanesWest": 1,
        "arrivalRate": 0.3,
        "duration": 4,
        "randomSeed": 7,
        "greenDuration": 30,
        "yellowDuration": 4,
        "allRedDuration": 2,
        "criticalGap": 4,
        "followUpTime": 2.5,
        "unstructuredTraffic": False,
        "aggressiveTwoWheelers": False,
    }
    payload.update(overrides)
    return payload


def _new_suite() -> str:
    res = client.post(
        "/api/suites",
        json={
            "name": "Batch",
            "description": "",
            "run_ids": [],
            "config_variations": {"arrivalRate": [0.2, 0.4]},
        },
    )
    assert res.status_code == 200
    suite_id: str = res.json()["id"]
    return suite_id


def _wait(job_id: str, timeout: float = 60.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body: Dict[str, Any] = client.get(f"/api/v1/study/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def test_dashboard_batch_runs_and_attaches_every_run_to_the_suite() -> None:
    suite_id = _new_suite()
    res = client.post(
        f"/api/suites/{suite_id}/batch",
        json={
            "baseConfig": _dashboard_payload(),
            "sweepParameters": {"arrivalRate": [0.2, 0.4]},
            "numSeeds": 2,
        },
    )
    assert res.status_code == 200
    done = _wait(res.json()["jobId"])
    assert done["status"] == "completed", done.get("error")

    suite = client.get(f"/api/suites/{suite_id}").json()
    runs = suite["runs"]
    assert len(runs) == 4  # 2 rates x 2 seeds
    assert sorted((r["arrival_rate"], r["random_seed"]) for r in runs) == [
        (0.2, 42),
        (0.2, 43),
        (0.4, 42),
        (0.4, 43),
    ]
    for run in runs:
        assert run["intersection_type"] == "fixed_time_signal"
        assert run["batch_id"] == suite_id
        # Stored with provenance, like every other study run.
        assert run["provenance"]["timing"]["timeStep"] == 0.1
        assert run["provenance"]["timing"]["duration"] == 4


def test_batch_for_an_unknown_suite_is_404_before_anything_runs() -> None:
    res = client.post(
        "/api/suites/no-such-suite/batch",
        json={
            "baseConfig": _dashboard_payload(),
            "sweepParameters": {"arrivalRate": [0.2]},
            "numSeeds": 1,
        },
    )
    assert res.status_code == 404


def test_invalid_base_config_is_rejected_up_front() -> None:
    suite_id = _new_suite()
    res = client.post(
        f"/api/suites/{suite_id}/batch",
        json={
            "baseConfig": _dashboard_payload(duration=0),
            "sweepParameters": {"arrivalRate": [0.2]},
            "numSeeds": 1,
        },
    )
    assert res.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"sweepParameters": {"arrivalRate": [0.2]}, "numSeeds": 0},
        {"sweepParameters": {"arrivalRate": [0.2]}, "numSeeds": 31},
        {"sweepParameters": {"arrivalRate": []}, "numSeeds": 1},
        {"sweepParameters": {"arrivalRate": [0]}, "numSeeds": 1},
        {"sweepParameters": {"laneWidth": [3.0]}, "numSeeds": 1},
        {"sweepParameters": {}, "numSeeds": 1},
        {
            "sweepParameters": {"arrivalRate": [0.1, 0.2, 0.3]},
            "numSeeds": MAX_BATCH_SIMULATIONS // 3 + 1,
        },
    ],
)
def test_batch_workload_outside_bounds_is_rejected(body: Dict[str, Any]) -> None:
    res = client.post(
        "/api/suites/any/batch", json={"baseConfig": _dashboard_payload(), **body}
    )
    assert res.status_code == 422


def test_suite_writes_require_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "API_KEY", "secret-key")
    create = client.post(
        "/api/suites",
        json={"name": "x", "description": "", "run_ids": [], "config_variations": {}},
    )
    assert create.status_code == 401
    batch = client.post(
        "/api/suites/any/batch",
        json={
            "baseConfig": _dashboard_payload(),
            "sweepParameters": {"arrivalRate": [0.2]},
            "numSeeds": 1,
        },
    )
    assert batch.status_code == 401


def _engine_config(**simulation: Any) -> Dict[str, Any]:
    return {
        "simulation": {"timeStep": 0.1, "duration": 3, "warmupTime": 0.0, **simulation},
        "geometry": {"intersectionType": "roundabout"},
        "traffic": {"arrivalRate": 0.3},
    }


def test_engine_config_batch_runs_its_own_geometry() -> None:
    suite_id = _new_suite()
    res = client.post(
        f"/api/suites/{suite_id}/batch",
        json={
            "baseConfig": _engine_config(),
            "sweepParameters": {"arrivalRate": [0.25]},
            "numSeeds": 1,
        },
    )
    assert res.status_code == 200
    done = _wait(res.json()["jobId"])
    assert done["status"] == "completed", done.get("error")
    (run,) = client.get(f"/api/suites/{suite_id}").json()["runs"]
    assert run["intersection_type"] == "roundabout"
    assert (run["arrival_rate"], run["random_seed"]) == (0.25, 42)


@pytest.mark.parametrize(
    "base_config",
    [
        # Fails the schema.
        {**_engine_config(), "geometry": {"intersectionType": "tunnel"}},
        # Passes the schema, fails a cross-field rule (warm-up >= duration).
        _engine_config(warmupTime=5.0),
    ],
)
def test_invalid_engine_config_is_rejected_up_front(
    base_config: Dict[str, Any],
) -> None:
    suite_id = _new_suite()
    res = client.post(
        f"/api/suites/{suite_id}/batch",
        json={
            "baseConfig": base_config,
            "sweepParameters": {"arrivalRate": [0.2]},
            "numSeeds": 1,
        },
    )
    assert res.status_code == 400
