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

from typing import Dict, Mapping, Optional, Sequence

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


# A delay comparison describes the vehicles each control served. When two
# controls' mean admitted share of the nominal demand, or mean unfinished
# share, differ by more than this (as a fraction, so 0.05 = 5 percentage
# points), their delays describe different populations and the comparison is
# flagged (study/control_comparison.py). Like the tie tolerance, a
# presentation rule, not a statistical test.
SERVED_DEMAND_TOLERANCE: float = 0.05


def _mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def lower_delay_served_less(
    a: Mapping[str, Sequence[float]], b: Mapping[str, Sequence[float]]
) -> bool:
    """True when the side with the lower mean delay served less of the demand.

    *a* and *b* map ``averageDelay``, ``admittedShareOfNominal`` and
    ``unfinishedShare`` to per-seed values. The lower-delay side "served
    less" when its admitted share is lower, or its unfinished share higher,
    by more than SERVED_DEMAND_TOLERANCE: its delay advantage may then come
    from the vehicles it kept out or left unfinished. When the lower-delay
    side served as much or more, the population difference only strengthens
    the delay reading, so it is not flagged. False when a value is missing
    or the delays are equal.
    """
    delay_a, delay_b = (
        _mean(a.get("averageDelay", ())),
        _mean(b.get("averageDelay", ())),
    )
    if delay_a is None or delay_b is None or delay_a == delay_b:
        return False
    low, high = (a, b) if delay_a < delay_b else (b, a)
    tol = SERVED_DEMAND_TOLERANCE + _EPS
    adm_low = _mean(low.get("admittedShareOfNominal", ()))
    adm_high = _mean(high.get("admittedShareOfNominal", ()))
    if adm_low is not None and adm_high is not None and adm_high - adm_low > tol:
        return True
    unf_low = _mean(low.get("unfinishedShare", ()))
    unf_high = _mean(high.get("unfinishedShare", ()))
    return unf_low is not None and unf_high is not None and unf_low - unf_high > tol


def entry_wait_reverses_delay(
    a: Mapping[str, Sequence[float]], b: Mapping[str, Sequence[float]]
) -> bool:
    """True when adding the wait to enter reverses which side has less delay.

    ``averageDelay`` is measured from entry into the network and
    ``averageEntryWait`` is the wait before it, over the same vehicles
    (exited after warm-up), so their sum is the delay from arrival. Under
    the point-queue entry model a strategy can show the lower in-network
    delay while its vehicles waited longer outside; this flags that case.
    A caution, not a verdict: it compares means and says nothing about
    significance. False when a value is missing, the delays are equal, or
    the sums are tied.
    """
    delay_a = _mean(a.get("averageDelay", ()))
    delay_b = _mean(b.get("averageDelay", ()))
    wait_a = _mean(a.get("averageEntryWait", ()))
    wait_b = _mean(b.get("averageEntryWait", ()))
    if None in (delay_a, delay_b, wait_a, wait_b) or delay_a == delay_b:
        return False
    assert delay_a is not None and delay_b is not None
    assert wait_a is not None and wait_b is not None
    total_a, total_b = delay_a + wait_a, delay_b + wait_b
    if abs(total_a - total_b) <= _EPS:
        return False
    return (delay_a < delay_b) != (total_a < total_b)


def tie_tolerance() -> Dict[str, float]:
    """The tolerance in effect, for inclusion in study outputs."""
    return {"absSeconds": DELAY_TIE_ABS_SECONDS, "relative": DELAY_TIE_RELATIVE}
