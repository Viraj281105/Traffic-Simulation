"""Stop-line presence detection on a signal's incoming lanes (V1.3).

One definition of "traffic at the stop line", shared by the adaptive signal
(which acts on it) and the signal-timing metrics (which only observe it, for
fixed-time and adaptive signals alike, so the two are measured the same way).

A lane's detector covers the last ``distance`` metres before its stop line. A
phase *releases* the incoming lanes whose signal head it shows green -- the
rule ``FixedTimeSignalController._apply_signals`` uses to lift a lane's
stop-line obstacle. Only incoming lanes are read, through each lane's own
vehicle list, so an observation costs one comparison per vehicle on an
approach, however many vehicles are elsewhere in the network.

Two counts are kept per green phase. *Presence* (any vehicle in the zone) is
demand: a vehicle standing at a red stop line is a call for its phase.
*Passage* (a vehicle in the zone moving at ``MOVING_SPEED`` or faster) is what
extends a green, as a passage detector does: a vehicle standing still in the
zone during green -- a left-turner yielding to oncoming traffic, or one held
by a blocked exit -- does not, so it cannot hold a green to its maximum on
its own. The minimum green covers a standing queue's start-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Tuple

from src.core.enums import Direction
from src.roads.lane import Lane

# A vehicle in the zone at this speed or faster counts as passing (m/s).
MOVING_SPEED = 1.0

if TYPE_CHECKING:
    from src.controllers.fixed_time_signal import FixedTimeSignalController


@dataclass(frozen=True)
class Observation:
    """What the detectors see at one instant, relative to the current phase.

    ``served``: vehicles detected on the lanes the current phase releases (0
    during clearance); ``passing``: those of them moving at ``MOVING_SPEED``
    or faster. ``calls``: for every other green phase, vehicles
    detected on lanes only that phase releases. ``per_direction``: vehicles
    detected on each approach's released lanes.
    """

    served: int
    passing: int
    calls: Dict[int, int]
    per_direction: Dict[str, int]


class StopLineDetection:
    def __init__(
        self, controller: "FixedTimeSignalController", distance: float
    ) -> None:
        self.controller = controller
        self.distance = float(distance)
        self.released: Dict[int, Tuple[Lane, ...]] = self._released_lanes()

    def _released_lanes(self) -> Dict[int, Tuple[Lane, ...]]:
        ctl = self.controller
        released: Dict[int, Tuple[Lane, ...]] = {}
        for i, phase in enumerate(ctl.phases):
            if phase.color != "green":
                continue
            lanes: List[Lane] = []
            for d in phase.directions:
                try:
                    lane_list = ctl.network.get_incoming_approach(d).get_lanes()
                except KeyError:
                    continue
                n = len(lane_list)
                for idx, lane in enumerate(lane_list):
                    heads = ctl._lane_turns(d, idx, n)
                    if any(t in phase.allowed_turns for t in heads):
                        lanes.append(lane)
            released[i] = tuple(lanes)
        return released

    def zone_count(self, lane: Lane) -> Tuple[int, int]:
        """Vehicles within ``distance`` of ``lane``'s stop line, and how many
        of them are moving (see ``MOVING_SPEED``).

        A vehicle midway through a lane change is registered on both lanes;
        it is counted once, on the lane it is moving into (``v.lane``).
        """
        start = lane.length - self.distance
        present = moving = 0
        for v in lane.get_vehicles():
            if v.lane is lane and v.position >= start:
                present += 1
                if v.speed >= MOVING_SPEED:
                    moving += 1
        return present, moving

    def observe(self, current_idx: int) -> Observation:
        counts: Dict[int, int] = {}
        moving: Dict[int, int] = {}
        per_dir = {d.value: 0 for d in Direction}
        for lanes in self.released.values():
            for lane in lanes:
                key = id(lane)
                if key not in counts:
                    counts[key], moving[key] = self.zone_count(lane)
                    if isinstance(lane.approach, Direction):
                        per_dir[lane.approach.value] += counts[key]
        current_lanes = self.released.get(current_idx, ())
        current_ids = {id(lane) for lane in current_lanes}
        served = sum(counts[id(lane)] for lane in current_lanes)
        passing = sum(moving[id(lane)] for lane in current_lanes)
        calls = {
            i: sum(counts[id(lane)] for lane in lanes if id(lane) not in current_ids)
            for i, lanes in self.released.items()
            if i != current_idx
        }
        return Observation(served, passing, calls, per_dir)
