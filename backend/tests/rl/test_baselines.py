"""Baselines and the evaluation loop (no training dependency)."""

import pytest

pytest.importorskip("numpy")
pytest.importorskip("gymnasium")

from src.rl.baselines import FixedTimePolicy, MaxPressurePolicy  # noqa: E402
from src.rl.evaluate import METRICS, compare, held_out_seeds  # noqa: E402

SMALL = {"episode_seconds": 40.0, "decision_interval": 5.0, "vehicles_per_hour": 500.0}


def test_fixed_time_alternates():
    p = FixedTimePolicy(green_s=30.0)
    assert [p.act(None, {"sim_time": t}) for t in (0, 29, 30, 59, 60)] == [0, 0, 1, 1, 0]
    with pytest.raises(ValueError):
        FixedTimePolicy(0)


def test_max_pressure_prefers_the_longer_queue_with_hysteresis():
    p = MaxPressurePolicy(switch_margin=1.0)
    q = {"north": 1.0, "south": 0.0, "east": 6.0, "west": 5.0}
    assert p.act(None, {"queues": q, "active_green": 0}) == 1
    even = {"north": 3.0, "south": 3.0, "east": 3.0, "west": 3.0}
    assert p.act(None, {"queues": even, "active_green": 0}) == 0
    assert p.act(None, {"queues": even, "active_green": 1}) == 1


def test_compare_emits_per_seed_arrays_for_each_policy():
    seeds = held_out_seeds(2)
    out = compare(seeds, SMALL)
    assert out["seeds"] == seeds
    assert set(out["policies"]) == {"fixed_time", "max_pressure"}
    for res in out["policies"].values():
        for m in METRICS:
            assert len(res[m]) == 2
    again = compare(seeds, SMALL)  # deterministic given the seeds
    for name in out["policies"]:
        for m in METRICS:
            assert out["policies"][name][m] == again["policies"][name][m]


def test_max_pressure_switches_toward_demand_in_the_loop():
    """Heavy east-west demand: max-pressure must give east-west some green."""
    from src.rl.env import SignalControlEnv

    env = SignalControlEnv(episode_seconds=60.0, vehicles_per_hour=300.0, ns_share=0.2)
    policy = MaxPressurePolicy()
    _, info = env.reset(seed=4)
    greens = set()
    done = False
    while not done:
        _, _, _, done, info = env.step(policy.act(None, info))
        greens.add(info["active_green"])
    assert 1 in greens
    assert env.episode_metrics()["throughput"] > 0
