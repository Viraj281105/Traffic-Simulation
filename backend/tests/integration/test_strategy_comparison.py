"""The live comparison of chosen strategies (snapshot/strategy_comparison.py).

Each choice is a canonical registry id; its run must be built with that
strategy's controller, on the same seed as every other run, and its results
must be saved, listed and reproduced under that id.
"""

import copy
from typing import Any, Dict, Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.auth import (
    get_current_user_email,
    get_current_user_id,
    get_optional_user_id,
)
from src.controllers.adaptive_signal import AdaptiveSignalController
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController
from src.controllers.signalised_roundabout import SignalisedRoundaboutController
from src.database import db
from src.live import sessions
from src.live.dashboard_config import DEFAULT_CONFIG
from src.main import app
from src.snapshot.strategy_comparison import (
    LIVE_COMPARISON_STRATEGIES,
    StrategyComparisonOrchestrator,
    canonical_comparison_strategies,
    default_entry_metering,
)
from src.strategies.registry import get_strategy_registry

ALL = list(LIVE_COMPARISON_STRATEGIES)

CONTROLLER = {
    "fixed_time_signal": FixedTimeSignalController,
    "adaptive_signal": AdaptiveSignalController,
    "conventional_roundabout": RoundaboutController,
    "metered_entry_roundabout": SignalisedRoundaboutController,
}

PAYLOAD: Dict[str, Any] = {
    "intersectionType": "fixed_time_signal",
    "intersectionSize": 11.0,
    "laneWidth": 3.5,
    "lanesNorth": 1,
    "lanesSouth": 1,
    "lanesEast": 1,
    "lanesWest": 1,
    "arrivalRate": 0.4,
    "randomSeed": 42,
    "greenDuration": 25,
    "yellowDuration": 3,
    "allRedDuration": 2,
    "duration": 60,
}


def _config(seed: int = 7) -> Dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["simulation"]["randomSeed"] = seed
    config["simulation"]["duration"] = 60
    return config


def test_every_live_strategy_is_registered() -> None:
    registry = get_strategy_registry()
    assert set(LIVE_COMPARISON_STRATEGIES) <= set(registry.list_ids())


@pytest.mark.parametrize("strategy", ALL)
def test_each_strategy_runs_its_own_controller_alone(strategy: str) -> None:
    orch = StrategyComparisonOrchestrator(_config(), [strategy])
    (run,) = orch.runs
    assert run.key == strategy
    assert type(run.controller) is CONTROLLER[strategy]


def test_all_four_share_one_seed_and_keep_their_order() -> None:
    orch = StrategyComparisonOrchestrator(_config(seed=11), list(reversed(ALL)))
    assert [r.key for r in orch.runs] == list(reversed(ALL))
    for _ in range(50):
        orch.step()
    seeds = {r.engine.spawner.random_seed for r in orch.runs}
    assert seeds == {11}
    snapshot = orch.get_snapshot()
    assert [r["strategy"] for r in snapshot["runs"]] == list(reversed(ALL))
    assert snapshot["elapsed"] == pytest.approx(5.0)
    # Same arrivals everywhere: every run has spawned the same vehicles.
    spawned = {r.engine.spawner.spawned_count for r in orch.runs}
    assert len(spawned) == 1


def test_signals_differ_only_in_signal_control() -> None:
    config = _config()
    fixed, adaptive = (
        StrategyComparisonOrchestrator(config, [s]).runs[0].config
        for s in ("fixed_time_signal", "adaptive_signal")
    )
    assert "signalControl" not in fixed["controller"]
    assert adaptive["controller"]["signalControl"] == "adaptive"
    adaptive["controller"].pop("signalControl")
    adaptive["controller"].pop("adaptive", None)
    assert adaptive == fixed


def test_metered_roundabout_uses_the_scenarios_plan_or_the_default() -> None:
    config = _config()
    run = StrategyComparisonOrchestrator(config, ["metered_entry_roundabout"]).runs[0]
    assert run.config["controller"]["entryMetering"] == default_entry_metering(
        ["north", "east", "south", "west"]
    )

    plan = default_entry_metering(["north", "east", "south", "west"])
    plan["phases"][0]["green"] = 31.0
    config["controller"]["entryControl"] = "metered_entry"
    config["controller"]["entryMetering"] = plan
    metered, conventional = StrategyComparisonOrchestrator(
        config, ["metered_entry_roundabout", "conventional_roundabout"]
    ).runs
    assert metered.config["controller"]["entryMetering"]["phases"][0]["green"] == 31.0
    # The conventional roundabout never inherits the scenario's metering.
    assert "entryControl" not in conventional.config["controller"]
    assert "entryMetering" not in conventional.config["controller"]
    assert type(conventional.controller) is RoundaboutController


