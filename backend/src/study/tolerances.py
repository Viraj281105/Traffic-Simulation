"""One definition of "about the same" for a mean-delay comparison.

Every place that classifies a pair of mean delays as tied / lower / higher
uses this rule, so the volume sweep, the run-comparison endpoint and the
guided results page (frontend/src/metrics/plainLanguage.ts, SIMILARITY.delay,
which mirrors these constants) can never disagree about the same numbers.

The rule is a *presentation* tolerance, not a statistical test: two delays
are "about the same" when they differ by no more than DELAY_TIE_ABS_SECONDS
or by no more than DELAY_TIE_RELATIVE of the larger delay. It exists so that
a fraction of a second between two single-seed means is never reported as one
control "winning". It says nothing about significance; only the repeated-seed
validation (study/validation.py) does that.
"""

from typing import Dict

DELAY_TIE_ABS_SECONDS: float = 1.0
DELAY_TIE_RELATIVE: float = 0.05

# Floating-point slack, so a gap exactly at a tolerance is not tipped over it
# by rounding (matches the frontend's comparison helper).
_EPS: float = 1e-9


def delays_are_tied(
    a: float,
    b: float,
    abs_seconds: float = DELAY_TIE_ABS_SECONDS,
    relative: float = DELAY_TIE_RELATIVE,
) -> bool:
    """True when two mean delays are within either tolerance of each other."""
    gap = abs(a - b)
    if gap <= abs_seconds + _EPS:
        return True
    larger = max(abs(a), abs(b))
    return larger > 0 and gap / larger <= relative + _EPS


def tie_tolerance() -> Dict[str, float]:
    """The tolerance in effect, for inclusion in study outputs."""
    return {"absSeconds": DELAY_TIE_ABS_SECONDS, "relative": DELAY_TIE_RELATIVE}
