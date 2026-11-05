"""Network baselines the learned policy is compared against (F18, W44).

Same interface as an RL policy on :class:`NetworkSignalEnv`: ``act(obs, info)``
returns one phase (0 = east-west, 1 = north-south) per signalised node, in
``env.signal_nodes`` order, through the same minimum-green and clearance rules.
Pure Python plus numpy; nothing is tuned against the evaluation seeds.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np


class NetworkFixedTime:
    """Every node alternates east-west / north-south every ``green_s`` seconds."""

    name = "fixed_time"

    def __init__(self, signal_nodes: Sequence[str], green_s: float = 30.0) -> None:
        if green_s <= 0:
            raise ValueError("green_s must be positive")
        self.signal_nodes = list(signal_nodes)
        self.green_s = float(green_s)

    def reset(self) -> None:
        pass

    def act(self, obs: Any, info: Dict[str, Any]) -> np.ndarray:
        phase = int(info["sim_time"] // self.green_s) % 2
        return np.full(len(self.signal_nodes), phase, dtype=np.int64)


class NetworkMaxPressure:
    """Per node, serve the axis with the larger pressure (Varaiya, 2013).

    Pressure of an axis is the vehicles waiting on its approaches minus the
    vehicles on the straight-ahead downstream links (spillback aware). The
    current phase is kept unless the other axis is ahead by ``switch_margin``
    and the node has held for ``min_hold_s``.
    """

    name = "max_pressure"

    def __init__(
        self,
        signal_nodes: Sequence[str],
        switch_margin: float = 1.0,
        min_hold_s: float = 10.0,
    ) -> None:
        self.signal_nodes = list(signal_nodes)
        self.switch_margin = float(switch_margin)
        self.min_hold_s = float(min_hold_s)

    def reset(self) -> None:
        pass

    def act(self, obs: Any, info: Dict[str, Any]) -> np.ndarray:
        out: List[int] = []
        for nid in self.signal_nodes:
            st = info["nodes"][nid]
            current = int(st["active_phase"])
            if st["in_transition"] or st["time_in_phase"] < self.min_hold_s:
                out.append(current)
                continue
            pr = st["pressure"]
            mine = pr["ew"] if current == 0 else pr["ns"]
            other = pr["ns"] if current == 0 else pr["ew"]
            out.append(1 - current if other > mine + self.switch_margin else current)
        return np.asarray(out, dtype=np.int64)


def make_baselines(
    signal_nodes: Sequence[str], fixed_green_s: float = 30.0
) -> Dict[str, Any]:
    return {
        "fixed_time": NetworkFixedTime(signal_nodes, fixed_green_s),
        "max_pressure": NetworkMaxPressure(signal_nodes),
    }
