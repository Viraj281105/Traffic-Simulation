"""Independent safety checker (gate G-AIM).

Replays the full per-step trajectory log and verifies, without using any
reservation data, that

* no two vehicle footprints touch the same tile at the same time step
  (footprints use the physical radius, tile sets are unions of per-sample
  tile sets, not the reservation windows),
* vehicles on the same approach lane never overlap longitudinally,
* no vehicle is left in the system (no deadlock),
* the minimum time gap between consecutive occupants of any tile is at least
  ``min_gap_required`` seconds,
* speed and acceleration stay within bounds.

The result is the ``safety`` object reported with every run.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from src.aim.geometry import Geometry
from src.aim.trajectory import KinParams


@dataclass
class Track:
    """Per-step log of one vehicle: sample ``i`` is at time ``t0 + i * dt``."""

    vid: int
    approach: int
    movement: str
    length: float
    t0: float
    xs: List[float] = field(default_factory=list)
    vs: List[float] = field(default_factory=list)
    exited: bool = False


@dataclass(frozen=True)
class SafetyReport:
    conflicts: int
    minGapSeconds: Optional[float]
    deadlock: bool
    maxAccel: float
    passed: bool
    maxDecel: float = 0.0
    maxSpeed: float = 0.0
    laneOverlaps: int = 0
    minLaneGapMetres: Optional[float] = None
    unfinished: int = 0
    vehicles: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def validate(
    tracks: List[Track],
    geometry: Geometry,
    dt: float,
    params: KinParams = KinParams(),
    *,
    unspawned: int = 0,
    min_gap_required: float = 0.2,
    tol: float = 1e-6,
) -> SafetyReport:
    occupied: Dict[Tuple[int, int], int] = {}  # (step, tile) -> vid
    pairs: Set[Tuple[int, int]] = set()
    runs: Dict[int, Dict[int, List[int]]] = {}  # tile -> vid -> [first, last]
    max_acc = max_dec = max_speed = 0.0
    for tr in tracks:
        k0 = int(round(tr.t0 / dt))
        for i, (x, v) in enumerate(zip(tr.xs, tr.vs)):
            max_speed = max(max_speed, v)
            if i:
                a = (v - tr.vs[i - 1]) / dt
                max_acc, max_dec = max(max_acc, a), max(max_dec, -a)
            if x < 0 or x - tr.length > geometry.length[(tr.approach, tr.movement)]:
                continue
            step = k0 + i
            for tile in geometry.tiles_between(
                tr.approach, tr.movement, x - tr.length, x
            ):
                other = occupied.setdefault((step, tile), tr.vid)
                if other != tr.vid:
                    pairs.add((min(other, tr.vid), max(other, tr.vid)))
                span = runs.setdefault(tile, {}).setdefault(tr.vid, [step, step])
                span[1] = step
    min_gap: Optional[float] = None
    for per_tile in runs.values():
        spans = sorted(per_tile.values())
        for prev, nxt in zip(spans, spans[1:]):
            if nxt[0] > prev[1]:
                gap = (nxt[0] - prev[1] - 1) * dt
                min_gap = gap if min_gap is None else min(min_gap, gap)
    lane_pairs: Set[Tuple[int, int]] = set()
    lane_gap: Optional[float] = None
    by_lane: Dict[int, List[Track]] = {}
    for tr in tracks:
        by_lane.setdefault(tr.approach, []).append(tr)
    for lane in by_lane.values():
        lane.sort(key=lambda tr: tr.t0)
        for idx, fol in enumerate(lane):
            for lead in lane[max(0, idx - 1) : idx]:  # nearest vehicle ahead
                lk = int(round(lead.t0 / dt))
                fk = int(round(fol.t0 / dt))
                for i, x in enumerate(fol.xs):
                    j = fk + i - lk
                    if j < 0 or j >= len(lead.xs) or x >= 0:
                        continue
                    gap_m = lead.xs[j] - lead.length - x
                    lane_gap = gap_m if lane_gap is None else min(lane_gap, gap_m)
                    if gap_m < -tol:
                        lane_pairs.add((lead.vid, fol.vid))
    unfinished = sum(1 for tr in tracks if not tr.exited) + unspawned
    bounds_ok = (
        max_acc <= params.accel + tol
        and max_dec <= params.decel + tol
        and max_speed <= params.vmax + tol
        and all(v >= -tol for tr in tracks for v in tr.vs)
    )
    gap_ok = min_gap is None or min_gap >= min_gap_required
    conflicts = len(pairs) + len(lane_pairs)
    return SafetyReport(
        conflicts=conflicts,
        minGapSeconds=min_gap,
        deadlock=unfinished > 0,
        maxAccel=max_acc,
        passed=conflicts == 0 and unfinished == 0 and bounds_ok and gap_ok,
        maxDecel=max_dec,
        maxSpeed=max_speed,
        laneOverlaps=len(lane_pairs),
        minLaneGapMetres=lane_gap,
        unfinished=unfinished,
        vehicles=len(tracks),
    )
