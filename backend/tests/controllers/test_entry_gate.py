"""The roundabout entry-gate seam (ADR-014 section 5, plan section 3.1).

The seam is consulted after the roundabout's own yield rules and before the
committed-long-vehicle override, so a closed gate can only add a yield. These
tests pin that contract; bit-identity of the default gate against the
pre-seam behaviour is pinned separately by the golden-fingerprint tests.
"""

import dataclasses
from typing import Any, List, Tuple

import pytest

from src.controllers.entry_gate import OPEN, AlwaysOpen, EntryGate, GateDecision
from src.controllers.roundabout import RoundaboutController
from src.core.enums import Direction
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.vehicle import Vehicle

_CONFIG = {
    "controller": {
        "innerRadius": 10.0,
        "outerRadius": 20.0,
        "criticalGap": 4.0,
        "followUpTime": 2.0,
        "entrySpeed": 5.0,
        "circulatingSpeed": 8.0,
    }
}


class _Gate:
    """A scripted gate that records every consultation."""

    def __init__(self, closed: Tuple[Direction, ...] = (), reason: Any = "red") -> None:
        self.closed = closed
        self.reason = reason
        self.calls: List[Tuple[Direction, Lane, float]] = []

    def allows(self, approach: Direction, lane: Lane, now: float) -> GateDecision:
        self.calls.append((approach, lane, now))
        if approach in self.closed:
            return GateDecision(open=False, reason=self.reason)
        return OPEN


def _roundabout(gate: Any = None) -> Tuple[RoundaboutController, RoadNetwork]:
    network = RoadNetwork()
    network.setup_default_intersection(
        approach_length=100.0, lane_width=3.5, lanes_per_approach=1
    )
    return RoundaboutController(_CONFIG, network, entry_gate=gate), network


def _head(
    network: RoadNetwork,
    direction: Direction,
    name: str,
    length: float = 4.0,
    short_of_line: float = 1.0,
) -> Tuple[Lane, Vehicle]:
    lane = network.get_incoming_approach(direction).get_lanes()[0]
    vehicle = Vehicle(
        name,
        length=length,
        width=2.0,
        desired_speed=5.0,
        route=[lane],
        start_position=lane.length - short_of_line,
        initial_speed=5.0,
    )
    lane.add_vehicle(vehicle)
    return lane, vehicle


def _circulating_vehicle_near_north_entry() -> Vehicle:
    # The same placement test_roundabout_yielding uses to force a yield.
    conn_lane = Lane("conn_circ", 1.75, 16.0, 10.0, 16.0)
    return Vehicle(
        "circ_1",
        length=4.5,
        width=2.0,
        desired_speed=8.0,
        route=[conn_lane],
        start_position=0.0,
        initial_speed=8.0,
    )


# --- the decision contract -------------------------------------------------


def test_an_open_decision_has_no_reason_by_default() -> None:
    assert GateDecision(open=True) == OPEN
    assert OPEN.open is True
    assert OPEN.reason is None


@pytest.mark.parametrize(
    "reason", ["red", "yellow", "ring_spillback_hold", "queue_cap"]
)
def test_a_closed_decision_keeps_each_adr_reason(reason: Any) -> None:
    decision = GateDecision(open=False, reason=reason)
    assert decision.open is False
    assert decision.reason == reason


