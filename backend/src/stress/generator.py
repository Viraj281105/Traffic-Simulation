"""Reproducible stress-scenario generator (``stress-v1``)."""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, List, Optional

from src.core.enums import Direction, TurnIntent
from src.roads.lane_config import target_direction

GENERATOR_VERSION = "stress-v1"
MAX_SCENARIOS = 30

FAMILIES = (
    "uneven_split",
    "turning_extreme",
    "mixed_aggression",
    "heavy_vehicles",
    "near_capacity",
    "over_capacity",
    "three_arm",
    "ring_lanes",
)
_DIRECTIONS = ("north", "south", "east", "west")


def _turning(rng: random.Random, extreme: bool) -> Dict[str, float]:
    if extreme:
        left = round(rng.uniform(0.35, 0.6), 2)
        right = round(rng.uniform(0.05, 0.15), 2)
    else:
        left = round(rng.uniform(0.1, 0.3), 2)
        right = round(rng.uniform(0.1, 0.3), 2)
    return {"left": left, "straight": round(1.0 - left - right, 2), "right": right}


def generate_one(seed: int, index: int, duration: float = 120.0) -> Dict[str, Any]:
    """Scenario ``index`` of the suite for ``seed``: the same inputs always give the same document."""
    rng = random.Random(f"{GENERATOR_VERSION}:{seed}:{index}")
    family = FAMILIES[index % len(FAMILIES)]
    base = rng.randint(350, 650)
    volumes = {d: base for d in _DIRECTIONS}
    lanes = 1
    turning_extreme = False
    aggression: Optional[str] = rng.choice([None, "standard", "moderate", "high"])
    mix: Optional[Dict[str, float]] = None
    ring_lanes: Optional[int] = None
    arms = list(_DIRECTIONS)

    if family == "uneven_split":
        major = rng.choice([("north", "south"), ("east", "west")])
        for d in _DIRECTIONS:
            volumes[d] = round(base * (1.6 if d in major else 0.4))
    elif family == "turning_extreme":
        turning_extreme = True
    elif family == "mixed_aggression":
        aggression = "high"
    elif family == "heavy_vehicles":
        heavy = round(rng.uniform(0.25, 0.4), 2)
        mix = {
            "car": round(1.0 - heavy - 0.05, 2),
            "suv": 0.05,
            "bus": round(heavy / 2, 2),
            "truck": round(heavy / 2, 2),
            "motorcycle": 0.0,
        }
        total = sum(mix.values())
        mix["car"] = round(mix["car"] + (1.0 - total), 2)
    elif family == "near_capacity":
        volumes = {d: rng.randint(800, 950) for d in _DIRECTIONS}
    elif family == "over_capacity":
        volumes = {d: rng.randint(1000, 1200) for d in _DIRECTIONS}
    elif family == "three_arm":
        arms.remove(rng.choice(_DIRECTIONS))
    elif family == "ring_lanes":
        lanes = rng.choice([1, 2])
        ring_lanes = rng.choice([1, 2, 3])

    approaches: Dict[str, Any] = {}
    for d in _DIRECTIONS:
        if d not in arms:
            approaches[d] = None
            continue
        turning = _turning(rng, turning_extreme)
        # Nothing may turn into a slot without an arm: move that share to the movements that remain.
        blocked = [
            m
            for m in ("left", "straight", "right")
            if target_direction(Direction(d), TurnIntent(m)).value not in arms
        ]
        if blocked:
            spare = sum(turning[m] for m in blocked)
            open_moves = [m for m in ("left", "straight", "right") if m not in blocked]
            for m in blocked:
                turning[m] = 0.0
            for m in open_moves:
                turning[m] = round(turning[m] + spare / len(open_moves), 2)
            turning[open_moves[0]] = round(
                1.0 - sum(turning[m] for m in open_moves[1:]), 2
            )
        approaches[d] = {
            "lanes": lanes,
            "vehiclesPerHour": volumes[d],
            "turning": turning,
        }
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": f"{GENERATOR_VERSION} #{index} ({family})",
        "junction": {"type": "fixed_time_signal"},
        "approaches": approaches,
        "simulation": {
            "duration": duration,
            "warmup": min(30.0, duration / 4),
            "seed": rng.randint(1, 10_000),
        },
    }
    if aggression is not None:
        doc["traffic"] = {"driverAggression": aggression}
    if mix is not None:
        doc["vehicles"] = {"mix": mix}
    if ring_lanes is not None:
        doc["roundabout"] = {"circulatingLanes": ring_lanes}
    return {"index": index, "family": family, "scenario": doc}


def generate(seed: int, count: int, duration: float = 120.0) -> List[Dict[str, Any]]:
    if not 1 <= count <= MAX_SCENARIOS:
        raise ValueError(f"count must be between 1 and {MAX_SCENARIOS}")
    return [generate_one(seed, i, duration) for i in range(count)]


def suite_fingerprint(scenarios: List[Dict[str, Any]]) -> str:
    canonical = json.dumps(scenarios, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
