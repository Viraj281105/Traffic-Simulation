"""Request-body cap on the stateless /api/v2 compute endpoints (R3.5)."""

import json
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.request_limits import LIMITED_PREFIXES, MAX_V2_BODY_BYTES
from src.main import app
from src.networks.from_scenario import scenario_to_network
from src.scenario.documents import parse_scenario

client = TestClient(app)

LIMITED = ["/api/v2/networks/validate", "/api/v2/planning/validate"]


@pytest.fixture(autouse=True)
def signed_in(signed_in_user: str) -> None:
    pass


def _oversized() -> bytes:
    return json.dumps({"network": {"pad": "x" * (MAX_V2_BODY_BYTES + 1)}}).encode()


@pytest.mark.parametrize("path", LIMITED)
def test_declared_oversize_body_is_413(path: str) -> None:
    res = client.post(
        path, content=_oversized(), headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.parametrize("path", LIMITED)
def test_streamed_oversize_body_without_length_is_413(path: str) -> None:
    body = _oversized()

    def chunks() -> Iterator[bytes]:
        for i in range(0, len(body), 64 * 1024):
            yield body[i : i + 64 * 1024]

    res = client.post(
        path, content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 413


def test_a_realistic_large_document_fits_with_a_wide_margin() -> None:
    # A four-arm, three-lane junction expressed as a network: the largest
    # document a planner would send to these endpoints.
    scenario: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Large junction",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {"lanes": 3, "vehiclesPerHour": 900}
            for d in ("north", "south", "east", "west")
        },
        "simulation": {"duration": 600, "warmup": 60, "seed": 1},
    }
    doc, errors = parse_scenario(scenario)
    assert doc is not None, errors
    body = json.dumps({"network": scenario_to_network(doc)}).encode()
    assert len(body) * 20 < MAX_V2_BODY_BYTES
    res = client.post(
        "/api/v2/networks/validate",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 200 and res.json()["valid"], res.json()


def test_other_routes_are_not_capped_by_this_middleware() -> None:
    assert not any(
        "/api/v2/planning/run".startswith(p) or "/api/v1".startswith(p)
        for p in LIMITED_PREFIXES
    )
