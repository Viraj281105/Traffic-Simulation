"""``RlComparison``: an RL policy against the fixed-time plan, on the same junction and seeds.

Source: ``rl/<comparison id>.json`` (format ``urbanflow-rl-comparison`` v1), written next to the
per-seed output of ``scripts/rl_evaluate.py`` (``urbanflow-rl-eval`` v1)::

    {"format": "urbanflow-rl-comparison", "version": 1, "generatedAt": "...",
     "junction": "Four-way, one lane",
     "metric": "mean_wait_s",
     "fixedPolicy": "fixed_time", "fixedLabel": "Fixed time, 30 s green",
     "rl": {"policy": "dqn", "label": "DQN", "policyId": "signal-control/3",
            "algorithm": "DQN", "trainingSteps": 20000},
     "caveats": ["Trained and evaluated on one simulator."],
     "scenarios": [{"scenarioId": "vph400", "label": "400 veh/h", "eval": <urbanflow-rl-eval document>}]}

Every scenario's ``eval`` holds one value per held-out seed for each policy. Seeds are paired within a
scenario. Each scenario gets a mean and a t interval per policy; the overall difference (RL minus fixed-time)
is a paired t test over every (scenario, seed) pair, from ``src.uncertainty.comparison``. The metric's
direction comes from the eval document's ``lower_is_better`` list. A scenario with fewer than two seeds
makes the comparison unavailable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from src.uncertainty.comparison import (
    DEFAULT_CONFIDENCE,
    compare_paired,
    mean_confidence_interval,
)

from .numbers import finite_list

COMPARISON_FORMAT = "urbanflow-rl-comparison"
EVAL_FORMAT = "urbanflow-rl-eval"

METRIC_INFO: Dict[str, Dict[str, str]] = {
    "mean_wait_s": {"label": "Mean wait per vehicle", "unit": "s"},
    "total_wait_s": {"label": "Total waiting time", "unit": "s"},
    "stopped_veh_s": {"label": "Stopped vehicle-seconds", "unit": "s"},
    "mean_queue": {"label": "Mean queue length", "unit": "vehicles"},
    "throughput": {"label": "Throughput", "unit": "vehicles"},
    "vehicles": {"label": "Vehicles", "unit": "vehicles"},
    "switches": {"label": "Phase switches", "unit": "count"},
    "episode_return": {"label": "Episode return", "unit": "reward"},
}


def _str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


def _policy_values(
    ev: Mapping[str, Any], policy: str, metric: str
) -> Optional[List[float]]:
    policies = ev.get("policies")
    entry = policies.get(policy) if isinstance(policies, dict) else None
    if not isinstance(entry, dict):
        return None
    return finite_list(entry.get(metric))


def _estimate(values: List[float]) -> Dict[str, Any]:
    interval = mean_confidence_interval(values, DEFAULT_CONFIDENCE)
    return {"mean": interval.mean, "ci": [interval.lower, interval.upper], "n": interval.n}


def build_rl_comparison(
    comparison_id: str, doc: Mapping[str, Any]
) -> Optional[Dict[str, Any]]:
    if doc.get("format") != COMPARISON_FORMAT:
        return None
    metric = _str(doc.get("metric"))
    junction, fixed_policy = _str(doc.get("junction")), _str(doc.get("fixedPolicy"))
    fixed_label = _str(doc.get("fixedLabel"))
    rl = doc.get("rl")
    scenarios = doc.get("scenarios")
    if (
        metric is None
        or junction is None
        or fixed_policy is None
        or fixed_label is None
        or metric not in METRIC_INFO
        or not isinstance(rl, dict)
        or not isinstance(scenarios, list)
        or not scenarios
    ):
        return None
    policy, rl_label, policy_id, algorithm = (
        _str(rl.get("policy")),
        _str(rl.get("label")),
        _str(rl.get("policyId")),
        _str(rl.get("algorithm")),
    )
    steps = rl.get("trainingSteps")
    if (
        policy is None
        or rl_label is None
        or policy_id is None
        or algorithm is None
        or not isinstance(steps, int)
        or isinstance(steps, bool)
    ):
        return None
    caveats_raw = doc.get("caveats", [])
    if not isinstance(caveats_raw, list) or not all(isinstance(c, str) for c in caveats_raw):
        return None

    lower_is_better: Optional[bool] = None
    out_scenarios: List[Dict[str, Any]] = []
    all_rl: List[float] = []
    all_fixed: List[float] = []
    for sc in scenarios:
        if not isinstance(sc, dict):
            return None
        ev = sc.get("eval")
        sid, label = _str(sc.get("scenarioId")), _str(sc.get("label"))
        if sid is None or label is None or not isinstance(ev, dict):
            return None
        if ev.get("format") != EVAL_FORMAT:
            return None
        lib = ev.get("lower_is_better")
        if not isinstance(lib, list):
            return None
        this_lower = metric in lib
        if lower_is_better is not None and lower_is_better != this_lower:
            return None
        lower_is_better = this_lower
        rl_vals = _policy_values(ev, policy, metric)
        fixed_vals = _policy_values(ev, fixed_policy, metric)
        if (
            rl_vals is None
            or fixed_vals is None
            or len(rl_vals) != len(fixed_vals)
            or len(rl_vals) < 2
        ):
            return None
        out_scenarios.append(
            {
                "scenarioId": sid,
                "label": label,
                "fixedTime": _estimate(fixed_vals),
                "rl": _estimate(rl_vals),
            }
        )
        all_rl += rl_vals
        all_fixed += fixed_vals
    assert lower_is_better is not None

    result = compare_paired(all_rl, all_fixed, method="paired_t")
    if result.direction == "none":
        verdict = "no_clear_difference"
    else:
        rl_wins = (result.direction == "a_lower") == lower_is_better
        verdict = "rl_better" if rl_wins else "fixed_better"
    info = METRIC_INFO[metric]
    return {
        "id": comparison_id,
        "junction": junction,
        "metric": {
            "id": metric,
            "label": info["label"],
            "unit": info["unit"],
            "lowerIsBetter": lower_is_better,
        },
        "fixedTime": {"label": fixed_label},
        "rl": {
            "label": rl_label,
            "policyId": policy_id,
            "algorithm": algorithm,
            "trainingSteps": steps,
        },
        "difference": {
            "mean": result.difference,
            "ci": [result.ci_lower, result.ci_upper],
            "pValue": result.p_value,
        },
        "confidenceLevel": result.confidence,
        "verdict": verdict,
        "scenarios": out_scenarios,
        "caveats": list(caveats_raw) + list(result.cautions),
    }
