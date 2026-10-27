"""The bounded search space over registered strategies, and the regime's scenario document.

A genome holds the strategy and every tunable parameter (the ones a strategy does not use are ignored).
Genomes are repaired only by clamping into the declared bounds; a genome the scenario validator or the
strategy compatibility checks reject is recorded with its reason and never simulated.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.scenario.documents import ScenarioDocument, validate_scenario

from .models import Regime, Strategy

Genome = Dict[str, Any]

# (low, high) of every continuous or integer parameter.
BOUNDS: Dict[str, Tuple[float, float]] = {
    "nsGreen": (10.0, 60.0),
    "ewGreen": (10.0, 60.0),
    "yellow": (3.0, 5.0),
    "allRed": (1.0, 3.0),
    "minGreen": (5.0, 20.0),
    "maxGreen": (25.0, 90.0),
    "extensionStep": (1.0, 5.0),
    "meterGreenNS": (10.0, 40.0),
    "meterGreenEW": (10.0, 40.0),
    "spillbackThreshold": (1.0, 6.0),
    "spillbackMaxHold": (0.0, 20.0),
    "ringLanes": (1.0, 2.0),
}
INTEGER_KEYS = {"spillbackThreshold", "ringLanes"}
BOOLEAN_KEYS = ("spillbackGuard",)
MAX_CYCLE = 120.0
MIN_CYCLE = 40.0

_ENGINE_STRATEGY = {
    "fixed_time": "fixed_time",
    "adaptive": "adaptive",
    "roundabout": "roundabout",
    "signalised_roundabout": "roundabout",
}


def engine_strategy(strategy: str) -> str:
    return _ENGINE_STRATEGY[strategy]


def clamp(genome: Genome) -> Genome:
    """Clamp every value into its bounds, round integers, and keep the cycle within [40, 120] s."""
    out: Genome = {"strategy": genome["strategy"]}
    for key, (low, high) in BOUNDS.items():
        value = float(genome.get(key, (low + high) / 2))
        value = min(high, max(low, value))
        out[key] = int(round(value)) if key in INTEGER_KEYS else round(value, 2)
    out["spillbackGuard"] = bool(genome.get("spillbackGuard", False))
    if out["maxGreen"] < out["minGreen"] + 5:
        out["maxGreen"] = round(min(BOUNDS["maxGreen"][1], out["minGreen"] + 5), 2)
    lost = 2 * (out["yellow"] + out["allRed"])
    cycle = out["nsGreen"] + out["ewGreen"] + lost
    if cycle > MAX_CYCLE:
        scale = (MAX_CYCLE - lost) / (out["nsGreen"] + out["ewGreen"])
        out["nsGreen"] = round(max(BOUNDS["nsGreen"][0], out["nsGreen"] * scale), 2)
        out["ewGreen"] = round(max(BOUNDS["ewGreen"][0], out["ewGreen"] * scale), 2)
    elif cycle < MIN_CYCLE:
        extra = (MIN_CYCLE - cycle) / 2
        out["nsGreen"] = round(out["nsGreen"] + extra, 2)
        out["ewGreen"] = round(out["ewGreen"] + extra, 2)
    return out


def random_genome(rng: random.Random, strategies: List[str]) -> Genome:
    genome: Genome = {"strategy": rng.choice(strategies)}
    for key, (low, high) in BOUNDS.items():
        genome[key] = rng.uniform(low, high)
    genome["spillbackGuard"] = rng.random() < 0.5
    return clamp(genome)


def crossover(rng: random.Random, a: Genome, b: Genome) -> Genome:
    child: Genome = {"strategy": a["strategy"] if rng.random() < 0.5 else b["strategy"]}
    for key in BOUNDS:
        child[key] = a[key] if rng.random() < 0.5 else b[key]
    child["spillbackGuard"] = (
        a["spillbackGuard"] if rng.random() < 0.5 else b["spillbackGuard"]
    )
    return clamp(child)


def mutate(
    rng: random.Random, genome: Genome, strategies: List[str], rate: float = 0.25
) -> Genome:
    child = dict(genome)
    if rng.random() < rate / 2 and len(strategies) > 1:
        child["strategy"] = rng.choice(
            [s for s in strategies if s != genome["strategy"]]
        )
    for key, (low, high) in BOUNDS.items():
        if rng.random() < rate:
            child[key] = float(child[key]) + rng.gauss(0.0, (high - low) * 0.15)
    if rng.random() < rate / 2:
        child["spillbackGuard"] = not child["spillbackGuard"]
    return clamp(child)


def fingerprint(genome: Genome) -> str:
    """Identity of a genome: only the parameters its strategy uses (so irrelevant genes do not split it)."""
    used = relevant(genome)
    canonical = json.dumps(used, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def relevant(genome: Genome) -> Dict[str, Any]:
    s = genome["strategy"]
    keys: List[str] = []
    if s in ("fixed_time", "adaptive"):
        keys = ["nsGreen", "ewGreen", "yellow", "allRed"]
        if s == "adaptive":
            keys += ["minGreen", "maxGreen", "extensionStep"]
    elif s == "roundabout":
        keys = ["ringLanes"]
    elif s == "signalised_roundabout":
        keys = [
            "ringLanes",
            "meterGreenNS",
            "meterGreenEW",
            "yellow",
            "allRed",
            "spillbackGuard",
        ]
        if genome.get("spillbackGuard"):
            keys += ["spillbackThreshold", "spillbackMaxHold"]
    return {"strategy": s, **{k: genome[k] for k in keys}}


# ---------------------------------------------------------------------------------------------------
# Regime scenario and candidate documents
# ---------------------------------------------------------------------------------------------------
def regime_scenario(regime: Regime) -> Dict[str, Any]:
    per_arm = regime.vehiclesPerHour
    if regime.unevenDemand:
        volumes = {
            "north": min(1200, round(per_arm * 1.4)),
            "south": min(1200, round(per_arm * 1.4)),
        }
        volumes.update({"east": round(per_arm * 0.6), "west": round(per_arm * 0.6)})
    else:
        volumes = {d: per_arm for d in ("north", "south", "east", "west")}
    doc: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": regime.name,
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": regime.lanesPerArm,
                "vehiclesPerHour": v,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            }
            for d, v in volumes.items()
        },
        "simulation": {"duration": regime.duration, "warmup": regime.warmup, "seed": 1},
    }
    if regime.aggression is not None:
        doc["traffic"] = {"driverAggression": regime.aggression}
    if regime.mix == "heavy_vehicles":
        doc["vehicles"] = {
            "mix": {
                "car": 0.65,
                "suv": 0.1,
                "bus": 0.1,
                "truck": 0.15,
                "motorcycle": 0.0,
            }
        }
    elif regime.mix == "two_wheelers":
        doc["vehicles"] = {
            "mix": {
                "car": 0.45,
                "suv": 0.1,
                "bus": 0.05,
                "truck": 0.0,
                "motorcycle": 0.4,
            }
        }
    return doc


def candidate_patch(genome: Genome) -> Dict[str, Any]:
    """The JSON merge-patch over the regime scenario that a genome stands for (a reusable descriptor)."""
    s = genome["strategy"]
    if s in ("fixed_time", "adaptive"):
        signal: Dict[str, Any] = {
            "nsGreenTime": genome["nsGreen"],
            "ewGreenTime": genome["ewGreen"],
            "yellowTime": genome["yellow"],
            "allRedTime": genome["allRed"],
        }
        if s == "adaptive":
            signal["adaptive"] = {
                "minGreen": genome["minGreen"],
                "maxGreen": genome["maxGreen"],
                "extensionStep": genome["extensionStep"],
            }
        return {"signal": signal}
    roundabout: Dict[str, Any] = {"circulatingLanes": genome["ringLanes"]}
    if s == "signalised_roundabout":
        metering: Dict[str, Any] = {
            "phases": [
                {"entries": ["north", "south"], "green": genome["meterGreenNS"]},
                {"entries": ["east", "west"], "green": genome["meterGreenEW"]},
            ],
            "yellow": genome["yellow"],
            "allRed": genome["allRed"],
        }
        if genome["spillbackGuard"]:
            metering["spillbackGuard"] = {
                "enabled": True,
                "stoppedThreshold": genome["spillbackThreshold"],
                "maxHold": genome["spillbackMaxHold"],
            }
        roundabout.update({"entryControl": "metered_entry", "entryMetering": metering})
    return {"roundabout": roundabout}


def _merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def candidate_document(
    regime: Regime, genome: Optional[Genome], strategy: str
) -> Dict[str, Any]:
    """The scenario a candidate (or, with ``genome=None``, an unchanged baseline) runs."""
    base = regime_scenario(regime)
    return base if genome is None else _merge(base, candidate_patch(genome))


def validate_candidate(regime: Regime, genome: Genome) -> Optional[str]:
    """None when the genome may be simulated, else the validator's reason (never simulated)."""
    document = candidate_document(regime, genome, genome["strategy"])
    try:
        ScenarioDocument.model_validate(document)
    except ValidationError as err:
        first = err.errors()[0]
        return "schema: " + ".".join(str(p) for p in first["loc"]) + ": " + first["msg"]
    check = validate_scenario(document, [engine_strategy(genome["strategy"])])
    if not check["valid"]:
        return "validator: " + "; ".join(str(e) for e in check["errors"][:2])
    return None


def strategies_for(names: List[Strategy]) -> List[str]:
    return list(dict.fromkeys(names))
