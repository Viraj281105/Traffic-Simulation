"""V1.4: a crossing a committed vehicle can no longer stop short of is not
handed to a vehicle waiting at its stop line, whatever the two lengths.

Regression for the 105 s adaptive-signal standstill found by the V1.4
experiment matrix (3-lane adaptive signal, mixed traffic, seed 2): a platoon
follower inside the box held nothing on the zone its leader had just
released, a left-turner at the stop line was admitted onto it, and the two
then waited for each other.
"""

from typing import Any, Dict, List, Tuple

from src.core.clock import Clock
from src.core.engine import SimulationEngine
from src.core.enums import Direction, TurnIntent
from src.intersection.conflict_manager import ConflictManager
from src.roads.network import RoadNetwork


def _setup() -> Tuple[ConflictManager, Any, Any, float]:
    # Three lanes, as in the failing run: the west left turn meets the east
    # lane-2 through movement 20 m along its path, beyond the 12 m reach of
    # V1.0's proximity arbitration, so nothing else would hold the turner.
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=200.0, lanes_per_approach=3)
    manager = ConflictManager()
    for lane in network.get_all_connection_lanes():
        manager.register_connection_lane(lane)
    manager.compute_conflict_points()
    manager.protect_unstoppable_committed = True  # any vehicle mix
    through = network.generate_route(Direction.EAST, 2, TurnIntent.STRAIGHT)[1]
    left = network.generate_route(Direction.WEST, 0, TurnIntent.LEFT)[1]
    key = (min(left.lane_id, through.lane_id), max(left.lane_id, through.lane_id))
    cp = manager._conflict_points[key]
    dist = cp.dist_on_a if through.lane_id == cp.lane_id_a else cp.dist_on_b
    return manager, through, left, dist


def _admission(
    manager: ConflictManager, left: Any, committed: List[Dict[str, Any]]
) -> float:
    manager.reset_reservations()
    return manager.get_conflict_distance(
        vehicle_id="turner",
        vehicle_turn_intent=TurnIntent.LEFT,
        connection_lane_id=left.lane_id,
        vehicle_position_on_lane=0.0,
        current_time=1.0,
        all_vehicles_info=committed,
        vehicle_speed=4.0,
        on_connection_lane=False,
        vehicle_length=2.2,
    )


def _car(through: Any, position: float, speed: float) -> List[Dict[str, Any]]:
    return [
        {
            "vehicle_id": "follower",
            "turn_intent": TurnIntent.STRAIGHT,
            "connection_lane_id": through.lane_id,
            "position_on_lane": position,
            "speed": speed,
            "length": 4.5,
        }
    ]


def test_turner_is_held_for_a_car_that_cannot_stop_short() -> None:
    manager, through, left, dist = _setup()
    # 8 m from the crossing at 8.8 m/s: 2 m to the buffer, 12.9 m to stop.
    committed = _car(through, dist - 8.0, 8.8)
    assert _admission(manager, left, committed) == 0.0


def test_legacy_cars_only_keeps_the_v10_admission() -> None:
    manager, through, left, dist = _setup()
    manager.protect_unstoppable_committed = False
    committed = _car(through, dist - 8.0, 8.8)
    assert _admission(manager, left, committed) == float("inf")


def test_engine_enables_the_rule_only_with_a_vehicle_mix() -> None:
    def manager_for(config: Dict[str, Any]) -> ConflictManager:
        return SimulationEngine(Clock(0.1), 10, config).conflict_manager

    base: Dict[str, Any] = {"roads": {"lanesPerApproach": 1}}
    mixed = {
        **base,
        "vehicleGeneration": {"vehicleMix": {"car": 0.9, "motorcycle": 0.1}},
    }
    assert not manager_for(base).protect_unstoppable_committed
    assert manager_for(mixed).protect_unstoppable_committed


def test_turner_is_admitted_while_the_car_can_still_stop() -> None:
    manager, through, left, dist = _setup()
    # Same place, crawling: it can stop well short, so V1.0 rules apply.
    committed = _car(through, dist - 8.0, 1.0)
    assert _admission(manager, left, committed) == float("inf")


def test_turner_is_admitted_once_the_car_has_cleared_the_crossing() -> None:
    manager, through, left, dist = _setup()
    # Beyond the 6 m reservation buffer, so V1.0 arbitration ignores it too.
    committed = _car(through, dist + 7.0, 8.8)
    assert _admission(manager, left, committed) == float("inf")


def test_rule_is_off_when_the_car_is_already_inside_the_buffer() -> None:
    manager, through, left, dist = _setup()
    # Inside the buffer, moving and clear of the point by more than its body,
    # the V1.0 rules decide exactly as before V1.4: the turner is admitted
    # (the car will be through long before the turner gets 20 m in).
    inside = _car(through, dist - 5.0, 8.8)
    assert _admission(manager, left, inside) == float("inf")
