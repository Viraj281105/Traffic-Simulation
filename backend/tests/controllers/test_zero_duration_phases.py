"""Signal phases last exactly their configured time, including zero (F-40).

The schema allows ``allRedTime: 0`` (``ge=0``). Both signal controllers used to
advance at most one phase per tick, so a zero-length all-red was still shown
for one tick (0.1 s), adding 0.4 s to every four-direction cycle. A phase whose
time is used up now ends in the same tick; the entry-metering plan already
leaves zero-length phases out altogether.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import pytest

from tests.engine.test_engine_reset import _build, _config

TICKS = 1100
_RUNS: Dict[Tuple[float, bool], Tuple[Dict[str, int], List[str], float]] = {}


def _phases_over_time(
    all_red: float, adaptive: bool
) -> Tuple[Dict[str, int], List[str], float]:
    """Ticks spent in each phase, the order phases were shown in, and the
    plan's cycle length. One run per setting; light traffic, since phase
    timing does not depend on it (the adaptive greens still respond)."""
    if (all_red, adaptive) in _RUNS:
        return _RUNS[(all_red, adaptive)]
    config = _config()
    config["traffic"]["arrivalRate"] = 0.2
    config["controller"]["allRedTime"] = all_red
    if adaptive:
        config["controller"]["signalControl"] = "adaptive"
    engine, controller, _ = _build(config)
    ticks: Dict[str, int] = {}
    order: List[str] = []
    for _ in range(TICKS):
        engine.step()
        name = controller.current_phase.name
        ticks[name] = ticks.get(name, 0) + 1
        if not order or order[-1] != name:
            order.append(name)
    cycle = sum(p.duration for p in controller.phases)
    _RUNS[(all_red, adaptive)] = (ticks, order, cycle)
    return ticks, order, cycle


@pytest.mark.parametrize("adaptive", [False, True], ids=["fixed-time", "adaptive"])
def test_a_zero_all_red_is_never_shown(adaptive: bool) -> None:
    ticks, order, _ = _phases_over_time(0.0, adaptive)
    assert ticks.get("all_red", 0) == 0
    # Yellow hands straight over to the next green.
    for before, after in zip(order, order[1:]):
        if before.endswith("_yellow"):
            assert after.endswith("_straight_right"), (before, after)


@pytest.mark.parametrize("adaptive", [False, True], ids=["fixed-time", "adaptive"])
def test_a_positive_all_red_lasts_its_configured_time(adaptive: bool) -> None:
    ticks, order, _ = _phases_over_time(2.0, adaptive)
    shown = order.count("all_red")
    assert shown > 0
    # Each all-red lasts 2.0 s = 20 ticks. The last one may be cut off by the
    # end of the run.
    assert 20 * (shown - 1) < ticks["all_red"] <= 20 * shown


def test_the_fixed_time_cycle_is_the_sum_of_its_phases() -> None:
    """Over whole cycles, time spent equals the configured cycle length:
    a zero-length phase no longer adds a tick to each cycle."""
    ticks, _, cycle = _phases_over_time(0.0, adaptive=False)
    assert cycle == pytest.approx(4 * (30.0 + 5.0 + 4.0 + 0.0))  # 156 s
    # 110 s run, cycle 156 s: the first three greens and lefts and yellows
    # each last their exact configured time.
    assert ticks["north_straight_right"] == 299  # 30 s, the first tick is t=0.1
    assert ticks["north_left"] == 50
    assert ticks["north_yellow"] == 40
    assert ticks["south_straight_right"] == 300
    assert ticks["south_left"] == 50
    assert ticks["south_yellow"] == 40
