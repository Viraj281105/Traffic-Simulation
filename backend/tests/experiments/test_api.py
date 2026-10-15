"""``/api/v3`` experiments: submit, status, result, capabilities, ownership, quotas and failure handling."""

import threading

import pytest

from src.experiments import limits

from .conftest import (
    FakeExecutor,
    as_user,
    build_client,
    experiment,
    submit,
    wait_for,
)

ALICE, BOB = "alice", "bob"


# --- capabilities ---------------------------------------------------------------------------------


def test_capabilities_report_only_what_exists(client):
    body = client.get("/api/v3/capabilities", headers=as_user(ALICE)).json()
    assert body["apiVersion"] == 3
    features = body["features"]
    assert features["robustnessExperiments"] is True
    # nothing the server cannot do yet is advertised
    for missing in (
        "experimentCancellation",
        "experimentPackages",
        "personalAccessTokens",
        "pythonClient",
        "aiCopilot",
        "discoveryLab",
    ):
        assert features[missing] is False
    assert body["quotas"] == limits.quotas()
    assert body["documents"]["request"] == "urbanflow-experiment@1"
    assert "demand_scale" in body["experiments"]["factorKinds"]
    assert "averageDelay" in body["experiments"]["primaryIndicators"]
    assert body["limits"]["maxRequestBodyBytes"] > 0


# --- submit, status, result -----------------------------------------------------------------------


def test_submit_returns_202_and_the_run_counts(client):
    accepted = submit(client)
    assert accepted["format"] == "urbanflow-experiment-status"
    assert accepted["counts"] == {
        "conditions": 10,
        "alternatives": 2,
        "replications": 2,
        "totalRuns": 40,
    }
    assert accepted["status"] in ("queued", "running", "completed")
    assert len(accepted["specFingerprint"]) == 16


def test_completed_experiment_has_the_contract_result(client):
    done = wait_for(client, submit(client)["id"])
    assert done["status"] == "completed" and done["resultAvailable"] is True
    result = client.get(
        f"/api/v3/experiments/{done['id']}/result", headers=as_user(ALICE)
    ).json()
    assert result["format"] == "urbanflow-experiment-result"
    counts = result["analysis"]["counts"]
    assert counts == {
        "conditions": 10,
        "validConditions": 10,
        "alternatives": 2,
        "replications": 2,
        "totalRuns": 40,
    }
    # assumptions travel with the result, with basis and rationale
    assert result["assumptions"] == [
        {
            "id": "demand",
            "kind": "demand_scale",
            "distribution": {"kind": "uniform"},
            "bounds": [0.8, 1.2],
            "basis": "assumed",
            "rationale": "plausible weekday variation",
        }
    ]
    assert result["analysis"]["realWorldValidity"] == "None — assumptions only"
    assert result["analysis"]["limitations"]
    assert result["baseline"] == "fixed"
    assert (
        result["analysis"]["eligibility"]["class"] == "exploratory"
    )  # 10 < 30 valid conditions
    comparison = result["analysis"]["alternatives"]["adaptive"]["comparison"]
    assert (
        comparison["win"]["count"] == 10
    )  # the fake makes adaptive 5 s better everywhere
    assert result["specFingerprint"] == done["specFingerprint"]
    assert len(result["resultFingerprint"]) == 16
    assert result["provenance"]["commonRandomNumbers"] is True


def test_same_specification_and_seed_give_the_same_result_fingerprint(client):
    first = wait_for(client, submit(client)["id"])
    second = wait_for(
        client, submit(client, name="renamed")["id"]
    )  # a label is not a computation
    one = client.get(
        f"/api/v3/experiments/{first['id']}/result", headers=as_user(ALICE)
    ).json()
    two = client.get(
        f"/api/v3/experiments/{second['id']}/result", headers=as_user(ALICE)
    ).json()
    assert one["resultFingerprint"] == two["resultFingerprint"]
    assert one["specFingerprint"] == two["specFingerprint"]
    different = experiment()
    different["uncertainty"]["seed"] = 6
    third = client.post(
        "/api/v3/experiments", json=different, headers=as_user(ALICE)
    ).json()
    wait_for(client, third["id"])
    three = client.get(
        f"/api/v3/experiments/{third['id']}/result", headers=as_user(ALICE)
    ).json()
    assert three["resultFingerprint"] != one["resultFingerprint"]


