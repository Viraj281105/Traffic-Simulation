"""Running stress suites and breakpoint sweeps on the shared process pool.

A *suite* runs generated stress scenarios under each strategy and classifies the failures of every run.
A *breakpoint sweep* runs one scenario at increasing levels of one factor (demand scale or driver
aggression) and reports where the strategy with the lowest mean delay changes, with a bootstrap estimate
of how sure that preference is at each level, and says so when there are too few levels or seeds to tell.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from src.scenario.documents import ScenarioDocument, compile_scenario, validate_scenario
from src.study.runner import (
    CancelledRun,
    Progress,
    SimTask,
    run_simulation_tasks_isolated,
)

from .classify import FAILURES, classify, rules
from .generator import GENERATOR_VERSION, generate, suite_fingerprint

Executor = Callable[
    [List[SimTask], Optional[Progress]], List[Union[Dict[str, Any], Exception]]
]

STRATEGIES = ("fixed_time", "adaptive", "roundabout", "signalised_roundabout")
BOOTSTRAP_RESAMPLES = 1000
MIN_LEVELS = 3
MIN_SEEDS = 2


class Cancelled(Exception):  # noqa: N818
    pass


def _engine(strategy: str) -> str:
    return "roundabout" if strategy == "signalised_roundabout" else strategy


def _with_strategy(scenario: Dict[str, Any], strategy: str) -> Optional[Dict[str, Any]]:
    """The scenario as ``strategy`` runs it, or None when the strategy does not apply (metering needs four arms)."""
    doc = copy.deepcopy(scenario)
    if strategy == "signalised_roundabout":
        arms = [d for d, a in doc["approaches"].items() if a is not None]
        if len(arms) != 4:
            return None
        rb = doc.setdefault("roundabout", {})
        rb["entryControl"] = "metered_entry"
        rb["entryMetering"] = {
            "phases": [
                {"entries": ["north", "south"], "green": 20.0},
                {"entries": ["east", "west"], "green": 20.0},
            ]
        }
    return doc


def _task(doc: Dict[str, Any], strategy: str, seed: int, label: str) -> SimTask:
    d = copy.deepcopy(doc)
    d["simulation"]["seed"] = seed
    parsed = ScenarioDocument.model_validate(d)
    engine = _engine(strategy)
    return SimTask(
        compile_scenario(parsed, engine),
        "roundabout" if engine == "roundabout" else "signal",
        parsed.simulation.duration,
        label,
        1.5 if engine == "roundabout" else 1.0,
    )


def _check(doc: Dict[str, Any], strategy: str) -> Optional[str]:
    result = validate_scenario(doc, [_engine(strategy)])
    return None if result["valid"] else "; ".join(str(e) for e in result["errors"][:2])


def _seeds(seed: int, count: int) -> List[int]:
    rng = random.Random(f"{GENERATOR_VERSION}:seeds:{seed}")
    return [rng.randrange(1, 2**31 - 1) for _ in range(count)]


def _approach_length(doc: Dict[str, Any]) -> float:
    lengths = [float(a.get("length", 200.0)) for a in doc["approaches"].values() if a]
    return min(lengths) if lengths else 200.0


def _run(
    executor: Executor, tasks: List[SimTask], progress: Optional[Progress]
) -> List[Union[Dict[str, Any], Exception]]:
    results = executor(tasks, progress)
    if any(isinstance(r, CancelledRun) for r in results):
        raise Cancelled()
    return results


# ---------------------------------------------------------------------------------------------------
# Suite
# ---------------------------------------------------------------------------------------------------
def run_suite(
    seed: int,
    count: int,
    strategies: Sequence[str],
    seeds_per_run: int,
    duration: float,
    executor: Executor = run_simulation_tasks_isolated,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    scenarios = generate(seed, count, duration)
    run_seeds = _seeds(seed, seeds_per_run)
    tasks: List[SimTask] = []
    plan: List[Tuple[int, str]] = []  # (scenario index, strategy) per block of seeds
    skipped: Dict[Tuple[int, str], str] = {}
    for item in scenarios:
        for strategy in strategies:
            doc = _with_strategy(item["scenario"], strategy)
            if doc is None:
                skipped[(item["index"], strategy)] = "not_applicable"
                continue
            reason = _check(doc, strategy)
            if reason is not None:
                skipped[(item["index"], strategy)] = "invalid_scenario: " + reason[:200]
                continue
            for s in run_seeds:
                tasks.append(
                    _task(doc, strategy, s, f"stress #{item['index']} {strategy} {s}")
                )
            plan.append((item["index"], strategy))
    results = _run(executor, tasks, progress) if tasks else []

    rows: List[Dict[str, Any]] = []
    width = len(run_seeds)
    by_block = {
        block: results[i * width : (i + 1) * width] for i, block in enumerate(plan)
    }
    totals = {s: {f: 0 for f in FAILURES} for s in strategies}
    for item in scenarios:
        length = _approach_length(item["scenario"])
        per_strategy: Dict[str, Any] = {}
        for strategy in strategies:
            key = (item["index"], strategy)
            if key in skipped:
                per_strategy[strategy] = {"skipped": skipped[key]}
                continue
            failures: Dict[str, int] = {}
            delays: List[float] = []
            errors = 0
            for res in by_block[key]:
                if isinstance(res, Exception):
                    errors += 1
                    continue
                m = res.get("metrics") or {}
                for f in classify(m, length):
                    failures[f] = failures.get(f, 0) + 1
                if isinstance(m.get("averageDelay"), (int, float)):
                    delays.append(float(m["averageDelay"]))
            for f in failures:
                totals[strategy][f] += 1
            per_strategy[strategy] = {
                "failures": failures,
                "runErrors": errors,
                "meanDelay": round(sum(delays) / len(delays), 4) if delays else None,
            }
        rows.append(
            {
                "index": item["index"],
                "family": item["family"],
                "name": item["scenario"]["name"],
                "results": per_strategy,
            }
        )
    return {
        "format": "urbanflow-stress-suite",
        "version": 1,
        "generator": GENERATOR_VERSION,
        "seed": seed,
        "suiteFingerprint": suite_fingerprint(scenarios),
        "seedsPerRun": len(run_seeds),
        "strategies": list(strategies),
        "rules": rules(),
        "scenarios": rows,
        "failureTotals": totals,
        "note": "Stationary extremes only: the engine has no time-varying demand or incidents. Failure "
        "rules are this lab's stated thresholds, not engineering standards; counts are scenarios with "
        "at least one failing run.",
    }


# ---------------------------------------------------------------------------------------------------
# Breakpoints
# ---------------------------------------------------------------------------------------------------
def _at_level(scenario: Dict[str, Any], factor: str, level: Any) -> Dict[str, Any]:
    doc = copy.deepcopy(scenario)
    if factor == "demand_scale":
        for arm in doc["approaches"].values():
            if arm is not None:
                arm["vehiclesPerHour"] = round(
                    min(7200.0, arm["vehiclesPerHour"] * float(level)), 2
                )
    else:
        doc.setdefault("traffic", {})["driverAggression"] = level
    return doc


def preference_shares(
    delays: Dict[str, List[Optional[float]]],
    rng: random.Random,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> Dict[str, float]:
    """Share of seed-bootstrap replicates in which each strategy has the lowest mean delay (paired seeds)."""
    names = sorted(delays)
    usable = [
        i
        for i in range(len(next(iter(delays.values()))))
        if all(delays[n][i] is not None for n in names)
    ]
    if not usable:
        return {}
    wins = {n: 0 for n in names}
    for _ in range(resamples):
        sample = [usable[rng.randrange(len(usable))] for _ in usable]
        means = {n: sum(delays[n][i] for i in sample) / len(sample) for n in names}  # type: ignore[misc]
        wins[min(names, key=lambda n: (means[n], n))] += 1
    return {n: round(w / resamples, 4) for n, w in wins.items()}


def run_breakpoints(
    scenario: Dict[str, Any],
    factor: str,
    levels: Sequence[Any],
    strategies: Sequence[str],
    seed: int,
    seeds_per_level: int,
    executor: Executor = run_simulation_tasks_isolated,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    run_seeds = _seeds(seed, seeds_per_level)
    tasks: List[SimTask] = []
    plan: List[Tuple[int, str]] = []
    skipped: Dict[Tuple[int, str], str] = {}
    for li, level in enumerate(levels):
        base = _at_level(scenario, factor, level)
        for strategy in strategies:
            doc = _with_strategy(base, strategy)
            reason = "not_applicable" if doc is None else _check(doc, strategy)
            if reason is not None or doc is None:
                skipped[(li, strategy)] = reason or "not_applicable"
                continue
            for s in run_seeds:
                tasks.append(
                    _task(
                        doc, strategy, s, f"breakpoint {factor}={level} {strategy} {s}"
                    )
                )
            plan.append((li, strategy))
    results = _run(executor, tasks, progress) if tasks else []
    width = len(run_seeds)
    by_block = {
        block: results[i * width : (i + 1) * width] for i, block in enumerate(plan)
    }

    rng = random.Random(f"{GENERATOR_VERSION}:bootstrap:{seed}")
    table: List[Dict[str, Any]] = []
    for li, level in enumerate(levels):
        delays: Dict[str, List[Optional[float]]] = {}
        for strategy in strategies:
            if (li, strategy) in skipped:
                continue
            delays[strategy] = [
                float(r["metrics"]["averageDelay"])
                if not isinstance(r, Exception)
                and isinstance(
                    (r.get("metrics") or {}).get("averageDelay"), (int, float)
                )
                else None
                for r in by_block[(li, strategy)]
            ]
        means = {
            s: (
                round(
                    sum(v for v in d if v is not None)
                    / len([v for v in d if v is not None]),
                    4,
                )
                if any(v is not None for v in d)
                else None
            )
            for s, d in delays.items()
        }
        feasible = {s: m for s, m in means.items() if m is not None}
        preferred = min(feasible, key=lambda s: (feasible[s], s)) if feasible else None
        shares = preference_shares(delays, rng) if len(delays) >= 2 else {}
        table.append(
            {
                "level": level,
                "meanDelay": means,
                "preferred": preferred,
                "preferenceShare": shares,
                "skipped": {s: r for (i, s), r in skipped.items() if i == li},
            }
        )

    too_few = []
    if len(levels) < MIN_LEVELS:
        too_few.append(f"fewer than {MIN_LEVELS} levels")
    if seeds_per_level < MIN_SEEDS:
        too_few.append(f"fewer than {MIN_SEEDS} seeds per level")
    breakpoints = []
    for a, b in zip(table, table[1:]):
        if a["preferred"] and b["preferred"] and a["preferred"] != b["preferred"]:
            breakpoints.append(
                {
                    "between": [a["level"], b["level"]],
                    "from": a["preferred"],
                    "to": b["preferred"],
                    "confidence": min(
                        a["preferenceShare"].get(a["preferred"], 0.0),
                        b["preferenceShare"].get(b["preferred"], 0.0),
                    ),
                }
            )
    canonical = json.dumps(
        {
            "scenario": scenario,
            "factor": factor,
            "levels": list(levels),
            "strategies": list(strategies),
            "seed": seed,
            "seeds": seeds_per_level,
        },
        sort_keys=True,
    )
    return {
        "format": "urbanflow-breakpoints",
        "version": 1,
        "factor": factor,
        "levels": list(levels),
        "strategies": list(strategies),
        "seedsPerLevel": seeds_per_level,
        "specFingerprint": hashlib.sha256(canonical.encode()).hexdigest()[:16],
        "table": table,
        "breakpoints": breakpoints,
        "tooFewToAssess": too_few or None,
        "note": "The breakpoint lies somewhere between the two levels shown; 'confidence' is the smaller "
        "of the two bootstrap preference shares (over seeds) and is not a probability that the real "
        "junction behaves this way. Sampling grid only: a change between two grid points can be missed.",
    }
