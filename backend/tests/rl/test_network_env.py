"""NetworkSignalEnv, network baselines, evaluation shape and paired comparisons."""

import json

import pytest

pytest.importorskip("numpy")
pytest.importorskip("gymnasium")

import numpy as np  # noqa: E402

from src.rl.network_baselines import NetworkFixedTime, NetworkMaxPressure  # noqa: E402
from src.rl.network_env import NODE_FEATURES, NetworkSignalEnv  # noqa: E402
from src.rl.network_eval import (  # noqa: E402
    compare_network,
    evaluate_network_policy,
    held_out_seeds,
)

SMALL = {"episode_seconds": 60.0, "decision_interval": 5.0}


def _rollout(seed, actions):
    env = NetworkSignalEnv(**SMALL)
    obs, _ = env.reset(seed=seed)
    trace, rewards = [obs.copy()], []
    for a in actions:
        obs, r, _t, _tr, _ = env.step(a)
        trace.append(obs.copy())
        rewards.append(r)
    return np.array(trace), np.array(rewards), env.episode_metrics()


def test_spaces_and_shapes():
    env = NetworkSignalEnv(**SMALL)
    n = len(env.signal_nodes)
    assert n == 4
    assert env.action_space.shape == (n,)
    assert env.observation_space.shape == (n * NODE_FEATURES,)
    obs, info = env.reset(seed=1)
    assert obs.shape == env.observation_space.shape
    assert env.observation_space.contains(obs)
    assert set(info["nodes"]) == set(env.signal_nodes)


def test_deterministic_given_seed_and_actions():
    acts = [np.array([i % 2] * 4) for i in range(12)]
    t1, r1, m1 = _rollout(5, acts)
    t2, r2, m2 = _rollout(5, acts)
    assert np.array_equal(t1, t2) and np.array_equal(r1, r2) and m1 == m2
    _, r3, _ = _rollout(6, acts)
    assert not np.array_equal(r1, r3)


def test_truncates_and_rewards_are_nonpositive():
    env = NetworkSignalEnv(**SMALL)
    env.reset(seed=0)
    done, steps, rewards = False, 0, []
    while not done:
        _o, r, term, trunc, _i = env.step(np.zeros(4, dtype=int))
        rewards.append(r)
        done = term or trunc
        steps += 1
    assert steps == 12 and max(rewards) <= 0.0 and min(rewards) < 0.0


def test_min_green_blocks_early_switch_and_wrong_shape_rejected():
    env = NetworkSignalEnv(episode_seconds=60.0, decision_interval=1.0, min_green=5.0)
    env.reset(seed=0)
    _o, _r, _t, _tr, info = env.step(np.ones(4, dtype=int))  # t=1 < min_green: held
    assert all(v["active_phase"] == 0 for v in info["nodes"].values())
    with pytest.raises(ValueError):
        env.step(np.ones(3, dtype=int))
    with pytest.raises(RuntimeError):
        NetworkSignalEnv(**SMALL).step(np.zeros(4, dtype=int))


def test_invalid_construction():
    with pytest.raises(ValueError):
        NetworkSignalEnv(reward_mode="x")
    with pytest.raises(ValueError):
        NetworkSignalEnv(episode_seconds=1.0, decision_interval=5.0)


def test_baselines_act_per_node():
    env = NetworkSignalEnv(**SMALL)
    obs, info = env.reset(seed=1)
    fixed = NetworkFixedTime(env.signal_nodes, 10.0)
    assert fixed.act(obs, {**info, "sim_time": 0.0}).tolist() == [0] * 4
    assert fixed.act(obs, {**info, "sim_time": 10.0}).tolist() == [1] * 4
    mp = NetworkMaxPressure(env.signal_nodes, switch_margin=0.5, min_hold_s=0.0)
    nid = env.signal_nodes[0]
    info["nodes"][nid].update(
        pressure={"ew": 0.0, "ns": 5.0},
        active_phase=0,
        in_transition=False,
        time_in_phase=99.0,
    )
    assert mp.act(obs, info)[0] == 1
    info["nodes"][nid]["pressure"] = {"ew": 5.0, "ns": 0.0}
    assert mp.act(obs, info)[0] == 0


def test_compare_network_shape_and_paired_comparisons():
    seeds = held_out_seeds(3)
    # a "random" stand-in for an RL policy keeps this independent of training
    rng = np.random.default_rng(0)
    doc = compare_network(seeds, SMALL, {"rl_ppo": lambda o, i: rng.integers(0, 2, 4)})
    assert doc["format"] == "urbanflow-rl-eval" and doc["seeds"] == seeds
    assert set(doc["policies"]) == {"fixed_time", "max_pressure", "rl_ppo"}
    for pol in doc["policies"].values():
        assert len(pol["mean_wait_s"]) == 3
    rows = [r for r in doc["paired_comparisons"] if r["metric"] == "mean_wait_s"]
    assert {r["baseline"] for r in rows} == {"fixed_time", "max_pressure"}
    assert rows[0]["comparison"]["n_pairs"] == 3 and "interval" in rows[0]["verdict"]
    assert doc["cautions"]
    json.dumps(doc)


def test_evaluation_is_paired_and_repeatable():
    env = NetworkSignalEnv(**SMALL)
    pol = NetworkFixedTime(env.signal_nodes, 30.0)
    a = evaluate_network_policy(pol.act, [1, 2], SMALL)
    b = evaluate_network_policy(pol.act, [1, 2], SMALL)
    assert a == b and a["throughput"][0] >= 0
