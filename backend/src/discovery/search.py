"""The search protocol: tuning -> selection -> held-out evaluation -> unseen conditions (strategy 15.2.5).

Seed pools are disjoint and drawn from the search seed. The held-out list is hashed and recorded *before*
the search starts and can only be read once the search has finished (``SeedPools.held_out`` raises
otherwise), so no tuning or selection decision can depend on it. The budget is a hard stop, cancellation
takes effect at the next batch boundary and leaves a consistent incomplete result, and the whole run is a
deterministic function of the specification (same spec and seed => same trace fingerprint).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from . import nsga2
from .models import (
    BASELINES,
    OBJECTIVES,
    RESULT_FORMAT,
    SEARCH_VERSION,
    UNSEEN_AGGRESSION,
    UNSEEN_DEMAND_SCALES,
    UNSEEN_SEEDS,
    Regime,
    SearchSpec,
    planned_runs,
)
from .space import (
    Genome,
    candidate_patch,
    crossover,
    fingerprint,
    mutate,
    random_genome,
    relevant,
    validate_candidate,
)

EXPERIMENTAL_NOTE = (
    "EXPERIMENTAL: found by search under the declared regime and assumptions, in this simulator only. "
    "It says nothing about real-world performance or safety, and it is not a recommendation."
)
BOOTSTRAP_RESAMPLES = 2000
MAX_SAMPLING_ATTEMPTS = 50


@dataclass(frozen=True)
class Candidate:
    """A genome (``None`` for an unchanged baseline) and the strategy it runs."""

    strategy: str
    genome: Optional[Genome] = None

    @property
    def key(self) -> str:
        return (
            fingerprint(self.genome)
            if self.genome is not None
            else f"baseline:{self.strategy}"
        )


@dataclass
class Outcome:
    """Objectives averaged over seeds (minimised; ``None`` when infeasible) and per-seed delays."""

    objectives: Optional[Tuple[float, ...]]
    metrics: Dict[str, float]
    per_seed_delay: List[Optional[float]]
    infeasible_reason: Optional[str] = None


class Evaluator(Protocol):
    def __call__(
        self,
        candidates: Sequence[Candidate],
        seeds: Sequence[int],
        regime: Regime,
        phase: str,
    ) -> Optional[List[Outcome]]:
        """One outcome per candidate, or ``None`` when the batch was cancelled."""
        ...


class SeedPools:
    def __init__(self, seed: int, tuning: int, selection: int, held_out: int) -> None:
        rng = random.Random(f"urbanflow-discovery-seeds:{seed}")
        drawn: List[int] = []
        while len(drawn) < tuning + selection + held_out:
            value = rng.randrange(1, 2**31 - 1)
            if value not in drawn:
                drawn.append(value)
        self.tuning = drawn[:tuning]
        self.selection = drawn[tuning : tuning + selection]
        self._held_out = drawn[tuning + selection :]
        assert not (set(self.tuning) & set(self.selection) & set(self._held_out))
        assert not (set(self.tuning) & set(self._held_out))
        assert not (set(self.selection) & set(self._held_out))
        self.held_out_hash = hashlib.sha256(
            json.dumps(self._held_out).encode()
        ).hexdigest()
        self._released = False

    def release(self) -> None:
        self._released = True

    @property
    def held_out(self) -> List[int]:
        if not self._released:
            raise RuntimeError(
                "held-out seeds are sealed until the search has finished"
            )
        return list(self._held_out)

    @staticmethod
    def hash_of(values: Sequence[int]) -> str:
        return hashlib.sha256(json.dumps(list(values)).encode()).hexdigest()


@dataclass
class SearchState:
    runs_used: int = 0
    log: List[Dict[str, Any]] = field(default_factory=list)
    rejected: Dict[str, int] = field(default_factory=dict)
    cancelled: bool = False
    budget_exhausted: bool = False


def _rounded(values: Optional[Tuple[float, ...]]) -> Optional[List[float]]:
    return None if values is None else [round(v, 6) for v in values]


def _objectives_dict(values: Optional[Tuple[float, ...]]) -> Optional[Dict[str, float]]:
    if values is None:
        return None
    out = dict(zip(OBJECTIVES, values))
    out["throughput"] = -out["throughput"]  # reported in its natural direction
    return {k: round(v, 6) for k, v in out.items()}


def _bootstrap_ci(diffs: List[float], seed: str) -> Tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(
        sum(diffs[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(BOOTSTRAP_RESAMPLES)
    )
    low = means[int(0.025 * (BOOTSTRAP_RESAMPLES - 1))]
    high = means[int(math.ceil(0.975 * (BOOTSTRAP_RESAMPLES - 1)))]
    return round(low, 6), round(high, 6)


class Search:
    def __init__(
        self,
        spec: SearchSpec,
        evaluator: Evaluator,
        should_stop: Callable[[], bool] = lambda: False,
        on_progress: Callable[[str, int, int], None] = lambda phase, used, planned: (
            None
        ),
    ) -> None:
        self.spec = spec
        self.evaluator = evaluator
        self.should_stop = should_stop
        self.on_progress = on_progress
        self.state = SearchState()
        self.pools = SeedPools(
            spec.seed,
            spec.budget.tuningSeeds,
            spec.budget.selectionSeeds,
            spec.budget.heldOutSeeds,
        )
        self.planned = planned_runs(spec)
        self.rng = random.Random(f"urbanflow-discovery:{spec.seed}")
        self.strategies: List[str] = [str(x) for x in dict.fromkeys(spec.strategies)]
        # fingerprint -> (genome, tuning objectives, generation first seen)
        self.archive: Dict[str, Tuple[Genome, Optional[Tuple[float, ...]], int]] = {}

    # ---- evaluation with budget, cancellation and logging -----------------------------------------
    def _evaluate(
        self,
        candidates: List[Candidate],
        seeds: List[int],
        phase: str,
        regime: Optional[Regime] = None,
        generation: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Outcome]]:
        needed = len(candidates) * len(seeds)
        if self.should_stop():
            self.state.cancelled = True
            return None
        if self.state.runs_used + needed > self.planned:
            self.state.budget_exhausted = True
            return None
        outcomes = self.evaluator(candidates, seeds, regime or self.spec.regime, phase)
        if outcomes is None:
            self.state.cancelled = True
            return None
        self.state.runs_used += needed
        for cand, out in zip(candidates, outcomes):
            entry: Dict[str, Any] = {
                "phase": phase,
                "candidate": cand.key,
                "strategy": cand.strategy,
                "seedsHash": SeedPools.hash_of(seeds),
                "objectives": _rounded(out.objectives),
                "infeasible": out.infeasible_reason,
            }
            if generation is not None:
                entry["generation"] = generation
            if extra:
                entry.update(extra)
            self.state.log.append(entry)
        self.on_progress(phase, self.state.runs_used, self.planned)
        return outcomes

    def _valid_genome(self, make: Callable[[], Genome]) -> Optional[Genome]:
        for _ in range(MAX_SAMPLING_ATTEMPTS):
            genome = make()
            reason = validate_candidate(self.spec.regime, genome)
            if reason is None:
                return genome
            code = "rejected_by_validator"
            self.state.rejected[code] = self.state.rejected.get(code, 0) + 1
            self.state.log.append(
                {
                    "phase": "validation",
                    "candidate": fingerprint(genome),
                    "rejected": reason[:300],
                }
            )
        return None

    # ---- tuning -----------------------------------------------------------------------------------
    def _tune(self) -> None:
        b = self.spec.budget
        population: List[Genome] = []
        seen: set[str] = set()
        for _ in range(b.population * 4):
            if len(population) >= b.population:
                break
            genome = self._valid_genome(
                lambda: random_genome(self.rng, self.strategies)
            )
            if genome is not None and fingerprint(genome) not in seen:
                seen.add(fingerprint(genome))
                population.append(genome)
        objectives = self._score(population, generation=0)
        if objectives is None:
            return
        for gen in range(1, b.generations):
            rank, crowd = nsga2.rank_and_crowding(objectives)
            offspring: List[Genome] = []
            attempts = 0
            while len(offspring) < b.population and attempts < b.population * 10:
                attempts += 1

                def make() -> Genome:
                    a = population[nsga2.tournament(self.rng, rank, crowd)]
                    c = population[nsga2.tournament(self.rng, rank, crowd)]
                    return mutate(self.rng, crossover(self.rng, a, c), self.strategies)

                child = self._valid_genome(make)
                if child is None:
                    continue
                key = fingerprint(child)
                if key in self.archive or key in {fingerprint(o) for o in offspring}:
                    continue
                offspring.append(child)
            child_objectives = self._score(offspring, generation=gen)
            if child_objectives is None:
                return
            pool = population + offspring
            pool_objectives = objectives + child_objectives
            survivors = nsga2.select_survivors(pool_objectives, b.population)
            population = [pool[i] for i in survivors]
            objectives = [pool_objectives[i] for i in survivors]

    def _score(
        self, genomes: List[Genome], generation: int
    ) -> Optional[List[Optional[Tuple[float, ...]]]]:
        if not genomes:
            return []
        candidates = [Candidate(g["strategy"], g) for g in genomes]
        outcomes = self._evaluate(
            candidates, self.pools.tuning, "tuning", generation=generation
        )
        if outcomes is None:
            return None
        for genome, out in zip(genomes, outcomes):
            self.archive.setdefault(
                fingerprint(genome), (genome, out.objectives, generation)
            )
        return [o.objectives for o in outcomes]

    # ---- the protocol -----------------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        self.on_progress("tuning", 0, self.planned)
        self._tune()
        entries = list(self.archive.values())
        points = [e[1] for e in entries]
        fronts = nsga2.non_dominated_sort(points) if points else []
        first = [i for i in fronts[0] if points[i] is not None] if fronts else []
        keep = nsga2.select_survivors(
            [points[i] for i in first], min(len(first), self.spec.budget.paretoCap)
        )
        pareto_entries = [entries[first[j]] for j in keep]
        pareto = [
            {
                "candidate": fingerprint(g),
                "generation": gen,
                "genome": relevant(g),
                "patch": candidate_patch(g),
                "tuningObjectives": _objectives_dict(obj),
            }
            for g, obj, gen in pareto_entries
        ]

        # Selection: the Pareto members on fresh seeds; the shortlist is chosen here, never on held-out.
        shortlist: List[Genome] = []
        selection_rows: List[Dict[str, Any]] = []
        if pareto_entries and not self.state.cancelled:
            genomes = [g for g, _, _ in pareto_entries]
            outcomes = self._evaluate(
                [Candidate(g["strategy"], g) for g in genomes],
                self.pools.selection,
                "selection",
            )
            if outcomes is not None:
                sel_points = [o.objectives for o in outcomes]
                chosen = nsga2.select_survivors(
                    sel_points, min(self.spec.budget.shortlist, len(genomes))
                )
                shortlist = [genomes[i] for i in chosen]
                selection_rows = [
                    {
                        "candidate": fingerprint(g),
                        "selectionObjectives": _objectives_dict(o.objectives),
                        "shortlisted": i in chosen,
                    }
                    for i, (g, o) in enumerate(zip(genomes, outcomes))
                ]

        # The search is over: only now may the held-out seeds be read.
        self.pools.release()
        held_out = (
            self._held_out(shortlist)
            if shortlist and not self.state.cancelled
            else None
        )
        unseen = (
            self._unseen(shortlist)
            if held_out is not None
            and self.spec.budget.unseenGrid
            and not self.state.cancelled
            else None
        )
        best_on_tuning = (
            min(
                (e for e in pareto_entries if e[0] in shortlist),
                key=lambda e: e[1][0] if e[1] else math.inf,
                default=None,
            )
            if pareto_entries
            else None
        )
        loses = None
        if held_out is not None and best_on_tuning is not None:
            row = held_out["candidates"].get(fingerprint(best_on_tuning[0]))
            if row is not None:
                loses = any(
                    (v.get("meanDifference") or 0) > 0
                    for v in row["versusBaselines"].values()
                )

        status = "cancelled" if self.state.cancelled else "completed"
        trace = hashlib.sha256(
            json.dumps(self.state.log, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        return {
            "format": RESULT_FORMAT,
            "version": SEARCH_VERSION,
            "status": status,
            "complete": status == "completed" and held_out is not None,
            "experimental": EXPERIMENTAL_NOTE,
            "method": "Bounded multi-objective evolutionary search (NSGA-II-style non-dominated sorting "
            "with crowding distance); not a learned model.",
            "specFingerprint": self.spec.fingerprint(),
            "traceFingerprint": trace,
            "runs": {"planned": self.planned, "used": self.state.runs_used},
            "budgetExhausted": self.state.budget_exhausted,
            "rejected": dict(self.state.rejected),
            "seedPools": {
                "tuning": len(self.pools.tuning),
                "selection": len(self.pools.selection),
                "heldOut": self.spec.budget.heldOutSeeds,
                "heldOutHashCommittedBeforeSearch": self.pools.held_out_hash,
                "disjoint": True,
            },
            "pareto": pareto,
            "selection": selection_rows,
            "heldOut": held_out,
            "bestOnTuningLosesOnHeldOut": loses,
            "preferenceChanges": unseen,
            "evaluationLog": self.state.log,
        }

    def _held_out(self, shortlist: List[Genome]) -> Optional[Dict[str, Any]]:
        seeds = self.pools.held_out
        candidates = [Candidate(g["strategy"], g) for g in shortlist] + [
            Candidate(s) for s in BASELINES
        ]
        outcomes = self._evaluate(candidates, seeds, "held_out")
        if outcomes is None:
            return None
        by_key = {c.key: o for c, o in zip(candidates, outcomes)}
        baselines = {s: by_key[f"baseline:{s}"] for s in BASELINES}
        rows: Dict[str, Any] = {}
        for genome in shortlist:
            key = fingerprint(genome)
            out = by_key[key]
            versus: Dict[str, Any] = {}
            for name, base in baselines.items():
                pairs = [
                    (a, b)
                    for a, b in zip(out.per_seed_delay, base.per_seed_delay)
                    if a is not None and b is not None
                ]
                if not pairs:
                    versus[name] = {"meanDifference": None, "ci95": None, "n": 0}
                    continue
                diffs = [a - b for a, b in pairs]
                versus[name] = {
                    "meanDifference": round(sum(diffs) / len(diffs), 6),
                    "ci95": list(
                        _bootstrap_ci(diffs, f"{self.spec.seed}:{key}:{name}")
                    ),
                    "n": len(diffs),
                    "lowerDelayInSeeds": sum(1 for d in diffs if d < 0),
                }
            rows[key] = {
                "genome": relevant(genome),
                "patch": candidate_patch(genome),
                "objectives": _objectives_dict(out.objectives),
                "infeasible": out.infeasible_reason,
                "versusBaselines": versus,
            }
        return {
            "seeds": len(seeds),
            "primaryIndicator": "averageDelay",
            "differenceMeaning": "candidate minus baseline, seconds; negative = lower delay than the baseline",
            "candidates": rows,
            "baselines": {
                name: {
                    "objectives": _objectives_dict(o.objectives),
                    "infeasible": o.infeasible_reason,
                }
                for name, o in baselines.items()
            },
        }

    def _unseen(self, shortlist: List[Genome]) -> Optional[List[Dict[str, Any]]]:
        seeds = self.pools.held_out[:UNSEEN_SEEDS]
        candidates = [Candidate(g["strategy"], g) for g in shortlist] + [
            Candidate(s) for s in BASELINES
        ]
        table: List[Dict[str, Any]] = []
        for scale in UNSEEN_DEMAND_SCALES:
            for aggression in UNSEEN_AGGRESSION:
                regime = self.spec.regime.model_copy(
                    update={
                        "vehiclesPerHour": max(
                            100,
                            min(1200, round(self.spec.regime.vehiclesPerHour * scale)),
                        ),
                        "aggression": aggression,
                    }
                )
                outcomes = self._evaluate(
                    candidates,
                    seeds,
                    "unseen",
                    regime=regime,
                    extra={"demandScale": scale, "aggression": aggression},
                )
                if outcomes is None:
                    return table or None
                delays = {
                    c.key: (o.objectives[0] if o.objectives is not None else None)
                    for c, o in zip(candidates, outcomes)
                }
                feasible = {k: v for k, v in delays.items() if v is not None}
                preferred = (
                    min(feasible, key=lambda k: (feasible[k], k)) if feasible else None
                )
                table.append(
                    {
                        "demandScale": scale,
                        "aggression": aggression,
                        "meanDelay": {
                            k: (round(v, 6) if v is not None else None)
                            for k, v in delays.items()
                        },
                        "lowestDelay": preferred,
                        "seeds": len(seeds),
                    }
                )
        return table
