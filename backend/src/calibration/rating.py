"""Thresholds and the rules that turn an error into GOOD / MODERATE / POOR.

These are *presentation* thresholds chosen for transparency, not a
statistical test and not a published standard (GEH is reported alongside flows
because traffic engineers expect it, but it does not drive the rating). They
are returned inside every result so a reader can see exactly what was applied.

Per comparison, with error = simulated - observed:

  GOOD      |error| <= absGood   OR   |error| / observed <= pctGood
  MODERATE  |error| <= absModerate OR |error| / observed <= pctModerate
  POOR      otherwise

The percentage rule is used only when |observed| >= minDenominator; below it
the percentage is not reported (``percentError: null``) and only the absolute
rule applies, so a tiny observed value never produces a huge meaningless %.

Overall (over every rated comparison):

  INSUFFICIENT_DATA  nothing could be rated
  POOR               more than 25 % of comparisons are POOR
  GOOD               no POOR and at least 80 % are GOOD
  MODERATE           everything else
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

GOOD = "GOOD"
MODERATE = "MODERATE"
POOR = "POOR"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

THRESHOLDS_VERSION = 1

THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "flow": {
        "unit": "veh/h",
        "pctGood": 10.0,
        "pctModerate": 25.0,
        "absGood": 20.0,
        "absModerate": 50.0,
        "minDenominator": 20.0,
    },
    "turning": {
        "unit": "share of approach",
        "pctGood": 20.0,
        "pctModerate": 40.0,
        "absGood": 0.05,
        "absModerate": 0.10,
        "minDenominator": 0.05,
    },
    "mix": {
        "unit": "share of vehicles",
        "pctGood": 20.0,
        "pctModerate": 40.0,
        "absGood": 0.03,
        "absModerate": 0.06,
        "minDenominator": 0.05,
    },
    "queue": {
        "unit": "vehicles",
        "pctGood": 25.0,
        "pctModerate": 50.0,
        "absGood": 1.0,
        "absModerate": 2.0,
        "minDenominator": 1.0,
    },
    "travelTime": {
        "unit": "s",
        "pctGood": 10.0,
        "pctModerate": 25.0,
        "absGood": 3.0,
        "absModerate": 8.0,
        "minDenominator": 5.0,
    },
    "signal": {
        "unit": "s",
        "pctGood": 10.0,
        "pctModerate": 25.0,
        "absGood": 2.0,
        "absModerate": 5.0,
        "minDenominator": 5.0,
    },
}

POOR_IF_POOR_SHARE_ABOVE = 0.25
GOOD_IF_GOOD_SHARE_AT_LEAST = 0.80
OVERALL_RULE_TEXT = (
    "POOR if more than 25% of comparisons are POOR; GOOD if none are POOR "
    "and at least 80% are GOOD; otherwise MODERATE; INSUFFICIENT_DATA if "
    "nothing could be rated."
)


def percent_error(kind: str, observed: float, error: float) -> Optional[float]:
    """Relative error in %, or None when the observed value is too small for a
    percentage to mean anything."""
    if abs(observed) < THRESHOLDS[kind]["minDenominator"]:
        return None
    return error / observed * 100.0


def rate(kind: str, observed: float, error: float) -> str:
    t = THRESHOLDS[kind]
    pct = percent_error(kind, observed, error)
    abs_err = abs(error)
    rel = abs(pct) if pct is not None else math.inf
    if abs_err <= t["absGood"] or rel <= t["pctGood"]:
        return GOOD
    if abs_err <= t["absModerate"] or rel <= t["pctModerate"]:
        return MODERATE
    return POOR


def geh(simulated: float, observed: float) -> float:
    """GEH statistic for two hourly volumes (0 when both are 0)."""
    total = simulated + observed
    if total <= 0:
        return 0.0
    return math.sqrt(2.0 * (simulated - observed) ** 2 / total)


def classify(ratings: List[str]) -> Dict[str, Any]:
    n = len(ratings)
    counts = {GOOD: 0, MODERATE: 0, POOR: 0}
    for r in ratings:
        counts[r] += 1
    if n == 0:
        overall = INSUFFICIENT_DATA
    elif counts[POOR] / n > POOR_IF_POOR_SHARE_ABOVE:
        overall = POOR
    elif counts[POOR] == 0 and counts[GOOD] / n >= GOOD_IF_GOOD_SHARE_AT_LEAST:
        overall = GOOD
    else:
        overall = MODERATE
    return {
        "overall": overall,
        "rated": n,
        "counts": counts,
        "rule": OVERALL_RULE_TEXT,
    }