def test_default_alternatives_are_the_three_built_in_strategies(client):
    body = experiment()
    del body["alternatives"]
    accepted = client.post(
        "/api/v3/experiments", json=body, headers=as_user(ALICE)
    ).json()
    assert accepted["counts"]["alternatives"] == 3
    wait_for(client, accepted["id"])


def test_list_is_newest_first_and_paged(client):
    ids = []
    for _ in range(3):
        ids.append(wait_for(client, submit(client)["id"])["id"])
    listing = client.get("/api/v3/experiments", headers=as_user(ALICE)).json()
    assert [e["id"] for e in listing["experiments"]] == ids[::-1]
    assert all(e["resultAvailable"] for e in listing["experiments"])
    page = client.get(
        "/api/v3/experiments?limit=1&offset=1", headers=as_user(ALICE)
    ).json()
    assert [e["id"] for e in page["experiments"]] == [ids[1]]
    assert (
        client.get("/api/v3/experiments?limit=0", headers=as_user(ALICE)).status_code
        == 422
    )
    assert (
        client.get("/api/v3/experiments?limit=101", headers=as_user(ALICE)).status_code
        == 422
    )


# --- ownership ------------------------------------------------------------------------------------


def test_another_users_experiment_is_a_404_everywhere(client):
    mine = wait_for(client, submit(client, ALICE)["id"])["id"]
    for method, path in (
        ("get", f"/api/v3/experiments/{mine}"),
        ("get", f"/api/v3/experiments/{mine}/result"),
        ("delete", f"/api/v3/experiments/{mine}"),
    ):
        theirs = getattr(client, method)(path, headers=as_user(BOB))
        unknown = getattr(client, method)(
            path.replace(mine, "0" * 32), headers=as_user(BOB)
        )
        assert theirs.status_code == 404
        assert (
            theirs.json() == unknown.json()
        )  # indistinguishable from an id that does not exist
    assert (
        client.get("/api/v3/experiments", headers=as_user(BOB)).json()["experiments"]
        == []
    )
    # and Alice still has it
    assert (
        client.get(f"/api/v3/experiments/{mine}", headers=as_user(ALICE)).status_code
        == 200
    )


def test_every_route_needs_a_user(client):
    for method, path in (
        ("get", "/api/v3/capabilities"),
        ("get", "/api/v3/experiments"),
        ("post", "/api/v3/experiments"),
        ("post", "/api/v3/experiments/validate"),
        ("get", "/api/v3/experiments/x"),
        ("get", "/api/v3/experiments/x/result"),
        ("delete", "/api/v3/experiments/x"),
    ):
        assert getattr(client, method)(path).status_code == 401, path


# --- validation -----------------------------------------------------------------------------------


def test_validate_reports_size_without_running_anything(make_service):
    fake = FakeExecutor()
    client = build_client(make_service(fake))
    out = client.post(
        "/api/v3/experiments/validate", json=experiment(), headers=as_user(ALICE)
    ).json()
    assert out["valid"] is True and out["errors"] == []
    assert out["counts"]["totalRuns"] == 40
    assert [a["id"] for a in out["alternatives"]] == ["fixed", "adaptive"]
    assert fake.calls == 0


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda b: b.update(surprise=1), "surprise"),
        (lambda b: b["scenario"].update(junction={"type": "teleporter"}), "scenario"),
        (lambda b: b.update(baseline="nope"), "baseline"),
        (
            lambda b: b.update(alternatives=[{"id": "only", "strategy": "fixed_time"}]),
            "two alternatives",
        ),
        (
            lambda b: b.update(
                alternatives=[
                    {"id": "a", "strategy": "fixed_time"},
                    {"id": "a", "strategy": "adaptive"},
                ]
            ),
            "unique",
        ),
        (
            lambda b: b.update(
                alternatives=[
                    {"id": "a", "strategy": "fixed_time"},
                    {"id": "b", "strategy": "hovercraft"},
                ]
            ),
            "hovercraft",
        ),
        (lambda b: b["uncertainty"].update(conditions=0), "conditions"),
        (lambda b: b["uncertainty"]["factors"][0].update(rationale=""), "rationale"),
        (
            lambda b: b["uncertainty"]["factors"].__setitem__(
                0,
                {
                    **b["uncertainty"]["factors"][0],
                    "kind": "mix_shift",
                    "bounds": [-0.5, 0.5],
                },
            ),
            "declare a vehicle mix",
        ),
    ],
)
def test_invalid_requests_are_422_with_every_problem_named(client, mutate, fragment):
    body = experiment()
    mutate(body)
    response = client.post("/api/v3/experiments", json=body, headers=as_user(ALICE))
    assert response.status_code == 422
    assert fragment in " ".join(response.json()["detail"]["errors"])
    # validate says the same thing without a 422
    check = client.post(
        "/api/v3/experiments/validate", json=body, headers=as_user(ALICE)
    ).json()
    assert check["valid"] is False and fragment in " ".join(check["errors"])


