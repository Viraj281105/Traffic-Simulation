"""Resilience metrics: how fast and how far a signal strategy is knocked off its
normal performance by a disruption (F13).

Each strategy is compared with *itself* without the disruption, on the same
seed (the gate arrivals use the same random draws, so the pair differs only by
the disruption). All figures are in-model comparisons from the mesoscopic
engine, not predictions.

Delay curve ``D(t)``: at the end of every bucket, the mean over vehicles in the
network of their accrued delay (time spent so far minus the free-flow time of
the distance covered, see ``engine.py``). It reacts at once when a disruption
starts, is defined while any vehicle is in the network, and returns to the
undisturbed level when the network has recovered.

Per run (scenario run S against its undisturbed twin B):

* ``peakDelaySeconds``       max of ``D_S``; ``peakExcessDelaySeconds`` is the
                             max of ``D_S - D_B`` (floored at 0).
* ``recoveryTimeSeconds``    from the end of the last disruption window to the
                             first bucket end (0 if that is the first one after the
                             disruption) from which ``D_S`` stays
                             within tolerance of ``D_B`` for ``holdBuckets``
                             buckets in a row: ``D_S <= D_B * (1 + tolRel) + tolAbs``.
                             ``None`` (and ``recovered`` false) if that never
                             happens before the run ends (censored).
* ``throughputLoss``         ``(completed_B - completed_S) / completed_B``,
                             floored at 0 (a surge may raise throughput).
* ``areaUnderDelayCurve``    ``sum(max(0, D_S - D_B)) * bucket`` in s^2; its
                             per-second mean is ``meanExcessDelaySeconds``.
* ``excessDelayVehicleSeconds`` total completed-vehicle delay of S minus B.

Resilience score ``R`` in [0, 1] (higher is better), a weighted mean of four
components, each in [0, 1]::

    recovery   = 1 - min(1, recoveryTime / (duration - disruptionEnd))   (0 if censored)
    throughput = 1 - min(1, throughputLoss)
    peak       = 1 / (1 + peakExcessDelay / 60 s)
    area       = 1 / (1 + meanExcessDelay / 30 s)
    R = 0.35 recovery + 0.25 throughput + 0.20 peak + 0.20 area

The weights and the two scales (60 s, 30 s) are modelling choices, returned in
the response so a reader can see and challenge them. With several seeds, the
score is the mean over seeds and the interval a seeded bootstrap 95% percentile
interval of that mean.
"""

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.incidents.engine import STRATEGIES, run_disruption
from src.incidents.model import Scenario
from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow

SCORE_WEIGHTS = {"recovery": 0.35, "throughput": 0.25, "peak": 0.20, "area": 0.20}
PEAK_SCALE_SECONDS = 60.0
AREA_SCALE_SECONDS = 30.0
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 20260305
MAX_SEEDS = 10


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def run_metrics(
    base: Dict[str, Any],
    scn: Dict[str, Any],
    disruption_end: float,
    duration: float,
    tolerance_rel: float = 0.10,
    tolerance_abs: float = 3.0,
    hold_buckets: int = 3,
) -> Dict[str, Any]:
    """Resilience figures for one (undisturbed, disturbed) pair of runs."""
    bs, ss = base["series"], scn["series"]
    bucket = float(ss["bucketSeconds"])
    times: List[float] = ss["time"]
    d_b: List[float] = bs["meanAccruedDelay"]
    d_s: List[float] = ss["meanAccruedDelay"]
    n = min(len(d_b), len(d_s), len(times))
    excess = [max(0.0, d_s[i] - d_b[i]) for i in range(n)]
    peak_delay = max(d_s[:n]) if n else 0.0
    peak_excess = max(excess) if excess else 0.0
    auc = sum(excess) * bucket
    mean_excess = auc / duration

    horizon = duration - disruption_end
    ok = [d_s[i] <= d_b[i] * (1.0 + tolerance_rel) + tolerance_abs for i in range(n)]
    recovery: Optional[float] = None
    first = next((i for i in range(n) if times[i] >= disruption_end - 1e-9), n)
    for i in range(first, n):
        if i + hold_buckets > n:
            break
        if all(ok[i : i + hold_buckets]):
            # Samples are bucket ends, so a network that is already within
            # tolerance at the first sample after the end counts as 0 s.
            recovery = 0.0 if i == first else max(0.0, times[i] - disruption_end)
            break
    base_done = base["completed"]
    loss = (base_done - scn["completed"]) / base_done if base_done else 0.0
    loss = max(0.0, loss)

    comp = {
        "recovery": 0.0 if recovery is None else 1.0 - min(1.0, recovery / horizon),
        "throughput": 1.0 - min(1.0, loss),
        "peak": 1.0 / (1.0 + peak_excess / PEAK_SCALE_SECONDS),
        "area": 1.0 / (1.0 + mean_excess / AREA_SCALE_SECONDS),
    }
    score = _clip01(sum(SCORE_WEIGHTS[k] * _clip01(v) for k, v in comp.items()))
    return {
        "seed": scn["seed"],
        "recovered": recovery is not None,
        "recoveryTimeSeconds": None if recovery is None else round(recovery, 3),
        "peakDelaySeconds": round(peak_delay, 3),
        "peakExcessDelaySeconds": round(peak_excess, 3),
        "throughputLoss": round(loss, 4),
        "areaUnderDelayCurve": round(auc, 3),
        "meanExcessDelaySeconds": round(mean_excess, 4),
        "excessDelayVehicleSeconds": round(
            scn["totalDelaySeconds"] - base["totalDelaySeconds"], 3
        ),
        "completedBaseline": base_done,
        "completed": scn["completed"],
        "blockedAtEntry": scn["blockedAtEntry"],
        "reroutedVehicles": scn["reroutedVehicles"],
        "conserved": bool(scn["conserved"] and base["conserved"]),
        "components": {k: round(v, 4) for k, v in comp.items()},
        "score": round(score, 4),
    }


