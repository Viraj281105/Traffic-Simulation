"""Reference controllers the learned policies are compared against.

Both act through the same environment interface as an RL policy (same
actions, same clearance and minimum-green rules), so a comparison differs only
in the decision rule. ``act(obs, info)`` returns 0 (north-south green) or 1
(east-west green). No third-party dependency.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol


class Policy(Protocol):
    name: str

    def reset(self) -> None: ...

    def act(self, obs: Any, info: Dict[str, Any]) -> int: ...


class FixedTimePolicy:
    """Alternating greens of ``green_s`` seconds each, regardless of demand.

    The time is the wall of simulated seconds, so a clearance eats into the
    green it precedes exactly as a fixed-time plan's lost time does.
    """

    name = "fixed_time"

    def __init__(self, green_s: float = 30.0) -> None:
        if green_s <= 0:
            raise ValueError("green_s must be positive")
        self.green_s = float(green_s)

    def reset(self) -> None:
        pass

    def act(self, obs: Any, info: Dict[str, Any]) -> int:
        return int(info["sim_time"] // self.green_s) % 2


class MaxPressurePolicy:
    """Serve the stage with the larger pressure (Varaiya, 2013).

    On an isolated junction the downstream queues are not observed (exits are
    free flowing), so a stage's pressure is the number of vehicles on its
    approaches: stopped vehicles plus ``approach_weight`` times the moving
    ones. The current green is kept unless the other stage is more pressed by
    more than ``switch_margin`` vehicles and has held for ``min_hold_s``, which
    stops flicker (the environment separately enforces its own minimum green).
    """

    name = "max_pressure"

    def __init__(
        self,
        switch_margin: float = 1.0,
        moving_weight: float = 0.5,
        min_hold_s: float = 10.0,
    ) -> None:
        self.switch_margin = float(switch_margin)
        self.moving_weight = float(moving_weight)
        self.min_hold_s = float(min_hold_s)

    def reset(self) -> None:
        pass

    def act(self, obs: Any, info: Dict[str, Any]) -> int:
        q = info["queues"]
        present = info.get("present")
        if present is None:
            # obs[4:8] is present / cap; recover the weighting without the cap
            # by using the stopped count alone when not provided.
            present = q
        pressure = []
        for dirs in (("north", "south"), ("east", "west")):
            stopped = sum(q[d] for d in dirs)
            total = sum(present[d] for d in dirs)
            pressure.append(stopped + self.moving_weight * max(0.0, total - stopped))
        current = int(info["active_green"])
        other = 1 - current
        if (
            info.get("in_transition") is False
            and info.get("time_in_phase", 1e9) < self.min_hold_s
        ):
            return current
        if pressure[other] > pressure[current] + self.switch_margin:
            return other
        return current


BASELINES = {
    FixedTimePolicy.name: FixedTimePolicy,
    MaxPressurePolicy.name: MaxPressurePolicy,
}
