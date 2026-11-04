"""Sensitivity analysis: which input changes the result most.

Two methods, both reproducible from ``seed`` (no wall-clock or global RNG):

One-at-a-time (OAT)
    Every input is moved alone from a baseline (default: the midpoint of its
    range) to its low and to its high bound. ``swing = |f(high) - f(low)|``;
    inputs are ranked by swing and ``share`` is swing / sum of swings.
    Cost: ``1 + 2k`` evaluations for ``k`` inputs. Misses interactions.

Sobol-lite
    Variance-based first-order (``S1``) and total-order (``ST``) indices with a
    Saltelli sampling plan and plain pseudo-random (not quasi-random) points.
    Inputs are uniform on their ranges::

        S1_i = mean(f(B) * (f(AB_i) - f(A))) / Var       (Saltelli 2010)
        ST_i = 0.5 * mean((f(A) - f(AB_i))^2) / Var      (Jansen 1999)

    where A and B are two independent ``n x k`` sample matrices, AB_i is A
    with column i taken from B, and Var is the variance of f over A and B.
    Cost: ``n * (k + 2)`` evaluations. With a small ``n`` the estimates are
    noisy and can fall slightly outside [0, 1]; they are reported unclipped
    together with ``clipped`` flags, and ranked by ``ST``. "Lite" means no
    bootstrap interval and no quasi-random sequence: treat ranks as indicative.

The model is any ``evaluate_many(points) -> values`` callable, where each point
is a ``{name: value}`` dict, so the maths is testable without a simulation.
``simulation_evaluator`` builds one that runs the traffic simulation, averaging
a metric over ``num_seeds`` seeded repetitions with the same seeds at every
point (common random numbers), which keeps simulation noise out of the contrast.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

Bounds = Mapping[str, Tuple[float, float]]
Point = Dict[str, float]
EvaluateMany = Callable[[List[Point]], List[float]]

# name -> (config path, integer-valued?)
PARAMETER_PATHS: Dict[str, Tuple[Tuple[str, ...], bool]] = {
    "arrivalRate": (("traffic", "arrivalRate"), False),
    "greenTime": (("controller", "greenTime"), False),
    "speedLimit": (("roads", "speedLimit"), False),
    "approachLength": (("roads", "approachLength"), False),
    "lanesPerApproach": (("roads", "lanesPerApproach"), True),
}


def _check_bounds(bounds: Bounds) -> List[str]:
    if not bounds:
        raise ValueError("at least one input range is required")
    for name, (lo, hi) in bounds.items():
        if not (math.isfinite(lo) and math.isfinite(hi)) or lo >= hi:
            raise ValueError(f"range for {name!r} must satisfy low < high")
    return list(bounds)


def one_at_a_time(
    evaluate_many: EvaluateMany,
    bounds: Bounds,
    baseline: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """OAT sensitivity; see the module docstring. Evaluates in one batch."""
    names = _check_bounds(bounds)
    base: Point = {
        n: (baseline[n] if baseline and n in baseline else sum(bounds[n]) / 2.0)
        for n in names
    }
    points: List[Point] = [dict(base)]
    for n in names:
        lo, hi = bounds[n]
        points.append({**base, n: lo})
        points.append({**base, n: hi})
    values = evaluate_many(points)
    if len(values) != len(points):
        raise ValueError("evaluator returned the wrong number of values")

    rows: List[Dict[str, Any]] = []
    for i, n in enumerate(names):
        f_lo, f_hi = values[1 + 2 * i], values[2 + 2 * i]
        rows.append(
            {
                "input": n,
                "low": bounds[n][0],
                "high": bounds[n][1],
                "atLow": f_lo,
                "atHigh": f_hi,
                "effect": f_hi - f_lo,
                "swing": abs(f_hi - f_lo),
            }
        )
    total = math.fsum(r["swing"] for r in rows)
    for r in rows:
        r["share"] = (r["swing"] / total) if total > 0.0 else None
    rows.sort(key=lambda r: (-r["swing"], r["input"]))
    for rank, r in enumerate(rows, start=1):
        r["rank"] = rank
    return {
        "method": "one-at-a-time",
        "baseline": base,
        "baselineValue": values[0],
        "evaluations": len(points),
        "ranking": rows,
        "note": (
            "Each input moved alone from the baseline; interactions between "
            "inputs are not captured."
        ),
    }


def sobol_lite(
    evaluate_many: EvaluateMany,
    bounds: Bounds,
    n_samples: int = 16,
    seed: int = 0,
) -> Dict[str, Any]:
    """Variance-based first/total-order indices; see the module docstring."""
    names = _check_bounds(bounds)
    if n_samples < 2:
        raise ValueError("n_samples must be at least 2")
    k = len(names)
    rng = random.Random(f"urbanflow-sobol-lite-v1:{seed}")

    def draw() -> List[List[float]]:
        return [
            [bounds[n][0] + rng.random() * (bounds[n][1] - bounds[n][0]) for n in names]
            for _ in range(n_samples)
        ]

    a, b = draw(), draw()

    def as_point(row: Sequence[float]) -> Point:
        return {n: row[j] for j, n in enumerate(names)}

    points: List[Point] = [as_point(r) for r in a] + [as_point(r) for r in b]
    for j in range(k):
        for r_a, r_b in zip(a, b):
            row = list(r_a)
            row[j] = r_b[j]
            points.append(as_point(row))
    values = evaluate_many(points)
    if len(values) != len(points):
        raise ValueError("evaluator returned the wrong number of values")

    f_a = values[:n_samples]
    f_b = values[n_samples : 2 * n_samples]
    both = f_a + f_b
    mean = math.fsum(both) / len(both)
    var = math.fsum((v - mean) ** 2 for v in both) / (len(both) - 1)

    rows: List[Dict[str, Any]] = []
    for j, n in enumerate(names):
        start = 2 * n_samples + j * n_samples
        f_ab = values[start : start + n_samples]
        if var > 0.0:
            s1 = math.fsum(fb * (fab - fa) for fa, fb, fab in zip(f_a, f_b, f_ab))
            st = math.fsum((fa - fab) ** 2 for fa, fab in zip(f_a, f_ab))
            s1 = s1 / n_samples / var
            st = 0.5 * st / n_samples / var
        else:
            s1 = st = None  # type: ignore[assignment]
        rows.append(
            {
                "input": n,
                "low": bounds[n][0],
                "high": bounds[n][1],
                "firstOrder": s1,
                "totalOrder": st,
                "clipped": (
                    None
                    if s1 is None or st is None
                    else bool(not 0.0 <= s1 <= 1.0 or not 0.0 <= st <= 1.0)
                ),
            }
        )
    rows.sort(
        key=lambda r: (
            -(r["totalOrder"] if r["totalOrder"] is not None else -math.inf),
            r["input"],
        )
    )
    for rank, r in enumerate(rows, start=1):
        r["rank"] = rank
    return {
        "method": "sobol-lite",
        "seed": seed,
        "nSamples": n_samples,
        "evaluations": len(points),
        "outputMean": mean,
        "outputVariance": var,
        "ranking": rows,
        "note": (
            "Saltelli sampling with pseudo-random points, first-order (Saltelli "
            "2010) and total-order (Jansen 1999) estimators. Small samples are "
            "noisy: indices can fall outside 0..1; treat ranks as indicative."
        ),
    }


def apply_inputs(base_config: Mapping[str, Any], point: Mapping[str, float]) -> Dict[str, Any]:
    """A copy of ``base_config`` with each named input written to its config path."""
    import copy

    cfg: Dict[str, Any] = copy.deepcopy(dict(base_config))
    for name, value in point.items():
        if name not in PARAMETER_PATHS:
            raise ValueError(f"unsupported input {name!r}")
        path, is_int = PARAMETER_PATHS[name]
        node = cfg
        for key in path[:-1]:
            node = node.setdefault(key, {})
        if name == "lanesPerApproach":
            lanes = max(1, int(round(value)))
            node[path[-1]] = {d: lanes for d in ("north", "south", "east", "west")}
        else:
            node[path[-1]] = int(round(value)) if is_int else float(value)
    return cfg


def simulation_evaluator(
    base_config: Mapping[str, Any],
    geometry: str,
    duration: float,
    metric_names: Sequence[str],
    num_seeds: int,
    base_seed: int,
) -> EvaluateMany:
    """``evaluate_many`` that runs the simulation (mean of ``metric_names`` over seeds)."""
    from src.study.multiseed import _metric, seeded_run_config
    from src.study.runner import GEOMETRY_TITLES, SimTask, run_simulation_tasks
    from src.study.seeds import derive_run_seeds

    seeds = derive_run_seeds(base_seed, num_seeds)

    def evaluate_many(points: List[Point]) -> List[float]:
        tasks = []
        for i, p in enumerate(points):
            cfg = apply_inputs(base_config, p)
            for s in seeds:
                tasks.append(
                    SimTask(
                        config=seeded_run_config(cfg, s, duration),
                        geometry=geometry,
                        duration=duration,
                        label=f"Point {i + 1}/{len(points)} · {GEOMETRY_TITLES[geometry]}",
                        cost=1.5 if geometry == "roundabout" else 1.0,
                    )
                )
        results = run_simulation_tasks(tasks)
        out: List[float] = []
        for i in range(len(points)):
            chunk = results[i * num_seeds : (i + 1) * num_seeds]
            vals = [_metric(r["metrics"], metric_names) for r in chunk]
            out.append(math.fsum(vals) / len(vals))
        return out

    return evaluate_many
