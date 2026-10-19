"""The entry-gate seam of the roundabout (ADR-014 section 5).

A gate answers one question for the head vehicle of an entry lane: may it
proceed to the give-way line this tick? ``RoundaboutController`` asks only
after its own rules (gap acceptance, follow-up time, long-vehicle mouth,
earlier neighbour, merging entry, keep-clear) have said "go" and before the
committed-long-vehicle override, so a closed gate can only *add* a yield:
it removes entry opportunities and never grants one. The default gate,
``AlwaysOpen``, is stateless and draws no random numbers, which is what keeps
the conventional roundabout bit-identical to its pre-seam behaviour.

This module deliberately knows nothing about signals; the metering gate that
will implement the protocol lives elsewhere.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Protocol

from src.core.enums import Direction
from src.roads.lane import Lane

GateReason = Literal["red", "yellow", "ring_spillback_hold", "queue_cap"]
"""Why a gate is closed (strategy 13.3; sprint plan 3.3). An open decision has none."""


@dataclass(frozen=True)
class GateDecision:
    """Whether the head of an entry lane may proceed, and why not if it may not."""

    open: bool
    reason: Optional[GateReason] = None


OPEN = GateDecision(open=True)
"""The shared open decision returned by ``AlwaysOpen``."""


class EntryGate(Protocol):
    """Consulted once per entry lane per tick, after the roundabout's own rules."""

    def allows(self, approach: Direction, lane: Lane, now: float) -> GateDecision: ...


class AlwaysOpen:
    """The default gate: every entry is open, so the roundabout decides alone."""

    def allows(self, approach: Direction, lane: Lane, now: float) -> GateDecision:
        return OPEN