def test_the_decision_is_immutable_with_exactly_two_fields() -> None:
    assert [f.name for f in dataclasses.fields(GateDecision)] == ["open", "reason"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        OPEN.open = False  # type: ignore[misc]


def test_always_open_permits_every_entry_with_the_default_reason() -> None:
    controller, network = _roundabout()
    gate = AlwaysOpen()
    for direction in Direction:
        lane = network.get_incoming_approach(direction).get_lanes()[0]
        decision = gate.allows(direction, lane, 123.4)
        assert decision.open is True
        assert decision.reason is None


def test_always_open_is_stateless_and_returns_the_shared_decision() -> None:
    controller, network = _roundabout()
    lane = network.get_incoming_approach(Direction.NORTH).get_lanes()[0]
    gate = AlwaysOpen()
    assert gate.allows(Direction.NORTH, lane, 0.0) is OPEN
    assert gate.allows(Direction.SOUTH, lane, 99.0) is OPEN
    assert vars(gate) == {}


def test_a_plain_class_with_allows_satisfies_the_protocol() -> None:
    gate: EntryGate = _Gate()
    controller, _ = _roundabout(gate)
    assert controller.entry_gate is gate


# --- the default gate ------------------------------------------------------


def test_the_roundabout_defaults_to_the_always_open_gate() -> None:
    controller, _ = _roundabout()
    assert isinstance(controller.entry_gate, AlwaysOpen)


def test_a_falsy_but_supplied_gate_is_still_used() -> None:
    class _Falsy(_Gate):
        def __bool__(self) -> bool:
            return False

    gate = _Falsy(closed=(Direction.NORTH,))
    controller, network = _roundabout(gate)
    lane, vehicle = _head(network, Direction.NORTH, "v")
    controller.update(0.1, [vehicle])
    assert controller.entry_gate is gate
    assert lane.virtual_obstacle is not None


def test_the_default_gate_leaves_a_clear_entry_open() -> None:
    controller, network = _roundabout()
    lane, vehicle = _head(network, Direction.NORTH, "v")
    controller.update(0.1, [vehicle])
    assert lane.virtual_obstacle is None


# --- a closed gate ---------------------------------------------------------


def test_a_closed_gate_holds_the_head_at_the_give_way_line() -> None:
    gate = _Gate(closed=(Direction.NORTH,))
    controller, network = _roundabout(gate)
    lane, vehicle = _head(network, Direction.NORTH, "v")
    controller.update(0.1, [vehicle])
    assert lane.virtual_obstacle is not None
    assert lane.virtual_obstacle.position == lane.length


def test_a_closed_gate_holds_only_its_own_approach() -> None:
    gate = _Gate(closed=(Direction.NORTH,))
    controller, network = _roundabout(gate)
    north_lane, north = _head(network, Direction.NORTH, "n")
    south_lane, south = _head(network, Direction.SOUTH, "s")
    controller.update(0.1, [north, south])
    assert north_lane.virtual_obstacle is not None
    assert south_lane.virtual_obstacle is None


def test_reopening_the_gate_releases_the_head() -> None:
    gate = _Gate(closed=(Direction.NORTH,))
    controller, network = _roundabout(gate)
    lane, vehicle = _head(network, Direction.NORTH, "v")
    controller.update(0.1, [vehicle])
    assert lane.virtual_obstacle is not None
    gate.closed = ()
    controller.update(0.1, [vehicle])
    assert lane.virtual_obstacle is None


def test_the_gate_is_given_the_approach_the_lane_and_the_controller_clock() -> None:
    gate = _Gate()
    controller, network = _roundabout(gate)
    lane, vehicle = _head(network, Direction.EAST, "v")
    controller.update(0.1, [vehicle])
    controller.update(0.25, [vehicle])
    east_calls = [c for c in gate.calls if c[0] is Direction.EAST]
    assert [c[1] for c in east_calls] == [lane, lane]
    assert [c[2] for c in east_calls] == pytest.approx([0.1, 0.35])
    assert controller.time_in_current_state == pytest.approx(0.35)


def test_the_gate_is_consulted_once_per_entry_lane_per_tick() -> None:
    gate = _Gate()
    controller, network = _roundabout(gate)
    controller.update(0.1, [])
    assert sorted(c[0].value for c in gate.calls) == sorted(d.value for d in Direction)


# --- evaluation order and safety -------------------------------------------


def test_the_gate_is_not_consulted_when_the_yield_rules_already_hold_the_head() -> None:
    gate = _Gate()
    controller, network = _roundabout(gate)
    lane, vehicle = _head(network, Direction.NORTH, "v")
    circulating = _circulating_vehicle_near_north_entry()
    controller.update(0.1, [vehicle, circulating])
    # The roundabout's own gap rule yielded, so the gate never got a say.
    assert lane.virtual_obstacle is not None
    assert all(call[0] is not Direction.NORTH for call in gate.calls)


def test_a_closed_gate_cannot_lift_an_existing_yield() -> None:
    # Open gate and closed gate give the same hold when the ring is not clear;
    # the gate only ever adds a yield.
    for closed in ((), (Direction.NORTH,)):
        controller, network = _roundabout(_Gate(closed=closed))
        lane, vehicle = _head(network, Direction.NORTH, "v")
        circulating = _circulating_vehicle_near_north_entry()
        controller.update(0.1, [vehicle, circulating])
        assert lane.virtual_obstacle is not None


def test_a_closed_gate_does_not_bypass_follow_up_spacing() -> None:
    # followUpTime is one of the existing rules that runs before the gate.
    gate = _Gate()
    controller, network = _roundabout(gate)
    lane, first = _head(network, Direction.NORTH, "a")
    controller.update(0.1, [first])
    lane.remove_vehicle(first)
    _, second = _head(network, Direction.NORTH, "b")
    controller.update(0.1, [second])
    controller.update(0.1, [second])  # departure now detected: spacing holds
    assert lane.virtual_obstacle is not None
    north_calls_before = len([c for c in gate.calls if c[0] is Direction.NORTH])
    controller.update(0.1, [second])
    assert len([c for c in gate.calls if c[0] is Direction.NORTH]) == north_calls_before


def test_a_committed_long_vehicle_is_not_stranded_by_a_closing_gate() -> None:
    gate = _Gate()
    controller, network = _roundabout(gate)
    lane, bus = _head(network, Direction.NORTH, "bus", length=12.0)
    controller.update(0.1, [bus])  # open, front already across the line
    controller.update(0.1, [bus])  # the commitment is latched
    assert lane.virtual_obstacle is None
    assert controller._committed_entry[lane.lane_id] == "bus"

    gate.closed = (Direction.NORTH,)
    for _ in range(5):
        controller.update(0.1, [bus])
        assert lane.virtual_obstacle is None


def test_a_closed_gate_does_hold_a_long_vehicle_that_is_not_yet_committed() -> None:
    gate = _Gate(closed=(Direction.NORTH,))
    controller, network = _roundabout(gate)
    # Centre 8 m short of the line: a 12 m bus's front is still 2 m short.
    lane, bus = _head(network, Direction.NORTH, "bus", length=12.0, short_of_line=8.0)
    controller.update(0.1, [bus])
    controller.update(0.1, [bus])
    assert lane.virtual_obstacle is not None
    assert lane.lane_id not in controller._committed_entry


def test_the_commitment_ends_when_the_long_vehicle_leaves_and_the_gate_applies_again() -> (
    None
):
    gate = _Gate()
    controller, network = _roundabout(gate)
    lane, bus = _head(network, Direction.NORTH, "bus", length=12.0)
    controller.update(0.1, [bus])
    controller.update(0.1, [bus])
    assert lane.lane_id in controller._committed_entry

    gate.closed = (Direction.NORTH,)
    lane.remove_vehicle(bus)
    _, car = _head(network, Direction.NORTH, "car")
    controller.update(0.1, [car])
    assert lane.lane_id not in controller._committed_entry
    # A later controller tick, with the follow-up spacing long past.
    controller.update(5.0, [car])
    assert lane.virtual_obstacle is not None


@pytest.mark.parametrize(
    "rule",
    [
        "_mouth_shared_with_long_vehicle",
        "_yields_to_earlier_neighbour",
        "_merging_entry_must_wait",
        "_keep_clear",
    ],
)
def test_the_gate_is_not_consulted_when_a_later_yield_rule_holds_the_head(
    rule: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each rule after gap acceptance and follow-up runs before the gate.

    The rule is forced to yield and its call is counted, so the test fails if
    the rule is never reached as well as if the gate is moved ahead of it.
    """
    gate = _Gate()
    controller, network = _roundabout(gate)
    reached: List[str] = []

    def _yields(*args: Any, **kwargs: Any) -> bool:
        reached.append(rule)
        return True

    monkeypatch.setattr(controller, rule, _yields)
    lane, vehicle = _head(network, Direction.NORTH, "v")
    controller.update(0.1, [vehicle])

    assert reached, f"{rule} was never evaluated for the north entry"
    assert lane.virtual_obstacle is not None
    assert all(call[0] is not Direction.NORTH for call in gate.calls)
