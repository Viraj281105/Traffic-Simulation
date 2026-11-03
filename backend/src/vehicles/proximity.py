"""Spatial index for find_leader's emergency proximity check (Layer 4).

Layer 4 compared every vehicle with every other vehicle on every tick, which
made it the largest single cost of a busy run (about half the engine time at
900 veh/h per arm on two lanes, checkpoint 11). It can only ever act on a
vehicle within

    _EMERGENCY_DIST + _LATERAL_MARGIN + (L_a + L_b + W_a + W_b) / 2

metres of the one it is checking (both of its branches test a distance of
at most that before anything else), so a uniform grid whose cells are at
least that wide finds every such vehicle in the 3 x 3 cells around it.

The pool updates vehicles one after another, each seeing the others as they
are at that moment, so the index is kept live: a vehicle is re-filed the
moment it moves (``move``). Candidates are returned in the order of the
active list, the order the full scan visits them, so ties resolve exactly as
before and find_leader's result is unchanged, bit for bit
(tests/vehicles/test_proximity_index.py, and the leader-trace pins).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from src.vehicles.router import _EMERGENCY_DIST, _LATERAL_MARGIN
from src.vehicles.vehicle import Vehicle

Cell = Tuple[int, int]

# Slack for floating-point rounding at cell boundaries.
_SLACK = 1.0


class ProximityGrid:
    """Live uniform grid over the active vehicles of one pool update."""

    def __init__(self, vehicles: Sequence[Vehicle]) -> None:
        self._order: Dict[int, int] = {id(v): i for i, v in enumerate(vehicles)}
        longest = max((v.length for v in vehicles), default=0.0)
        widest = max((v.width for v in vehicles), default=0.0)
        self.cell_size = _EMERGENCY_DIST + _LATERAL_MARGIN + longest + widest + _SLACK
        self._cells: Dict[Cell, List[Vehicle]] = {}
        self._where: Dict[int, Cell] = {}
        for v in vehicles:
            self.move(v)

    def _cell(self, v: Vehicle) -> Optional[Cell]:
        """The cell of ``v``'s position; None for a non-finite position.

        The full scan never acts on such a vehicle (every distance test with
        a NaN is false), so it is left out here too instead of failing.
        """
        x, y = v.coords
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        size = self.cell_size
        return (math.floor(x / size), math.floor(y / size))

    def move(self, v: Vehicle) -> None:
        """File ``v`` under its current position (or drop it once it has no
        lane: Layer 4 ignores such vehicles)."""
        key = id(v)
        old = self._where.get(key)
        new = self._cell(v) if v.lane is not None else None
        if old == new:
            return
        if old is not None:
            self._cells[old].remove(v)
            del self._where[key]
        if new is not None:
            self._cells.setdefault(new, []).append(v)
            self._where[key] = new

    def near(self, v: Vehicle) -> List[Vehicle]:
        """Every vehicle Layer 4 could act on for ``v`` (``v`` included), in
        active-list order."""
        cell = self._cell(v)
        if cell is None:
            return []
        cx, cy = cell
        found: List[Vehicle] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                found.extend(self._cells.get((cx + dx, cy + dy), ()))
        order = self._order
        found.sort(key=lambda o: order[id(o)])
        return found
