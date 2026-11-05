"""Input bounds on the stateless /api/v2 compute endpoints (package 2F).

Each request is made as a signed-in test user (the ``signed_in_user`` dependency override used by
the other API tests) with oversized or out-of-range input. Expected: 413 or 422, never 500, and
an answer within a time budget, so a bound that is missing shows up as a slow request or a 200
instead of a silent pass. Valid-auth requests with in-range input are NOT sent: they would run
simulations.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

import pytest
from fastapi.testclient import TestClient

from src.api.request_limits import MAX_V2_BODY_BYTES
from src.main import app

TIME_BUDGET_SECONDS = 5.0
REFUSED = (413, 422)

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def signed_in(signed_in_user: str) -> None:
    pass


def _post(path: str, body: Any) -> Tuple[int, float]:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    start = time.monotonic()
    res = client.post(path, content=raw, headers={"Content-Type": "application/json"})
    return res.status_code, time.monotonic() - start


GRAPH_OK: Dict[str, Any] = {"nodes": [], "links": []}

# (id, path, body): each body breaks exactly one documented bound.
OUT_OF_RANGE: List[Tuple[str, str, Dict[str, Any]]] = [
    ("netmetrics-duration", "/api/v2/network-metrics/simulate", {"duration": 1e9}),
    ("netmetrics-duration-zero", "/api/v2/network-metrics/simulate", {"duration": 0}),
    ("netmetrics-bucket", "/api/v2/network-metrics/simulate", {"bucketSeconds": 0}),
    ("netmetrics-latitude", "/api/v2/network-metrics/simulate", {"originLat": 999}),
    (
        "netmetrics-grid",
        "/api/v2/network-metrics/simulate",
        {"grid": {"rows": 10_000, "cols": 10_000}},
    ),
    (
        "netmetrics-flow",
        "/api/v2/network-metrics/simulate",
        {"flows": [{"origin": "a", "destination": "b", "vehiclesPerHour": 1e9}]},
    ),
    ("netmetrics-threshold", "/api/v2/network-metrics/congestion", {"threshold": 50}),
    (
        "calibration-no-flows",
        "/api/v2/calibration/network-fit",
        {"graph": GRAPH_OK, "flows": [], "countsCsv": "a"},
    ),
    (
        "calibration-budget",
        "/api/v2/calibration/network-fit",
        {
            "graph": GRAPH_OK,
            "flows": [{"origin": "a", "destination": "b", "vehiclesPerHour": 1}],
            "countsCsv": "a",
            "options": {"budget": 10**9},
        },
    ),
    (
        "calibration-duration",
        "/api/v2/calibration/network-fit",
        {
            "graph": GRAPH_OK,
            "flows": [{"origin": "a", "destination": "b", "vehiclesPerHour": 1}],
            "countsCsv": "a",
            "sim": {"duration": 1e9},
        },
    ),
    (
        "calibration-csv-too-long",
        "/api/v2/calibration/network-fit/validate-counts",
        {"graph": GRAPH_OK, "countsCsv": "x" * 8_000_001},
    ),
    (
        "calibration-too-many-flows",
        "/api/v2/calibration/network-fit",
        {
            "graph": GRAPH_OK,
            "flows": [{"origin": "a", "destination": "b", "vehiclesPerHour": 1}] * 500,
            "countsCsv": "a",
        },
    ),
    (
        "twin-interval",
        "/api/v2/twin/compare",
        {"observations": [], "intervalSeconds": 1e12},
    ),
    ("twin-warmup", "/api/v2/twin/compare", {"observations": [], "warmupSeconds": -5}),
    (
        "twin-too-many-observations",
        "/api/v2/twin/compare",
        {"observations": [{"linkId": "l", "timestamp": 0, "count": 1}] * 20_001},
    ),
    (
        "twin-negative-count",
        "/api/v2/twin/compare",
        {"observations": [{"linkId": "l", "timestamp": 0, "count": -1}]},
    ),
    (
        "twin-whatif-horizon",
        "/api/v2/twin/whatif",
        {"observations": [], "horizonWindows": 10**6},
    ),
    (
        "twin-whatif-scale",
        "/api/v2/twin/whatif",
        {"observations": [], "scenario": {"demandScale": 1e9}},
    ),
    ("incidents-duration", "/api/v2/incidents/simulate", {"duration": 1e9}),
    ("incidents-bucket", "/api/v2/incidents/simulate", {"bucketSeconds": 0.001}),
    (
        "incidents-seeds",
        "/api/v2/incidents/resilience",
        {"seeds": list(range(100_000))},
    ),
    ("incidents-no-seeds", "/api/v2/incidents/resilience", {"seeds": []}),
    ("incidents-hold", "/api/v2/incidents/resilience", {"holdBuckets": 10**6}),
    ("incidents-strategy", "/api/v2/incidents/simulate", {"strategy": "rm -rf"}),
    (
        "priority-duration",
        "/api/v2/priority/emergency-comparison",
        {"scenario": {"durationSeconds": 1e9}},
    ),
    ("priority-seeds", "/api/v2/priority/emergency-comparison", {"numSeeds": 10**6}),
    (
        "priority-rate",
        "/api/v2/priority/transit-comparison",
        {"scenario": {"arrivalRate": 1e6}},
    ),
    ("priority-confidence", "/api/v2/priority/transit-comparison", {"confidence": 5}),
    (
        "priority-many-emergency",
        "/api/v2/priority/emergency-comparison",
        {"emergencyVehicles": [{"timeSeconds": 1}] * 10_000},
    ),
    ("v2x-duration", "/api/v2/v2x/experiment", {"duration": 1e9}),
    ("v2x-seeds", "/api/v2/v2x/experiment", {"seeds": list(range(100_000))}),
    ("v2x-loss", "/api/v2/v2x/experiment", {"channel": {"lossProbability": 5}}),
    ("v2x-latency", "/api/v2/v2x/experiment", {"channel": {"latencyMs": 1e12}}),
    ("v2x-grid", "/api/v2/v2x/experiment", {"grid": {"rows": 500, "cols": 500}}),
    ("v2x-penetrations", "/api/v2/v2x/experiment", {"penetrations": [0.5] * 1000}),
    ("jobs-tenant", "/api/v2/jobs/enqueue-dry-run", {"tenant": "../../etc"}),
    (
        "jobs-seeds",
        "/api/v2/jobs/enqueue-dry-run",
        {"tenant": "acme", "run": {"numSeeds": 10**6}},
    ),
    (
        "jobs-visibility",
        "/api/v2/jobs/enqueue-dry-run",
        {"tenant": "acme", "visibilityTimeoutSeconds": 10**9},
    ),
    (
        "jobs-unknown-field",
        "/api/v2/jobs/enqueue-dry-run",
        {"tenant": "acme", "unexpected": 1},
    ),
]


@pytest.mark.parametrize(
    ("path", "body"), [p[1:] for p in OUT_OF_RANGE], ids=[p[0] for p in OUT_OF_RANGE]
)
def test_out_of_range_value_is_422_quickly(path: str, body: Dict[str, Any]) -> None:
    status, elapsed = _post(path, body)
    assert status in REFUSED, f"{path} answered {status} for {sorted(body)}"
    assert elapsed < TIME_BUDGET_SECONDS, f"{path} took {elapsed:.1f}s to refuse"


def test_jobs_oversized_cost_tags_are_refused() -> None:
    tags = {f"k{i}": "v" * 200 for i in range(2000)}
    status, elapsed = _post(
        "/api/v2/jobs/enqueue-dry-run", {"tenant": "acme", "costTags": tags}
    )
    assert status in REFUSED + (400,), status
    assert elapsed < TIME_BUDGET_SECONDS


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/network-metrics/simulate",
        "/api/v2/twin/compare",
        "/api/v2/incidents/simulate",
        "/api/v2/priority/emergency-comparison",
        "/api/v2/v2x/experiment",
        "/api/v2/jobs/enqueue-dry-run",
    ],
)
def test_malformed_and_wrongly_typed_bodies_are_422_not_500(path: str) -> None:
    for body in (
        b"{not json",
        b"[]",
        b'"text"',
        b"null",
        b'{"duration": "ten", "numSeeds": "ten"}',
    ):
        status, _ = _post(path, body)
        assert status in REFUSED, (path, body, status)


@pytest.mark.parametrize(
    "query",
    [
        "rows=0",
        "rows=10000",
        "cols=-1",
        "spacing=1e12",
        "vehiclesPerHour=nan",
        "originLat=200",
    ],
)
def test_grid_query_bounds(query: str) -> None:
    start = time.monotonic()
    res = client.get(f"/api/v2/network-metrics/grid?{query}")
    assert res.status_code == 422, (query, res.status_code)
    assert time.monotonic() - start < TIME_BUDGET_SECONDS


# Families the 1 MiB middleware cap (src/api/request_limits.py LIMITED_PREFIXES) does not cover.
# The bodies below are invalid on purpose (the priority models ignore unknown fields, so numSeeds is set too), so a missing cap shows as 422 or 400 instead of 413.
_UNCAPPED = "S-01: path is not in LIMITED_PREFIXES, so the body is read in full before validation"


def _padded(extra_bytes: int) -> bytes:
    return json.dumps(
        {"duration": -1, "numSeeds": -1, "pad": "x" * extra_bytes}
    ).encode()


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(
            "/api/v2/network-metrics/simulate",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        pytest.param(
            "/api/v2/twin/compare",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        pytest.param(
            "/api/v2/incidents/simulate",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        pytest.param(
            "/api/v2/priority/emergency-comparison",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        pytest.param(
            "/api/v2/v2x/experiment",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        pytest.param(
            "/api/v2/jobs/enqueue-dry-run",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        pytest.param(
            "/api/v2/network-graphs/validate",
            marks=pytest.mark.xfail(strict=True, reason=_UNCAPPED),
        ),
        # Covered by the cap, kept as the control that the test itself works.
        "/api/v2/networks/validate",
    ],
)
def test_body_over_one_mebibyte_is_413(path: str) -> None:
    status, elapsed = _post(path, _padded(MAX_V2_BODY_BYTES + 1024))
    assert status == 413, f"{path} answered {status}"
    assert elapsed < TIME_BUDGET_SECONDS


def test_calibration_oversized_upload_is_refused() -> None:
    """Calibration legitimately takes an up-to-8 MB counts file, so it has no 1 MiB cap; the
    field limit must still refuse anything larger."""
    body = {"graph": GRAPH_OK, "countsCsv": "x" * (9 * 1024 * 1024)}
    status, elapsed = _post("/api/v2/calibration/network-fit/validate-counts", body)
    assert status in REFUSED, status
    assert elapsed < TIME_BUDGET_SECONDS
