"""POST /api/v1/study/multi-seed and its job variant."""

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.study import router as study_router

client = TestClient(app)


@pytest.fixture
def captured(monkeypatch) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []

    def fake(**kwargs: Any) -> Dict[str, Any]:
        calls.append(kwargs)
        return {"numSeeds": kwargs["num_seeds"]}

    monkeypatch.setattr(study_router, "run_multi_seed", fake)
    return calls


def test_defaults_and_pass_through(captured) -> None:
    res = client.post(
        "/api/v1/study/multi-seed",
        json={"geometry": "roundabout", "numSeeds": 3, "seed": 7, "duration": 10},
    )
    assert res.status_code == 200
    call = captured[0]
    assert call["geometry"] == "roundabout"
    assert call["num_seeds"] == 3 and call["base_seed"] == 7
    assert call["duration"] == 10 and call["config"] is None


def test_empty_body_uses_defaults(captured) -> None:
    assert client.post("/api/v1/study/multi-seed").status_code == 200
    assert captured[0]["geometry"] == "signal" and captured[0]["num_seeds"] == 5


@pytest.mark.parametrize(
    "body",
    [
        {"geometry": "bridge"},
        {"numSeeds": 0},
        {"numSeeds": 31},
        {"seed": -1},
        {"seed": 2**31},
        {"duration": 0.5},
        {"duration": 3601},
        {"scenario": {}, "customConfig": {}},
        {"customConfig": {"simulation": {"timeStep": 5}}},
    ],
)
def test_invalid_requests_are_rejected(captured, body) -> None:
    assert client.post("/api/v1/study/multi-seed", json=body).status_code == 422
    assert captured == []


def test_job_variant_returns_202(captured) -> None:
    res = client.post("/api/v1/study/multi-seed/jobs", json={"numSeeds": 2})
    assert res.status_code == 202
    assert "id" in res.json() or "jobId" in res.json()


def test_real_run_end_to_end() -> None:
    res = client.post(
        "/api/v1/study/multi-seed",
        json={"numSeeds": 2, "duration": 4, "seed": 1},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["baseSeed"] == 1 and len(body["seedRuns"]) == 2
    again = client.post(
        "/api/v1/study/multi-seed",
        json={"numSeeds": 2, "duration": 4, "seed": 1},
    ).json()
    assert again == body
