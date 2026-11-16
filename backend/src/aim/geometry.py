"""Conflict-tile geometry of a single 4-way intersection (F20, package 3B).

Discretisation (documented, deliberately conservative):

* The intersection box is a ``box`` x ``box`` square (default 14 m) cut into a
  ``n`` x ``n`` grid of square conflict tiles (default 2 m, so 7 x 7 = 49).
* Every approach has one inbound lane whose centre line is ``lane_offset``
  (1.75 m) right of the box centre (right-hand traffic). Approaches are
  numbered 0..3 for traffic coming from the south, west, north and east
  (heading north, east, south, west).
* A movement is a centre-line path through the box: ``straight``, ``right``
  (quarter circle, radius ``box/2 - offset``) or ``left`` (quarter circle,
  radius ``box/2 + offset``). Paths are sampled every ``ds`` metres (0.25 m)
  of arc length ``s`` (``s = 0`` is the box entry line).
* A vehicle footprint is a capsule: the union of discs of radius ``radius``
  (half width plus any safety margin) centred on the path samples between its
  rear and its front. A tile is touched by a sample when the disc reaches the
  tile rectangle.
* For every tile a movement touches, ``windows`` holds ``(tile, s_enter,
  s_exit)``: the first and last arc length at which the footprint disc touches
  the tile, widened by one sample step outwards. A vehicle of length ``L``
  whose front is at ``s`` therefore occupies the tile while
  ``s >= s_enter`` and ``s - L <= s_exit``. Those windows are what the
  reservation manager books; the independent checker instead unions the
  per-sample tile sets (``tiles_between``), a different computation.
"""

import math
from typing import Dict, FrozenSet, List, Set, Tuple

APPROACH_NAMES = ("south", "west", "north", "east")
MOVEMENTS = ("straight", "left", "right")

Window = Tuple[int, float, float]  # (tile, s_enter, s_exit)


class Geometry:
    def __init__(
        self,
        box: float = 14.0,
        tile: float = 2.0,
        lane_offset: float = 1.75,
        radius: float = 1.0,
        ds: float = 0.25,
    ) -> None:
        if box <= 0 or tile <= 0 or ds <= 0 or radius <= 0:
            raise ValueError("box, tile, ds and radius must be positive")
        if not 0 < lane_offset < box / 2:
            raise ValueError("lane_offset must lie inside the half box")
        self.box, self.tile, self.lane_offset = box, tile, lane_offset
        self.radius, self.ds = radius, ds
        self.n = int(round(box / tile))
        self.samples: Dict[Tuple[int, str], List[FrozenSet[int]]] = {}
        self.windows: Dict[Tuple[int, str], List[Window]] = {}
        self.length: Dict[Tuple[int, str], float] = {}
        for approach in range(4):
            for movement in MOVEMENTS:
                self._build(approach, movement)

    @property
    def tile_count(self) -> int:
        return self.n * self.n

    def _canonical(self, movement: str) -> Tuple[float, List[Tuple[float, float]]]:
        """Centre-line samples for the approach from the south (heading +y)."""
        c, off = self.box / 2, self.lane_offset
        if movement == "straight":
            length = self.box
        else:
            radius = c - off if movement == "right" else c + off
            length = radius * math.pi / 2
        count = int(math.ceil(length / self.ds)) + 1
        points: List[Tuple[float, float]] = []
        for i in range(count):
            s = min(i * self.ds, length)
            if movement == "straight":
                points.append((c + off, s))
            elif movement == "right":
                ang = s / radius
                points.append(
                    (self.box - radius * math.cos(ang), radius * math.sin(ang))
                )
            else:
                ang = s / radius
                points.append((radius * math.cos(ang), radius * math.sin(ang)))
        return length, points

    def _rotate(self, point: Tuple[float, float], times: int) -> Tuple[float, float]:
        c = self.box / 2
        dx, dy = point[0] - c, point[1] - c
        for _ in range(times):  # clockwise quarter turn
            dx, dy = dy, -dx
        return c + dx, c + dy

    def _touched(self, px: float, py: float) -> FrozenSet[int]:
        r, t, n = self.radius, self.tile, self.n
        out = set()
        for j in range(max(0, int((py - r) // t)), min(n - 1, int((py + r) // t)) + 1):
            for i in range(
                max(0, int((px - r) // t)), min(n - 1, int((px + r) // t)) + 1
            ):
                dx = max(i * t - px, 0.0, px - (i + 1) * t)
                dy = max(j * t - py, 0.0, py - (j + 1) * t)
                if dx * dx + dy * dy <= r * r:
                    out.add(j * n + i)
        return frozenset(out)

    def _build(self, approach: int, movement: str) -> None:
        length, points = self._canonical(movement)
        sets: List[FrozenSet[int]] = []
        first: Dict[int, float] = {}
        last: Dict[int, float] = {}
        for i, p in enumerate(points):
            px, py = self._rotate(p, approach)
            tiles = self._touched(px, py)
            sets.append(tiles)
            s = min(i * self.ds, length)
            for tile in tiles:
                first.setdefault(tile, s)
                last[tile] = s
        key = (approach, movement)
        self.samples[key] = sets
        self.length[key] = length
        self.windows[key] = [
            (tile, max(0.0, first[tile] - self.ds), last[tile] + self.ds)
            for tile in sorted(first)
        ]

    def tiles_between(
        self, approach: int, movement: str, s_rear: float, s_front: float
    ) -> FrozenSet[int]:
        """Tiles touched by a footprint whose rear is at ``s_rear`` and front at
        ``s_front`` (arc length along the movement). Empty outside the box."""
        if s_front < 0:
            return frozenset()
        sets = self.samples[(approach, movement)]
        lo = max(0, int(math.floor(s_rear / self.ds)))
        hi = min(len(sets) - 1, int(math.ceil(s_front / self.ds)))
        out: Set[int] = set()
        for i in range(lo, hi + 1):
            out |= sets[i]
        return frozenset(out)


_CACHE: Dict[Tuple[float, ...], Geometry] = {}


def build_geometry(
    box: float = 14.0,
    tile: float = 2.0,
    lane_offset: float = 1.75,
    radius: float = 1.0,
    ds: float = 0.25,
) -> Geometry:
    """Cached geometry (it is immutable after construction)."""
    key = (box, tile, lane_offset, radius, ds)
    if key not in _CACHE:
        _CACHE[key] = Geometry(box, tile, lane_offset, radius, ds)
    return _CACHE[key]
