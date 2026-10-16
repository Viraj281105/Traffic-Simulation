"""Validating an experiment request without simulating anything, and
bounding its cost (alternatives, runs and engine steps) before it can run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from src.core.limits import nested_deeper_than, too_deep_message
from src.planning.alternatives import (
    DefaultStrategyAlternatives,
    InlineAlternatives,
    ResolvedAlternative,
    resolve_all,
)
from src.scenario.documents import (
    ScenarioDocument,
    compile_scenario,
    parse_scenario,
)
from src.uncertainty.apply import preflight
from src.uncertainty.spec import (
    run_counts,
)

from . import limits
from .models import (
    ExperimentRequest,
)

MIN_MEASURED_SECONDS_WARNING = 60.0


@dataclass
class Prepared:
    request: Optional[ExperimentRequest] = None
    base: Optional[ScenarioDocument] = None
    alternatives: List[ResolvedAlternative] = field(default_factory=list)
    baseline: Optional[str] = None
    counts: Optional[Dict[str, int]] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def _pydantic_errors(err: ValidationError) -> List[str]:
    return [
        f"{'.'.join(str(p) for p in e.get('loc', ()))}: {e.get('msg', 'invalid')}"
        for e in err.errors()
    ]


def _quota_error(quota: str, message: str) -> str:
    return f"quota {limits.QUOTA_NAMES[quota]}: {message}"


def _simulation_steps(prepared: "Prepared", base: ScenarioDocument) -> int:
    """Engine steps the whole experiment needs: for every alternative, steps per run (the scenario's
    duration over the *compiled* time step, which ``advanced`` may change) times conditions times
    replications."""
    assert prepared.counts is not None
    per_cell = 0
    for alt in prepared.alternatives:
        if alt.document is None:
            continue
        try:
            step = float(
                compile_scenario(alt.document, alt.spec.strategy)["simulation"][
                    "timeStep"
                ]
            )
        except (ValueError, KeyError, TypeError):
            step = alt.document.simulation.timeStep
        per_cell += math.ceil(base.simulation.duration / step)
    return per_cell * prepared.counts["conditions"] * prepared.counts["replications"]


def prepare(payload: Any) -> Prepared:
    """Validate a request without simulating anything.

    Everything that costs CPU is bounded before it runs: the document's depth first, then the number of
    alternatives, and only then the per-alternative validation.
    """
    out = Prepared()
    if not isinstance(payload, dict):
        out.errors.append("An experiment must be a JSON object")
        return out
    if nested_deeper_than(payload, limits.MAX_DOCUMENT_DEPTH):
        out.errors.append(too_deep_message(limits.MAX_DOCUMENT_DEPTH))
        return out
    try:
        request = ExperimentRequest.model_validate(payload)
    except ValidationError as err:
        out.errors.extend(_pydantic_errors(err))
        return out
    out.request = request

    base, scenario_errors = parse_scenario(request.scenario)
    if base is None:
        out.errors.extend(f"scenario: {e}" for e in scenario_errors)
        return out
    out.base = base

    given = len(request.alternatives or [])
    if given > limits.MAX_ALTERNATIVES:
        # Refused before any alternative is resolved: each one costs a full scenario validation.
        out.errors.append(
            _quota_error(
                "alternatives",
                f"{given} alternatives given, at most {limits.MAX_ALTERNATIVES} allowed",
            )
        )
        return out

    source = (
        InlineAlternatives(request.alternatives)
        if request.alternatives
        else DefaultStrategyAlternatives()
    )
    resolved = resolve_all(base, source)
    out.alternatives = resolved
    ids = [r.id for r in resolved]
    if len(set(ids)) != len(ids):
        out.errors.append("alternative ids must be unique")
    if len(resolved) < 2:
        out.errors.append("an experiment needs at least two alternatives")
    for r in resolved:
        out.errors.extend(r.errors)
        out.warnings.extend(r.warnings)
        if r.document is not None:
            out.errors.extend(
                f"{r.id}: {e}"
                for e in preflight(r.document, request.uncertainty.factors)
            )

    measured = base.simulation.duration - base.simulation.warmup
    if measured < MIN_MEASURED_SECONDS_WARNING:
        out.warnings.append(
            f"Only {measured:g} s are measured after warm-up. Few vehicles may finish a trip in "
            "that time, and a condition in which none does is excluded (its delay is undefined); "
            f"{MIN_MEASURED_SECONDS_WARNING:g} s or more is advisable."
        )

    out.baseline = request.baseline or (resolved[0].id if resolved else None)
    if out.baseline is not None and out.baseline not in ids:
        out.errors.append(f"baseline {out.baseline!r} is not one of the alternatives")

    if len(resolved) >= 2:
        out.counts = run_counts(request.uncertainty, len(resolved))
        if out.counts["totalRuns"] > limits.MAX_RUNS_PER_EXPERIMENT:
            out.errors.append(
                _quota_error(
                    "runsPerExperiment",
                    f"{out.counts['conditions']} conditions x {out.counts['alternatives']} "
                    f"alternatives x {out.counts['replications']} replications = "
                    f"{out.counts['totalRuns']} runs, at most {limits.MAX_RUNS_PER_EXPERIMENT} allowed",
                )
            )
        steps = _simulation_steps(out, base)
        if steps > limits.MAX_SIMULATION_STEPS_PER_EXPERIMENT:
            out.errors.append(
                _quota_error(
                    "simulationStepsPerExperiment",
                    f"{out.counts['totalRuns']} runs of {base.simulation.duration:g} s need "
                    f"{steps:,} engine steps, at most "
                    f"{limits.MAX_SIMULATION_STEPS_PER_EXPERIMENT:,} allowed "
                    "(steps = duration / time step; a smaller time step costs more)",
                )
            )
    return out
