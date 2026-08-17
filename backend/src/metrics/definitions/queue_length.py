from typing import Dict, List

from src.vehicles.vehicle import Vehicle


def get_current_queue_lengths(
    active_vehicles: List[Vehicle], wait_speed_threshold: float = 0.5
) -> Dict[str, int]:
    """Returns the instantaneous queue lengths per approach direction."""
    queues = {"north": 0, "south": 0, "east": 0, "west": 0}
    mapping = {"n": "north", "s": "south", "e": "east", "w": "west"}

    for v in active_vehicles:
        if v.lane is None:
            continue

        lane_id = v.lane.lane_id.lower()
        # Only count incoming lanes
        if "_in_" in lane_id:
            dir_char = lane_id.split("_")[0]
            direction = mapping.get(dir_char)
            if direction in queues and v.speed < wait_speed_threshold:
                queues[direction] += 1

    return queues
