"""Stored runs: who may see and change them (src/access.py, src/history/).

A run saved by a signed-in user is theirs: every history route answers 404
to anyone else, exactly as for a missing run, and it never appears in another
caller's listing. Unowned runs (studies started without signing in) stay
public to read, but their labels can only be changed by an admin. Before
these tests, every one of these routes served any run to anyone, and PATCH
let an anonymous request rename any user's saved run.
"""

from typing import Any, Iterator, Optional

import pytest
from fastapi.testclient import TestClient

from src.auth import (
    get_current_user_id,
    get_current_user_is_admin,
    get_optional_user_id,
    get_optional_user_is_admin,
)
from src.database import db
from src.database.dao import SimulationRunDAO
from src.main import app

client = TestClient(app)
BASE = "/api/v1/study/history/runs"

CONFIG = {
    "simulation": {"duration": 5.0, "timeStep": 0.1, "randomSeed": 7},
    "geometry": {"intersectionType": "fixed_time_signal"},
}


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "history-access.db"))
    monkeypatch.delenv("API_KEY", raising=False)
    db.init_db()


@pytest.fixture
def act_as() -> Iterator[Any]:
    """Switch the caller between requests; None signs out."""

    deps = (
        get_current_user_id,
        get_current_user_is_admin,
        get_optional_user_id,
        get_optional_user_is_admin,
    )

    def sign_in(user: Optional[str], admin: bool = False) -> None:
        for dep in deps:
            app.dependency_overrides.pop(dep, None)
        if user is None:
            return  # real dependencies: no token -> anonymous / 401
        app.dependency_overrides[get_current_user_id] = lambda: user
        app.dependency_overrides[get_current_user_is_admin] = lambda: admin
        app.dependency_overrides[get_optional_user_id] = lambda: user
        app.dependency_overrides[get_optional_user_is_admin] = lambda: admin

    try:
        yield sign_in
    finally:
        for dep in deps:
            app.dependency_overrides.pop(dep, None)


def _store(run_id: str, owner: Optional[str], metrics: Any = None) -> None:
    with db.get_db_connection() as conn:
        SimulationRunDAO.save(
            conn,
            run_id,
            "completed",
            5.0,
            intersection_type="fixed_time_signal",
            random_seed=7,
            duration=5.0,
            config=CONFIG,
            summary_metrics=metrics
            if metrics is not None
            else {"averageDelay": 4.0, "throughput": 10},
            name=f"run of {owner}",
            user_id=owner,
        )


def _listed(**params: Any) -> set[str]:
    res = client.get(BASE, params=params)
    assert res.status_code == 200
    return {r["id"] for r in res.json()}


READ_ROUTES = ("", "/reproducibility", "/export?format=json", "/export?format=csv")


def test_owned_run_is_private_on_every_read_route(act_as: Any) -> None:
    _store("alice_run", "alice")
    for who in ("bob", None):
        act_as(who)
        for suffix in READ_ROUTES:
            path = f"{BASE}/alice_run{suffix}"
            assert client.get(path).status_code == 404, (who, path)
        assert "alice_run" not in _listed()
        compare = {"runIdA": "alice_run", "runIdB": "alice_run"}
        assert client.post(f"{BASE}/compare", json=compare).status_code == 404
        assert client.post(f"{BASE}/alice_run/reproduce").status_code == 404

    act_as("alice")
    for suffix in READ_ROUTES:
        assert client.get(f"{BASE}/alice_run{suffix}").status_code == 200, suffix
    assert "alice_run" in _listed()

    act_as("root", admin=True)
    assert client.get(f"{BASE}/alice_run/reproducibility").status_code == 200
    assert "alice_run" in _listed()


def test_unowned_runs_stay_public(act_as: Any) -> None:
    _store("sweep_run", None)
    _store("alice_run", "alice")
    act_as(None)
    assert _listed() == {"sweep_run"}
    assert client.get(f"{BASE}/sweep_run/reproducibility").status_code == 200
    act_as("bob")
    assert _listed() == {"sweep_run"}
    act_as("alice")
    assert _listed() == {"sweep_run", "alice_run"}


def test_filters_cannot_widen_the_visible_set(act_as: Any) -> None:
    _store("alice_run", "alice")
    act_as("bob")
    for params in (
        {"intersection_type": "fixed_time_signal"},
        {"seed": 7},
        {"batch_id": "replay"},
        {"intersection_type": "x' OR '1'='1"},
    ):
        assert "alice_run" not in _listed(**params), params


def test_labels_need_the_owner_or_an_admin(act_as: Any) -> None:
    _store("alice_run", "alice")
    _store("sweep_run", None)
    body = {"name": "renamed", "notes": '=HYPERLINK("x")'}

    act_as(None)
    assert client.patch(f"{BASE}/alice_run", json=body).status_code == 401
    assert client.patch(f"{BASE}/sweep_run", json=body).status_code == 401

    act_as("bob")
    assert client.patch(f"{BASE}/alice_run", json=body).status_code == 404
    assert client.patch(f"{BASE}/sweep_run", json=body).status_code == 403
    assert client.patch(f"{BASE}/missing", json=body).status_code == 404

    act_as("alice")
    assert client.get(f"{BASE}/alice_run/reproducibility").json()["name"] == (
        "run of alice"
    )
    res = client.patch(f"{BASE}/alice_run", json=body)
    assert res.status_code == 200 and res.json()["name"] == "renamed"
    assert client.patch(f"{BASE}/sweep_run", json=body).status_code == 403

    act_as("root", admin=True)
    assert client.patch(f"{BASE}/sweep_run", json=body).status_code == 200


