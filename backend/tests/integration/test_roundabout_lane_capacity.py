"""A third approach lane on a two-lane roundabout ring adds no capacity -- and
costs none either, on average.

The ring has at most two lanes (``MAX_CIRCULATING_LANES``); a third approach
lane is a merging entry onto the inner ring lane, which validation accepts
with a warning (validation.md K1). Its expected effect on capacity is nil, but
any single seed varies: over 40 seeds at this demand the per-seed difference
had a standard deviation of about 5 % and ranged from -11.5 % to +11.8 %
(V2.0 release-gate audit, 2026-10-13). A per-seed bound is therefore either
noise-sensitive or too loose to mean anything, so this checks the claim the
way it was measured: the total served over ten paired seeds.

Margin: with ~5 % per-seed noise, the ten-seed ratio has a standard error of
about 1.6 %, so 0.95 is three standard errors below "no effect" (a spurious
failure is very unlikely, and the seeds are fixed, so the result is
deterministic) while a genuine merge loss of about 8 % or more would fail it.
Measured on these seeds: 983 / 989 = 0.994.
"""

import pytest

from tests.integration.test_calibration_pass import _run

SEEDS = range(1, 11)
DEMAND_VPH = 5400.0
DURATION_S = 240.0
MIN_RATIO = 0.95


@pytest.mark.slow
def test_a_merging_third_lane_costs_no_capacity_on_average() -> None:
    two = three = 0
    for seed in SEEDS:
        engine2, m2 = _run("roundabout", DEMAND_VPH, 2, seed, DURATION_S)
        engine3, m3 = _run("roundabout", DEMAND_VPH, 3, seed, DURATION_S)
        assert engine2.pool.collision_count == 0 and engine3.pool.collision_count == 0
        two += m2["throughput"]
        three += m3["throughput"]
    assert three >= MIN_RATIO * two, (three, two, three / two)