def test_a_non_object_body_is_rejected(client):
    response = client.post("/api/v3/experiments", json=[1, 2], headers=as_user(ALICE))
    assert response.status_code == 422


# --- experiment-size quotas (422 naming the quota) ------------------------------------------------


def test_too_many_runs_is_422_naming_the_quota(client):
    body = experiment()
    body["uncertainty"].update(conditions=1000, replications=10)
    response = client.post("/api/v3/experiments", json=body, headers=as_user(ALICE))
    assert response.status_code == 422
    assert "maxRunsPerExperiment" in " ".join(response.json()["detail"]["errors"])


def test_too_much_simulated_work_is_422_naming_the_quota(client):
    body = experiment()
    body["scenario"] = {
        **body["scenario"],
        "simulation": {"duration": 3600, "warmup": 30, "seed": 1},
    }
    body["uncertainty"].update(
        conditions=100, replications=2
    )  # 400 runs x 36 000 steps
    response = client.post("/api/v3/experiments", json=body, headers=as_user(ALICE))
    assert response.status_code == 422
    assert "maxSimulationStepsPerExperiment" in " ".join(
        response.json()["detail"]["errors"]
    )


def test_too_many_alternatives_is_422_naming_the_quota(client):
    body = experiment(
        alternatives=[
            {"id": f"a{i}", "strategy": "fixed_time"}
            for i in range(limits.MAX_ALTERNATIVES + 1)
        ]
    )
    response = client.post("/api/v3/experiments", json=body, headers=as_user(ALICE))
    assert response.status_code == 422
    assert "maxAlternatives" in " ".join(response.json()["detail"]["errors"])


# --- concurrency and storage quotas (429) ----------------------------------------------------------


def test_one_running_experiment_per_user_and_a_server_wide_cap(make_service):
    release = threading.Event()
    client = build_client(make_service(FakeExecutor(block=release)))
    try:
        first = submit(client, ALICE)
        again = client.post(
            "/api/v3/experiments", json=experiment(), headers=as_user(ALICE)
        )
        assert again.status_code == 429
        assert "maxActiveExperimentsPerUser" in again.json()["detail"]
        submit(client, BOB)  # a different user may run one
        third = client.post(
            "/api/v3/experiments", json=experiment(), headers=as_user("carol")
        )
        assert third.status_code == 429
        assert "maxActiveExperiments:" in third.json()["detail"]
        # while running: status is live, no result yet, cannot be deleted
        status = client.get(
            f"/api/v3/experiments/{first['id']}", headers=as_user(ALICE)
        ).json()
        assert (
            status["status"] in ("queued", "running")
            and status["resultAvailable"] is False
        )
        no_result = client.get(
            f"/api/v3/experiments/{first['id']}/result", headers=as_user(ALICE)
        )
        assert no_result.status_code == 409
        refused = client.delete(
            f"/api/v3/experiments/{first['id']}", headers=as_user(ALICE)
        )
        assert refused.status_code == 409 and "cancellation" in refused.json()["detail"]
    finally:
        release.set()
    wait_for(client, first["id"], ALICE)
    # once finished, the slot is free again
    wait_for(client, submit(client, ALICE)["id"])


def test_stored_experiments_per_user_are_capped_until_one_is_deleted(
    client, monkeypatch
):
    monkeypatch.setattr(limits, "MAX_STORED_EXPERIMENTS_PER_USER", 2)
    first = wait_for(client, submit(client)["id"])
    wait_for(client, submit(client)["id"])
    refused = client.post(
        "/api/v3/experiments", json=experiment(), headers=as_user(ALICE)
    )
    assert (
        refused.status_code == 429
        and "maxStoredExperimentsPerUser" in refused.json()["detail"]
    )
    assert (
        client.delete(
            f"/api/v3/experiments/{first['id']}", headers=as_user(ALICE)
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v3/experiments/{first['id']}", headers=as_user(ALICE)
        ).status_code
        == 404
    )
    wait_for(client, submit(client)["id"])


