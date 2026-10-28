"""A hostile, deeply nested planning study is a 422, never a 500 (v3 W1 security review, residual risk 8).

``alternatives[].patch`` and the scenario's ``advanced`` section are free-form JSON that the merge and the
validation walk recursively; about 3000 levels used to overflow the stack and answer HTTP 500. These tests go
through the real app, so they cover the routes as well as the service."""

import copy
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.core.limits import MAX_DOCUMENT_DEPTH, nested_deeper_than
from src.main import app

from .conftest import SCENARIO, study

ROUTES = ("/api/v2/planning/validate", "/api/v2/planning/run", "/api/v2/planning/jobs")


@pytest.fixture
def client(signed_in_user: str) -> Iterator[TestClient]:
    yield TestClient(app)


def _nest(depth: int) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    cursor = root
    for _ in range(depth):
        cursor["a"] = {}
        cursor = cursor["a"]
    return root


def _deep_study(where: str, depth: int) -> Dict[str, Any]:
    body = study()
    if where == "patch":
        body["alternatives"][1]["patch"] = _nest(depth)
    else:
        scenario = copy.deepcopy(SCENARIO)
        scenario["advanced"] = _nest(depth)
        body["subject"] = {"scenario": scenario}
    return body


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("where", ["patch", "advanced"])
def test_a_deeply_nested_study_is_a_422_with_a_message(client, route, where):
    # Depth 100 exceeds MAX_DOCUMENT_DEPTH (24) while remaining within Python's JSON serialization stack.
    response = client.post(route, json=_deep_study(where, 100))
    assert response.status_code == 422, response.text[:300]
    assert (
        f"The document is nested more than {MAX_DOCUMENT_DEPTH} levels deep"
        in response.text
    )


@pytest.mark.parametrize("route", ROUTES)
def test_a_deep_study_error_uses_the_standard_envelope(client, route):
    body = client.post(route, json=_deep_study("patch", 100)).json()
    assert "error" in body or "detail" in body
    assert "nested more than" in str(body)


def test_a_realistic_nesting_is_still_accepted(client):
    body = study()
    body["alternatives"][1]["patch"] = {
        "approaches": {
            "north": {"turning": {"left": 0.2, "straight": 0.6, "right": 0.2}}
        }
    }
    response = client.post("/api/v2/planning/validate", json=body)
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_the_depth_helper_counts_levels_without_recursing():
    assert not nested_deeper_than({}, 1)
    assert not nested_deeper_than(_nest(23), MAX_DOCUMENT_DEPTH)
    assert nested_deeper_than(_nest(24), MAX_DOCUMENT_DEPTH)
    assert nested_deeper_than([[[[]]]], 3)
    assert nested_deeper_than(_nest(100_000), MAX_DOCUMENT_DEPTH)
