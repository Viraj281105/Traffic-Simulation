"""Engine configurations for the RL environment (no optional dependencies)."""

from __future__ import annotations

import copy
from typing import Any, Dict

from src.scenario.documents import compile_scenario, parse_scenario, validate_scenario

ARMS = ("north", "south", "east", "west")
STRATEGY = "fixed_time"


def junction_config(
    vehicles_per_hour: float = 400.0,
    lanes: int = 1,
    seed: int = 1,
    duration: float = 300.0,
    yellow: float = 3.0,
    all_red: float = 1.0,
    ns_share: float = 1.0,
) -> Dict[str, Any]:
    """Compiled engine config for a four-arm signalised junction.

    ``ns_share`` scales the north/south demand against east/west (1.0 =
    balanced, 2.0 = north/south carry twice the east/west flow).
    """
    approaches = {}
    for arm in ARMS:
        vph = vehicles_per_hour * (ns_share if arm in ("north", "south") else 1.0)
        approaches[arm] = {
            "lanes": lanes,
            "length": 200.0,
            "vehiclesPerHour": vph,
            "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
        }
    doc = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "rl-junction",
        "junction": {"type": "fixed_time_signal"},
        "approaches": approaches,
        "simulation": {"duration": float(duration), "warmup": 0.0, "seed": int(seed)},
        "signal": {"yellowTime": float(yellow), "allRedTime": float(all_red)},
    }
    parsed, errors = parse_scenario(doc)
    if parsed is None or errors:
        raise ValueError(f"invalid RL scenario: {errors}")
    report = validate_scenario(doc, [STRATEGY])
    if not report["valid"]:
        raise ValueError(f"invalid RL scenario: {report['errors']}")
    return copy.deepcopy(compile_scenario(parsed, STRATEGY))
