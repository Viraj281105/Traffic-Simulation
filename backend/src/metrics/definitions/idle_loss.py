from typing import Dict, List

from src.core.enums import Direction
from src.vehicles.vehicle import Vehicle


def calculate_idle_loss_tick(
    active_vehicles: List[Vehicle],
    signals_state: Dict[Direction, str],
    wait_speed_threshold: float = 0.5,
) -> bool:
    """Checks if capacity is wasted in the current tick.

    Returns True if an approach is stopped on RED with waiting vehicles, while
    all approaches currently on GREEN have zero vehicles.
    """
    # Categorize approaches into green and red
    green_approaches = set()
    red_approaches = set()

    for d, color in signals_state.items():
        if color == "green":
            green_approaches.add(d.value.lower())
        else:
            red_approaches.add(d.value.lower())

    if not green_approaches or not red_approaches:
        return False

    # Count vehicles on each approach
    green_veh_count = 0
    has_waiting_on_red = False
    mapping = {"n": "north", "s": "south", "e": "east", "w": "west"}

    for v in active_vehicles:
        if v.lane is None:
            continue
        lane_id = v.lane.lane_id.lower()
        if "_in_" in lane_id:
            dir_char = lane_id.split("_")[0]
            direction = mapping.get(dir_char)
            if direction in green_approaches:
                green_veh_count += 1
            elif direction in red_approaches:
                if v.speed < wait_speed_threshold:
                    has_waiting_on_red = True

    # Idle loss condition: red has waiting vehicles, but green is completely empty
    return has_waiting_on_red and green_veh_count == 0
