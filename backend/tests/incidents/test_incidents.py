"""Incidents, closures, weather, surges and resilience (F13)."""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.incidents import (
    Scenario,
    evaluate_resilience,
    run_disruption,
    run_metrics,
    weather_factors,
)
from src.incidents.catalogue import PRESETS, NetworkSpec, build_network
from src.incidents.model import validate_scenario
from src.incidents.resilience import bootstrap_interval
from src.incidents.router import router
from src.incidents.weather import (
    MAX_HEADWAY_FACTOR,
    MIN_DISCHARGE,
    MIN_SATURATION_FACTOR,
    MIN_SPEED_FACTOR,
    WEATHER_KINDS,
    combine,
)
from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.networks.grid import build_three_by_three, grid_flows
from src.networks.network_sim import Flow, simulate_network

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def corridor() -> Any:
    g = build_two_junction_corridor()
    return g, [
        Flow(f.origin, f.destination, f.vehicles_per_hour * 1.8)
        for f in corridor_flows()
    ]


def grid() -> Any:
    return build_three_by_three(), grid_flows(3, 3, 800)


def sc(**kw: Any) -> Scenario:
    return Scenario.model_validate(kw)


CRASH = {"type": "crash", "links": ["J1>J2"], "start": 200, "duration": 240}
GRID_CLOSURE = {"type": "closure", "links": ["J11>J12"], "start": 150, "duration": 300}


# --- no incident: bit-identical to the original engine -----------------------


@pytest.mark.parametrize("seed", [1, 2, 7])
@pytest.mark.parametrize("which", ["corridor", "grid"])
def test_no_incident_is_bit_identical_to_simulate_network(
    seed: int, which: str
) -> None:
    g, flows = corridor() if which == "corridor" else grid()
    ref = simulate_network(g, flows, duration=600, seed=seed)
    got = run_disruption(g, flows, Scenario(), duration=600, seed=seed)
    for key in (
        "generated",
        "entered",
        "blockedAtEntry",
        "completed",
        "active",
        "conserved",
        "meanTravelSeconds",
        "meanDelaySeconds",
        "totalTravelSeconds",
        "totalDelaySeconds",
        "unroutable",
        "perLink",
        "perNode",
    ):
        assert got[key] == ref[key], key


def test_zero_severity_weather_and_unit_surge_change_nothing() -> None:
    g, flows = grid()
    ref = run_disruption(g, flows, Scenario(), duration=500, seed=4)
    scn = sc(
        weather=[{"kind": "snow", "severity": 0.0, "start": 50, "duration": 300}],
        surges=[{"start": 100, "duration": 100, "multiplier": 1.0}],
    )
    got = run_disruption(g, flows, scn, duration=500, seed=4)
    for key in ("generated", "completed", "totalDelaySeconds", "perLink"):
        assert got[key] == ref[key], key


def test_runs_are_reproducible_from_the_seed() -> None:
    g, flows = grid()
    scn = sc(incidents=[GRID_CLOSURE], weather=[{"kind": "rain", "duration": 200}])
    a = run_disruption(g, flows, scn, duration=600, seed=9, strategy="max_pressure")
    b = run_disruption(g, flows, scn, duration=600, seed=9, strategy="max_pressure")
    assert a == b


# --- conservation ------------------------------------------------------------


