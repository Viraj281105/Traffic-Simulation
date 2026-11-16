"""Shadow mode: record what the system would recommend, compare it later with
what really happened. Never acts; it only stores numbers and computes metrics.

Each record holds the system's predicted cost (lower is better) for every
option it considered, its recommended option, and, once known, the action
actually taken and the cost really observed for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ShadowRecord:
    interval: str
    recommended: str
    predicted_costs: Dict[str, float]
    chosen: Optional[str] = None
    observed_cost: Optional[float] = None


def shadow_report(records: Sequence[ShadowRecord]) -> Dict[str, Any]:
    """Agreement metrics over the records that have an observed outcome.

    - matchRate: share where recommended == chosen.
    - meanAbsError / meanBias: predicted cost of the chosen action minus the
      observed cost (bias > 0 means the system over-predicted cost).
    - meanRegret: predicted cost of the chosen action minus that of the
      recommended action (what the chosen action cost over the recommendation,
      per the model); >= 0 when the recommendation is the model's best.
    """
    done = [r for r in records if r.chosen is not None]
    matches = sum(1 for r in done if r.recommended == r.chosen)
    errors: List[float] = []
    regrets: List[float] = []
    for r in done:
        assert r.chosen is not None
        chosen_pred = r.predicted_costs.get(r.chosen)
        if chosen_pred is None:
            continue
        if r.observed_cost is not None:
            errors.append(chosen_pred - r.observed_cost)
        rec_pred = r.predicted_costs.get(r.recommended)
        if rec_pred is not None:
            regrets.append(chosen_pred - rec_pred)

    def mean(xs: List[float]) -> Optional[float]:
        return sum(xs) / len(xs) if xs else None

    return {
        "advisoryOnly": True,
        "recorded": len(records),
        "withOutcome": len(done),
        "matchRate": matches / len(done) if done else None,
        "meanAbsError": mean([abs(e) for e in errors]),
        "meanBias": mean(errors),
        "meanRegret": mean(regrets),
        "errorSamples": len(errors),
        "regretSamples": len(regrets),
    }


class ShadowLog:
    def __init__(self) -> None:
        self._records: Dict[str, ShadowRecord] = {}

    def record(
        self, interval: str, recommended: str, predicted_costs: Dict[str, float]
    ) -> ShadowRecord:
        rec = ShadowRecord(interval, recommended, dict(predicted_costs))
        self._records[interval] = rec
        return rec

    def observe(self, interval: str, chosen: str, observed_cost: float) -> ShadowRecord:
        rec = self._records[interval]
        rec.chosen = chosen
        rec.observed_cost = observed_cost
        return rec

    def report(self) -> Dict[str, Any]:
        return shadow_report(list(self._records.values()))
