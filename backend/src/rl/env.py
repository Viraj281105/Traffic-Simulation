"""Gymnasium environment around one signalised junction (F18).

* **Action** -- ``Discrete(2)``: the green to show for the next decision
  interval (0 = north-south, 1 = east-west). Yellow and all-red clearance and
  a minimum green are enforced by :class:`ExternalPhaseController`, so the
  agent cannot make the junction unsafe, only inefficient.
* **Observation** -- ``Box(12,)`` in [0, 1]: per approach (N, S, E, W) the
  stopped-vehicle queue and the vehicles on the approach (both divided by
  ``queue_cap``), then the active green one-hot, an "in clearance" flag and the
  time in the current phase over ``max_phase_norm`` seconds.
* **Reward** -- negative delay: minus the vehicle-seconds spent stopped on the
  approaches during the interval, divided by ``reward_scale`` (``"queue"`` mode
  uses the queue length at the end of the interval instead).
* **Determinism** -- ``reset(seed=s)`` fixes the arrival stream and driver
  behaviour of the underlying engine. Same seed and same actions, same episode.
  Without a seed the episode seeds are drawn from the environment's own
  generator, which the first ``reset(seed=...)`` pins.

Needs ``gymnasium`` and ``numpy`` (``backend/requirements-rl.txt``).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.core.clock import Clock
from src.core.enums import Direction
from src.engine.simulation_engine import SimulationEngine
from src.rl.controller import ExternalPhaseController
from src.rl.scenario import junction_config

STOPPED_SPEED = 0.5  # m/s, the project-wide wait threshold
DIRECTIONS: Tuple[Direction, ...] = (
    Direction.NORTH,
    Direction.SOUTH,
    Direction.EAST,
    Direction.WEST,
)
OBS_SIZE = 12


class SignalControlEnv(gym.Env):  # type: ignore[misc]
    metadata = {"render_modes": []}

    def __init__(
        self,
        vehicles_per_hour: float = 400.0,
        lanes: int = 1,
        ns_share: float = 1.0,
        episode_seconds: float = 300.0,
        decision_interval: float = 5.0,
        min_green: float = 5.0,
        yellow: float = 3.0,
        all_red: float = 1.0,
        queue_cap: float = 20.0,
        reward_mode: str = "delay",
        reward_scale: float = 50.0,
        max_phase_norm: float = 60.0,
        base_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__()
        if reward_mode not in ("delay", "queue"):
            raise ValueError("reward_mode must be 'delay' or 'queue'")
        if decision_interval <= 0 or episode_seconds < decision_interval:
            raise ValueError("need 0 < decision_interval <= episode_seconds")
        self.params: Dict[str, Any] = {
            "vehicles_per_hour": vehicles_per_hour,
            "lanes": lanes,
            "ns_share": ns_share,
            "episode_seconds": episode_seconds,
            "decision_interval": decision_interval,
            "min_green": min_green,
            "yellow": yellow,
            "all_red": all_red,
            "queue_cap": queue_cap,
            "reward_mode": reward_mode,
            "reward_scale": reward_scale,
            "max_phase_norm": max_phase_norm,
        }
        self._base_config = base_config
        self.action_space = spaces.Discrete(2)
        self.observation_space = spaces.Box(0.0, 1.0, (OBS_SIZE,), np.float32)
        self.engine: Optional[SimulationEngine] = None
        self.controller: Optional[ExternalPhaseController] = None
        self.episode_seed: int = 0
        self.sim_time: float = 0.0
        self._stopped_seconds: float = 0.0
        self._ticks_per_decision = 1

    # ------------------------------------------------------------------
    def _build(self, seed: int) -> None:
        p = self.params
        if self._base_config is not None:
            config = copy.deepcopy(self._base_config)
            config.setdefault("simulation", {})["randomSeed"] = seed
        else:
            config = junction_config(
                p["vehicles_per_hour"],
                p["lanes"],
                seed,
                p["episode_seconds"],
                p["yellow"],
                p["all_red"],
                p["ns_share"],
            )
        config["simulation"]["duration"] = p["episode_seconds"] + 1.0
        clock = Clock(time_step=float(config["simulation"]["timeStep"]))
        self.engine = SimulationEngine(
            clock, duration=config["simulation"]["duration"], config=config
        )
        self.controller = ExternalPhaseController(
            config, self.engine.network, min_green=p["min_green"]
        )
        self.engine.controller = self.controller
        self._ticks_per_decision = max(
            1, int(round(p["decision_interval"] / clock.time_step))
        )

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        if options and "episode_seed" in options:
            self.episode_seed = int(options["episode_seed"])
        elif seed is not None:
            self.episode_seed = int(seed)
        else:
            self.episode_seed = int(self.np_random.integers(1, 2**31 - 1))
        self._build(self.episode_seed)
        self.sim_time = 0.0
        self._stopped_seconds = 0.0
        return self._observe(), self._info()

    # ------------------------------------------------------------------
    def _approach_counts(self) -> Tuple[np.ndarray, np.ndarray]:
        """(stopped, present) vehicle counts per approach, N S E W."""
        assert self.engine is not None
        stopped = np.zeros(4, dtype=np.float64)
        present = np.zeros(4, dtype=np.float64)
        for i, d in enumerate(DIRECTIONS):
            try:
                approach = self.engine.network.get_incoming_approach(d)
            except KeyError:
                continue
            for lane in approach.get_lanes():
                for v in lane.get_vehicles():
                    if v.lane is not lane:
                        continue
                    present[i] += 1
                    if v.speed < STOPPED_SPEED:
                        stopped[i] += 1
        return stopped, present

    def queue_counts(self) -> Dict[str, float]:
        """Stopped vehicles per approach (for the baselines and the info dict)."""
        stopped, _ = self._approach_counts()
        return {d.value: float(stopped[i]) for i, d in enumerate(DIRECTIONS)}

    def _observe(self) -> np.ndarray:
        assert self.controller is not None
        cap = self.params["queue_cap"]
        stopped, present = self._approach_counts()
        green = self.controller.active_green
        obs = np.concatenate(
            [
                np.clip(stopped / cap, 0.0, 1.0),
                np.clip(present / cap, 0.0, 1.0),
                [
                    1.0 if green == 0 else 0.0,
                    1.0 if green == 1 else 0.0,
                    1.0 if self.controller.in_transition else 0.0,
                    min(
                        1.0,
                        self.controller.time_in_current_state
                        / self.params["max_phase_norm"],
                    ),
                ],
            ]
        )
        return obs.astype(np.float32)

    def _info(self) -> Dict[str, Any]:
        assert self.engine is not None and self.controller is not None
        stopped, present = self._approach_counts()
        return {
            "sim_time": self.sim_time,
            "episode_seed": self.episode_seed,
            "queues": {d.value: float(stopped[i]) for i, d in enumerate(DIRECTIONS)},
            "present": {d.value: float(present[i]) for i, d in enumerate(DIRECTIONS)},
            "active_green": self.controller.active_green,
            "in_transition": self.controller.in_transition,
            "time_in_phase": self.controller.time_in_current_state,
            "stopped_seconds": self._stopped_seconds,
            "throughput": len(self.engine.pool.exited_vehicles),
        }

    def step(
        self, action: Any
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if self.engine is None or self.controller is None:
            raise RuntimeError("call reset() before step()")
        self.controller.request_green(int(action))
        dt = self.engine.clock.time_step
        interval_stopped = 0.0
        for _ in range(self._ticks_per_decision):
            self.engine.step()
            stopped, _ = self._approach_counts()
            interval_stopped += float(stopped.sum()) * dt
        self.sim_time = self.engine.clock.get_elapsed_time()
        self._stopped_seconds += interval_stopped
        if self.params["reward_mode"] == "queue":
            reward = -float(self._approach_counts()[0].sum()) / self.params["queue_cap"]
        else:
            reward = -interval_stopped / self.params["reward_scale"]
        truncated = self.sim_time >= self.params["episode_seconds"] - 1e-9
        return self._observe(), float(reward), False, truncated, self._info()

    # ------------------------------------------------------------------
    def episode_metrics(self) -> Dict[str, float]:
        """Whole-episode figures for evaluation (valid any time after reset)."""
        assert self.engine is not None
        pool = self.engine.pool
        everyone = list(pool.exited_vehicles) + list(pool.active_vehicles)
        waits = [float(v.wait_time) for v in everyone]
        return {
            "mean_wait_s": float(np.mean(waits)) if waits else 0.0,
            "total_wait_s": float(np.sum(waits)),
            "stopped_veh_s": float(self._stopped_seconds),
            "mean_queue": float(self._stopped_seconds / max(self.sim_time, 1e-9)),
            "throughput": float(len(pool.exited_vehicles)),
            "vehicles": float(len(everyone)),
            "switches": float(self.controller.switches if self.controller else 0),
        }