# --- failure --------------------------------------------------------------------------------------


def test_a_crashing_executor_marks_the_experiment_failed_without_leaking_internals(
    make_service,
):
    client = build_client(make_service(FakeExecutor(raises=True)))
    failed = wait_for(client, submit(client)["id"])
    # an unexpected error shows its type only; its message (which may hold paths) stays in the server log
    assert failed["status"] == "failed" and "RuntimeError" in failed["error"]
    assert "exploded" not in failed["error"]
    response = client.get(
        f"/api/v3/experiments/{failed['id']}/result", headers=as_user(ALICE)
    )
    assert response.status_code == 409 and "RuntimeError" in response.json()["detail"]
    # a failed experiment can be deleted, and the slot is free
    assert (
        client.delete(
            f"/api/v3/experiments/{failed['id']}", headers=as_user(ALICE)
        ).status_code
        == 200
    )


def test_runs_that_fail_are_excluded_and_counted_not_fatal(make_service):
    class CrashOnOneCondition(FakeExecutor):
        def __call__(self, tasks, progress=None):
            results = super().__call__(tasks, progress)
            return [
                RuntimeError("simulated crash") if "condition 2 " in t.label else r
                for t, r in zip(tasks, results)
            ]

    client = build_client(make_service(CrashOnOneCondition()))
    done = wait_for(client, submit(client)["id"])
    assert done["status"] == "completed"
    result = client.get(
        f"/api/v3/experiments/{done['id']}/result", headers=as_user(ALICE)
    ).json()
    assert result["analysis"]["counts"]["validConditions"] == 9
    assert result["analysis"]["exclusions"]["byReason"] == {"run_failed": 1}


# --- one real run through the API -----------------------------------------------------------------


def test_real_engine_end_to_end_through_the_api(tmp_path, monkeypatch):
    """Submit, run on the real engine, read the result: two identical alternatives must tie exactly."""
    from src.experiments.service import ExperimentService, ExperimentStore

    client = build_client(ExperimentService(store=ExperimentStore(persist=False)))
    body = experiment(
        alternatives=[
            {"id": "first", "strategy": "fixed_time"},
            {"id": "second", "strategy": "fixed_time"},
        ]
    )
    body["scenario"]["simulation"] = {"duration": 60, "warmup": 5, "seed": 3}
    body["scenario"]["approaches"] = {
        d: {**a, "vehiclesPerHour": 600}
        for d, a in body["scenario"]["approaches"].items()
    }
    body["uncertainty"].update(conditions=3, replications=1)
    accepted = client.post("/api/v3/experiments", json=body, headers=as_user(ALICE))
    assert accepted.status_code == 202
    done = wait_for(client, accepted.json()["id"], timeout=120)
    assert done["status"] == "completed", done
    result = client.get(
        f"/api/v3/experiments/{done['id']}/result", headers=as_user(ALICE)
    ).json()
    comparison = result["analysis"]["alternatives"]["second"]["comparison"]
    assert comparison["tie"]["count"] == 3
    assert comparison["difference"]["mean"]["value"] == 0.0
    assert result["execution"]["runsExecuted"] == 6


def test_a_short_measured_window_is_warned_about_before_submission(client):
    short = experiment()
    short["scenario"]["simulation"] = {"duration": 30, "warmup": 5, "seed": 3}
    check = client.post(
        "/api/v3/experiments/validate", json=short, headers=as_user(ALICE)
    ).json()
    assert check["valid"] is True
    assert any("25 s are measured" in w and "excluded" in w for w in check["warnings"])
    long_enough = experiment()
    long_enough["scenario"]["simulation"] = {"duration": 90, "warmup": 10, "seed": 3}
    ok = client.post(
        "/api/v3/experiments/validate", json=long_enough, headers=as_user(ALICE)
    ).json()
    assert not any(
        "measured after warm-up" in w for w in ok["warnings"]
    )  # 80 s measured
