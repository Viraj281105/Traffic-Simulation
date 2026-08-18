import pytest

from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.registry import ControllerRegistry
from src.controllers.roundabout import RoundaboutController
from src.roads.network import RoadNetwork


def test_controller_registry() -> None:
    signal_cls = ControllerRegistry.get_controller_class("fixed_time_signal")
    assert signal_cls == FixedTimeSignalController

    roundabout_cls = ControllerRegistry.get_controller_class("roundabout")
    assert roundabout_cls == RoundaboutController

    with pytest.raises(KeyError):
        ControllerRegistry.get_controller_class("invalid_name")


def test_fixed_time_signal_transitions() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    config = {
        "controller": {
            "greenTime": 10,
            "yellowTime": 3,
            "allRedTime": 2,
            "phaseSequence": [
                "ns_green",
                "ns_yellow",
                "all_red",
                "ew_green",
                "ew_yellow",
                "all_red",
            ],
        }
    }

    controller = FixedTimeSignalController(config, network)
    assert controller.current_phase == "ns_green"
    assert controller.phase_time_remaining == 10.0

    # Advance by 5s
    controller.update(5.0, [])
    assert controller.current_phase == "ns_green"
    assert controller.phase_time_remaining == 5.0

    # Advance by 5.1s -> transition to ns_yellow
    controller.update(5.1, [])
    assert controller.current_phase == "ns_yellow"
    assert pytest.approx(controller.phase_time_remaining) == 2.9

    # Check signal state dictionary
    state = controller.get_state()
    assert state["type"] == "fixed_time_signal"
    assert state["currentPhase"] == "ns_yellow"
    assert any(
        s["direction"] == "north" and s["color"] == "yellow" for s in state["signals"]
    )
    assert any(
        s["direction"] == "east" and s["color"] == "red" for s in state["signals"]
    )


def test_roundabout_controller() -> None:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=2
    )

    config = {
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "circulatingSpeed": 8.0,
        }
    }

    controller = RoundaboutController(config, network)
    state = controller.get_state()
    assert state["type"] == "roundabout"
    assert state["innerRadius"] == 10.0
    assert state["outerRadius"] == 20.0
    assert state["gapAcceptance"] == 4.0


def test_roundabout_yielding() -> None:
    """Verifies that vehicles yield when time_gap < critical_gap, and proceed when gap > critical_gap."""
    from src.core.enums import Direction
    from src.roads.lane import Lane
    from src.vehicles.vehicle import Vehicle

    network = RoadNetwork()
    network.setup_default_intersection(100.0, 3.5, 2)
    config = {
        "controller": {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "criticalGap": 4.0,
            "circulatingSpeed": 8.0,
        }
    }
    controller = RoundaboutController(config, network)

    # Place a circulating vehicle close to North entry point (approx 1.75, 15.0)
    # conn_circ lane ID must start with "conn" so that the controller identifies it as circulating
    conn_lane = Lane("conn_circ", 1.75, 16.0, 10.0, 16.0)
    circ_vehicle = Vehicle(
        "circ_1",
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=[conn_lane],
        start_position=0.0,
        initial_speed=8.0,
    )

    # Update controller
    controller.update(0.1, [circ_vehicle])

    # Incoming North lane should have virtual obstacle active (yield)
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    assert lane.virtual_obstacle is not None

    # Move circulating vehicle far away by updating its position along a long route
    conn_lane_far = Lane("conn_circ_far", 100.0, 100.0, 200.0, 100.0)
    circ_vehicle.lane = conn_lane_far
    circ_vehicle.position = 0.0

    controller.update(0.1, [circ_vehicle])

    # Obstacle should be cleared
    assert lane.virtual_obstacle is None
