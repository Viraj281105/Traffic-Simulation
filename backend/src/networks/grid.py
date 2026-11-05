"""Grid scenarios (F5): a rows x cols lattice of signalised junctions with a
gate on every open end, plus the 12-junction (3 x 4) network used for the
scale benchmark. Roads are two-way (two links)."""

import math
from typing import Any, Dict, List, Optional, Tuple

from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.network_sim import Flow

MAX_GRID_SIDE = 12
_METRES_PER_DEG_LAT = 111_320.0


def junction_id(r: int, c: int) -> str:
    return f"J{r}{c}" if r < 10 and c < 10 else f"J{r}_{c}"


def build_grid(
    rows: int = 3,
    cols: int = 3,
    spacing: float = 300.0,
    *,
    speed: float = 13.89,
    arterial_rows: Tuple[int, ...] = (),
    arterial_cols: Tuple[int, ...] = (),
    lanes: int = 1,
    arterial_lanes: int = 2,
    gate_offset: float = 250.0,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    name: Optional[str] = None,
) -> RoadGraph:
    """``rows x cols`` signalised junctions ``J<r><c>`` (row 0 is the north row,
    column 0 the west column) joined by two-way links ``A>B``, with a gate at
    every open end: ``GW<r>``/``GE<r>`` on the west/east of each row and
    ``GN<c>``/``GS<c>`` on the north/south of each column. Rows or columns
    listed in ``arterial_rows``/``arterial_cols`` get ``arterial_lanes``.
    When ``origin_lat``/``origin_lon`` are given, every node also gets lat/lon
    (flat-earth approximation around that origin; local x is east, y north)."""
    if not (1 <= rows <= MAX_GRID_SIDE and 1 <= cols <= MAX_GRID_SIDE):
        raise ValueError(f"rows and cols must be between 1 and {MAX_GRID_SIDE}")
    if spacing < 20.0:
        raise ValueError("spacing must be at least 20 m")
    pos: Dict[str, Tuple[float, float]] = {}
    kind: Dict[str, str] = {}
    for r in range(rows):
        for c in range(cols):
            j = junction_id(r, c)
            pos[j] = (c * spacing, -r * spacing)
            kind[j] = "junction"
    for r in range(rows):
        pos[f"GW{r}"] = (-gate_offset, -r * spacing)
        pos[f"GE{r}"] = ((cols - 1) * spacing + gate_offset, -r * spacing)
    for c in range(cols):
        pos[f"GN{c}"] = (c * spacing, gate_offset)
        pos[f"GS{c}"] = (c * spacing, -(rows - 1) * spacing - gate_offset)
    for g in pos:
        kind.setdefault(g, "gate")

    cos_lat = math.cos(math.radians(origin_lat)) if origin_lat is not None else 1.0
    nodes: List[GraphNode] = []
    for nid in sorted(pos):
        x, y = pos[nid]
        extra = {}
        if origin_lat is not None and origin_lon is not None:
            extra = {
                "lat": round(origin_lat + y / _METRES_PER_DEG_LAT, 7),
                "lon": round(origin_lon + x / (_METRES_PER_DEG_LAT * cos_lat), 7),
            }
        nodes.append(
            GraphNode(
                id=nid,
                x=x,
                y=y,
                kind=kind[nid],  # type: ignore[arg-type]
                control="signal" if kind[nid] == "junction" else None,
                **extra,
            )
        )

    def road(a: str, b: str, arterial: bool) -> List[GraphLink]:
        (ax, ay), (bx, by) = pos[a], pos[b]
        length = abs(bx - ax) + abs(by - ay)
        n_lanes = arterial_lanes if arterial else lanes
        return [
            GraphLink(
                id=f"{p}>{q}",
                **{"from": p, "to": q},
                length=length,
                lanes=n_lanes,
                speed=speed,
            )
            for p, q in ((a, b), (b, a))
        ]

    links: List[GraphLink] = []
    for r in range(rows):
        art = r in arterial_rows
        links += road(f"GW{r}", junction_id(r, 0), art)
        for c in range(cols - 1):
            links += road(junction_id(r, c), junction_id(r, c + 1), art)
        links += road(junction_id(r, cols - 1), f"GE{r}", art)
    for c in range(cols):
        art = c in arterial_cols
        links += road(f"GN{c}", junction_id(0, c), art)
        for r in range(rows - 1):
            links += road(junction_id(r, c), junction_id(r + 1, c), art)
        links += road(junction_id(rows - 1, c), f"GS{c}", art)
    return RoadGraph(
        name=name or f"{rows}x{cols} grid",
        source="grid",
        nodes=nodes,
        links=links,
    )


def grid_flows(
    rows: int = 3,
    cols: int = 3,
    vehicles_per_hour: float = 300.0,
    cross_share: float = 0.5,
) -> List[Flow]:
    """Default demand for :func:`build_grid`: a through flow from every gate to
    the opposite gate (``vehicles_per_hour`` each way along rows, scaled by
    ``cross_share`` along columns), plus one corner-to-corner flow each way."""
    flows: List[Flow] = []
    for r in range(rows):
        flows.append(Flow(f"GW{r}", f"GE{r}", vehicles_per_hour))
        flows.append(Flow(f"GE{r}", f"GW{r}", vehicles_per_hour))
    for c in range(cols):
        flows.append(Flow(f"GN{c}", f"GS{c}", vehicles_per_hour * cross_share))
        flows.append(Flow(f"GS{c}", f"GN{c}", vehicles_per_hour * cross_share))
    flows.append(Flow("GW0", f"GS{cols - 1}", vehicles_per_hour * 0.25))
    flows.append(Flow(f"GE{rows - 1}", "GN0", vehicles_per_hour * 0.25))
    return flows


def build_three_by_three(spacing: float = 300.0, **kw: Any) -> RoadGraph:
    """The 3 x 3 grid of the W41 gate: middle row and column are arterials."""
    kw.setdefault("arterial_rows", (1,))
    kw.setdefault("arterial_cols", (1,))
    return build_grid(3, 3, spacing, name="3x3 grid", **kw)


def build_twelve_junction_network(
    spacing: float = 300.0,
    origin_lat: Optional[float] = 51.5074,
    origin_lon: Optional[float] = -0.1278,
) -> RoadGraph:
    """A 3 x 4 network of 12 signalised junctions: middle row is a two-lane
    arterial and the second column a two-lane avenue, anchored to a lat/lon
    so a map viewer can place it."""
    return build_grid(
        3,
        4,
        spacing,
        arterial_rows=(1,),
        arterial_cols=(1,),
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        name="12-junction network",
    )


def twelve_junction_flows(vehicles_per_hour: float = 300.0) -> List[Flow]:
    return grid_flows(3, 4, vehicles_per_hour)
