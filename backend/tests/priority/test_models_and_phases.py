"""Bounds of the priority inputs, the vehicle model and the plan cursor."""

from typing import Any, Dict

import pytest

from src.controllers.adaptive_signal import AdaptiveSignalController
from src.controllers.factory import create_controller
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.enums import Direction, TurnIntent
from src.priority import models as m
from src.priority.models import (
    EmergencySpec,
    PreemptionConfig,
    ScenarioSpec,
    TransitLineSpec,
    TransitPriorityConfig,
    YieldConfig,
)
from src.priority.phases import PhaseDriver
from src.priority.runs import build_config
from src.priority.vehicles import (
    EMERGENCY_KINDS,
    candidate_lanes,
    find_entry,
    lane_preferred_index,
)
from src.roads.network import RoadNetwork

KINDS: Dict[str, object] = dict(EMERGENCY_KINDS)


def _driver(lanes: int = 1) -> PhaseDriver:
    config = build_config(ScenarioSpec(lanes_per_approach=lanes), seed=1)
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=lanes
    )
    ctl = create_controller(config, network)
    assert isinstance(ctl, FixedTimeSignalController)
    return PhaseDriver(ctl)


# -- bounds ---------------------------------------------------------------


@pytest.mark.parametrize(
    "spec",
    [
        ScenarioSpec(duration_s=10.0),
        ScenarioSpec(duration_s=m.MAX_DURATION_S + 1),
        ScenarioSpec(arrival_rate=0.0),
        ScenarioSpec(arrival_rate=5.0),
        ScenarioSpec(lanes_per_approach=4),
        ScenarioSpec(time_step_s=0.5),
        ScenarioSpec(green_s=float("nan")),
    ],
)
def test_scenario_bounds(spec: ScenarioSpec) -> None:
    with pytest.raises(ValueError):
        spec.validate()


def test_default_scenario_is_valid() -> None:
    ScenarioSpec().validate()


def test_seed_budget_is_bounded() -> None:
    m.check_seed_budget(2, 300.0)
    with pytest.raises(ValueError):
        m.check_seed_budget(1, 60.0)
    with pytest.raises(ValueError):
        m.check_seed_budget(m.MAX_SEEDS + 1, 60.0)
    with pytest.raises(ValueError):
        m.check_seed_budget(20, 600.0)  # 12000 simulated seconds per arm


def test_emergency_spec_bounds() -> None:
    EmergencySpec("ambulance", "north", "straight", 100.0).validate(KINDS, 300.0)
    for bad in (
        EmergencySpec("tank", "north", "straight", 100.0),
        EmergencySpec("ambulance", "up", "straight", 100.0),
        EmergencySpec("ambulance", "north", "uturn", 100.0),
        EmergencySpec("ambulance", "north", "straight", 290.0),
        EmergencySpec("ambulance", "north", "straight", -1.0),
        EmergencySpec("ambulance", "north", "straight", 10.0, lane=9),
    ):
        with pytest.raises(ValueError):
            bad.validate(KINDS, 300.0)


def test_config_bounds() -> None:
    PreemptionConfig().validate()
    YieldConfig().validate()
    TransitPriorityConfig().validate()
    with pytest.raises(ValueError):
        PreemptionConfig(detection_distance_m=None, detection_time_s=None).validate()
    with pytest.raises(ValueError):
        PreemptionConfig(min_green_s=0.0).validate()
    with pytest.raises(ValueError):
        PreemptionConfig(max_hold_s=500.0).validate()
    with pytest.raises(ValueError):
        PreemptionConfig(min_green_s=20.0, max_hold_s=10.0).validate()
    with pytest.raises(ValueError):
        YieldConfig(headway_factor=0.0).validate()
    with pytest.raises(ValueError):
        TransitPriorityConfig(max_extension_s=60.0).validate()
    line = TransitLineSpec("L1", "north", "straight", 90.0, 10.0, 3)
    line.validate(300.0)
    with pytest.raises(ValueError):
        TransitLineSpec("L1", "north", "straight", 5.0, 10.0, 3).validate(300.0)
    with pytest.raises(ValueError):
        TransitLineSpec("L1", "north", "straight", 90.0, 10.0, 99).validate(300.0)


# -- vehicle model ----------------------------------------------------------