def test_csv_export_neutralises_spreadsheet_formulas(act_as: Any) -> None:
    _store("alice_run", "alice")
    act_as("alice")
    client.patch(
        f"{BASE}/alice_run",
        json={"name": "=1+1", "notes": "@SUM(A1)", "tags": ["+x", "-3.5"]},
    )
    csv_text = client.get(f"{BASE}/alice_run/export?format=csv").text
    assert "run,name,'=1+1" in csv_text
    assert "run,notes,'@SUM(A1)" in csv_text
    # The tags cell starts with "+", so it is quoted as text as a whole.
    assert "run,tags,'+x; -3.5" in csv_text
    # Numbers are data, not formulas: a negative value is left alone.
    assert "'-" not in csv_text.replace("'-3.5", "")


def test_compare_never_substitutes_zero_for_a_missing_metric(act_as: Any) -> None:
    dual = {"signal": {"averageDelay": 9.0}, "roundabout": {"averageDelay": 3.0}}
    _store("dual_a", None, dual)
    _store("dual_b", None, dual)
    _store("single", None, {"averageDelay": 4.0, "throughput": 10})
    act_as(None)

    both_dual = client.post(
        f"{BASE}/compare", json={"runIdA": "dual_a", "runIdB": "dual_b"}
    ).json()["comparison"]
    # Previously both delays read as 0.0 and the runs were declared a "tie".
    assert both_dual["winner"] == "unavailable"
    assert both_dual["delayDelta"] is None
    assert both_dual["throughputDelta"] is None

    mixed = client.post(
        f"{BASE}/compare", json={"runIdA": "single", "runIdB": "dual_a"}
    ).json()["comparison"]
    assert mixed["winner"] == "unavailable"
    assert mixed["delayDeltaPercent"] is None


def test_compare_still_describes_two_comparable_runs(act_as: Any) -> None:
    _store("a", None, {"averageDelay": 10.0, "throughput": 20, "totalStops": 5})
    _store("b", None, {"averageDelay": 5.0, "throughput": 22, "totalStops": 3})
    act_as(None)
    c = client.post(f"{BASE}/compare", json={"runIdA": "a", "runIdB": "b"}).json()
    assert c["comparison"]["delayDelta"] == -5.0
    assert c["comparison"]["delayDeltaPercent"] == -50.0
    assert c["comparison"]["throughputDelta"] == 2.0
    assert c["comparison"]["stopsDelta"] == -2
    assert c["comparison"]["winner"] == "fixed_time_signal"


def test_reproduce_refuses_an_unbounded_stored_run(act_as: Any) -> None:
    """A replay saved without a live engine stores the client's duration and
    time step; reproducing it must not start an unbounded synchronous run."""
    from src.auth import get_current_user_email

    act_as("alice")
    app.dependency_overrides[get_current_user_email] = lambda: "alice@example.com"
    try:
        for sim in (
            {"duration": 1e9, "timeStep": 0.1},
            {"duration": 3600.0, "timeStep": 1e-6},
            {"duration": 60.0, "timeStep": 0.0},
        ):
            # No live engine behind this client, so the server keeps the
            # client's own config, duration and time step.
            saved = client.post(
                "/api/v1/replays",
                json={
                    "name": "client-supplied",
                    "config": {**CONFIG, "simulation": {**sim, "randomSeed": 1}},
                    "metrics": {"averageDelay": 1.0, "throughput": 3},
                },
            )
            assert saved.status_code == 200, saved.text
            res = client.post(f"{BASE}/{saved.json()['runId']}/reproduce")
            assert res.status_code == 400, (sim, res.text)
    finally:
        app.dependency_overrides.pop(get_current_user_email, None)


def test_suite_batch_runs_belong_to_the_suite_owner(
    act_as: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A private suite's batch results used to be stored with no owner, so
    anyone could list them with ?batch_id=<suite id>."""
    from src.study import batch

    captured: dict[str, Any] = {}

    def fake_batch(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {"runIds": []}

    monkeypatch.setattr(batch, "run_suite_batch_experiment", fake_batch)
    act_as("alice")
    suite_id = client.post(
        "/api/suites",
        json={"name": "s", "description": "", "run_ids": [], "config_variations": {}},
    ).json()["id"]
    res = client.post(
        f"/api/suites/{suite_id}/batch",
        json={
            "baseConfig": {"intersectionType": "fixed_time_signal", "duration": 4},
            "sweepParameters": {"arrivalRate": [0.2]},
            "numSeeds": 1,
        },
    )
    assert res.status_code == 200
    import time

    from src.main import jobs

    job = jobs.get(res.json()["jobId"])
    assert job is not None
    deadline = time.monotonic() + 30
    while job.status not in ("completed", "failed") and time.monotonic() < deadline:
        time.sleep(0.05)
    assert job.status == "completed", job.error
    assert captured["owner_id"] == "alice"


def test_suite_csv_neutralises_spreadsheet_formulas() -> None:
    from src.study.report_generator import generate_suite_csv

    csv_text = generate_suite_csv(
        [
            {
                "id": "r1",
                "intersection_type": "roundabout",
                "random_seed": 1,
                "name": "=cmd|' /C calc'!A0",
                "summary_metrics": {"@evil": 1, "averageDelay": -2.5},
            }
        ]
    )
    assert "'=cmd" in csv_text and "'@evil" in csv_text
    assert ",averageDelay,-2.5" in csv_text