@pytest.mark.parametrize("strategy", ["fixed_time", "max_pressure"])
@pytest.mark.parametrize(
    "scenario",
    [
        sc(incidents=[GRID_CLOSURE]),
        sc(incidents=[{**GRID_CLOSURE, "policy": "hold"}]),
        sc(incidents=[GRID_CLOSURE], reroute=False),
        sc(  # one-lane link, every lane lost: a full block held in place
            incidents=[
                {"type": "crash", "links": ["J10>J00"], "start": 100, "duration": 250}
            ]
        ),
        sc(
            incidents=[
                {"type": "closure", "links": ["GW1>J10"], "start": 50, "duration": 400}
            ]
        ),
        sc(
            incidents=[GRID_CLOSURE],
            weather=[{"kind": "ice", "duration": 300}],
            surges=[{"start": 100, "duration": 300, "multiplier": 3.0}],
        ),
    ],
)
def test_vehicles_are_conserved_with_closures(
    strategy: str, scenario: Scenario
) -> None:
    g, flows = grid()
    r = run_disruption(g, flows, scenario, duration=700, seed=3, strategy=strategy)
    assert r["conserved"]
    assert r["generated"] == r["completed"] + r["active"] + r["blockedAtEntry"]
    assert r["entered"] == r["completed"] + r["active"]
    queued = sum(v["occupancy"] for v in r["perLink"].values())
    assert queued == r["active"]


def test_closed_first_link_turns_arrivals_away() -> None:
    g, flows = grid()
    scn = sc(
        incidents=[
            {"type": "closure", "links": ["GW1>J10"], "start": 0, "duration": 300}
        ]
    )
    r = run_disruption(g, flows, scn, duration=300, seed=1)
    assert r["blockedAtEntry"] > 0 and r["conserved"]


# --- rerouting -----------------------------------------------------------------


def test_rerouting_is_used_around_a_closure() -> None:
    g, flows = build_three_by_three(), grid_flows(3, 3, 400)
    scn = sc(incidents=[GRID_CLOSURE])
    base = run_disruption(g, flows, Scenario(), duration=700, seed=3)
    on = run_disruption(g, flows, scn, duration=700, seed=3)
    off = run_disruption(
        g, flows, sc(incidents=[GRID_CLOSURE], reroute=False), duration=700, seed=3
    )
    assert on["reroutedVehicles"] > 0 and off["reroutedVehicles"] == 0
    # Fewer vehicles use the closed link, and an outer-row link carries more.
    assert on["perLink"]["J11>J12"]["passed"] < base["perLink"]["J11>J12"]["passed"]
    assert on["perLink"]["J00>J01"]["passed"] > off["perLink"]["J00>J01"]["passed"]
    # And rerouting beats waiting out the closure.
    assert on["totalDelaySeconds"] < off["totalDelaySeconds"]
    assert any(s["fullyBlocked"] == ["J11>J12"] for s in on["segments"])


def test_no_detour_means_vehicles_wait() -> None:
    g, flows = corridor()
    scn = sc(
        incidents=[
            {"type": "closure", "links": ["J1>J2"], "start": 100, "duration": 200}
        ]
    )
    r = run_disruption(g, flows, scn, duration=600, seed=2)
    base = run_disruption(g, flows, Scenario(), duration=600, seed=2)
    assert r["reroutedVehicles"] == 0 and r["conserved"]
    assert r["totalDelaySeconds"] > base["totalDelaySeconds"]


def test_drain_lets_vehicles_on_the_link_leave_hold_does_not() -> None:
    g, flows = corridor()
    mk = lambda policy: sc(  # noqa: E731
        incidents=[
            {
                "type": "closure",
                "links": ["J1>J2"],
                "start": 150,
                "duration": 200,
                "policy": policy,
            }
        ]
    )
    drain = run_disruption(g, flows, mk("drain"), duration=349, seed=2)
    hold = run_disruption(g, flows, mk("hold"), duration=349, seed=2)
    assert drain["perLink"]["J1>J2"]["passed"] > hold["perLink"]["J1>J2"]["passed"]


# --- weather -------------------------------------------------------------------


@pytest.mark.parametrize("kind", WEATHER_KINDS)
def test_weather_factors_are_monotone_and_bounded(kind: str) -> None:
    prev = weather_factors(kind, 0.0)
    assert (prev.speed, prev.saturation, prev.headway) == (1.0, 1.0, 1.0)
    for s in (0.1, 0.25, 0.5, 0.75, 1.0):
        f = weather_factors(kind, s)
        assert f.speed <= prev.speed and f.saturation <= prev.saturation
        assert f.headway >= prev.headway and f.discharge <= prev.discharge
        assert MIN_SPEED_FACTOR <= f.speed <= 1.0
        assert MIN_SATURATION_FACTOR <= f.saturation <= 1.0
        assert 1.0 <= f.headway <= MAX_HEADWAY_FACTOR
        assert f.discharge >= MIN_DISCHARGE
        prev = f
    assert weather_factors(kind, 7.0) == weather_factors(kind, 1.0)  # clamped


