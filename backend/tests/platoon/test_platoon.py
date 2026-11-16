import random
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platoon import control as fsm
from src.platoon.analysis import string_stability, throughput_vph
from src.platoon.experiment import ExperimentSpec, channel_sweep, run_experiment
from src.platoon.router import router
from src.platoon.sim import (
    ScenarioSpec,
    SimConfig,
    Simulation,
    build,
    make_channel,
    run,
)

SEEDS = list(range(1, 9))


# -- safety ---------------------------------------------------------------


@pytest.mark.parametrize("mode", ["cacc", "idm"])
def test_no_collisions_under_hard_brake(mode: str) -> None:
    spec = ScenarioSpec(vehicles=12, duration=120.0, pulse_decel=6.0, pulse_s=3.0)
    for seed in SEEDS:
        res = run(spec, mode, seed)
        assert res.collisions == 0
        assert res.min_gap_m > 0.0


def test_no_collisions_with_latency_and_loss() -> None:
    spec = ScenarioSpec(
        vehicles=12,
        duration=120.0,
        pulse_decel=6.0,
        channel=make_channel(0.2, 0.4),
        cfg=SimConfig(reaction_s=0.6),
    )
    for seed in SEEDS:
        res = run(spec, "cacc", seed)
        assert res.collisions == 0 and res.min_gap_m > 0.0


# -- stability and throughput ---------------------------------------------


def test_cacc_string_stable_while_idm_amplifies_at_small_time_gap() -> None:
    cacc = string_stability(10, 0.3, "cacc", speed=15.0, reaction_s=1.0)
    idm = string_stability(10, 0.3, "idm", speed=15.0, reaction_s=1.0)
    assert cacc["stable"] and cacc["stepRatioMax"] < 1.0
    assert not idm["stable"] and idm["stepRatioMax"] > 1.0
    assert cacc["amplification"] < idm["amplification"]


def test_cacc_degrades_with_heavy_latency() -> None:
    ok = string_stability(10, 0.3, "cacc", speed=15.0)
    bad = string_stability(10, 0.3, "cacc", speed=15.0, channel=make_channel(0.3))
    assert bad["stepRatioMax"] > ok["stepRatioMax"]


def test_throughput_cacc_beats_idm_at_same_speed() -> None:
    assert throughput_vph(25.0, "cacc", 0.6) > 2 * throughput_vph(25.0, "idm", 1.5)
    spec = ScenarioSpec(vehicles=8, duration=150.0)
    assert run(spec, "cacc", 1).throughput_vph > run(spec, "idm", 1).throughput_vph


# -- FSM -------------------------------------------------------------------


def test_transition_table_rejects_invalid_events() -> None:
    assert fsm.transition(fsm.FOLLOWER, "message_stale") == fsm.FALLBACK
    with pytest.raises(ValueError):
        fsm.transition(fsm.FREE, "join_complete")


def _two_platoons() -> Tuple[Simulation, int, int]:
    sim = build(ScenarioSpec(vehicles=6, duration=100.0, jitter=0.0), "idm", 1)
    front = sim.form([0, 1, 2])
    rear = sim.form([3, 4, 5])
    return sim, front, rear


def test_merge_makes_rear_leader_a_follower() -> None:
    sim, front, rear = _two_platoons()
    assert sim.vs[3].state == fsm.LEADER
    assert sim.merge(front, rear)
    assert sim.vs[3].state == fsm.JOINING
    assert sim.platoons[front] == [0, 1, 2, 3, 4, 5] and rear not in sim.platoons
    for _ in range(1500):
        sim.step()
    assert all(v.state == fsm.FOLLOWER for v in sim.vs[1:])
    assert sim.collisions == 0


def test_merge_refused_when_too_large_or_not_adjacent() -> None:
    sim, front, rear = _two_platoons()
    sim.cfg = replace(sim.cfg, max_size=5)
    assert not sim.merge(front, rear)
    assert not sim.merge(rear, front)


def test_split_creates_new_leader_with_wider_gap() -> None:
    sim = build(ScenarioSpec(vehicles=6, duration=100.0, jitter=0.0), "cacc", 1)
    sim.schedule_split(0, 3, at_time=5.0)
    for _ in range(1200):
        sim.step()
    assert sim.vs[3].state == fsm.LEADER
    assert sorted(len(m) for m in sim.platoons.values()) == [3, 3]
    assert sim._gap(3) > 2 * sim._gap(2)
    assert sim.collisions == 0
    assert sim.split(0, 0) is None  # cannot split at the head


def test_split_by_position() -> None:
    sim = build(ScenarioSpec(vehicles=4, duration=60.0, jitter=0.0), "cacc", 1)
    sim.schedule_split(0, 2, at_position=sim.vs[0].x + 1000.0)
    for _ in range(300):
        sim.step()
    assert sim.vs[2].state == fsm.FOLLOWER
    for _ in range(200):
        sim.step()
    assert sim.vs[2].state == fsm.LEADER


