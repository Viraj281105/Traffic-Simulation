"""Background study jobs: POST starts one, GET reports progress and result."""

import time
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.study import jobs as jobs_module

client = TestClient(app)


def _wait(job_id: str, timeout: float = 60.0) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        res = client.get(f"/api/v1/study/jobs/{job_id}")
        assert res.status_code == 200
        body: Dict[str, Any] = res.json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


@pytest.fixture
def study_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.database import db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))


def test_sweep_job_reports_progress_and_returns_the_sweep(study_db: None) -> None:
    res = client.post(
        "/api/v1/study/sweeps/jobs",
        json={"arrivalRates": [0.2, 0.4], "duration": 5.0, "randomSeed": 3},
    )
    assert res.status_code == 202
    started = res.json()
    assert started["kind"] == "sweep"
    assert started["status"] in ("queued", "running", "completed")

    done = _wait(started["jobId"])
    assert done["status"] == "completed", done["error"]
    progress = done["progress"]
    assert progress["total"] == 4  # 2 tiers x 2 geometries
    assert progress["completed"] == 4
    assert progress["phase"] == "done"
    assert len(done["result"]["runs"]) == 2

    # Persisted exactly like a synchronous sweep.
    stored = client.get(f"/api/v1/study/sweeps/{done['result']['sessionId']}")
    assert stored.status_code == 200


def test_monte_carlo_job_returns_the_study(study_db: None) -> None:
    res = client.post(
        "/api/v1/study/validate/monte-carlo/jobs",
        json={"numSeeds": 2, "duration": 3.0},
    )
    assert res.status_code == 202
    done = _wait(res.json()["jobId"])
    assert done["status"] == "completed", done["error"]
    assert done["progress"]["total"] == 4  # 2 seeds x 2 geometries
    assert done["result"]["numSeeds"] == 2
    assert len(done["result"]["seedRuns"]) == 2


def test_job_request_is_validated_before_starting() -> None:
    res = client.post("/api/v1/study/sweeps/jobs", json={"duration": 0})
    assert res.status_code == 422


def test_failed_study_is_reported_not_lost(
    study_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src import main

    def broken(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(main, "run_volume_sweep_experiment", broken)
    res = client.post("/api/v1/study/sweeps/jobs", json={"duration": 5.0})
    done = _wait(res.json()["jobId"])
    assert done["status"] == "failed"
    assert done["error"] == "engine exploded"
    assert done["result"] is None


def test_unknown_job_is_404() -> None:
    assert client.get("/api/v1/study/jobs/nope").status_code == 404


def test_active_jobs_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs_module, "MAX_ACTIVE_JOBS", 0)
    res = client.post("/api/v1/study/sweeps/jobs", json={"duration": 5.0})
    assert res.status_code == 429


def test_finished_jobs_are_evicted(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = jobs_module.JobRegistry()
    job = registry.submit("sweep", lambda progress: {"ok": True})
    deadline = time.monotonic() + 5
    while job.finished_at is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert registry.get(job.id) is job

    monkeypatch.setattr(jobs_module, "FINISHED_JOB_TTL_SECONDS", -1.0)
    registry.submit("sweep", lambda progress: {"ok": True})
    assert registry.get(job.id) is None
