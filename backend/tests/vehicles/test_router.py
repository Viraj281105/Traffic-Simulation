import pytest

from src.roads.lane import Lane
from src.vehicles.router import find_leader
from src.vehicles.vehicle import Vehicle


def test_find_leader_empty_lane() -> None:
    lane = Lane("w_in_0", -100.0, 0.0, 0.0, 0.0)
    v1 = Vehicle("veh_1", 4.5, 2.0, 10.0, [lane], start_position=5.0)
    lane._vehicles.append(v1)

    leader, gap = find_leader(v1)
    assert leader is None
    assert gap == float("inf")


def test_find_leader_physical_leader() -> None:
    lane = Lane("w_in_0", -100.0, 0.0, 0.0, 0.0)
    v1 = Vehicle("veh_1", 4.5, 2.0, 10.0, [lane], start_position=5.0)
    v2 = Vehicle("veh_2", 4.5, 2.0, 10.0, [lane], start_position=20.0)
    lane._vehicles.extend([v1, v2])

    leader, gap = find_leader(v1)
    assert leader == v2
    # gap = v2.pos - v2.length/2 - (v1.pos + v1.length/2) = 20 - 2.25 - 7.25 = 10.5
    assert pytest.approx(gap) == 10.5
