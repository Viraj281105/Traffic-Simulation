"""Simulation evaluator: runs every (candidate, seed) on the shared process pool in one batch.

Baselines are the existing controllers on the unchanged regime scenario, compiled exactly as a direct run
of that scenario would be, on the same seeds as the candidates (common random numbers).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from src.scenario.documents import ScenarioDocument, compile_scenario
from src.study.runner import (
    CancelledRun,
    Progress,
    SimTask,
    run_simulation_tasks_isolated,
)
from src.uncertainty.runner import TaskExecutor

from .models import Regime
from .search import Candidate, Outcome
from .space import candidate_document, engine_strategy

Result = Union[Dict[str, Any], Exception]


def run_task(document: Dict[str, Any], strategy: str, seed: int, label: str) -> SimTask:
    doc = copy.deepcopy(document)
    doc["simulation"]["seed"] = seed
    parsed = ScenarioDocument.model_validate(doc)
    engine = engine_strategy(strategy)
    return SimTask(
        config=compile_scenario(parsed, engine),
        geometry="roundabout" if engine == "roundabout" else "signal",
        duration=parsed.simulation.duration,
        label=label,
        cost=1.5 if engine == "roundabout" else 1.0,
    )


_SERVED = ("averageEntryWait", "admittedShareOfNominal", "unfinishedShare")


def _served(m: Dict[str, Any], key: str) -> Optional[float]:
    v = (
        (m.get("demandAccounting") or {}).get(key)
        if key == "admittedShareOfNominal"
        else m.get(key)
    )
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _queued(regime: Regime) -> bool:
    return regime.entryQueue is not None and regime.entryQueue.enabled


def objectives_of(
    results: Sequence[Result],
    delay_from_arrival: bool = False,
) -> Tuple[
    Optional[Tuple[float, ...]], Dict[str, float], List[Optional[float]], Optional[str]
]:
    """Mean objectives over a candidate's seeds; infeasible if any seed failed, collided or hit a limit.

    ``delay_from_arrival`` (the regime runs the point-queue entry model): the
    delay objective adds each run's ``averageEntryWait``, the wait outside
    the network of the same vehicles, so a candidate cannot lower its delay
    by keeping traffic out. Off (the default model): the in-network delay,
    exactly as before. Served demand (entry wait, admitted share, unfinished
    share) is reported beside the objectives either way, never optimised.
    """
    rows: List[Tuple[float, float, float, float]] = []
    per_seed: List[Optional[float]] = []
    reason: Optional[str] = None
    served: Dict[str, List[float]] = {k: [] for k in _SERVED}
    in_network: List[float] = []
    for result in results:
        if isinstance(result, Exception):
            reason = reason or "run_failed"
            per_seed.append(None)
            continue
        m = result.get("metrics") or {}
        throughput = float(m.get("throughput") or 0)
        if (m.get("collisionCount") or 0) > 0:
            reason = reason or "collision"
        elif m.get("vehicleLimitReached"):
            reason = reason or "vehicle_limit"
        elif throughput < 1:
            reason = reason or "no_completed_vehicles"
        delay = float(m.get("averageDelay") or 0.0)
        in_network.append(delay)
        for key in _SERVED:
            v = _served(m, key)
            if v is not None:
                served[key].append(v)
        if delay_from_arrival:
            delay += _served(m, "averageEntryWait") or 0.0
        per_seed.append(delay if throughput >= 1 else None)
        near = float(m.get("nearMissCount") or 0) / max(throughput, 1.0) * 1000.0
        rows.append((delay, -throughput, float(m.get("maxQueueLength") or 0), near))
    if reason is not None or not rows:
        return None, {}, per_seed, reason or "no_runs"
    mean = tuple(sum(r[k] for r in rows) / len(rows) for k in range(4))
    metrics = {
        "averageDelay": mean[0],
        "throughput": -mean[1],
        "maxQueueLength": mean[2],
        "nearMissesPer1000": mean[3],
    }
    if delay_from_arrival:
        # The objective above is the delay from arrival; keep the in-network
        # part readable on its own.
        metrics["inNetworkDelay"] = sum(in_network) / len(in_network)
    for key, values in served.items():
        if values:
            metrics[key] = round(sum(values) / len(values), 4)
    return mean, metrics, per_seed, None


class SimulationEvaluator:
    def __init__(
        self,
        progress: Optional[Progress] = None,
        executor: Optional[TaskExecutor] = None,
    ) -> None:
        self.progress = progress
        self.executor = executor or run_simulation_tasks_isolated

    def __call__(
        self,
        candidates: Sequence[Candidate],
        seeds: Sequence[int],
        regime: Regime,
        phase: str,
    ) -> Optional[List[Outcome]]:
        tasks: List[SimTask] = []
        for cand in candidates:
            document = candidate_document(regime, cand.genome, cand.strategy)
            for seed in seeds:
                tasks.append(
                    run_task(
                        document,
                        cand.strategy,
                        seed,
                        f"{phase} · {cand.key[:12]} · {seed}",
                    )
                )
        results = self.executor(tasks, self.progress)
        if any(isinstance(r, CancelledRun) for r in results):
            return None
        outcomes: List[Outcome] = []
        width = len(seeds)
        for i in range(len(candidates)):
            chunk = results[i * width : (i + 1) * width]
            objectives, metrics, per_seed, reason = objectives_of(
                chunk, delay_from_arrival=_queued(regime)
            )
            outcomes.append(Outcome(objectives, metrics, per_seed, reason))
        return outcomes
