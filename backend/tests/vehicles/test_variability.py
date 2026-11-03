"""Opt-in driver heterogeneity and demand variability (ADR-020)."""

from __future__ import annotations

import copy
import math
import statistics
from typing import Any, Dict, List

import pytest

from src.scenario.config_validation import semantic_config_errors
from src.study.multiseed import default_study_config, seeded_run_config
from src.study.runner import SimTask, run_simulation_tasks
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.variability import (
    DemandFactors,
    DemandVariability,
    DriverDraws,
    DriverHeterogeneity,
    describe,
    parse_demand_variability,
    parse_driver_heterogeneity,
    scaled_idm,
    validate_variability,
    variability_stream,
)

DRIVERS = {
    "enabled": True,
    "headwaySpread": 0.3,
    "accelerationSpread": 0.2,
    "decelerationSpread": 0.2,
}
DEMAND = {"enabled": True, "spread": 0.4, "intervalSeconds": 60}


def _config(**traffic: Any) -> Dict[str, Any]:
    cfg = default_study_config(40.0)
    cfg["traffic"].update(traffic)
    return cfg


def _metrics(
    cfg: Dict[str, Any], seed: int, geometry: str = "signal"
) -> Dict[str, Any]:
    task = SimTask(
        config=seeded_run_config(cfg, seed, 40.0),
        geometry=geometry,
        duration=40.0,
        label="t",
    )
    metrics: Dict[str, Any] = run_simulation_tasks([task])[0]["metrics"]
    return metrics


# --- parsing and validation -------------------------------------------------


def test_absent_or_disabled_blocks_are_off() -> None:
    assert parse_driver_heterogeneity({}) is None
    assert parse_demand_variability({}) is None
    off = {"driverHeterogeneity": {"enabled": False, "headwaySpread": 0.3}}
    assert parse_driver_heterogeneity(off) is None
    zero = {"driverHeterogeneity": {"enabled": True}}
    assert parse_driver_heterogeneity(zero) is None
    assert describe({"traffic": {}}) == {
        "driverHeterogeneity": False,
        "demandVariability": False,
    }


def test_enabled_blocks_parse() -> None:
    assert parse_driver_heterogeneity({"driverHeterogeneity": DRIVERS}) == (
        DriverHeterogeneity(0.3, 0.2, 0.2)
    )
    assert parse_demand_variability({"demandVariability": DEMAND}) == (
        DemandVariability(0.4, 60.0)
    )


def _drv(**kw: Any) -> Dict[str, Any]:
    return {"driverHeterogeneity": {"enabled": True, **kw}}


def _dem(**kw: Any) -> Dict[str, Any]:
    return {"demandVariability": {"enabled": True, **kw}}


@pytest.mark.parametrize(
    "block, text",
    [
        (_drv(headwaySpread=0.6), "headwaySpread"),
        (_drv(accelerationSpread=-0.1), "accelerationSpread"),
        (_drv(decelerationSpread=float("nan")), "finite"),
        (_drv(headwaySpread=True), "finite"),
        ({"driverHeterogeneity": {"enabled": "yes"}}, "enabled"),
        ({"driverHeterogeneity": 3}, "object"),
        (_dem(spread=0.9), "spread"),
        (_dem(spread=0.2, intervalSeconds=5), "intervalSeconds"),
        (_dem(spread=0.2, intervalSeconds=1e9), "intervalSeconds"),
    ],
)
def test_bad_blocks_are_rejected_with_a_named_field(
    block: Dict[str, Any], text: str
) -> None:
    problems = validate_variability({"traffic": block})
    assert problems and text in problems[0] and "traffic." in problems[0]


def test_config_validation_reports_variability_errors() -> None:
    cfg = _config(driverHeterogeneity={"enabled": True, "headwaySpread": 0.9})
    assert any("driverHeterogeneity" in e for e in semantic_config_errors(cfg))


# --- streams ----------------------------------------------------------------


def test_streams_are_deterministic_and_distinct() -> None:
    a = [variability_stream(1, "x").random() for _ in range(3)]
    assert a == [variability_stream(1, "x").random() for _ in range(3)]
    assert variability_stream(1, "x").random() != variability_stream(2, "x").random()
    assert variability_stream(1, "x").random() != variability_stream(1, "y").random()


def test_driver_factors_are_bounded_and_centred() -> None:
    draws = DriverDraws(DriverHeterogeneity(0.3, 0.2, 0.1), 7)
    rows = [draws.next_factors() for _ in range(4000)]
    for index, spread in enumerate((0.3, 0.2, 0.1)):
        column = [r[index] for r in rows]
        assert min(column) >= 1 - spread and max(column) <= 1 + spread
        assert abs(statistics.fmean(column) - 1.0) < 0.01
        assert max(column) - min(column) > 1.8 * spread


