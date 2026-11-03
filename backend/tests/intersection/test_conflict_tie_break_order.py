"""Equal-priority conflict ties go to the lower vehicle id *as text* (F-42).

``ConflictManager`` breaks a tie between two equal-priority movements with
``other_id < vehicle_id``. Spawner ids are ``veh_{n}`` without padding, so
``veh_10`` wins over ``veh_9``: text order, not spawn order. The order is
total (exactly one of a pair yields), so it cannot deadlock, and it is part of
every signal run's result (golden fingerprints, leader-trace pins). This pins
it so a change to it is deliberate: switching to spawn order is a behaviour
change for signal runs and needs approval.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.core.enums import TurnIntent
from src.intersection.conflict_manager import ConflictManager
from src.roads.lane import Lane


def _manager() -> ConflictManager:
    cm = ConflictManager()
    cm.register_connection_lane(
        Lane("conn_a", start_x=-20.0, start_y=0.0, end_x=20.0, end_y=0.0)
    )
    cm.register_connection_lane(
        Lane("conn_b", start_x=0.0, start_y=-20.0, end_x=0.0, end_y=20.0)
    )
    cm.compute_conflict_points()
    return cm


def _blocked(cm: ConflictManager, me: str, other: str) -> bool:
    """Whether *me* on conn_a yields to *other* on conn_b, both going
    straight and equally close to the crossing."""
    others: List[Dict[str, Any]] = [
        {
            "vehicle_id": other,
            "turn_intent": TurnIntent.STRAIGHT,
            "connection_lane_id": "conn_b",
            "position_on_lane": 10.0,
        }
    ]
    dist = cm.get_conflict_distance(
        me, TurnIntent.STRAIGHT, "conn_a", 10.0, 0.0, all_vehicles_info=others
    )
    cm.reset_reservations()
    return dist < float("inf")


def test_ties_go_to_the_lower_id_in_text_order() -> None:
    cm = _manager()
    # veh_10 sorts before veh_9 as text, so veh_9 yields and veh_10 does not.
    assert _blocked(cm, "veh_9", "veh_10")
    assert not _blocked(cm, "veh_10", "veh_9")
    # Where text and number order agree, the earlier vehicle wins.
    assert _blocked(cm, "veh_3", "veh_2")
    assert not _blocked(cm, "veh_2", "veh_3")
