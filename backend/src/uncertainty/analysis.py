"""Robustness Lab analysis core (strategy section 5.3-5.7, ADR-015): pure functions, no simulation.

Input: per condition, the primary indicator of every alternative for every replication. Output: a
JSON-serialisable document with win/tie/loss against the baseline (Wilson intervals), the distribution of
the paired difference (bootstrap intervals), regret, preference share, exclusion accounting and the
eligibility checklist.

What this module deliberately does not do (scheduled later, and reported as such rather than faked):
one-factor preference-flip detection and Spearman sensitivity (W3). Split-half stability and the
variance split are evaluated here (W4). When all five required criteria pass, a result is classified
"eligible".

Rules honoured here:

* The unit of inference is the **condition**; replications are averaged inside a condition.
* A condition is excluded **for every alternative** if any of its runs is missing, failed or non-finite
  (pairing is preserved); exclusions are counted by reason and by factor stratum.
* A tie is a result and stays inside every denominator.
* Nothing is ranked: no p-values, no "winner".
* Aggregation sorts by condition index, so the order in which results arrive cannot change the output.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.study.tolerances import (
    DELAY_TIE_ABS_SECONDS,
    DELAY_TIE_RELATIVE,
    delays_are_tied,
)

from .stats import (
    bootstrap_intervals,
    mean_sorted,
    percentile_sorted,
    variance_decomposition,
    wilson_interval,
)

ANALYSIS_FORMAT = "urbanflow-robustness-analysis"
ANALYSIS_VERSION = 1

EXPLORATORY_BELOW = 30  # valid conditions
PRECISION_HALF_WIDTH = 0.10
MAX_EXCLUDED_SHARE = 0.10
MAX_STRATUM_EXCLUDED_SHARE = 0.20
MIN_REPLICATIONS = 2
STRATA_PER_FACTOR = (
    5  # equal-count strata used for exclusion accounting (and later for flips)
)
BOOTSTRAP_RESAMPLES = 2000
RESULT_DECIMALS = 6
_EPS = 1e-9

SPLIT_HALF_EVALUATIONS = 20
SPLIT_HALF_PASS_THRESHOLD = 18

REAL_WORLD_VALIDITY = "None — assumptions only"

LIMITATIONS: List[str] = [
    "Every input distribution is an assumption of the analyst, not an estimate from data.",
    "Intervals treat the sampled conditions as exchangeable draws; with Latin-hypercube stratification "
    "they are approximate and slightly conservative.",
    "The unit of inference is the sampled condition, not the simulation run; replications reduce noise "
    "inside a condition and do not add conditions.",
    "Win, tie and loss are descriptive comparisons against the baseline, not a ranking and not a test "
    "of significance.",
    "Interactions between factors are not resolved.",
    "Headway scale is a proxy for driver behaviour: the engine has no explicit reaction delay.",
    "The simulation is not calibrated to observed traffic; 'eligible' (when available) would mean "
    "adequately sampled for the declared assumptions, never that the model is correct.",
]

EXCLUSION_REASONS = (
    "validation_failed",  # the perturbed scenario failed validation (rejected, never repaired)
    "run_failed",
    "timeout",
    "vehicle_limit",
    "deadlock",
    "no_completed_vehicles",  # no vehicle finished its trip after warm-up: the delay is undefined
    "non_finite",
    "missing_run",
)


@dataclass(frozen=True)
class ConditionResult:
    """One sampled condition as the analysis sees it."""

    index: int
    # factor id -> stratum (0..N-1) from the sampler; kept for every condition, valid or not.
    strata: Mapping[str, int]
    # alternative id -> primary indicator per replication. Empty or partial for a failed condition.
    outcomes: Mapping[str, Sequence[float]] = field(default_factory=dict)
    # Reason the runner already excluded this condition (one of EXCLUSION_REASONS), else None.
    exclusion: Optional[str] = None


def _rounded(value: float) -> float:
    return round(value, RESULT_DECIMALS) + 0.0  # + 0.0 turns -0.0 into 0.0


def _tolerance_block(tau: Optional[float]) -> Dict[str, Any]:
    if tau is None:
        return {
            "kind": "rule",
            "absSeconds": DELAY_TIE_ABS_SECONDS,
            "relative": DELAY_TIE_RELATIVE,
        }
    return {"kind": "absolute", "value": _rounded(tau)}


def _tied(a: float, b: float, tau: Optional[float]) -> bool:
    if tau is None:
        return delays_are_tied(a, b)
    return abs(a - b) <= tau + _EPS


def classify(alternative: float, baseline: float, tau: Optional[float]) -> str:
    """win / tie / loss of an alternative against the baseline; lower is better."""
    if _tied(alternative, baseline, tau):
        return "tie"
    return "win" if alternative < baseline else "loss"


def _proportion(count: int, n: int) -> Dict[str, Any]:
    low, high = wilson_interval(count, n)
    return {
        "count": count,
        "p": _rounded(count / n),
        "ci": [_rounded(low), _rounded(high)],
    }


def _half_width(block: Mapping[str, Any]) -> float:
    low, high = block["ci"]
    return float(high - low) / 2.0


def _seeded_rng(seed: int, label: str) -> random.Random:
    digest = hashlib.sha256(f"urbanflow-analysis-v1:{seed}:{label}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _condition_state(
    condition: ConditionResult, alternatives: Sequence[str], replications: int
) -> Optional[str]:
    """The exclusion reason for a condition, or None when it is valid."""
    if condition.exclusion is not None:
        if condition.exclusion not in EXCLUSION_REASONS:
            raise ValueError(f"unknown exclusion reason {condition.exclusion!r}")
        return condition.exclusion
    for alt in alternatives:
        values = condition.outcomes.get(alt)
        if values is None or len(values) != replications:
            return "missing_run"
    for alt in alternatives:
        if not all(math.isfinite(v) for v in condition.outcomes[alt]):
            return "non_finite"
    return None


def _stratum_bucket(stratum: int, conditions: int) -> int:
    return min(STRATA_PER_FACTOR - 1, stratum * STRATA_PER_FACTOR // conditions)


def _exclusion_accounting(
    conditions: Sequence[ConditionResult],
    reasons: Mapping[int, Optional[str]],
    factor_ids: Sequence[str],
) -> Dict[str, Any]:
    n = len(conditions)
    by_reason: Dict[str, int] = {}
    for reason in reasons.values():
        if reason is not None:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    excluded = sum(by_reason.values())

    strata_rows: List[Dict[str, Any]] = []
    worst = 0.0
    for fid in factor_ids:
        totals: Dict[int, int] = {}
        dropped: Dict[int, int] = {}
        for c in conditions:
            bucket = _stratum_bucket(c.strata[fid], n)
            totals[bucket] = totals.get(bucket, 0) + 1
            if reasons[c.index] is not None:
                dropped[bucket] = dropped.get(bucket, 0) + 1
        for bucket in sorted(totals):
            share = dropped.get(bucket, 0) / totals[bucket]
            worst = max(worst, share)
            strata_rows.append(
                {
                    "factor": fid,
                    "stratum": bucket,
                    "of": totals[bucket],
                    "excluded": dropped.get(bucket, 0),
                    "share": _rounded(share),
                }
            )
    return {
        "excluded": excluded,
        "overallShare": _rounded(excluded / n),
        "byReason": {k: by_reason[k] for k in sorted(by_reason)},
        "byFactorStratum": strata_rows,
        "worstStratumShare": _rounded(worst),
    }


def _difference_block(
    diffs: List[float], rng: random.Random, resamples: int
) -> Dict[str, Any]:
    ordered = sorted(diffs)
    point = {
        "mean": mean_sorted(ordered),
        "median": percentile_sorted(ordered, 0.5),
        "p5": percentile_sorted(ordered, 0.05),
        "p95": percentile_sorted(ordered, 0.95),
    }
    intervals = bootstrap_intervals(
        diffs,
        {
            "mean": mean_sorted,
            "median": lambda s: percentile_sorted(s, 0.5),
            "p5": lambda s: percentile_sorted(s, 0.05),
            "p95": lambda s: percentile_sorted(s, 0.95),
        },
        rng,
        resamples=resamples,
    )
    return {
        name: {
            "value": _rounded(point[name]),
            "ci": [_rounded(intervals[name][0]), _rounded(intervals[name][1])],
        }
        for name in point
    }


def _sign(val: float, eps: float = _EPS) -> int:
    if val > eps:
        return 1
    if val < -eps:
        return -1
    return 0


def _split_half_stability(
    valid_count: int,
    comparisons: Mapping[str, Mapping[str, Any]],
    y: Mapping[str, Sequence[float]],
    alternatives: Sequence[str],
    baseline: str,
    tie_tolerance: Optional[float],
    seed: int,
) -> Dict[str, Any]:
    if valid_count < EXPLORATORY_BELOW:
        return {
            "passed": None,
            "splitsEvaluated": 0,
            "splitsPassed": 0,
            "threshold": SPLIT_HALF_PASS_THRESHOLD,
            "evaluations": SPLIT_HALF_EVALUATIONS,
            "detail": (
                "no valid conditions"
                if valid_count == 0
                else f"fewer than {EXPLORATORY_BELOW} valid conditions ({valid_count}); "
                f"split-half stability requires at least {EXPLORATORY_BELOW}"
            ),
        }

    non_baselines = [a for a in alternatives if a != baseline]
    if not non_baselines:
        return {
            "passed": None,
            "splitsEvaluated": 0,
            "splitsPassed": 0,
            "threshold": SPLIT_HALF_PASS_THRESHOLD,
            "evaluations": SPLIT_HALF_EVALUATIONS,
            "detail": "no alternative comparisons available",
        }

    full_w_win = {a: _half_width(comparisons[a]["win"]) for a in non_baselines}
    full_w_loss = {a: _half_width(comparisons[a]["loss"]) for a in non_baselines}

    rng = _seeded_rng(seed, "split_half")
    half = valid_count // 2
    splits_passed = 0

    for _ in range(SPLIT_HALF_EVALUATIONS):
        indices = list(range(valid_count))
        rng.shuffle(indices)
        h1 = indices[:half]
        h2 = indices[half:]
        n1 = len(h1)
        n2 = len(h2)

        split_ok = True
        for a in non_baselines:
            classes_1 = [classify(y[a][i], y[baseline][i], tie_tolerance) for i in h1]
            p_win_1 = classes_1.count("win") / n1
            p_loss_1 = classes_1.count("loss") / n1
            d_1 = [y[a][i] - y[baseline][i] for i in h1]
            med_d_1 = percentile_sorted(sorted(d_1), 0.5)

            classes_2 = [classify(y[a][i], y[baseline][i], tie_tolerance) for i in h2]
            p_win_2 = classes_2.count("win") / n2
            p_loss_2 = classes_2.count("loss") / n2
            d_2 = [y[a][i] - y[baseline][i] for i in h2]
            med_d_2 = percentile_sorted(sorted(d_2), 0.5)

            w_win_diff = abs(p_win_1 - p_win_2)
            w_loss_diff = abs(p_loss_1 - p_loss_2)
            sign_1 = _sign(med_d_1)
            sign_2 = _sign(med_d_2)

            if not (
                w_win_diff < full_w_win[a] + _EPS
                and w_loss_diff < full_w_loss[a] + _EPS
                and sign_1 == sign_2
            ):
                split_ok = False
                break

        if split_ok:
            splits_passed += 1

    passed = splits_passed >= SPLIT_HALF_PASS_THRESHOLD
    detail = (
        f"{splits_passed}/{SPLIT_HALF_EVALUATIONS} random splits agreed on median D sign "
        f"and kept half-estimates within Wilson half-widths; "
        f"limit {SPLIT_HALF_PASS_THRESHOLD}/{SPLIT_HALF_EVALUATIONS} (90%)"
    )
    return {
        "passed": passed,
        "splitsEvaluated": SPLIT_HALF_EVALUATIONS,
        "splitsPassed": splits_passed,
        "threshold": SPLIT_HALF_PASS_THRESHOLD,
        "evaluations": SPLIT_HALF_EVALUATIONS,
        "detail": detail,
    }


def _eligibility(
    valid: int,
    replications: int,
    comparisons: Mapping[str, Mapping[str, Any]],
    exclusions: Mapping[str, Any],
    predeclared: bool,
    stability: Mapping[str, Any],
) -> Dict[str, Any]:
    widths = [
        _half_width(block[key])
        for block in comparisons.values()
        for key in ("win", "loss")
    ]
    worst_width = max(widths) if widths else None
    criteria: List[Dict[str, Any]] = [
        {
            "id": "precision",
            "passed": None
            if worst_width is None
            else worst_width <= PRECISION_HALF_WIDTH,
            "detail": (
                "no valid conditions"
                if worst_width is None
                else f"largest 95% Wilson half-width of P(win)/P(loss) is {worst_width:.3f}; "
                f"limit {PRECISION_HALF_WIDTH}"
            ),
        },
        {
            "id": "stability",
            "passed": stability["passed"],
            "detail": stability["detail"],
        },
        {
            "id": "replications",
            "passed": replications >= MIN_REPLICATIONS,
            "detail": f"{replications} per condition; at least {MIN_REPLICATIONS} are needed to "
            "estimate within-condition noise",
        },
        {
            "id": "exclusions",
            "passed": exclusions["overallShare"] <= MAX_EXCLUDED_SHARE + _EPS
            and exclusions["worstStratumShare"] <= MAX_STRATUM_EXCLUDED_SHARE + _EPS,
            "detail": f"{exclusions['overallShare']:.1%} excluded overall (limit "
            f"{MAX_EXCLUDED_SHARE:.0%}); worst factor stratum {exclusions['worstStratumShare']:.1%} "
            f"(limit {MAX_STRATUM_EXCLUDED_SHARE:.0%})",
        },
        {
            "id": "predeclaration",
            "passed": predeclared,
            "detail": "specification, primary indicator and tolerance were fingerprinted before the run"
            if predeclared
            else "the specification was not fingerprinted before the run",
        },
    ]
    if valid < EXPLORATORY_BELOW:
        verdict = "exploratory"
    elif all(c["passed"] is True for c in criteria):
        verdict = "eligible"
    else:
        verdict = "indicative"
    return {"class": verdict, "validConditions": valid, "criteria": criteria}


def analyze(
    conditions: Sequence[ConditionResult],
    *,
    alternatives: Sequence[str],
    baseline: str,
    replications: int,
    factor_ids: Sequence[str],
    primary_indicator: str = "averageDelay",
    tie_tolerance: Optional[float] = None,
    seed: int = 0,
    predeclared: bool = True,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
) -> Dict[str, Any]:
    """Analyse an ensemble. ``conditions`` must hold every sampled condition, valid or not."""
    alternatives = list(alternatives)
    if baseline not in alternatives:
        raise ValueError("the baseline must be one of the alternatives")
    if len(set(alternatives)) != len(alternatives):
        raise ValueError("alternative ids must be unique")
    if len(alternatives) < 2:
        raise ValueError("a comparison needs at least two alternatives")
    if replications < 1:
        raise ValueError("replications must be at least 1")
    ordered = sorted(conditions, key=lambda c: c.index)
    n = len(ordered)
    if n == 0:
        raise ValueError("no conditions to analyse")
    if [c.index for c in ordered] != list(range(n)):
        raise ValueError("condition indexes must be exactly 0..N-1, once each")
    for c in ordered:
        missing = [f for f in factor_ids if f not in c.strata]
        if missing:
            raise ValueError(f"condition {c.index} has no stratum for {missing}")

    reasons = {
        c.index: _condition_state(c, alternatives, replications) for c in ordered
    }
    valid = [c for c in ordered if reasons[c.index] is None]
    exclusions = _exclusion_accounting(ordered, reasons, factor_ids)
    n_valid = len(valid)

    # Y(i, a): replications averaged inside the condition.
    y: Dict[str, List[float]] = {
        a: [math.fsum(c.outcomes[a]) / replications for c in valid]
        for a in alternatives
    }

    per_alternative: Dict[str, Dict[str, Any]] = {}
    comparisons: Dict[str, Dict[str, Any]] = {}
    can_decompose_variance = n_valid >= 2 and replications >= MIN_REPLICATIONS
    if n_valid:
        best = [min(y[a][i] for a in alternatives) for i in range(n_valid)]
        for a in alternatives:
            regrets = sorted(y[a][i] - best[i] for i in range(n_valid))
            shares = sum(
                1 for i in range(n_valid) if _tied(y[a][i], best[i], tie_tolerance)
            )
            var_split = (
                variance_decomposition([c.outcomes[a] for c in valid])
                if can_decompose_variance
                else None
            )
            entry: Dict[str, Any] = {
                "isBaseline": a == baseline,
                "meanOutcome": _rounded(math.fsum(y[a]) / n_valid),
                "regret": {
                    "mean": _rounded(math.fsum(regrets) / n_valid),
                    "p95": _rounded(percentile_sorted(regrets, 0.95)),
                    "sampleMax": _rounded(regrets[-1]),
                },
                "preferenceShare": _rounded(shares / n_valid),
                "varianceSplit": var_split,
            }
            if a != baseline:
                classes = [
                    classify(y[a][i], y[baseline][i], tie_tolerance)
                    for i in range(n_valid)
                ]
                diff_block = _difference_block(
                    [y[a][i] - y[baseline][i] for i in range(n_valid)],
                    _seeded_rng(seed, a),
                    bootstrap_resamples,
                )
                if can_decompose_variance:
                    diff_runs = [
                        [
                            c.outcomes[a][k] - c.outcomes[baseline][k]
                            for k in range(replications)
                        ]
                        for c in valid
                    ]
                    diff_block["varianceSplit"] = variance_decomposition(diff_runs)
                else:
                    diff_block["varianceSplit"] = None

                block = {
                    "win": _proportion(classes.count("win"), n_valid),
                    "tie": _proportion(classes.count("tie"), n_valid),
                    "loss": _proportion(classes.count("loss"), n_valid),
                    "difference": diff_block,
                }
                comparisons[a] = block
                entry["comparison"] = block
            per_alternative[a] = entry
    else:
        for a in alternatives:
            per_alternative[a] = {
                "isBaseline": a == baseline,
                "comparison": None,
                "varianceSplit": None,
            }

    stability = _split_half_stability(
        n_valid,
        comparisons,
        y,
        alternatives,
        baseline,
        tie_tolerance,
        seed,
    )
    variance_split = (
        {a: per_alternative[a]["varianceSplit"] for a in alternatives}
        if can_decompose_variance
        else None
    )

    return {
        "format": ANALYSIS_FORMAT,
        "version": ANALYSIS_VERSION,
        "primaryIndicator": primary_indicator,
        "lowerIsBetter": True,
        "tolerance": _tolerance_block(tie_tolerance),
        "confidenceLevel": 0.95,
        "baseline": baseline,
        "counts": {
            "conditions": n,
            "validConditions": n_valid,
            "alternatives": len(alternatives),
            "replications": replications,
            "totalRuns": n * len(alternatives) * replications,
        },
        "exclusions": exclusions,
        "alternatives": per_alternative,
        "stability": stability,
        "varianceSplit": variance_split,
        "eligibility": _eligibility(
            n_valid,
            replications,
            comparisons,
            exclusions,
            predeclared,
            stability,
        ),
        "realWorldValidity": REAL_WORLD_VALIDITY,
        "limitations": list(LIMITATIONS),
    }


def result_fingerprint(analysis: Mapping[str, Any]) -> str:
    """16-hex SHA-256 of the canonical analysis document (it carries no timestamps)."""
    canonical = json.dumps(analysis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


__all__ = [
    "ANALYSIS_FORMAT",
    "ANALYSIS_VERSION",
    "ConditionResult",
    "EXCLUSION_REASONS",
    "LIMITATIONS",
    "REAL_WORLD_VALIDITY",
    "SPLIT_HALF_EVALUATIONS",
    "SPLIT_HALF_PASS_THRESHOLD",
    "analyze",
    "classify",
    "result_fingerprint",
]