def test_stacked_weather_stays_within_bounds() -> None:
    f = combine([weather_factors(k, 1.0) for k in WEATHER_KINDS] * 3)
    assert f.speed >= MIN_SPEED_FACTOR and f.headway <= MAX_HEADWAY_FACTOR
    assert f.discharge >= MIN_DISCHARGE


def test_weather_kinds_are_ordered_by_harshness() -> None:
    sp = [weather_factors(k, 1.0).speed for k in ("rain", "snow", "ice")]
    assert sp == sorted(sp, reverse=True)


@pytest.mark.parametrize("kind", WEATHER_KINDS)
@pytest.mark.parametrize("strategy", ["fixed_time", "max_pressure"])
def test_worse_weather_never_lowers_delay(kind: str, strategy: str) -> None:
    g, flows = build_three_by_three(), grid_flows(3, 3, 500)
    delays: List[float] = []
    for sev in (0.0, 0.35, 0.7, 1.0):
        scn = sc(weather=[{"kind": kind, "severity": sev, "start": 0, "duration": 600}])
        r = run_disruption(g, flows, scn, duration=600, seed=5, strategy=strategy)
        delays.append(r["totalDelaySeconds"])
    assert delays == sorted(delays), delays
    assert delays[-1] > delays[0]


# --- surges and incidents ---------------------------------------------------------


def test_surge_adds_demand_only_inside_its_window() -> None:
    g, flows = grid()
    base = run_disruption(g, flows, Scenario(), duration=600, seed=2)
    scn = sc(
        surges=[
            {
                "origin": "GW1",
                "destination": "GE1",
                "start": 100,
                "duration": 200,
                "multiplier": 3.0,
            }
        ]
    )
    r = run_disruption(g, flows, scn, duration=600, seed=2)
    assert r["generated"] > base["generated"]
    pre = [i for i, t in enumerate(r["series"]["time"]) if t <= 90]
    assert [r["series"]["entered"][i] for i in pre] == [
        base["series"]["entered"][i] for i in pre
    ]


def test_surge_validation_rejects_unmatched_flows_and_unknown_links() -> None:
    g, flows = grid()
    bad = sc(
        surges=[{"origin": "NOPE", "start": 0, "duration": 10, "multiplier": 2}],
        incidents=[{"type": "crash", "links": ["X>Y"], "start": 0, "duration": 10}],
    )
    errors = validate_scenario(g, flows, bad)
    assert len(errors) >= 3
    assert any("unknown link" in e for e in errors)


def test_crash_raises_delay_and_a_longer_crash_costs_more() -> None:
    g, flows = corridor()
    short = sc(incidents=[{**CRASH, "duration": 100}])
    long_ = sc(incidents=[{**CRASH, "duration": 400}])
    d = [
        run_disruption(g, flows, s, duration=1000, seed=1)["totalDelaySeconds"]
        for s in (Scenario(), short, long_)
    ]
    assert d[0] < d[1] < d[2]


# --- recovery time and resilience ---------------------------------------------------


def test_recovery_time_on_a_corridor() -> None:
    g, flows = corridor()
    res = evaluate_resilience(
        g, flows, sc(incidents=[CRASH]), seeds=[1, 2], duration=1200
    )
    for strat, entry in res["strategies"].items():
        assert entry["recoveredRuns"] == 2, strat
        for run in entry["perSeed"]:
            assert run["recovered"]
            assert 0.0 <= run["recoveryTimeSeconds"] <= 1200 - 440
            assert run["peakExcessDelaySeconds"] > 0
        assert entry["recoveryTimeSeconds"] is not None