def bootstrap_interval(values: Sequence[float]) -> Optional[Tuple[float, float]]:
    """Seeded 95% percentile bootstrap interval of the mean (None for n < 2)."""
    n = len(values)
    if n < 2:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(BOOTSTRAP_RESAMPLES)
    )
    lo = means[int(0.025 * BOOTSTRAP_RESAMPLES)]
    hi = means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]
    return round(lo, 4), round(hi, 4)


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def evaluate_resilience(
    graph: RoadGraph,
    flows: List[Flow],
    scenario: Scenario,
    *,
    strategies: Sequence[str] = STRATEGIES,
    seeds: Sequence[int] = (1, 2, 3, 4, 5),
    duration: float = 900.0,
    bucket_seconds: float = 30.0,
    tolerance_rel: float = 0.10,
    tolerance_abs: float = 3.0,
    hold_buckets: int = 3,
    include_series: bool = False,
) -> Dict[str, Any]:
    """Resilience score (mean over ``seeds`` with an interval) per strategy."""
    end = scenario.disruption_end()
    if end is None:
        raise ValueError(
            "the scenario has no disruption; add an incident, weather or surge"
        )
    if end >= duration - 2 * bucket_seconds:
        raise ValueError(
            "the disruption ends too close to the end of the run to measure "
            "recovery; lengthen the run or shorten the disruption"
        )
    if not seeds or len(seeds) > MAX_SEEDS:
        raise ValueError(f"give between 1 and {MAX_SEEDS} seeds")
    empty = Scenario(reroute=scenario.reroute)
    per_strategy: Dict[str, Any] = {}
    for strat in strategies:
        runs: List[Dict[str, Any]] = []
        series: List[Dict[str, Any]] = []
        for seed in seeds:
            kw: Dict[str, Any] = dict(
                duration=duration,
                seed=seed,
                strategy=strat,
                bucket_seconds=bucket_seconds,
            )
            base = run_disruption(graph, flows, empty, **kw)
            scn = run_disruption(graph, flows, scenario, **kw)
            runs.append(
                run_metrics(
                    base, scn, end, duration, tolerance_rel, tolerance_abs, hold_buckets
                )
            )
            if include_series:
                series.append(
                    {
                        "seed": seed,
                        "time": scn["series"]["time"],
                        "baseline": base["series"]["meanAccruedDelay"],
                        "scenario": scn["series"]["meanAccruedDelay"],
                    }
                )
        scores = [r["score"] for r in runs]
        rec = [r["recoveryTimeSeconds"] for r in runs if r["recovered"]]
        interval = bootstrap_interval(scores)
        entry: Dict[str, Any] = {
            "score": round(_mean(scores), 4),
            "scoreInterval": None if interval is None else list(interval),
            "recoveredRuns": len(rec),
            "runs": len(runs),
            "recoveryTimeSeconds": round(_mean(rec), 3) if rec else None,
            "peakDelaySeconds": round(_mean([r["peakDelaySeconds"] for r in runs]), 3),
            "peakExcessDelaySeconds": round(
                _mean([r["peakExcessDelaySeconds"] for r in runs]), 3
            ),
            "throughputLoss": round(_mean([r["throughputLoss"] for r in runs]), 4),
            "areaUnderDelayCurve": round(
                _mean([r["areaUnderDelayCurve"] for r in runs]), 3
            ),
            "excessDelayVehicleSeconds": round(
                _mean([r["excessDelayVehicleSeconds"] for r in runs]), 3
            ),
            "perSeed": runs,
        }
        if include_series:
            entry["series"] = series
        per_strategy[strat] = entry
    best = max(per_strategy, key=lambda k: per_strategy[k]["score"])
    return {
        "format": "urbanflow-resilience",
        "version": 1,
        "inModelOnly": True,
        "duration": duration,
        "bucketSeconds": bucket_seconds,
        "disruptionEnd": end,
        "seeds": list(seeds),
        "tolerance": {
            "relative": tolerance_rel,
            "absoluteSeconds": tolerance_abs,
            "holdBuckets": hold_buckets,
        },
        "scoreFormula": {
            "weights": SCORE_WEIGHTS,
            "peakScaleSeconds": PEAK_SCALE_SECONDS,
            "areaScaleSeconds": AREA_SCALE_SECONDS,
            "interval": "95% seeded bootstrap percentile interval of the mean score",
        },
        "strategies": per_strategy,
        "best": best,
        "note": (
            "Scores compare strategies inside this model under this scenario. "
            "Intervals are narrow with few seeds and do not cover model error."
        ),
    }
