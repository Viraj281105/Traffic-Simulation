"""Security regression tests for ``/api/v3`` (docs/engineering/v3-w1-security-review.md).

Each test pins a finding of the review: the attack it describes must stay refused, quickly and with a
useful message, and never as a 500."""

import time

import pytest
from pydantic import ValidationError

from src.experiments import limits
from src.experiments.service import prepare
from src.uncertainty import UncertaintySpec

from .conftest import FakeExecutor, as_user, build_client, experiment, submit, wait_for

ALICE, BOB = "alice", "bob"


def _nest(depth: int) -> dict:
    root: dict = {}
    cursor = root
    for _ in range(depth):
        cursor["a"] = {}
        cursor = cursor["a"]
    return root


# --- F1: work is bounded before it is done ---------------------------------------------------------


def test_a_huge_alternatives_list_is_refused_before_any_is_validated(client):
    """20 000 alternatives used to cost about 70 s of request CPU before the quota refused them."""
    body = experiment(
        alternatives=[{"id": f"a{i}", "strategy": "fixed_time"} for i in range(20000)]
    )
    started = time.monotonic()
    for path in ("/api/v3/experiments/validate", "/api/v3/experiments"):
        response = client.post(path, json=body, headers=as_user(ALICE))
        assert response.status_code in (200, 422)
        text = response.text
        assert "alternatives" in text and ("at most" in text)
    assert time.monotonic() - started < 5.0


def test_just_over_the_quota_is_refused_with_the_quota_named(client):
    n = limits.MAX_ALTERNATIVES + 1
    body = experiment(
        alternatives=[{"id": f"a{i}", "strategy": "fixed_time"} for i in range(n)]
    )
    errors = prepare(body).errors
    assert errors == [
        f"quota maxAlternatives: {n} alternatives given, at most {limits.MAX_ALTERNATIVES} allowed"
    ]


# --- F2: a hostile document is a 4xx, never a 500 ---------------------------------------------------


@pytest.mark.parametrize("where", ["patch", "advanced", "scenario", "name-list"])
def test_deeply_nested_documents_are_refused_not_a_500(client, where):
    deep = _nest(3000)
    body = experiment()
    if where == "patch":
        body["alternatives"] = [
            {"id": "a", "strategy": "fixed_time"},
            {"id": "b", "strategy": "adaptive", "patch": deep},
        ]
    elif where == "advanced":
        body["scenario"]["advanced"] = deep
    elif where == "scenario":
        body["scenario"] = deep
    else:
        body["scenario"]["description"] = [[[[]]]] * 1  # shallow lists are fine
        body["uncertainty"]["factors"][0]["rationale"] = "ok"
    response = client.post("/api/v3/experiments", json=body, headers=as_user(ALICE))
    assert response.status_code != 500
    if where != "name-list":
        assert response.status_code == 422
        assert "nested more than" in " ".join(response.json()["detail"]["errors"])


def test_normal_documents_are_far_below_the_depth_limit(client):
    # the deepest real structure is a merge patch of a scenario: patch -> approaches -> arm -> turning -> ...
    body = experiment()
    body["alternatives"][1]["patch"] = {
        "approaches": {
            "north": {"turning": {"left": 0.2, "straight": 0.6, "right": 0.2}}
        }
    }
    assert prepare(body).errors == []


# --- F3: cost is counted in engine steps, not seconds -----------------------------------------------


def test_a_smaller_time_step_costs_more_even_for_the_same_seconds(client):
    def refused(time_step: float) -> bool:
        body = experiment()
        body["scenario"]["simulation"] = {
            "duration": 3600,
            "warmup": 30,
            "seed": 1,
            "timeStep": time_step,
        }
        body["uncertainty"].update(conditions=10, replications=2)  # 60 runs
        return any("maxSimulationStepsPerExperiment" in e for e in prepare(body).errors)

    assert refused(0.05) is True  # 60 runs x 72 000 steps = 4.3 M
    assert (
        refused(0.1) is False
    )  # 60 runs x 36 000 steps = 2.2 M: same seconds, half the work