def test_recovery_is_censored_when_the_run_ends_first() -> None:
    g, flows = corridor()
    closure = sc(
        incidents=[
            {
                "type": "closure",
                "links": ["J1>J2", "J2>J1"],
                "start": 100,
                "duration": 300,
            }
        ]
    )
    res = evaluate_resilience(
        g, flows, closure, strategies=["fixed_time"], seeds=[1], duration=560
    )
    run = res["strategies"]["fixed_time"]["perSeed"][0]
    assert not run["recovered"] and run["recoveryTimeSeconds"] is None
    assert run["components"]["recovery"] == 0.0


def test_unaffected_run_recovers_immediately_with_a_top_score() -> None:
    g, flows = grid()
    harmless = sc(
        weather=[{"kind": "rain", "severity": 0.0, "start": 100, "duration": 100}]
    )
    res = evaluate_resilience(g, flows, harmless, seeds=[1, 2], duration=600)
    for entry in res["strategies"].values():
        assert entry["score"] == pytest.approx(1.0, abs=1e-6)


def test_score_and_components_are_bounded_for_every_preset() -> None:
    for p in PRESETS:
        g, flows = build_network(NetworkSpec.model_validate(p["network"]))
        scn = Scenario.model_validate(p["scenario"])
        assert validate_scenario(g, flows, scn) == [], p["id"]
        res = evaluate_resilience(g, flows, scn, seeds=[1, 2], duration=p["duration"])
        assert set(res["strategies"]) == {"fixed_time", "max_pressure"}
        for entry in res["strategies"].values():
            assert 0.0 <= entry["score"] <= 1.0, p["id"]
            lo, hi = entry["scoreInterval"]
            assert (
                0.0 <= lo <= entry["score"] + 1e-9
                and entry["score"] - 1e-9 <= hi <= 1.0
            )
            for run in entry["perSeed"]:
                assert run["conserved"]
                assert all(0.0 <= v <= 1.0 for v in run["components"].values())
                assert 0.0 <= run["score"] <= 1.0
                assert 0.0 <= run["throughputLoss"] <= 1.0


def test_a_harsher_disruption_scores_lower() -> None:
    g, flows = corridor()
    mild = sc(incidents=[{**CRASH, "duration": 60}])
    harsh = sc(incidents=[{**CRASH, "duration": 300, "lanesBlocked": 2}])
    s = lambda scn: evaluate_resilience(  # noqa: E731
        g, flows, scn, strategies=["fixed_time"], seeds=[1, 2], duration=1200
    )["strategies"]["fixed_time"]["score"]
    assert s(mild) > s(harsh)


def test_single_seed_has_no_interval_and_bootstrap_is_deterministic() -> None:
    assert bootstrap_interval([0.5]) is None
    assert bootstrap_interval([0.4, 0.5, 0.6]) == bootstrap_interval([0.4, 0.5, 0.6])
    g, flows = corridor()
    res = evaluate_resilience(g, flows, sc(incidents=[CRASH]), seeds=[1], duration=1000)
    assert res["strategies"]["fixed_time"]["scoreInterval"] is None


def test_evaluate_rejects_bad_input() -> None:
    g, flows = corridor()
    with pytest.raises(ValueError):
        evaluate_resilience(g, flows, Scenario())
    with pytest.raises(ValueError):
        evaluate_resilience(g, flows, sc(incidents=[CRASH]), duration=470)
    with pytest.raises(ValueError):
        evaluate_resilience(g, flows, sc(incidents=[CRASH]), seeds=[])
    with pytest.raises(ValueError):
        run_disruption(g, flows, Scenario(), strategy="nope")


def test_run_metrics_on_identical_runs_is_perfect() -> None:
    g, flows = corridor()
    a = run_disruption(g, flows, Scenario(), duration=600, seed=1)
    m = run_metrics(a, a, 200.0, 600.0)
    assert m["score"] == pytest.approx(1.0) and m["recoveryTimeSeconds"] == 0.0
    assert m["peakExcessDelaySeconds"] == 0.0


