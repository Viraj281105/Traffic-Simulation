"""Fixtures for the ``/api/v3`` experiment tests.

The router is mounted on a small app of its own with a header-based user, so ownership between two users
can be tested (the main app's fixture signs in one fixed user). A fake executor stands in for the
simulation, so these tests exercise the API, quotas and persistence rather than the engine; the engine path
is covered by tests/uncertainty/test_runner.py and one end-to-end test here."""

import copy
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from src.experiments.router import create_router
from src.experiments.service import ExperimentService, ExperimentStore

SCENARIO: Dict[str, Any] = {
    "format": "urbanflow-scenario",
    "version": 1,
    "name": "API test junction",
    "junction": {"type": "fixed_time_signal"},
    "approaches": {
        d: {
            "lanes": 1,
            "vehiclesPerHour": 300,
            "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
        }
        for d in ("north", "south", "east", "west")
    },
    "simulation": {"duration": 60, "warmup": 5, "seed": 3},
}


def experiment(**over: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "format": "urbanflow-experiment",
        "version": 1,
        "name": "API test experiment",
        "scenario": copy.deepcopy(SCENARIO),
        "alternatives": [
            {"id": "fixed", "strategy": "fixed_time"},
            {"id": "adaptive", "strategy": "adaptive"},
        ],
        "uncertainty": {
            "conditions": 10,
            "replications": 2,
            "seed": 5,
            "factors": [
                {
                    "id": "demand",
                    "kind": "demand_scale",
                    "distribution": {"kind": "uniform"},
                    "bounds": [0.8, 1.2],
                    "basis": "assumed",
                    "rationale": "plausible weekday variation",
                }
            ],
        },
    }
    body.update(over)
    return body


class FakeExecutor:
    """Canned metrics; optionally blocks until released so a job can be held in the running state."""

    def __init__(self, block: Optional[threading.Event] = None, raises: bool = False):
        self.block = block
        self.raises = raises
        self.calls = 0

    def __call__(self, tasks: List[Any], progress: Any = None) -> List[Any]:
        self.calls += 1
        if self.block is not None:
            assert self.block.wait(timeout=30), "test never released the executor"
        if self.raises:
            raise RuntimeError("worker pool exploded")
        out = []
        for task in tasks:
            strategy = task.config["scenario"]["strategy"]
            delay = 40.0 + 100.0 * task.config["traffic"]["arrivalRate"]
            out.append(
                {
                    "metrics": {
                        "averageDelay": delay
                        - (5.0 if strategy == "adaptive" else 0.0),
                        "vehicleLimitReached": False,
                    }
                }
            )
        return out


def build_client(service: ExperimentService) -> TestClient:
    app = FastAPI()

    def user(x_user: Optional[str] = Header(default=None)) -> str:
        if not x_user:
            raise HTTPException(status_code=401, detail="no user")
        return x_user

    app.include_router(create_router(user_dependency=user, service=service))
    return TestClient(app)


@pytest.fixture
def make_service(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., ExperimentService]:
    monkeypatch.setattr("src.database.db.DB_PATH", str(tmp_path / "experiments.db"))

    def make(executor: Any = None, persist: bool = False) -> ExperimentService:
        return ExperimentService(
            store=ExperimentStore(persist=persist), executor=executor or FakeExecutor()
        )

    return make


@pytest.fixture
def client(make_service: Callable[..., ExperimentService]) -> Iterator[TestClient]:
    yield build_client(make_service())


def as_user(name: str) -> Dict[str, str]:
    return {"X-User": name}


def wait_for(
    client: TestClient, experiment_id: str, user: str = "alice", timeout: float = 30.0
) -> Dict[str, Any]:
    """Poll the status until the experiment is no longer queued or running."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get(
            f"/api/v3/experiments/{experiment_id}", headers=as_user(user)
        ).json()
        if status["status"] not in ("queued", "running"):
            return status
        time.sleep(0.02)
    raise AssertionError("experiment did not finish in time")


def submit(client: TestClient, user: str = "alice", **over: Any) -> Dict[str, Any]:
    response = client.post(
        "/api/v3/experiments", json=experiment(**over), headers=as_user(user)
    )
    assert response.status_code == 202, response.text
    return response.json()
