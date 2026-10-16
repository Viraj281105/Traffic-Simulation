"""Unit tests for StopLineDetection and Observation (src.controllers.signal_detection)."""

from dataclasses import FrozenInstanceError
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from src.controllers.factory import create_controller
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.signal_detection import (
    MOVING_SPEED,
    Observation,
    StopLineDetection,
)
from src.core.enums import Direction
from src.roads.lane import Lane
from src.roads.network import RoadNetwork

PAIRED = ["ns_green", "ns_yellow", "all_red", "ew_green", "ew_yellow", "all_red"]


class _VehicleStub:
    """Mock vehicle providing just what StopLineDetection reads."""

    def __init__(self, lane: Lane, position: float, speed: float) -> None:
        self.lane = lane
        self.position = position
        self.speed = speed


def _make_controller(lanes: int = 1) -> FixedTimeSignalController:
    config: Dict[str, Any] = {
        "simulation": {"duration": 60.0, "timeStep": 0.1, "randomSeed": 1},
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {"approachLength": 100.0, "laneWidth": 3.5, "lanesPerApproach": lanes},
        "traffic": {"arrivalRate": 0.5},
        "controller": {
            "greenTime": 30.0,
            "yellowTime": 4.0,
            "allRedTime": 2.0,
            "phaseSequence": list(PAIRED),
        },
    }
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=lanes
    )
    ctl = create_controller(config, network)
    assert isinstance(ctl, FixedTimeSignalController)
    return ctl


def test_observation_dataclass_contract() -> None:
    """Verifies Observation immutability, fields, and value equality."""
    obs = Observation(
        served=2,
        passing=1,
        calls={3: 1},
        per_direction={"north": 1, "south": 1, "east": 1, "west": 0},
    )
    assert obs.served == 2
    assert obs.passing == 1
    assert obs.calls == {3: 1}
    assert obs.per_direction["north"] == 1

    with pytest.raises(FrozenInstanceError):
        obs.served = 5  # type: ignore[misc]

    same = Observation(
        served=2,
        passing=1,
        calls={3: 1},
        per_direction={"north": 1, "south": 1, "east": 1, "west": 0},
    )
    assert obs == same


def test_stop_line_detection_initialization() -> None:
    """Verifies that only green phases have registered released lanes."""
    ctl = _make_controller(lanes=1)
    detection = StopLineDetection(ctl, distance=30.0)

    assert detection.distance == 30.0
    # In PAIRED: index 0 (ns_green) and index 3 (ew_green) are green.
    assert set(detection.released.keys()) == {0, 3}
    assert len(detection.released[0]) == 2  # North and South 1-lane approaches
    assert len(detection.released[3]) == 2  # East and West 1-lane approaches


def test_zone_count_boundaries() -> None:
    """Tests vehicle position detection and speed classification thresholds."""
    ctl = _make_controller(lanes=1)
    detection = StopLineDetection(ctl, distance=25.0)
    lane = ctl.network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    lane_len = lane.length
    det_start = lane_len - 25.0

    # 1. Empty lane
    assert detection.zone_count(lane) == (0, 0)

    # 2. Vehicle far behind the detection zone
    v_outside = _VehicleStub(lane, position=det_start - 5.0, speed=10.0)
    lane.add_vehicle(v_outside)
    assert detection.zone_count(lane) == (0, 0)

    # 3. Vehicle right on the start boundary, stopped
    v_boundary = _VehicleStub(lane, position=det_start, speed=0.5)
    lane.add_vehicle(v_boundary)
    assert detection.zone_count(lane) == (1, 0)

    # 4. Vehicle in zone moving exactly at MOVING_SPEED threshold
    v_moving = _VehicleStub(lane, position=det_start + 10.0, speed=MOVING_SPEED)
    lane.add_vehicle(v_moving)
    assert detection.zone_count(lane) == (2, 1)

    # 5. Vehicle at the stop line moving fast
    v_stop_line = _VehicleStub(lane, position=lane_len, speed=15.0)
    lane.add_vehicle(v_stop_line)
    assert detection.zone_count(lane) == (3, 2)


def test_zone_count_lane_change_deduplication() -> None:
    """Ensures a vehicle in the process of changing lanes is only counted on its target lane."""
    ctl = _make_controller(lanes=2)
    detection = StopLineDetection(ctl, distance=25.0)
    lanes = ctl.network.get_incoming_approach(Direction.NORTH).get_lanes()
    lane0, lane1 = lanes[0], lanes[1]

    # Vehicle is physically registered in lane0's vehicle list, but v.lane is lane1
    v = _VehicleStub(lane=lane1, position=lane0.length - 10.0, speed=5.0)
    lane0.add_vehicle(v)

    # lane0 must not count it because v.lane is not lane0
    assert detection.zone_count(lane0) == (0, 0)


def test_observe_green_and_clearance_phases() -> None:
    """Tests observe() output across active green and clearance (all_red) phases."""
    ctl = _make_controller(lanes=1)
    detection = StopLineDetection(ctl, distance=30.0)

    north_lane = ctl.network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    south_lane = ctl.network.get_incoming_approach(Direction.SOUTH).get_lanes()[0]
    east_lane = ctl.network.get_incoming_approach(Direction.EAST).get_lanes()[0]

    # Stopped car waiting at North
    north_lane.add_vehicle(
        _VehicleStub(north_lane, north_lane.length - 10.0, speed=0.0)
    )
    # Moving car approaching South
    south_lane.add_vehicle(
        _VehicleStub(south_lane, south_lane.length - 15.0, speed=5.0)
    )
    # Stopped car waiting at East (cross street)
    east_lane.add_vehicle(_VehicleStub(east_lane, east_lane.length - 5.0, speed=0.0))

    # Current phase is 0 (ns_green)
    obs = detection.observe(current_idx=0)
    assert obs.served == 2  # North + South
    assert obs.passing == 1  # Only South is moving >= MOVING_SPEED
    assert obs.calls == {3: 1}  # East waiting calls phase 3 (ew_green)
    assert obs.per_direction["north"] == 1
    assert obs.per_direction["south"] == 1
    assert obs.per_direction["east"] == 1
    assert obs.per_direction["west"] == 0

    # Clearance phase 2 (all_red) -> no lanes released
    obs_clearance = detection.observe(current_idx=2)
    assert obs_clearance.served == 0
    assert obs_clearance.passing == 0
    assert obs_clearance.calls == {0: 2, 3: 1}


def test_released_lanes_handles_missing_direction() -> None:
    """Verifies that missing network directions are handled gracefully without raising KeyError."""
    mock_ctl = MagicMock(spec=FixedTimeSignalController)
    mock_phase = MagicMock()
    mock_phase.color = "green"
    mock_phase.directions = [Direction.NORTH, Direction.SOUTH]
    mock_phase.allowed_turns = ["straight"]
    mock_ctl.phases = [mock_phase]

    mock_network = MagicMock(spec=RoadNetwork)
    mock_network.get_incoming_approach.side_effect = KeyError("No south approach")
    mock_ctl.network = mock_network

    detection = StopLineDetection(mock_ctl, distance=20.0)
    assert detection.released == {0: ()}