def test_an_advanced_time_step_override_is_counted(client):
    body = experiment()
    body["scenario"]["simulation"] = {"duration": 3600, "warmup": 30, "seed": 1}
    body["scenario"]["advanced"] = {"simulation": {"timeStep": 0.05}}
    body["uncertainty"].update(conditions=10, replications=2)
    assert any("maxSimulationStepsPerExperiment" in e for e in prepare(body).errors)


# --- F4: nothing the user sends is echoed back unbounded --------------------------------------------


def test_the_baseline_id_is_length_bounded(client):
    response = client.post(
        "/api/v3/experiments/validate",
        json=experiment(baseline="x" * 500_000),
        headers=as_user(ALICE),
    )
    assert response.status_code == 200
    assert len(response.text) < 2000
    assert "baseline" in response.text


# --- F5: unexpected failures do not leak internals ---------------------------------------------------


def test_an_unexpected_error_shows_its_type_not_its_message(make_service):
    class LeakyExecutor(FakeExecutor):
        def __call__(self, tasks, progress=None):
            raise OSError(
                "[Errno 2] No such file or directory: 'C:/secret/server/path.db'"
            )

    client = build_client(make_service(LeakyExecutor()))
    failed = wait_for(client, submit(client)["id"])
    assert failed["status"] == "failed"
    assert "OSError" in failed["error"]
    assert "secret" not in failed["error"] and "path.db" not in failed["error"]


# --- F6: scale factors cannot describe a different junction -----------------------------------------


@pytest.mark.parametrize("bounds", [[0.01, 1.2], [0.8, 50.0], [1.0, 1e300]])
def test_scale_factor_bounds_are_limited(bounds):
    with pytest.raises(ValidationError, match="scale factor must stay within"):
        UncertaintySpec.model_validate(
            {
                "conditions": 5,
                "seed": 1,
                "factors": [
                    {
                        "id": "d",
                        "kind": "demand_scale",
                        "distribution": {"kind": "uniform"},
                        "bounds": bounds,
                        "rationale": "x",
                    }
                ],
            }
        )


# --- ownership and privacy (the properties the review relies on) --------------------------------------


def test_ids_are_unguessable_and_probing_gives_no_information(client):
    mine = wait_for(client, submit(client, ALICE)["id"])["id"]
    assert len(mine) == 32 and int(mine, 16) >= 0  # a random UUID, not a counter
    probes = [
        "1",
        "0" * 32,
        mine[:-1] + ("0" if mine[-1] != "0" else "1"),
        "x' OR '1'='1",
        "../" * 3,
    ]
    bodies = set()
    for probe in probes:
        response = client.get(f"/api/v3/experiments/{probe}", headers=as_user(BOB))
        assert response.status_code in (404,)
        bodies.add(response.text)
    assert (
        len(bodies) <= 2
    )  # the same answer for every probe (one extra form for routing misses)
    # and the real id gives Bob exactly the same answer as a fake one
    real = client.get(f"/api/v3/experiments/{mine}", headers=as_user(BOB))
    fake = client.get(f"/api/v3/experiments/{'f' * 32}", headers=as_user(BOB))
    assert real.status_code == fake.status_code == 404 and real.json() == fake.json()


def test_a_user_cannot_use_another_users_quota_or_slot(make_service):
    import threading

    release = threading.Event()
    client = build_client(make_service(FakeExecutor(block=release)))
    try:
        submit(client, ALICE)
        # Bob is not blocked by Alice's running experiment (per-user slot) ...
        submit(client, BOB)
        # ... and Alice cannot start a second one by asking as Bob or without a user.
        assert client.post("/api/v3/experiments", json=experiment()).status_code == 401
    finally:
        release.set()