def test_strategy_lists_are_canonicalised_and_checked() -> None:
    assert canonical_comparison_strategies(["adaptive", "roundabout", "adaptive"]) == [
        "adaptive_signal",
        "conventional_roundabout",
    ]
    for bad in ([], "fixed_time_signal", ["nope"], None):
        with pytest.raises(ValueError):
            canonical_comparison_strategies(bad)


# ── API ────────────────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "comparison.db"))
    monkeypatch.delenv("API_KEY", raising=False)
    db.init_db()
    # Saving a run needs a signed-in user.
    app.dependency_overrides[get_current_user_id] = lambda: "alice"
    app.dependency_overrides[get_current_user_email] = lambda: "alice@example.com"
    app.dependency_overrides[get_optional_user_id] = lambda: "alice"
    try:
        with TestClient(app) as c:
            yield c
    finally:
        for dep in (get_current_user_id, get_current_user_email, get_optional_user_id):
            app.dependency_overrides.pop(dep, None)


def _session(client: TestClient) -> sessions.LiveSession:
    key = client.cookies.get(sessions.LIVE_SESSION_COOKIE)
    assert key is not None
    return sessions.live_sessions[key]


def test_strategies_endpoint_lists_the_registry(client: TestClient) -> None:
    body = client.get("/api/strategies").json()
    ids = [s["id"] for s in body["strategies"]]
    assert ids[:4] == ALL
    by_id = {s["id"]: s for s in body["strategies"]}
    assert by_id["metered_entry_roundabout"]["family"] == "roundabout"
    assert by_id["adaptive_signal"]["family"] == "signal"
    assert all(by_id[s]["liveComparison"] for s in ALL)
    assert body["liveComparison"]["maxStrategies"] == 4
    assert body["liveComparison"]["defaultSelection"] == [
        "fixed_time_signal",
        "conventional_roundabout",
    ]
    assert body["aliases"]["adaptive"] == "adaptive_signal"


def test_config_selects_strategies_and_rejects_unknown_ones(client: TestClient) -> None:
    res = client.post(
        "/api/simulation/config",
        json={**PAYLOAD, "strategies": ["adaptive_signal", "metered_entry_roundabout"]},
    )
    assert res.status_code == 200, res.text
    status = client.get("/api/simulation/comparison/status").json()
    assert status["strategies"] == ["adaptive_signal", "metered_entry_roundabout"]
    # The strategy list never leaks into the engine configuration.
    assert "strategies" not in _session(client).current_live_config

    bad = client.post("/api/simulation/config", json={**PAYLOAD, "strategies": ["x"]})
    assert bad.status_code == 400
    status = client.get("/api/simulation/comparison/status").json()
    assert status["strategies"] == ["adaptive_signal", "metered_entry_roundabout"]

    # A config without a choice is the default choice, as a reloaded
    # dashboard shows it.
    client.post("/api/simulation/config", json=PAYLOAD)
    status = client.get("/api/simulation/comparison/status").json()
    assert status["strategies"] == ["fixed_time_signal", "conventional_roundabout"]


def test_changing_only_the_strategies_rebuilds_the_comparison(
    client: TestClient,
) -> None:
    client.post("/api/simulation/config", json={**PAYLOAD, "strategies": ALL[:2]})
    client.get("/api/simulation/comparison/status")
    before = _session(client).comparison_orchestrator
    res = client.post("/api/simulation/config", json={**PAYLOAD, "strategies": ALL})
    assert res.json()["message"] == "Simulation configuration unchanged"
    assert _session(client).comparison_orchestrator is not before
    assert client.get("/api/simulation/comparison/status").json()["strategies"] == ALL


def test_a_saved_comparison_is_attributed_and_reproducible(client: TestClient) -> None:
    client.post("/api/simulation/config", json={**PAYLOAD, "strategies": ALL})
    client.get("/api/simulation/comparison/status")
    orch = _session(client).comparison_orchestrator
    assert orch is not None
    for _ in range(150):
        orch.step()

    saved = client.post(
        "/api/v1/replays",
        json={
            "name": "four-way",
            "config": {"simulation": {"randomSeed": 42}},
            "metrics": {},
            "mode": "comparison",
        },
    )
    assert saved.status_code == 200, saved.text
    run_id = saved.json()["runId"]

    record = client.get(f"/api/v1/study/history/runs/{run_id}/reproducibility").json()
    assert record["runMode"] == "comparison"
    assert list(record["summaryMetrics"]["strategies"]) == ALL
    assert record["config"]["comparison"]["strategies"] == ALL

    res = client.post(f"/api/v1/study/history/runs/{run_id}/reproduce")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "comparison"
    assert body["discrepancies"] == []
    assert body["isDeterministic"] is True
    compared = body["comparedMetrics"]
    for strategy in ALL:
        assert any(c.startswith(f"{strategy}.") for c in compared), compared