def test_zero_spread_trait_does_not_shift_the_others() -> None:
    both = DriverDraws(DriverHeterogeneity(0.3, 0.2, 0.2), 9)
    only = DriverDraws(DriverHeterogeneity(0.3, 0.0, 0.0), 9)
    for _ in range(5):
        a, b = both.next_factors(), only.next_factors()
        assert a[0] == b[0] and b[1] == 1.0 and b[2] == 1.0


def test_demand_factors_per_run_and_per_block() -> None:
    whole = DemandFactors(DemandVariability(0.4, None), 3)
    assert whole.factor_at(0) == whole.factor_at(900.0)
    blocks = DemandFactors(DemandVariability(0.4, 60.0), 3)
    values = [blocks.factor_at(t) for t in (0, 59, 60, 119, 120)]
    assert values[0] == values[1] and values[2] == values[3]
    assert len({values[0], values[2], values[4]}) == 3
    assert all(0.6 <= v <= 1.4 for v in values)
    again = DemandFactors(DemandVariability(0.4, 60.0), 3)
    assert again.factor_at(120) == values[4]  # independent of query order


def test_scaled_idm_scales_only_the_three_traits() -> None:
    base = IntelligentDriverModel()
    scaled = scaled_idm(base, (2.0, 0.5, 1.5))
    assert scaled._desired_time_headway == 3.0
    assert scaled._max_acceleration == 1.0
    assert scaled._comfort_deceleration == 4.5
    assert scaled._minimum_gap == base._minimum_gap
    assert base._desired_time_headway == 1.5  # base untouched


# --- engine behaviour -------------------------------------------------------


def test_off_is_bit_identical_to_absent() -> None:
    plain = _metrics(_config(), 11)
    off = _metrics(
        _config(
            driverHeterogeneity={"enabled": False, "headwaySpread": 0.4},
            demandVariability={"enabled": False, "spread": 0.5},
        ),
        11,
    )
    assert plain == off


@pytest.mark.parametrize("geometry", ["signal", "roundabout"])
def test_on_is_deterministic_and_differs_from_off(geometry: str) -> None:
    cfg = _config(driverHeterogeneity=DRIVERS, demandVariability=DEMAND)
    a, b = _metrics(cfg, 11, geometry), _metrics(cfg, 11, geometry)
    assert a == b
    assert a != _metrics(_config(), 11, geometry)


def test_different_seeds_differ_with_models_on() -> None:
    cfg = _config(driverHeterogeneity=DRIVERS, demandVariability=DEMAND)
    assert _metrics(cfg, 11) != _metrics(cfg, 12)


def _spawner(traffic: Dict[str, Any]) -> Any:
    from src.core.clock import Clock
    from src.engine.simulation_engine import SimulationEngine

    cfg = seeded_run_config(_config(**traffic), 5, 40.0)
    cfg["geometry"] = {"intersectionType": "fixed_time_signal"}
    engine = SimulationEngine(Clock(0.1), 40.0, copy.deepcopy(cfg))
    assert engine.spawner is not None
    return engine.spawner


def test_demand_model_does_not_change_driver_model_draws() -> None:
    def factors(traffic: Dict[str, Any]) -> List[Any]:
        draws = _spawner(traffic)._driver_draws
        assert draws is not None
        return [draws.next_factors() for _ in range(5)]

    only = factors({"driverHeterogeneity": DRIVERS})
    both = factors({"driverHeterogeneity": DRIVERS, "demandVariability": DEMAND})
    assert only == both


def test_driver_model_leaves_the_main_stream_alone() -> None:
    def next_draws(traffic: Dict[str, Any]) -> List[float]:
        s = _spawner(traffic)
        return [s.rng.random() for _ in range(5)]

    assert next_draws({}) == next_draws({"driverHeterogeneity": DRIVERS})


def test_models_on_spread_delay_across_seeds_and_stay_finite() -> None:
    cfg = _config(driverHeterogeneity=DRIVERS, demandVariability=DEMAND)
    delays = []
    for seed in range(21, 27):
        m = _metrics(cfg, seed)
        assert m["collisionCount"] == 0
        assert all(math.isfinite(v) for v in m.values() if isinstance(v, (int, float)))
        delays.append(m.get("averageDelay", m.get("averageWaitTime", 0.0)))
    assert statistics.pstdev(delays) > 0
