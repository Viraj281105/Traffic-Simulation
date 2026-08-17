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