def test_auto_formation_from_free_vehicles() -> None:
    spec = ScenarioSpec(
        vehicles=4, duration=200.0, jitter=0.0, cfg=SimConfig(auto_form=True)
    )
    sim = build(spec, "idm", 1)
    assert all(v.state == fsm.FREE for v in sim.vs)
    for _ in range(2000):
        sim.step()
    assert sim.vs[0].state == fsm.LEADER
    assert all(v.state == fsm.FOLLOWER for v in sim.vs[1:])
    assert len(sim.platoons) == 1 and sim.collisions == 0


def test_slot_conflict_rule_is_deterministic() -> None:
    reqs = [
        fsm.SlotRequest(7, (0, 3), 20.0),
        fsm.SlotRequest(5, (0, 3), 12.0),
        fsm.SlotRequest(5, (0, 4), 30.0),
        fsm.SlotRequest(9, (0, 3), 12.0),
    ]
    granted, denied = fsm.resolve_slot_conflicts(reqs)
    assert [(r.vehicle_id, r.slot) for r in granted] == [(5, (0, 3))]
    assert len(denied) == 3
    shuffled = reqs[:]
    random.Random(1).shuffle(shuffled)
    assert fsm.resolve_slot_conflicts(shuffled)[0] == granted


# -- stale-message fallback -------------------------------------------------


def test_stale_messages_trigger_fallback_then_recovery() -> None:
    def blackout(t: float, receiver: int, rng: random.Random) -> Optional[float]:
        return None if 20.0 <= t < 40.0 else 0.0

    spec = ScenarioSpec(vehicles=6, duration=120.0, pulse_decel=5.0, channel=blackout)
    sim = build(spec, "cacc", 3)
    seen: List[str] = []
    for k in range(1200):
        sim.step()
        if k == 350:
            seen = [v.state for v in sim.vs[1:]]
    assert seen == [fsm.FALLBACK] * 5
    assert all(v.state == fsm.FOLLOWER for v in sim.vs[1:])
    assert sim.collisions == 0 and sim.min_gap_seen > 0.0
    assert any(new == fsm.FALLBACK for _, _, _, new in sim.log)


# -- determinism and experiment --------------------------------------------


def test_determinism() -> None:
    spec = ScenarioSpec(vehicles=6, duration=60.0, channel=make_channel(0.1, 0.2, 0.05))
    a, b = run(spec, "cacc", 4), run(spec, "cacc", 4)
    assert a.speeds == b.speeds and a.min_gap_m == b.min_gap_m
    assert run(spec, "cacc", 5).speeds != a.speeds


def test_experiment_paired_comparison_and_sweep() -> None:
    spec = ExperimentSpec(vehicles=8, duration=100.0, seeds=(1, 2, 3))
    out = run_experiment(spec)
    thr = out["metrics"]["throughputVph"]
    assert thr["changePct"] > 50 and thr["comparison"]["direction"] == "a_higher"
    assert out["safety"]["platoonCollisions"] == 0
    assert "fuelLPer100Km" in out["metrics"] and out["isEstimate"]
    cells = channel_sweep(spec, [0.0, 0.3], [0.0, 0.5])
    assert len(cells) == 4 and all(c["collisions"] == 0 for c in cells)
    with pytest.raises(ValueError):
        run_experiment(replace(spec, seeds=(1,)))


# -- router -----------------------------------------------------------------

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_catalogue() -> None:
    body = client.get("/api/v2/platoon/catalogue").json()
    assert "FALLBACK" in body["states"] and body["limits"]["vehicles"] == 20
    assert {"from": "FOLLOWER", "event": "split", "to": "LEADER"} in body["transitions"]


def test_experiment_endpoint() -> None:
    r = client.post(
        "/api/v2/platoon/experiment",
        json={
            "vehicles": 6,
            "durationSeconds": 60,
            "seeds": [1, 2],
            "channelSweep": {"latenciesMs": [0], "lossProbabilities": [0, 0.3]},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    thr = body["metrics"]["throughputVph"]
    assert thr["platoonMean"] > thr["humanMean"]
    assert len(body["channelSweep"]) == 2
    assert body["throughputSteadyState"]["cacc"] > body["throughputSteadyState"]["idm"]


@pytest.mark.parametrize(
    "payload",
    [
        {"vehicles": 21},
        {"durationSeconds": 601},
        {"seeds": list(range(11))},
        {"seeds": [1]},
        {"method": "nope"},
        {
            "vehicles": 20,
            "durationSeconds": 600,
            "seeds": list(range(10)),
            "channelSweep": {},
        },
    ],
)
def test_experiment_bounds(payload: Dict[str, Any]) -> None:
    assert client.post("/api/v2/platoon/experiment", json=payload).status_code == 422
