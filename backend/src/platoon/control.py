"""Per-vehicle finite-state machine and slot conflict resolution.

States
------
FREE      human-driven (IDM), not in a platoon.
LEADER    first vehicle of a platoon (IDM-driven); a platoon may have one member.
JOINING   in a platoon but still closing the gap: min(CACC, IDM) accel.
FOLLOWER  CACC at the platoon time gap using the predecessor's messages.
FALLBACK  messages stale (or gap below the minimum): IDM with a widened time
          gap, i.e. emergency fallback to human-style car following.

Transitions (event -> state); anything else raises ``ValueError``::

    FREE      --lead-->            LEADER     someone joined behind it
    FREE      --join-->            JOINING    accepted into a platoon slot
    LEADER    --merge-->           JOINING    its platoon merged behind another
    LEADER    --dissolve-->        FREE       platoon of one disbanded
    JOINING   --join_complete-->   FOLLOWER   gap and speed matched
    JOINING   --message_stale-->   FALLBACK
    JOINING   --unsafe_gap-->      FALLBACK
    JOINING   --split-->           LEADER
    FOLLOWER  --message_stale-->   FALLBACK   no fresh message for timeout_s
    FOLLOWER  --unsafe_gap-->      FALLBACK   gap below the minimum
    FOLLOWER  --split-->           LEADER     platoon split at this vehicle
    FALLBACK  --message_fresh-->   JOINING    messages fresh for recover_s
    FALLBACK  --split-->           LEADER

Slot conflicts: two vehicles asking for the same slot (same platoon, same
position), or one vehicle asking for several, are settled by one deterministic
rule: the request with the SMALLEST gap to the slot wins, ties go to the lowest
vehicle id, then the lowest slot. A vehicle is granted at most one slot. Losers
are denied and may ask again later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

FREE = "FREE"
LEADER = "LEADER"
JOINING = "JOINING"
FOLLOWER = "FOLLOWER"
FALLBACK = "FALLBACK"
STATES = (FREE, LEADER, JOINING, FOLLOWER, FALLBACK)

TRANSITIONS: Dict[Tuple[str, str], str] = {
    (FREE, "lead"): LEADER,
    (FREE, "join"): JOINING,
    (LEADER, "merge"): JOINING,
    (LEADER, "dissolve"): FREE,
    (JOINING, "join_complete"): FOLLOWER,
    (JOINING, "message_stale"): FALLBACK,
    (JOINING, "unsafe_gap"): FALLBACK,
    (JOINING, "split"): LEADER,
    (FOLLOWER, "message_stale"): FALLBACK,
    (FOLLOWER, "unsafe_gap"): FALLBACK,
    (FOLLOWER, "split"): LEADER,
    (FALLBACK, "message_fresh"): JOINING,
    (FALLBACK, "split"): LEADER,
}


def transition(state: str, event: str) -> str:
    """Next state, or ``ValueError`` for an event not allowed in ``state``."""
    try:
        return TRANSITIONS[(state, event)]
    except KeyError:
        raise ValueError(f"event {event!r} is not allowed in state {state}") from None


@dataclass(frozen=True)
class SlotRequest:
    vehicle_id: int
    slot: Tuple[int, int]  # (platoon id, position in that platoon)
    gap_m: float  # bumper gap from the requester to the slot's predecessor


def resolve_slot_conflicts(
    requests: Sequence[SlotRequest],
) -> Tuple[List[SlotRequest], List[SlotRequest]]:
    """Return (granted, denied); see the module docstring for the rule."""
    order = sorted(requests, key=lambda r: (r.gap_m, r.vehicle_id, r.slot))
    taken_slots = set()
    served = set()
    granted: List[SlotRequest] = []
    denied: List[SlotRequest] = []
    for r in order:
        if r.slot in taken_slots or r.vehicle_id in served:
            denied.append(r)
        else:
            taken_slots.add(r.slot)
            served.add(r.vehicle_id)
            granted.append(r)
    return granted, denied
