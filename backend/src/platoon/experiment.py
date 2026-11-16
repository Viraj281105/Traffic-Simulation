"""Seeded experiment: platoon (CACC) vs human (IDM) with paired comparison.

Each seed runs the same scenario twice (same hard-brake pulse and driver
jitter): a formed CACC platoon whose head is a human-style IDM leader, and an
all-IDM line. Metrics per run: steady-state throughput, estimated fuel and CO2
intensity (``metrics.trajectory_metrics``: a RELATIVE speed/idle/acceleration
proxy, not a measurement), minimum gap and collisions. Paired differences use
``uncertainty.comparison``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.metrics.trajectory_metrics import summarize_emissions
from src.platoon.sim import RunResult, ScenarioSpec, SimConfig, make_channel, run
from src.uncertainty.comparison import compare_paired, verdict

HUMAN_REACTION_S = 0.6
LABEL = (
    "Simulation estimates from a single-lane 1-D model with a relative fuel proxy; "
    "not a field measurement."
)


@dataclass(frozen=True)
class ExperimentSpec:
    vehicles: int = 10
    duration: float = 200.0
    speed: float = 25.0
    time_gap: float = 0.6
    latency_s: float = 0.0
    loss: float = 0.0
    pulse_decel: float = 4.0
    seeds: Tuple[int, ...] = (1, 2, 3, 4, 5)
    reaction_s: float = HUMAN_REACTION_S
    confidence: float = 0.95
    method: str = "paired_t"


def _scenario(spec: ExperimentSpec, **over: Any) -> ScenarioSpec:
    base = ScenarioSpec(
        vehicles=spec.vehicles,
        duration=spec.duration,
        speed=spec.speed,
        time_gap=spec.time_gap,
        pulse_decel=spec.pulse_decel,
        channel=make_channel(spec.latency_s, spec.loss),
        cfg=SimConfig(reaction_s=spec.reaction_s),
    )
    return replace(base, **over)


def _metrics(res: RunResult) -> Dict[str, float]:
    em = summarize_emissions(res.speeds, res.dt)
    return {
        "throughputVph": res.throughput_vph,
        "fuelLPer100Km": float(em["fuelLPer100Km"] or math.nan),
        "co2GPerKm": float(em["co2GPerKm"] or math.nan),
        "minGapM": res.min_gap_m,
        "collisions": float(res.collisions),
        "fallbackEvents": float(res.fallback_events),
    }


def _mean(xs: Sequence[float]) -> float:
    return math.fsum(xs) / len(xs)


def _pct(new: float, base: float) -> Optional[float]:
    return (new - base) / base * 100.0 if base else None


def run_experiment(spec: ExperimentSpec) -> Dict[str, Any]:
    """Run all seeds in both modes and compare platoon (A) with human (B)."""
    if len(spec.seeds) < 2:
        raise ValueError("need at least 2 seeds for a paired comparison")
    sc = _scenario(spec)
    plat = [_metrics(run(sc, "cacc", s)) for s in spec.seeds]
    hum = [_metrics(run(sc, "idm", s)) for s in spec.seeds]
    return _summarise(spec, plat, hum)


def _summarise(
    spec: ExperimentSpec, plat: List[Dict[str, float]], hum: List[Dict[str, float]]
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, lower_better in (
        ("throughputVph", False),
        ("fuelLPer100Km", True),
        ("co2GPerKm", True),
    ):
        a, b = [m[key] for m in plat], [m[key] for m in hum]
        cmp = compare_paired(a, b, method=spec.method, confidence=spec.confidence)
        out[key] = {
            "platoonMean": _mean(a),
            "humanMean": _mean(b),
            "changePct": _pct(_mean(a), _mean(b)),
            "comparison": cmp.to_dict(),
            "verdict": verdict(cmp, lower_is_better=lower_better),
        }
    return {
        "seeds": list(spec.seeds),
        "metrics": out,
        "safety": {
            "platoonMinGapM": min(m["minGapM"] for m in plat),
            "humanMinGapM": min(m["minGapM"] for m in hum),
            "platoonCollisions": int(sum(m["collisions"] for m in plat)),
            "humanCollisions": int(sum(m["collisions"] for m in hum)),
            "platoonFallbackEvents": int(sum(m["fallbackEvents"] for m in plat)),
        },
        "perSeed": [
            {"seed": s, "platoon": p, "human": h}
            for s, p, h in zip(spec.seeds, plat, hum)
        ],
        "isEstimate": True,
        "label": LABEL,
    }


def channel_sweep(
    spec: ExperimentSpec,
    latencies_s: Sequence[float],
    losses: Sequence[float],
) -> List[Dict[str, Any]]:
    """Platoon benefit vs latency and loss; the human baseline is run once per seed."""
    base = _scenario(spec)
    hum = [_metrics(run(base, "idm", s)) for s in spec.seeds]
    cells: List[Dict[str, Any]] = []
    for lat in latencies_s:
        for loss in losses:
            sc = replace(base, channel=make_channel(lat, loss))
            plat = [_metrics(run(sc, "cacc", s)) for s in spec.seeds]
            summ = _summarise(spec, plat, hum)
            cells.append(
                {
                    "latencySeconds": lat,
                    "lossProbability": loss,
                    "fuelChangePct": summ["metrics"]["fuelLPer100Km"]["changePct"],
                    "throughputChangePct": summ["metrics"]["throughputVph"][
                        "changePct"
                    ],
                    "minGapM": summ["safety"]["platoonMinGapM"],
                    "collisions": summ["safety"]["platoonCollisions"],
                    "fallbackEvents": summ["safety"]["platoonFallbackEvents"],
                }
            )
    return cells
