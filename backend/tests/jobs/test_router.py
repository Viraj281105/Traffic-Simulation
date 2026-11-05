"""/api/v2/jobs: queue stats and the enqueue dry run (which never enqueues)."""

from typing import Any, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.jobs import InMemoryJobQueue, QueueError, QueueStats
from src.jobs.router import get_queue, router

from .conftest import make_message


@pytest.fixture
def parts() -> Iterator[tuple[TestClient, InMemoryJobQueue]]:
    queue = InMemoryJobQueue()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_queue] = lambda: queue
    yield TestClient(app), queue


def test_queue_stats(parts: tuple[TestClient, InMemoryJobQueue]) -> None:
    client, queue = parts
    queue.send(make_message())
    body = client.get("/api/v2/jobs/queue-stats").json()
    assert body == {
        "backend": "memory",
        "enqueueEnabled": False,
        "visible": 1,
        "inFlight": 0,
        "deadLetter": 0,
    }


def test_queue_stats_503_when_the_queue_is_down() -> None:
    class Down:
        def stats(self) -> QueueStats:
            raise QueueError("unreachable")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_queue] = lambda: Down()
    response = TestClient(app).get("/api/v2/jobs/queue-stats")
    assert response.status_code == 503


def _payload(**extra: Any) -> dict[str, Any]:
    return {
        "tenant": "acme",
        "run": {"numSeeds": 3, "duration": 10},
        "costTags": {"project": "urbanflow", "env": "staging", "owner": "viraj"},
        **extra,
    }


def test_dry_run_returns_the_message_and_enqueues_nothing(
    parts: tuple[TestClient, InMemoryJobQueue],
) -> None:
    client, queue = parts
    response = client.post("/api/v2/jobs/enqueue-dry-run", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["enqueued"] is False and body["dryRun"] is True
    message = body["message"]
    assert message["tenant"] == "acme"
    assert message["costTags"]["run-id"] == message["runId"]
    assert message["run"]["numSeeds"] == 3
    assert body["messageBytes"] > 0
    assert queue.stats().visible == 0


def test_dry_run_requires_the_mandatory_tags(
    parts: tuple[TestClient, InMemoryJobQueue], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("URBANFLOW_OWNER", raising=False)
    monkeypatch.delenv("URBANFLOW_ENV", raising=False)
    client, _ = parts
    response = client.post(
        "/api/v2/jobs/enqueue-dry-run",
        json={"tenant": "acme", "costTags": {"project": "urbanflow"}},
    )
    assert response.status_code == 422
    assert "owner" in response.json()["detail"]


def test_dry_run_rejects_an_invalid_spec(
    parts: tuple[TestClient, InMemoryJobQueue],
) -> None:
    client, _ = parts
    response = client.post(
        "/api/v2/jobs/enqueue-dry-run", json=_payload(run={"numSeeds": 0})
    )
    assert response.status_code == 422
