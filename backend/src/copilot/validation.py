"""The validation boundary: every proposed experiment passes the backend's own checks before it can be
confirmed. Problems come back with stable codes and, where one exists, a deterministic valid alternative."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.experiments import limits
from src.experiments.preparation import prepare

from .models import ProposalIssue


def _code(error: str) -> str:
    names = limits.QUOTA_NAMES
    if f"quota {names['runsPerExperiment']}" in error:
        return "QUOTA_RUNS"
    if f"quota {names['simulationStepsPerExperiment']}" in error:
        return "QUOTA_STEPS"
    if f"quota {names['alternatives']}" in error:
        return "QUOTA_ALTERNATIVES"
    if f"quota {names['dailySimulatedSecondsPerUser']}" in error:
        return "QUOTA_DAILY_SECONDS"
    if "unknown strategy" in error:
        return "STRATEGY_UNKNOWN"
    if error.startswith("scenario:"):
        return "SCENARIO_INVALID"
    if "baseline" in error:
        return "BASELINE_INVALID"
    if "metering" in error or "entryMetering" in error:
        return "STRATEGY_INCOMPATIBLE"
    return "VALIDATION_FAILED"


def _conditions_within(counts: Dict[str, int], runs_limit: int) -> Optional[int]:
    """Largest condition count whose run total stays within ``runs_limit`` (at least 1), or None."""
    per_condition = counts["alternatives"] * counts["replications"]
    if per_condition <= 0:
        return None
    best = runs_limit // per_condition
    return best if best >= 1 else None


def validate_experiment(
    experiment: Dict[str, Any],
) -> Tuple[bool, List[ProposalIssue], Optional[int], Optional[float]]:
    """``(valid, issues, estimated runs, estimated simulated seconds)`` for a proposed experiment."""
    prepared = prepare(experiment)
    issues: List[ProposalIssue] = []
    counts = prepared.counts
    runs = counts["totalRuns"] if counts else None
    seconds = (
        float(prepared.base.simulation.duration) * runs
        if prepared.base is not None and runs is not None
        else None
    )
    for error in prepared.errors:
        code = _code(error)
        suggestion: Optional[Dict[str, Any]] = None
        if code in ("QUOTA_RUNS", "QUOTA_STEPS") and counts:
            conditions = counts["conditions"]
            if code == "QUOTA_RUNS":
                target = _conditions_within(counts, limits.MAX_RUNS_PER_EXPERIMENT)
            else:
                steps = _steps(prepared)
                target = (
                    limits.MAX_SIMULATION_STEPS_PER_EXPERIMENT * conditions // steps
                    if steps > 0
                    else None
                )
            if target:
                suggestion = {"uncertainty.conditions": target}
        elif code == "QUOTA_ALTERNATIVES":
            suggestion = {"alternatives": limits.MAX_ALTERNATIVES}
        issues.append(
            ProposalIssue(code=code, message=error[:500], suggestion=suggestion)
        )

    daily = limits.MAX_DAILY_SIMULATED_SECONDS_PER_USER
    if seconds is not None and seconds > daily and counts and prepared.base is not None:
        per_condition = (
            float(prepared.base.simulation.duration)
            * counts["alternatives"]
            * counts["replications"]
        )
        target = int(daily // per_condition) if per_condition else 0
        issues.append(
            ProposalIssue(
                code="QUOTA_DAILY_SECONDS",
                message=(
                    f"quota {limits.QUOTA_NAMES['dailySimulatedSecondsPerUser']}: the experiment needs "
                    f"{seconds:,.0f} simulated seconds, more than the {daily:,} allowed per day"
                ),
                suggestion={"uncertainty.conditions": target} if target >= 1 else None,
            )
        )
    return not issues, issues, runs, seconds


def _steps(prepared: Any) -> int:
    from src.experiments.preparation import _simulation_steps

    try:
        return int(_simulation_steps(prepared, prepared.base))
    except Exception:  # noqa: BLE001 - an estimate only
        return 1


def apply_suggestion(
    experiment: Dict[str, Any], suggestion: Dict[str, Any]
) -> Dict[str, Any]:
    """A copy of ``experiment`` with a validation suggestion applied (only the keys suggestions use)."""
    import copy

    changed = copy.deepcopy(experiment)
    for key, value in suggestion.items():
        if key == "uncertainty.conditions" and isinstance(value, int) and value >= 1:
            changed["uncertainty"]["conditions"] = value
        elif key == "alternatives" and isinstance(value, int) and value >= 2:
            changed["alternatives"] = changed["alternatives"][:value]
            ids = [a["id"] for a in changed["alternatives"]]
            if changed.get("baseline") not in ids:
                changed["baseline"] = ids[0]
    return changed
