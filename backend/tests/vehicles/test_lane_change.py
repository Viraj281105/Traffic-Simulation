"""V1.2 lane changing: MOBIL decisions executed as gradual manoeuvres."""

from typing import List, Optional, Tuple

import pytest

from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.lane_change import (
    COOLDOWN,
    END_MARGIN,
    LaneChangeModel,
    LaneChangeSettings,
    origin_lane_leader,
    resolve_lane_change_settings,
)
from src.vehicles.pool import VehiclePool
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import resolve_vehicle_population

L, S, R = TurnIntent.LEFT, TurnIntent.STRAIGHT, TurnIntent.RIGHT
N = Direction.NORTH


def _network(lanes: int = 2) -> RoadNetwork:
    network = RoadNetwork()
    network.setup_default_intersection(approach_length=200.0, lanes_per_approach=lanes)
    return network


def _lanes(network: RoadNetwork) -> List[Lane]:
    return network.get_incoming_approach(N).get_lanes()


def _vehicle(
    network: RoadNetwork,
    vid: str,
    lane_idx: int,
    position: float,
    speed: float,
    turn: TurnIntent = S,
    length: float = 4.5,
) -> Vehicle:
    route = network.generate_route(N, lane_idx, turn)
    return Vehicle(
        vid,
        length,
        1.9,
        13.0,
        route,
        start_position=position,
        initial_speed=speed,
        turn_intent=turn,
    )


def _model(**kwargs: float) -> LaneChangeModel:
    return LaneChangeModel(LaneChangeSettings(**kwargs), IntelligentDriverModel())  # type: ignore[arg-type]


def _blocked_scenario() -> Tuple[RoadNetwork, Vehicle, Vehicle]:
    """A through vehicle closing on a stopped vehicle, next lane empty."""
    network = _network()
    blocker = _vehicle(network, "blocker", 1, 80.0, 0.0)
    me = _vehicle(network, "me", 1, 50.0, 10.0)
    return network, me, blocker


def test_settings_resolve_from_config() -> None:
    assert resolve_lane_change_settings({}) == LaneChangeSettings()
    settings = resolve_lane_change_settings(
        {
            "roads": {
                "laneChange": {
                    "enabled": False,
                    "accelerationThreshold": 0.5,
                    "safeDeceleration": 3.0,
                    "politeness": 0.0,
                }
            }
        }
    )
    assert settings == LaneChangeSettings(False, 0.5, 3.0, 0.0)


def test_change_is_gradual_and_completes_before_the_lane_end() -> None:
    network, me, _ = _blocked_scenario()
    origin, target = _lanes(network)[1], _lanes(network)[0]
    assert _model().attempt(me, network, current_time=10.0, last_change_time=-99)

    # Logically in the target lane at once, physically still in the origin.
    assert me.lane is target
    assert me.route[0] is target
    assert me.lane_change is not None
    assert me in target.get_vehicles() and me in origin.get_vehicles()
    x0, _ = me.coords
    assert x0 == pytest.approx(origin.start_coords[0])

    distance = me.lane_change.distance
    assert distance == pytest.approx(max(12.0, 10.0 * 3.0))
    assert target.length - 50.0 >= distance + END_MARGIN

    xs = [x0]
    while me.lane_change is not None:
        me.update_state(0.0, 0.1)
        xs.append(me.coords[0])
    # Monotone, small per-tick lateral steps: never a jump.
    steps = [b - a for a, b in zip(xs, xs[1:])]
    lateral = target.start_coords[0] - origin.start_coords[0]
    assert all(step * lateral >= -1e-9 for step in steps)
    assert max(abs(s) for s in steps) < 0.25
    assert xs[-1] == pytest.approx(target.start_coords[0])
    # Released the origin lane on completion, still on its approach.
    assert me not in origin.get_vehicles()
    assert me.lane is target
    assert me.position < target.length


def test_heading_yaws_towards_the_target_lane() -> None:
    network, me, _ = _blocked_scenario()
    lane_heading = _lanes(network)[1].heading
    _model().attempt(me, network, 0.0, -99)
    for _ in range(15):  # 15 m into a 30 m manoeuvre: mid-change
        me.update_state(0.0, 0.1)
    assert me.lane_change is not None
    assert me.heading != pytest.approx(lane_heading)
    assert abs(((me.heading - lane_heading) + 180) % 360 - 180) < 20


def test_unsafe_gap_is_rejected() -> None:
    network, me, _ = _blocked_scenario()
    # Fast vehicle right behind in the target lane: it would have to brake
    # harder than b_safe.
    _vehicle(network, "fast", 0, 44.0, 14.0)
    assert not _model().attempt(me, network, 0.0, -99)
    assert me.lane is _lanes(network)[1]
    assert me.lane_change is None


def test_physically_occupied_target_is_rejected() -> None:
    network, me, _ = _blocked_scenario()
    _vehicle(network, "beside", 0, 51.0, 10.0)  # overlapping alongside
    assert not _model().attempt(me, network, 0.0, -99)


def test_no_incentive_means_no_change() -> None:
    network = _network()
    me = _vehicle(network, "me", 1, 50.0, 10.0)
    assert not _model().attempt(me, network, 0.0, -99)


def test_threshold_and_disable_switch() -> None:
    network, me, _ = _blocked_scenario()
    assert not _model(enabled=False).attempt(me, network, 0.0, -99)
    assert not _model(acceleration_threshold=50.0).attempt(me, network, 0.0, -99)


