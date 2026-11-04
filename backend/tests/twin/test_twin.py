"""Digital twin core: replay, comparison metrics, runner, what-if, endpoints."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.twin.compare import best_lag, compare, series_metrics
from src.twin.models import Observation
from src.twin.router import router
from src.twin.runner import TwinRunner
from src.twin.sources import ObservationSource, ReplaySource, StubLiveSource
from src.twin.whatif import Scenario, apply_scenario, what_if

FIXTURE = Path(__file__).parent / "fixtures" / "corridor_observations.csv"


def _obs(link: str, t: float, n: int, v=None) -> Observation:
    return Observation(link_id=link, timestamp=t, count=n, mean_speed=v)


# -- sources ---------------------------------------------------------------
def test_replay_is_deterministic_and_ordered() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    a = ReplaySource.from_csv(text).poll(10**9)
    b = ReplaySource.from_csv(text).poll(10**9)
    assert a == b
    assert [(o.timestamp, o.link_id) for o in a] == sorted(
        (o.timestamp, o.link_id) for o in a
    )
    assert len(a) == 9


def test_replay_poll_drains_and_pacing_is_deterministic() -> None:
    src = ReplaySource.from_csv(FIXTURE.read_text(encoding="utf-8"), speedup=60.0)
    assert isinstance(src, ObservationSource)
    sleeps: list = []
    batches = list(src.paced(60.0, sleep=sleeps.append))
    assert [len(b) for b in batches] == [3, 3, 3]
    assert sleeps == [1.0, 1.0, 1.0]  # 60 s of recording per wall second
    assert src.poll(10**9) == []
    sched = ReplaySource.from_csv(
        FIXTURE.read_text(encoding="utf-8"), speedup=30.0
    ).schedule()
    assert [round(w, 6) for w, _ in sched][::3] == [0.0, 2.0, 4.0]


def test_replay_jsonl_matches_csv_and_rejects_bad_speedup() -> None:
    lines = "\n".join(
        json.dumps({"linkId": "W>J1", "timestamp": t, "count": c})
        for t, c in [(0, 5), (60, 7)]
    )
    assert [o.count for o in ReplaySource.from_jsonl(lines).poll(1000)] == [5, 7]
    with pytest.raises(ValueError):
        ReplaySource([], speedup=0)


def test_stub_live_source_never_connects_and_drains() -> None:
    stub = StubLiveSource(endpoint="kafka://not-used")
    assert isinstance(stub, ObservationSource)
    stub.push(_obs("W>J1", 70, 4))
    stub.push(_obs("W>J1", 10, 3))
    assert [o.timestamp for o in stub.poll(60)] == [10]
    assert [o.timestamp for o in stub.poll(120)] == [70]
    assert stub.poll(120) == []


# -- comparison metrics (hand computed) ---------------------------------------
def test_series_metrics_hand_computed() -> None:
    # predicted 12, 8, 15 vs observed 10, 10, 10: errors +2, -2, +5
    m = series_metrics([12, 8, 15], [10, 10, 10])
    assert m["mae"] == pytest.approx(3.0)
    assert m["bias"] == pytest.approx(5 / 3, abs=1e-5)
    assert m["mape"] == pytest.approx((20 + 20 + 50) / 3)
    # a zero observation is left out of MAPE but not of MAE
    z = series_metrics([1, 4], [0, 2])
    assert z["mae"] == pytest.approx(1.5)
    assert z["mape"] == pytest.approx(100.0)
    assert series_metrics([1], [0])["mape"] is None


def test_compare_per_link_network_and_alerts() -> None:
    predicted = {0: {"a": 10, "b": 20}, 1: {"a": 14, "b": 30}}
    observed = {0: {"a": 10, "b": 10}, 1: {"a": 10, "b": 30}}
    r = compare(predicted, observed, interval=60.0, alert_threshold_pct=30.0)
    assert r["perLink"]["a"]["mae"] == pytest.approx(2.0)  # |0|, |4|
    assert r["perLink"]["a"]["mape"] == pytest.approx(20.0)
    assert r["perLink"]["b"]["bias"] == pytest.approx(5.0)  # +10, 0
    # network totals: predicted 30, 44 vs observed 20, 40
    assert [s["error"] for s in r["series"]] == [10, 4]
    assert r["network"]["mae"] == pytest.approx(7.0)
    assert r["network"]["mape"] == pytest.approx((50 + 10) / 2)
    assert r["network"]["bias"] == pytest.approx(7.0)
    # window 0 is 50 % off (alert); window 1 is 10 %; overall 30 % is not above 30
    assert [(a["kind"], a["window"]) for a in r["alerts"]] == [("window", 0)]
    assert r["alert"] is True
    quiet = compare(predicted, observed, 60.0, alert_threshold_pct=60.0)
    assert quiet["alert"] is False and quiet["alerts"] == []


def test_best_lag_detects_a_shift() -> None:
    observed = [0, 0, 10, 20, 10, 0, 0, 0]
    predicted = [0, 10, 20, 10, 0, 0, 0, 0]  # runs one window early
    assert best_lag(predicted, observed) == 1
    assert best_lag(observed, observed) == 0
    r = compare(
        {k: {"a": v} for k, v in enumerate(predicted)},
        {k: {"a": v} for k, v in enumerate(observed)},
        interval=60.0,
    )
    assert r["network"]["lagWindows"] == 1 and r["network"]["lagSeconds"] == 60.0


# -- runner ----------------------------------------------------------------
def _twin() -> TwinRunner:
    twin = TwinRunner(
        build_two_junction_corridor(),
        corridor_flows(),
        interval=60.0,
        warmup=120.0,
        seed=3,
    )
    twin.ingest(ReplaySource.from_csv(FIXTURE.read_text(encoding="utf-8")).poll(10**9))
    twin.run()
    return twin


def test_runner_is_deterministic_and_state_is_json() -> None:
    a, b = _twin().state(), _twin().state()
    assert a == b
    assert json.loads(json.dumps(a)) == a
    assert a["format"] == "urbanflow-twin-state"
    assert [w["window"] for w in a["timeline"]] == [0, 1, 2]
    assert a["comparison"]["network"]["n"] == 3


def test_runner_demand_follows_observations() -> None:
    twin = TwinRunner(build_two_junction_corridor(), corridor_flows(), interval=60.0)
    assert twin.current_flows() == corridor_flows()
    # W>J1 carried 20 veh in 60 s = 1200 veh/h: twice the 600 veh/h base from W
    twin.ingest([_obs("W>J1", 0, 20), _obs("J1>J2", 0, 20), _obs("W>J1", 1000, 1)])
    flows = {
        (f.origin, f.destination): f.vehicles_per_hour for f in twin.implied_flows(0)
    }
    assert flows[("W", "E")] == pytest.approx(1200.0)
    assert flows[("N1", "S2")] == pytest.approx(150.0)  # unobserved origin keeps base
    # unknown links and pre-start data are ignored
    assert twin.ingest([_obs("nope", 0, 1)]) == 0


# -- what-if ----------------------------------------------------------------
def test_apply_scenario_changes_a_copy_and_rejects_unknown_links() -> None:
    g = build_two_junction_corridor()
    v, flows = apply_scenario(
        g,
        corridor_flows(),
        Scenario(close_links=["J1>J2"], lanes={"W>J1": 1}, demand_scale=2.0),
    )
    assert "J1>J2" in g.link_map() and "J1>J2" not in v.link_map()
    assert v.link_map()["W>J1"].lanes == 1 and g.link_map()["W>J1"].lanes == 2
    assert flows[0].vehicles_per_hour == 1200.0
    with pytest.raises(ValueError):
        apply_scenario(g, [], Scenario(close_links=["X>Y"]))


def test_what_if_reduced_capacity_raises_delay_on_the_corridor() -> None:
    twin = TwinRunner(
        build_two_junction_corridor(), corridor_flows(), interval=300.0, warmup=300.0
    )
    r = what_if(twin, Scenario(lanes={"J1>J2": 1}, demand_scale=1.6))
    assert r["delta"]["meanDelaySeconds"] > 10.0
    assert r["variant"]["meanDelaySeconds"] > r["baseline"]["meanDelaySeconds"]
    assert what_if(twin, Scenario(lanes={"J1>J2": 1}))["delta"]["meanDelaySeconds"] > 0


def test_what_if_closing_a_link_stops_downstream_flow() -> None:
    twin = TwinRunner(
        build_two_junction_corridor(), corridor_flows(), interval=300.0, warmup=300.0
    )
    r = what_if(twin, Scenario(close_links=["J1>J2"]))
    assert r["perLink"]["J1>J2"]["variant"] is None
    assert r["perLink"]["J2>E"]["delta"] < 0
    assert "W->E" in r["variant"]["unroutable"]
    assert r["delta"]["completed"] < 0
    assert twin.predicted == {}  # the fork leaves the twin untouched


# -- endpoints --------------------------------------------------------------
def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _body() -> dict:
    obs = [
        {"linkId": o.link_id, "timestamp": o.timestamp, "count": o.count}
        for o in ReplaySource.from_csv(FIXTURE.read_text(encoding="utf-8")).poll(10**9)
    ]
    return {"observations": obs, "seed": 3}


def test_compare_endpoint_shape_and_repeatability() -> None:
    c = _client()
    r = c.post("/api/v2/twin/compare", json=_body())
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"timeline", "comparison", "currentFlows", "latestWindow"}
    assert set(body["comparison"]) >= {
        "network",
        "perLink",
        "series",
        "alert",
        "alerts",
    }
    assert c.post("/api/v2/twin/compare", json=_body()).json() == body


def test_whatif_endpoint_and_validation() -> None:
    c = _client()
    body = _body() | {
        "intervalSeconds": 300,
        "warmupSeconds": 300,
        "scenario": {"lanes": {"J1>J2": 1}, "demandScale": 1.6},
    }
    r = c.post("/api/v2/twin/whatif", json=body)
    assert r.status_code == 200
    assert r.json()["delta"]["meanDelaySeconds"] > 0
    bad = _body() | {"scenario": {"closeLinks": ["nope"]}}
    assert c.post("/api/v2/twin/whatif", json=bad).status_code == 400
    assert (
        c.post(
            "/api/v2/twin/compare", json={"observations": [{"linkId": "x"}]}
        ).status_code
        == 422
    )
