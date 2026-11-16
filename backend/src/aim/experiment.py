"""Like-for-like AIM vs signal comparison over seeds, a demand sweep and a
message-loss stress test (F20, package 3B).

Both controllers run in the same simulator with the same vehicles (the demand
for a seed does not depend on the controller), so each seed gives a pair and
the comparison is paired (``src.uncertainty.comparison``). Differences are
AIM minus signal: negative delay and stops favour AIM, positive throughput
favours AIM.

Caveat that travels with every result: this is an in-model, all-vehicles-
connected best case, and the baseline is a fixed-time two-phase signal, not an
optimised actuated one.
"""

from dataclasses import replace
from typing import Any, Dict, List, Sequence

from src.aim.manager import SignalPlan
from src.aim.simulation import SimConfig, SimResult, run
from src.uncertainty.comparison import compare_paired, verdict

DEFAULT_DEMANDS = (150.0, 300.0, 450.0, 600.0)
DEFAULT_LOSSES = (0.0, 0.25, 0.5, 0.8, 0.95)
# metric key -> lower is better
METRICS = {"meanDelay": True, "stopsPerVehicle": True, "throughputVph": False}

ASSUMPTIONS = (
    "In-model, all-vehicles-connected best case: every vehicle is automated and "
    "connected, obeys its reservation exactly, and there is no sensing or actuation "
    "error, no pedestrians, cyclists or unconnected vehicles.",
    "One isolated 4-way intersection, one inbound lane per approach (FIFO), "
    "straight/left/right movements on a 7 x 7 grid of 2 m conflict tiles.",
    "The baseline is a fixed-time two-phase signal with yellow and all-red, with "
    "permissive turns resolved by the same tile gap acceptance as AIM; it is not "
    "an optimised or actuated plan.",
    "Delay is box-entry time minus the unimpeded entry time; throughput counts "
    "vehicles entering the box before the end of the demand window.",
)


def _aggregate_safety(results: Sequence[SimResult]) -> Dict[str, Any]:
    gaps = [
        r.safety.minGapSeconds for r in results if r.safety.minGapSeconds is not None
    ]
    return {
        "conflicts": sum(r.safety.conflicts for r in results),
        "minGapSeconds": min(gaps) if gaps else None,
        "deadlock": any(r.safety.deadlock for r in results),
        "maxAccel": max(r.safety.maxAccel for r in results),
        "passed": all(r.safety.passed for r in results),
    }


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _series(results: Sequence[SimResult], key: str) -> List[float]:
    return [r.metrics[key] for r in results]


def _summary(results: Sequence[SimResult]) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: _mean(_series(results, k)) for k in METRICS}
    out["p95Delay"] = _mean(_series(results, "p95Delay"))
    out["lostMessages"] = _mean(_series(results, "lostMessages"))
    out["safety"] = _aggregate_safety(results)
    return out


def compare_results(
    aim: Sequence[SimResult],
    signal: Sequence[SimResult],
    confidence: float,
    method: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, lower_better in METRICS.items():
        cmp = compare_paired(
            _series(aim, key),
            _series(signal, key),
            method=method,
            confidence=confidence,
        )
        out[key] = {**cmp.to_dict(), "verdict": verdict(cmp, lower_better)}
    return out


def run_pair(base: SimConfig, seeds: Sequence[int]) -> Dict[str, List[SimResult]]:
    return {
        mode: [run(replace(base, mode=mode, seed=s), keep_tracks=False) for s in seeds]
        for mode in ("aim", "signal")
    }


def run_comparison(
    seeds: Sequence[int],
    demands: Sequence[float] = DEFAULT_DEMANDS,
    *,
    duration: float = 300.0,
    left_fraction: float = 0.15,
    right_fraction: float = 0.15,
    signal: SignalPlan = SignalPlan(),
    loss_probabilities: Sequence[float] = (),
    stress_demand: float = 450.0,
    confidence: float = 0.95,
    method: str = "paired_t",
) -> Dict[str, Any]:
    base = SimConfig(
        duration=duration,
        left_fraction=left_fraction,
        right_fraction=right_fraction,
        signal=signal,
    )
    sweep: List[Dict[str, Any]] = []
    for demand in demands:
        pair = run_pair(replace(base, demand_vph=demand), seeds)
        sweep.append(
            {
                "demandVehPerHourPerApproach": demand,
                "aim": _summary(pair["aim"]),
                "signal": _summary(pair["signal"]),
                "comparison": compare_results(
                    pair["aim"], pair["signal"], confidence, method
                ),
            }
        )
    stress: List[Dict[str, Any]] = []
    if loss_probabilities:
        stress_base = replace(base, demand_vph=stress_demand)
        sig = [run(replace(stress_base, mode="signal", seed=s), False) for s in seeds]
        for p in loss_probabilities:
            aim = [
                run(replace(stress_base, mode="aim", seed=s, loss_probability=p), False)
                for s in seeds
            ]
            stress.append(
                {
                    "lossProbability": p,
                    "aim": _summary(aim),
                    "signal": _summary(sig),
                    "comparison": compare_results(aim, sig, confidence, method),
                }
            )
    return {
        "provenance": {
            "seeds": list(seeds),
            "durationSeconds": duration,
            "turnMix": {"left": left_fraction, "right": right_fraction},
            "signal": {
                "greenSeconds": signal.green,
                "yellowSeconds": signal.yellow,
                "allRedSeconds": signal.all_red,
            },
            "confidence": confidence,
            "method": method,
            "stressDemandVehPerHourPerApproach": stress_demand if stress else None,
            "assumptions": list(ASSUMPTIONS),
            "inModelBestCase": True,
        },
        "sweep": sweep,
        "messageLossStress": stress,
        "gateGAim": {
            "passed": all(s["aim"]["safety"]["passed"] for s in sweep + stress),
            "description": "independent replay checker: no tile overlap, no "
            "deadlock, minimum gap, speed and acceleration bounds",
        },
    }