def test_cooldown_between_changes() -> None:
    network, me, _ = _blocked_scenario()
    assert not _model().attempt(me, network, 10.0, last_change_time=10.0 - COOLDOWN / 2)
    assert _model().attempt(me, network, 10.0, last_change_time=10.0 - COOLDOWN)


def test_no_change_too_close_to_the_stop_line() -> None:
    network = _network()
    end = _lanes(network)[1].length
    _vehicle(network, "blocker", 1, end - 5.0, 0.0)
    me = _vehicle(network, "me", 1, end - 30.0, 10.0)
    assert not _model().attempt(me, network, 0.0, -99)


def test_turning_vehicles_keep_to_their_lane() -> None:
    network = _network()
    _vehicle(network, "blocker", 0, 80.0, 0.0, turn=L)
    left = _vehicle(network, "left", 0, 50.0, 10.0, turn=L)
    # Lane 1 is empty and faster, but a left turn is not permitted from it.
    assert not _model().attempt(left, network, 0.0, -99)


def test_through_traffic_respects_controller_lane_use() -> None:
    network, me, _ = _blocked_scenario()
    network.set_lane_use(N, 0, frozenset({L}))  # lane 0 is a left-turn pocket
    assert not _model().attempt(me, network, 0.0, -99)


def test_mandatory_change_into_a_permitted_lane() -> None:
    network = _network()
    # A left-turner in lane 1, which does not permit left turns. Nothing
    # slows it, so only the mandatory rule can move it.
    wrong = _vehicle(network, "wrong", 1, 40.0, 10.0, turn=L)
    model = _model()
    assert model.attempt(wrong, network, 0.0, -99)
    assert wrong.lane is _lanes(network)[0]
    assert wrong.route[1].lane_id == "conn_north_0_left"
    assert model.missed_turns == 0


def test_missed_turn_when_a_change_is_no_longer_possible() -> None:
    network = _network()
    end = _lanes(network)[1].length
    wrong = _vehicle(network, "wrong", 1, end - 15.0, 5.0, turn=L)
    model = _model()
    assert not model.attempt(wrong, network, 0.0, -99)
    assert wrong.turn_intent in network.permitted_turns(N, 1)
    assert wrong.turn_intent is S
    assert wrong.route[1].lane_id == "conn_north_1_straight"
    assert model.missed_turns == 1


def test_mandatory_change_still_needs_a_safe_gap() -> None:
    network = _network()
    wrong = _vehicle(network, "wrong", 1, 40.0, 10.0, turn=L)
    _vehicle(network, "beside", 0, 41.0, 10.0, turn=L)
    assert not _model().attempt(wrong, network, 0.0, -99)
    assert wrong.lane is _lanes(network)[1]


def test_origin_lane_leader_constrains_a_changing_vehicle() -> None:
    network, me, blocker = _blocked_scenario()
    assert origin_lane_leader(me) == (None, float("inf"))
    _model().attempt(me, network, 0.0, -99)
    leader, gap = origin_lane_leader(me)
    assert leader is blocker
    assert gap == pytest.approx(80.0 - 50.0 - 4.5)


def test_bus_changes_lanes_over_a_longer_distance() -> None:
    population = resolve_vehicle_population(
        {"vehicleGeneration": {"vehicleMix": {"bus": 1.0}}}
    )
    assert population is not None
    network = _network()
    # Stopped vehicle ~17 m ahead of the bus's front: a clear incentive even
    # for a bus's gentle acceleration (a = 1.0 m/s^2).
    _vehicle(network, "blocker", 1, 85.0, 0.0)
    bus = _vehicle(network, "bus", 1, 60.0, 4.0, length=12.0)
    bus.params = population.params_by_type["bus"]
    assert _model().attempt(bus, network, 0.0, -99)
    assert bus.lane_change is not None
    assert bus.lane_change.distance == pytest.approx(
        bus.params.profile.lane_change_min_distance
    )


class _Engine:
    def __init__(self, network: RoadNetwork) -> None:
        self.network = network
        self.config: dict = {}
        self.idm: Optional[IntelligentDriverModel] = None


def test_pool_runs_changes_and_counts_them() -> None:
    network, me, blocker = _blocked_scenario()
    pool = VehiclePool()
    pool.add_vehicle(blocker)
    pool.add_vehicle(me)
    engine = _Engine(network)
    pool._attempt_lane_change(me, 5.0, engine)
    assert pool.lane_change_count == 1
    assert pool._last_lane_change["me"] == 5.0
    # reset() drops both registrations of a mid-manoeuvre vehicle.
    pool.reset()
    assert all(not lane.get_vehicles() for lane in _lanes(network))
    assert pool.lane_change_count == 0


def test_collision_audit_checks_vehicles_that_are_changing_lanes() -> None:
    network, me, _ = _blocked_scenario()
    _model().attempt(me, network, 0.0, -99)
    # A vehicle sitting exactly where the changing vehicle still is, in the
    # lane it is leaving. Parallel lanes of one approach are normally exempt
    # from the audit; a vehicle straddling them is not.
    ghost = _vehicle(network, "ghost", 1, 50.0, 0.0)
    pool = VehiclePool()
    pool.add_vehicle(me)
    pool.add_vehicle(ghost)
    pool._collision_audit()
    assert pool.collision_count == 1

    clear_net, mover, _ = _blocked_scenario()
    _model().attempt(mover, clear_net, 0.0, -99)
    far = _vehicle(clear_net, "far", 1, 20.0, 0.0)
    pool2 = VehiclePool()
    pool2.add_vehicle(mover)
    pool2.add_vehicle(far)
    pool2._collision_audit()
    assert pool2.collision_count == 0