def test_emergency_kinds_outperform_a_car() -> None:
    car = ScenarioSpec().speed_limit_mps * 1.05  # fastest legacy car
    for kind in EMERGENCY_KINDS.values():
        profile = kind.profile()
        assert kind.length <= 7.0  # inside the geometry the junction is sized for
        assert profile.type_id == kind.kind_id
        assert kind.params(13.89).desired_speed_range[0] > car
        assert profile.max_acceleration >= 1.5
    ambulance = EMERGENCY_KINDS["ambulance"].profile()
    assert ambulance.max_acceleration > 2.0 > 0
    assert ambulance.comfort_deceleration > 3.0


def test_lane_choice_follows_the_network_policy() -> None:
    assert lane_preferred_index(1, "left") == 0
    assert lane_preferred_index(2, "left") == 0
    assert lane_preferred_index(2, "straight") == 1
    assert lane_preferred_index(3, "right") == 2
    assert lane_preferred_index(3, "straight") == 1
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=2
    )
    assert candidate_lanes(network, Direction.NORTH, "left", None)[0] == 0
    with pytest.raises(ValueError):
        candidate_lanes(network, Direction.NORTH, "left", 5)
    with pytest.raises(ValueError):
        candidate_lanes(network, Direction.NORTH, "left", 1)


def test_find_entry_on_an_empty_approach() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=200.0, lane_width=3.5, lanes_per_approach=1
    )
    entry = find_entry(network, Direction.NORTH, "straight", None, 5.5, 1.5, 4.0, 19.0)
    assert entry == (0, 19.0)


# -- plan cursor --------------------------------------------------------------


def test_driver_finds_the_green_for_a_movement() -> None:
    driver = _driver()
    north_straight = driver.find_green(Direction.NORTH, TurnIntent.STRAIGHT)
    east_left = driver.find_green(Direction.EAST, TurnIntent.LEFT)
    assert north_straight == 0 and driver.phases[0].name == "ns_green"
    assert east_left is not None and driver.phases[east_left].name == "ew_green"
    assert driver.serves(0, Direction.SOUTH, TurnIntent.LEFT)  # permissive left
    assert not driver.serves(0, Direction.EAST, TurnIntent.STRAIGHT)


def test_driver_clearance_is_the_plans_own_yellow() -> None:
    driver = _driver()
    assert driver.phases[driver.clearance_start(0) or 0].color == "yellow"
    ew = driver.find_green(Direction.EAST, TurnIntent.STRAIGHT)
    assert ew is not None
    assert driver.phases[driver.clearance_start(ew) or 0].name == "ew_yellow"
    assert driver.next_green(0) == ew
    assert driver.next_green(ew, exclude=driver.phases[ew].directions) == 0


def test_driver_advance_matches_the_plan_when_unredirected() -> None:
    driver = _driver()
    config: Dict[str, Any] = build_config(ScenarioSpec(), seed=1)
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=200.0, lane_width=3.5)
    reference = create_controller(config, network)
    assert isinstance(reference, FixedTimeSignalController)
    for _ in range(1500):
        driver.advance(0.1)
        reference.update(0.1, [])
        assert driver.index == reference.current_phase_idx
        assert abs(driver.elapsed - reference.time_in_current_state) < 1e-9


def test_driver_advance_can_redirect_the_next_green() -> None:
    driver = _driver()
    ew = driver.find_green(Direction.EAST, TurnIntent.STRAIGHT)
    assert ew is not None
    driver.jump(driver.clearance_start(ew) or 0)  # ew_yellow
    # Without redirection ew_yellow -> all_red -> ns_green; ask for ew instead.
    seen = []
    for _ in range(100):
        driver.advance(
            0.1,
            lambda old: (
                ew if driver.phases[(old + 1) % 6].color == "green" else (old + 1) % 6
            ),
        )
        seen.append(driver.index)
    assert ew in seen and 0 not in seen


def test_priority_needs_a_fixed_time_plan() -> None:
    config = build_config(ScenarioSpec(), seed=1)
    config["controller"]["adaptive"] = {}
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=200.0, lane_width=3.5)
    adaptive = AdaptiveSignalController(config, network)
    with pytest.raises(ValueError):
        PhaseDriver(adaptive)