# --- router -------------------------------------------------------------------------


def test_catalogue_route() -> None:
    r = client.get("/api/v2/incidents/catalogue")
    assert r.status_code == 200
    body = r.json()
    assert body["inModelOnly"] is True
    assert {s["id"] for s in body["scenarios"]} == {p["id"] for p in PRESETS}
    assert set(body["weather"]["fullSeverityFactors"]) == set(WEATHER_KINDS)
    assert sum(body["scoreFormula"]["weights"].values()) == pytest.approx(1.0)
    assert "stressLabExtension" in body


def test_simulate_route_with_a_preset() -> None:
    r = client.post(
        "/api/v2/incidents/simulate",
        json={"preset": "grid-closure-detour", "duration": 700, "seed": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run"]["conserved"] and body["baseline"]["conserved"]
    assert body["run"]["reroutedVehicles"] > 0
    assert 0.0 <= body["metrics"]["score"] <= 1.0
    assert len(body["run"]["series"]["time"]) == len(
        body["run"]["series"]["meanAccruedDelay"]
    )


def test_simulate_route_without_baseline_or_scenario() -> None:
    r = client.post(
        "/api/v2/incidents/simulate", json={"compareBaseline": False, "duration": 120}
    )
    assert r.status_code == 200
    assert "baseline" not in r.json()
    ref = simulate_network(*corridor_default(), duration=120, seed=1)
    assert r.json()["run"]["completed"] == ref["completed"]


def corridor_default() -> Any:
    g, flows = build_network(NetworkSpec())
    return g, flows


def test_simulate_route_with_a_custom_graph() -> None:
    g, flows = corridor()
    from src.networks.graph import serialize_graph

    body: Dict[str, Any] = {
        "graph": serialize_graph(g),
        "flows": [
            {
                "origin": f.origin,
                "destination": f.destination,
                "vehiclesPerHour": f.vehicles_per_hour,
            }
            for f in flows
        ],
        "scenario": {"incidents": [CRASH]},
        "duration": 800,
        "strategy": "max_pressure",
    }
    r = client.post("/api/v2/incidents/simulate", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["run"]["strategy"] == "max_pressure"


def test_resilience_route() -> None:
    r = client.post(
        "/api/v2/incidents/resilience",
        json={"preset": "corridor-crash", "seeds": [1, 2], "includeSeries": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["best"] in body["strategies"]
    for entry in body["strategies"].values():
        assert 0.0 <= entry["score"] <= 1.0
        assert entry["scoreInterval"] is not None and len(entry["series"]) == 2
    assert body["scoreFormula"]["weights"]


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/v2/incidents/simulate", {"preset": "nope"}),
        (
            "/api/v2/incidents/simulate",
            {
                "scenario": {
                    "incidents": [
                        {"type": "crash", "links": ["ZZ"], "start": 0, "duration": 5}
                    ]
                }
            },
        ),
        ("/api/v2/incidents/simulate", {"strategy": "random"}),
        ("/api/v2/incidents/simulate", {"graph": {"nodes": []}, "flows": []}),
        ("/api/v2/incidents/resilience", {"scenario": {}}),  # nothing to measure
        ("/api/v2/incidents/resilience", {"preset": "corridor-crash", "seeds": []}),
        ("/api/v2/incidents/resilience", {"preset": "corridor-crash", "duration": 300}),
        (
            "/api/v2/incidents/resilience",
            {"preset": "corridor-crash", "seeds": list(range(11))},
        ),
        (
            "/api/v2/incidents/resilience",
            {
                "preset": "corridor-crash",
                "network": {"kind": "grid", "rows": 12, "cols": 12},
                "scenario": {"weather": [{"kind": "fog", "duration": 100}]},
                "duration": 3600,
                "seeds": list(range(10)),
            },
        ),
    ],
)
def test_bad_requests_are_422(path: str, body: Dict[str, Any]) -> None:
    assert client.post(path, json=body).status_code == 422
