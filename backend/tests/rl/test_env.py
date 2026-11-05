"""SignalControlEnv: spaces, determinism, reward, truncation."""

import pytest

pytest.importorskip("numpy")
pytest.importorskip("gymnasium")

import numpy as np  # noqa: E402

from src.rl.env import OBS_SIZE, SignalControlEnv  # noqa: E402

SMALL = {"episode_seconds": 60.0, "decision_interval": 5.0, "vehicles_per_hour": 600.0}


def _rollout(seed, actions):
    env = SignalControlEnv(**SMALL)
    obs, _ = env.reset(seed=seed)
    trace = [obs.copy()]
    rewards = []
    for a in actions:
        obs, r, _term, _trunc, _ = env.step(a)
        trace.append(obs.copy())
        rewards.append(r)
    return np.array(trace), np.array(rewards), env.episode_metrics()


def test_spaces_and_reset_shape():
    env = SignalControlEnv(**SMALL)
    obs, info = env.reset(seed=1)
    assert obs.shape == (OBS_SIZE,) and obs.dtype == np.float32
    assert env.observation_space.contains(obs)
    assert env.action_space.n == 2
    assert info["episode_seed"] == 1


def test_same_seed_same_actions_is_identical():
    actions = [0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0]
    a = _rollout(7, actions)
    b = _rollout(7, actions)
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1])
    assert a[2] == b[2]


def test_different_seeds_differ():
    actions = [0, 1] * 6
    a = _rollout(7, actions)
    b = _rollout(8, actions)
    assert not np.array_equal(a[0], b[0])


def test_unseeded_episodes_follow_the_env_generator():
    def seeds():
        env = SignalControlEnv(**SMALL)
        env.reset(seed=5)
        out = []
        for _ in range(3):
            _, info = env.reset()
            out.append(info["episode_seed"])
        return out

    assert seeds() == seeds()


def test_reward_is_negative_delay_and_episode_truncates():
    env = SignalControlEnv(**SMALL)
    env.reset(seed=2)
    total, steps, truncated = 0.0, 0, False
    info = {}
    while not truncated:
        _, r, terminated, truncated, info = env.step(steps % 2)
        assert r <= 0.0 and not terminated
        total += r
        steps += 1
    assert steps == 12  # 60 s / 5 s
    assert total < 0.0
    assert info["sim_time"] == pytest.approx(60.0)


def test_step_before_reset_raises():
    with pytest.raises(RuntimeError):
        SignalControlEnv(**SMALL).step(0)


def test_bad_parameters_rejected():
    with pytest.raises(ValueError):
        SignalControlEnv(reward_mode="nope")
    with pytest.raises(ValueError):
        SignalControlEnv(episode_seconds=1.0, decision_interval=5.0)


def test_gymnasium_env_checker_passes():
    from gymnasium.utils.env_checker import check_env

    check_env(SignalControlEnv(**SMALL), skip_render_check=True)
