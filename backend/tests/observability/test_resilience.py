"""The app with failing dependencies: it must fail cleanly and recover (package 1D)."""

from __future__ import annotations

import sqlite3
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, signed_in_user: str
) -> Iterator[TestClient]:
    monkeypatch.setenv("METRICS_TOKEN", "tok")
    # Server errors become 500 responses (as in production) instead of test failures.
    yield TestClient(app, raise_server_exceptions=False)


def _db_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr("src.database.db.sqlite3.connect", refuse)


def _count_5xx(client: TestClient) -> float:
    text = client.get("/metrics", headers={"Authorization": "Bearer tok"}).text
    total = 0.0
    for line in text.splitlines():
        if line.startswith("urbanflow_http_requests_total{") and 'status="5xx"' in line:
            total += float(line.rsplit(" ", 1)[1])
    return total


def test_health_and_compute_survive_database_outage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _db_down(monkeypatch)
    assert client.get("/health").json() == {"status": "healthy"}
    grid = client.get("/api/v2/network-metrics/grid?rows=2&cols=2")
    assert grid.status_code == 200  # pure computation needs no database


def test_database_routes_fail_with_500_not_a_hang_and_are_counted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _count_5xx(client)
    _db_down(monkeypatch)
    res = client.get("/api/v1/study/history/runs")
    assert res.status_code >= 500
    assert "Traceback" not in res.text  # no stack trace leaks to the client
    assert _count_5xx(client) == before + 1


def test_service_recovers_when_database_returns(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as m:
        _db_down(m)
        assert client.get("/api/v1/study/history/runs").status_code >= 500
    # Dependency back (the patch is undone): the same route answers again.
    assert client.get("/api/v1/study/history/runs").status_code < 500
    assert client.get("/health").status_code == 200


def test_metrics_endpoint_still_scrapes_during_outage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _db_down(monkeypatch)
    res = client.get("/metrics", headers={"Authorization": "Bearer tok"})
    assert res.status_code == 200
