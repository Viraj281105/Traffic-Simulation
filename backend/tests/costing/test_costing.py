"""Costing: price table, estimator, per-run cost, aggregation, budget and routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.costing import (
    PriceError,
    budget_status,
    estimate_cost,
    load_prices,
    should_admit,
)
from src.costing.prices import parse_prices
from src.costing.router import create_router
from src.insights.locations import ResultsLocations

PRICES = load_prices()


def _table() -> Dict[str, Any]:
    return {
        "label": "x",
        "asOf": "2026-01-01",
        "region": "r",
        "currency": "USD",
        "defaultInstance": "a",
        "instances": {"a": {"vcpus": 2, "onDemandHourly": 0.1, "spotHourly": 0.04}},
        "s3": {"perGbMonth": 0.02},
        "sqs": {"perMillionRequests": 0.4},
    }


def test_bundled_table_loads() -> None:
    assert PRICES.region and PRICES.as_of and "APPROXIMATE" in PRICES.label
    assert PRICES.default_instance in PRICES.instances


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(asOf="yesterday"),
        lambda d: d["instances"]["a"].update(vcpus=0),
        lambda d: d["instances"]["a"].update(spotHourly=1.0),
        lambda d: d["instances"]["a"].update(onDemandHourly=-1),
        lambda d: d.update(defaultInstance="zzz"),
        lambda d: d.pop("s3"),
        lambda d: d.update(instances={}),
    ],
)
def test_invalid_tables_rejected(mutate: Any) -> None:
    data = _table()
    parse_prices(data)
    mutate(data)
    with pytest.raises(PriceError):
        parse_prices(data)


def test_estimate_hand_computed() -> None:
    # m5.large on-demand 0.096/h, 2 vCPU: 3600 s at weight 1 -> 0.048
    # 2 GB stored 1 month at 0.023 -> 0.046; 500000 requests at 0.4/M -> 0.2
    est = estimate_cost(
        PRICES,
        compute_seconds=3600,
        vcpu_weight=1,
        instance_type="m5.large",
        stored_bytes=2_000_000_000,
        queue_requests=500_000,
    )
    assert (est.compute, est.storage, est.queue) == (0.048, 0.046, 0.2)
    assert est.total == pytest.approx(0.294)
    assert est.confidence == "estimate, not a bill"
    assert est.currency == "USD" and est.assumptions


def test_spot_is_cheaper_and_bad_inputs_fail() -> None:
    on = estimate_cost(PRICES, compute_seconds=7200, vcpu_weight=2)
    spot = estimate_cost(PRICES, compute_seconds=7200, vcpu_weight=2, spot=True)
    assert on.compute == pytest.approx(0.192) and spot.compute == pytest.approx(0.076)
    with pytest.raises(KeyError):
        estimate_cost(PRICES, compute_seconds=1, instance_type="nope")
    with pytest.raises(ValueError):
        estimate_cost(PRICES, compute_seconds=-1)
    with pytest.raises(ValueError):
        estimate_cost(PRICES, compute_seconds=1, vcpu_weight=3)  # m5.large has 2


def test_budget_boundaries() -> None:
    assert should_admit(2.0, budget=10, spent=8).allow  # exactly what is left
    deny = should_admit(2.01, budget=10, spent=8)
    assert not deny.allow and "exceeds" in deny.reason
    assert not should_admit(0.0, budget=10, spent=10).allow
    assert should_admit(0.0, budget=10, spent=9.99).allow
    st = budget_status(100, 40, 4)
    assert st.remaining == 60 and st.daily_burn == 10 and st.days_to_exhaustion == 6
    assert budget_status(100, 0, 4).days_to_exhaustion is None
    assert budget_status(100, 100, 4).days_to_exhaustion == 0
    with pytest.raises(ValueError):
        should_admit(-1, 1, 0)


def _write_run(root: Path, run_id: str, tenant: str, seconds: float, day: str) -> None:
    d = root / "runs" / run_id
    d.mkdir(parents=True)
    (d / "job.json").write_text(
        json.dumps(
            {
                "runId": run_id,
                "tenant": tenant,
                "computeSeconds": seconds,
                "costTags": {"project": "urbanflow", "env": "dev", "tenant": tenant},
            }
        )
    )
    (d / "manifest.json").write_text(json.dumps({"createdAt": f"{day}T10:00:00Z"}))


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    _write_run(tmp_path, "r1", "acme", 3600, "2026-11-01")
    _write_run(tmp_path, "r2", "acme", 7200, "2026-11-01")
    _write_run(tmp_path, "r3", "acme", 3600, "2026-11-02")
    _write_run(tmp_path, "r4", "other", 3600, "2026-11-01")
    app = FastAPI()
    app.include_router(create_router(locations=ResultsLocations(tmp_path)))
    return TestClient(app)


def test_run_cost_and_missing(client: TestClient) -> None:
    body = client.get("/api/v2/costing/runs/r1").json()
    assert body["items"]["compute"] == 0.048 and body["day"] == "2026-11-01"
    assert body["confidence"] == "estimate, not a bill"
    assert client.get("/api/v2/costing/runs/ghost").status_code == 404
    assert client.get("/api/v2/costing/runs/..%2Fx").status_code == 404
    assert client.get("/api/v2/costing/runs/r1?instanceType=zz").status_code == 422


def test_tenant_summary(client: TestClient) -> None:
    body = client.get("/api/v2/costing/tenants/acme/summary?day=2026-11-01").json()
    assert body["runs"] == 2 and body["computeSeconds"] == 10800
    assert body["total"] == pytest.approx(
        0.144002
    )  # 0.048001 + 0.096001 (rounded per run)
    assert body["byTag"]["env"]["dev"] == body["total"]
    empty = client.get("/api/v2/costing/tenants/nobody/summary?day=2026-11-01").json()
    assert empty["runs"] == 0 and empty["total"] == 0
    assert client.get("/api/v2/costing/tenants/acme/summary?day=bad").status_code == 422


def test_prices_and_estimate_routes(client: TestClient) -> None:
    assert client.get("/api/v2/costing/prices").json()["region"] == PRICES.region
    ok = client.post("/api/v2/costing/estimate", json={"computeSeconds": 3600})
    assert ok.status_code == 200 and ok.json()["items"]["compute"] == 0.048
    for bad in (
        {"computeSeconds": -1},
        {"computeSeconds": 1, "vcpuWeight": 0},
        {"computeSeconds": 1, "storedBytes": 10**16},
        {"computeSeconds": 1, "instanceType": "nope"},
        {"computeSeconds": 1, "vcpuWeight": 99},
    ):
        assert client.post("/api/v2/costing/estimate", json=bad).status_code == 422
