"""Paired common-random-number ensemble runner (W1 WP3, strategy section 5.3 and 5.6, ADR-015).

For every sampled condition *i* and replication *k*, **all alternatives run the same perturbed scenario with
the same engine seed** (``derive_seed(spec.seed, i, k)``); they differ only in their own control. All runs
of the ensemble are submitted to the shared process pool in one batch, so the pool is kept busy and the
result does not depend on the order in which workers finish (results come back in task order and the
analysis sorts by condition index).

Failures never abort the ensemble and are never repaired:

* the perturbed scenario fails validation        -> condition excluded, reason ``validation_failed``;
* a simulation raises                            -> ``run_failed``;
* a run hits the vehicle limit                   -> ``vehicle_limit``;
* no vehicle finished its trip after warm-up     -> ``no_completed_vehicles``: the engine reports a
  delay of 0.0 for an empty sample, which is not a measurement and must never be compared;
* the primary indicator is missing or not finite -> ``non_finite``.

A condition is excluded for **every** alternative if any of its runs is unusable (pairing is preserved).
``timeout`` and ``deadlock`` are reserved reasons: simulations have a fixed number of ticks, so a run cannot
hang, and the engine exposes no deadlock flag yet.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

from src.scenario.documents import (
    STRATEGIES,
    ScenarioDocument,
    compile_scenario,
    validate_scenario,
)
from src.study.runner import (
    CancelledRun,
    Progress,
    SimTask,
    run_simulation_tasks_isolated,
    study_workers,
)

from .analysis import ConditionResult, analyze, result_fingerprint
from .apply import FactorApplicationError, apply_factors, preflight
from .sampler import Condition, sample_conditions
from .spec import UncertaintySpec, fingerprint, run_counts

TaskExecutor = Callable[
    [List[SimTask], Optional[Progress]], List[Union[Dict[str, Any], Exception]]
]

_ROUNDABOUT_COST = 1.5  # scheduling hint only: roundabout runs are heavier


@dataclass(frozen=True)
class RunAlternative:
    """One alternative: a strategy and the scenario it controls (already patched from the base)."""

    id: str
    strategy: str
    document: ScenarioDocument


class EnsembleRefusedError(ValueError):
    """The experiment cannot run at all (problems found before any simulation)."""

    def __init__(self, errors: Sequence[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def run_key(condition: int, replication: int, alternative: str) -> str:
    """Stable identity of one simulation run inside an experiment (used by checkpoints)."""
    return f"{condition}:{replication}:{alternative}"


@dataclass
class EnsembleRun:
    sampled: List[Condition]
    conditions: List[ConditionResult]
    runs_planned: int
    runs_executed: int
    elapsed_seconds: float
    workers: int
    notes: List[str] = field(default_factory=list)
    # Cancelled before every run finished. ``checkpoint`` holds the metrics of every run that did
    # finish (by run_key); a later call passes it back as ``completed`` and runs only the rest.
    cancelled: bool = False
    checkpoint: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    runs_from_checkpoint: int = 0


def _check_alternatives(alternatives: Sequence[RunAlternative]) -> None:
    errors: List[str] = []
    ids = [a.id for a in alternatives]
    if len(alternatives) < 2:
        errors.append("an experiment needs at least two alternatives")
    if len(set(ids)) != len(ids):
        errors.append("alternative ids must be unique")
    for alt in alternatives:
        if alt.strategy not in STRATEGIES:
            errors.append(f"{alt.id}: unknown strategy {alt.strategy!r}")
    if errors:
        raise EnsembleRefusedError(errors)


def _indicator(result: Dict[str, Any], name: str) -> float:
    value = (result.get("metrics") or {}).get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return math.nan
    return float(value)


def _nothing_completed(result: Dict[str, Any]) -> bool:
    """True when the run reports that no vehicle finished its trip after warm-up.

    The delay indicators are then undefined, but the collector reports 0.0 for them. A run without a
    ``throughput`` figure (a stub) is given the benefit of the doubt; every real run has one.
    """
    throughput = (result.get("metrics") or {}).get("throughput")
    return (
        isinstance(throughput, (int, float))
        and not isinstance(throughput, bool)
        and throughput < 1
    )


def _limit_reached(result: Dict[str, Any]) -> bool:
    return bool((result.get("metrics") or {}).get("vehicleLimitReached"))


# When a condition has several problems, the first listed is the one reported.
_PRECEDENCE = (
    "validation_failed",
    "run_failed",
    "vehicle_limit",
    "no_completed_vehicles",
    "non_finite",
)


def _note_failure(failures: Dict[int, str], index: int, reason: str) -> None:
    current = failures.get(index)
    if current is None or _PRECEDENCE.index(reason) < _PRECEDENCE.index(current):
        failures[index] = reason


def run_ensemble(
    spec: UncertaintySpec,
    alternatives: Sequence[RunAlternative],
    *,
    progress: Optional[Progress] = None,
    executor: TaskExecutor = run_simulation_tasks_isolated,
    completed: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> EnsembleRun:
    """Sample the conditions, run every (condition, alternative, replication) and collect the outcomes."""
    _check_alternatives(alternatives)
    problems: List[str] = []
    for alt in alternatives:
        problems.extend(f"{alt.id}: {e}" for e in preflight(alt.document, spec.factors))
    if problems:
        raise EnsembleRefusedError(problems)

    sampled = sample_conditions(spec)
    n_alts = len(alternatives)
    counts = run_counts(spec, n_alts)

    # 1. Build and compile every run of each condition up front; a condition that cannot be built is
    #    excluded (never repaired) and none of its runs is queued.
    excluded: Dict[int, str] = {}
    planned: Dict[
        int, List[tuple[int, int, SimTask]]
    ] = {}  # condition -> (rep, alt position, task)
    for condition in sampled:
        runs: List[tuple[int, int, SimTask]] = []
        try:
            for pos, alt in enumerate(alternatives):
                perturbed = apply_factors(alt.document, spec.factors, condition.values)
                check = validate_scenario(perturbed.model_dump(), [alt.strategy])
                if not check["valid"]:
                    raise FactorApplicationError("; ".join(check["errors"][:2]))
                for rep, seed in enumerate(condition.seeds):
                    document = perturbed.model_copy(deep=True)
                    document.simulation.seed = (
                        seed  # common random numbers: one seed for all alternatives
                    )
                    runs.append(
                        (
                            rep,
                            pos,
                            SimTask(
                                config=compile_scenario(document, alt.strategy),
                                geometry=(
                                    "roundabout"
                                    if alt.strategy == "roundabout"
                                    else "signal"
                                ),
                                duration=document.simulation.duration,
                                label=f"condition {condition.index} · rep {rep} · {alt.id}",
                                cost=(
                                    _ROUNDABOUT_COST
                                    if alt.strategy == "roundabout"
                                    else 1.0
                                ),
                            ),
                        )
                    )
        except (FactorApplicationError, ValueError):
            excluded[condition.index] = "validation_failed"
            continue
        planned[condition.index] = sorted(runs, key=lambda r: (r[0], r[1]))

    # 2. One batch of simulations in (condition, replication, alternative) order.
    tasks: List[SimTask] = []
    keys: List[
        tuple[int, int, int]
    ] = []  # (condition, replication, alternative position)
    for condition in sampled:
        for rep, pos, task in planned.get(condition.index, []):
            tasks.append(task)
            keys.append((condition.index, rep, pos))

    # Runs finished before a cancellation are not repeated: their stored metrics stand in for a result.
    # Every run is deterministic (condition, replication and seed fix it), so a resumed experiment
    # produces exactly the outcomes of an uninterrupted one.
    done = completed or {}
    key_of = [run_key(index, rep, alternatives[pos].id) for (index, rep, pos) in keys]
    todo = [i for i, key in enumerate(key_of) if key not in done]
    started = time.monotonic()
    fresh = executor([tasks[i] for i in todo], progress) if todo else []
    elapsed = time.monotonic() - started
    if len(fresh) != len(todo):
        raise RuntimeError(
            "the executor returned a different number of results than tasks"
        )
    results: List[Union[Dict[str, Any], Exception]] = [{}] * len(tasks)
    for i, key in enumerate(key_of):
        if key in done:
            results[i] = dict(done[key])
    cancelled_conditions: set[int] = set()
    checkpoint: Dict[str, Dict[str, Any]] = {
        key: {"metrics": dict(done[key].get("metrics") or {})} for key in done
    }
    for i, outcome in zip(todo, fresh):
        results[i] = outcome
        if isinstance(outcome, CancelledRun):
            cancelled_conditions.add(keys[i][0])
        elif not isinstance(outcome, Exception):
            checkpoint[key_of[i]] = {"metrics": dict(outcome.get("metrics") or {})}

    # 3. Gather outcomes per condition and apply the exclusion rules.
    outcomes: Dict[int, Dict[str, List[float]]] = {}
    failures: Dict[int, str] = {}
    for (index, _rep, pos), result in zip(keys, results):
        if isinstance(result, CancelledRun):
            continue
        per_alt = outcomes.setdefault(index, {}).setdefault(alternatives[pos].id, [])
        if isinstance(result, Exception):
            per_alt.append(math.nan)
            _note_failure(failures, index, "run_failed")
            continue
        value = _indicator(result, spec.primaryIndicator)
        per_alt.append(value)
        if _limit_reached(result):
            _note_failure(failures, index, "vehicle_limit")
        if _nothing_completed(result):
            _note_failure(failures, index, "no_completed_vehicles")
        if not math.isfinite(value):
            _note_failure(failures, index, "non_finite")

    conditions: List[ConditionResult] = []
    for condition in sampled:
        index = condition.index
        reason = (
            excluded.get(index)
            or ("incomplete_cancelled" if index in cancelled_conditions else None)
            or failures.get(index)
        )
        conditions.append(
            ConditionResult(
                index=index,
                strata=dict(condition.strata),
                outcomes={} if reason else outcomes.get(index, {}),
                exclusion=reason,
            )
        )
    return EnsembleRun(
        sampled=sampled,
        conditions=conditions,
        runs_planned=counts["totalRuns"],
        runs_executed=len(tasks),
        elapsed_seconds=elapsed,
        workers=study_workers(),
        cancelled=bool(cancelled_conditions),
        checkpoint=checkpoint,
        runs_from_checkpoint=len(tasks) - len(todo),
    )


def run_experiment(
    spec: UncertaintySpec,
    alternatives: Sequence[RunAlternative],
    baseline: str,
    *,
    progress: Optional[Progress] = None,
    executor: TaskExecutor = run_simulation_tasks_isolated,
    completed: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run the ensemble and analyse it. The specification is fingerprinted before any run.

    A cancelled ensemble returns ``cancelled: True`` with the checkpoint of finished runs and, when the
    finished conditions allow one, a partial analysis whose unfinished conditions are excluded as
    ``incomplete_cancelled``. It has no ``resultFingerprint``: only a complete run is fingerprinted."""
    spec_fingerprint = fingerprint(
        spec
    )  # pre-declaration: computed before the first simulation
    run = run_ensemble(
        spec, alternatives, progress=progress, executor=executor, completed=completed
    )
    analysis: Optional[Dict[str, Any]]
    try:
        analysis = analyze(
            run.conditions,
            alternatives=[a.id for a in alternatives],
            baseline=baseline,
            replications=spec.replications,
            factor_ids=[f.id for f in spec.factors],
            primary_indicator=spec.primaryIndicator,
            tie_tolerance=spec.tieTolerance,
            seed=spec.seed,
            predeclared=bool(spec_fingerprint),
        )
    except ValueError:
        if not run.cancelled:
            raise
        analysis = None  # too little finished to analyse; the checkpoint is still kept
    execution = {
        "runsPlanned": run.runs_planned,
        "runsExecuted": run.runs_executed,
        "runsFromCheckpoint": run.runs_from_checkpoint,
        "workers": run.workers,
        "wallSeconds": round(run.elapsed_seconds, 3),
    }
    if run.cancelled:
        return {
            "cancelled": True,
            "specFingerprint": spec_fingerprint,
            "analysis": analysis,
            "checkpoint": run.checkpoint,
            "execution": execution,
        }
    assert analysis is not None
    return {
        "checkpoint": run.checkpoint,
        "specFingerprint": spec_fingerprint,
        "resultFingerprint": result_fingerprint(analysis),
        "analysis": analysis,
        # Execution details are diagnostic and kept out of the fingerprinted analysis: they may differ
        # between machines without changing the result.
        "execution": execution,
    }
