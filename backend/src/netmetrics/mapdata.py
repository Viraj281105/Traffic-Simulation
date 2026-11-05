"""Map data for a multi-junction viewer (F5, W45): nodes and links with local
x/y metres (x east, y north) and, when known, lat/lon."""

import math
from typing import Any, Dict, List, Optional

from src.networks.graph import RoadGraph

MAP_FORMAT = "urbanflow-map-data"
_M_PER_DEG_LAT = 111_320.0


def _lonlat(x: float, y: float, lat0: float, lon0: float) -> Dict[str, float]:
    return {
        "lat": round(lat0 + y / _M_PER_DEG_LAT, 7),
        "lon": round(lon0 + x / (_M_PER_DEG_LAT * math.cos(math.radians(lat0))), 7),
    }


def map_data(
    graph: RoadGraph,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    link_values: Optional[Dict[str, float]] = None,
    value_label: str = "value",
) -> Dict[str, Any]:
    """Nodes and links for a viewer. Nodes that carry lat/lon keep them; others
    get them from ``origin_lat``/``origin_lon`` (local (0, 0)) when given, else
    ``lat``/``lon`` are omitted and ``hasGeo`` is false. ``link_values`` (for
    example occupancy ratio per link) is attached to each link as ``value``.
    Output is sorted by id, so equal graphs give equal output."""
    origin = origin_lat is not None and origin_lon is not None
    nodes: List[Dict[str, Any]] = []
    geo: Dict[str, Dict[str, float]] = {}
    for n in sorted(graph.nodes, key=lambda n: n.id):
        pos: Dict[str, float] = {}
        if n.lat is not None and n.lon is not None:
            pos = {"lat": n.lat, "lon": n.lon}
        elif origin:
            pos = _lonlat(n.x, n.y, origin_lat, origin_lon)  # type: ignore[arg-type]
        geo[n.id] = pos
        nodes.append(
            {
                "id": n.id,
                "kind": n.kind,
                "signal": n.control == "signal",
                "x": n.x,
                "y": n.y,
                **pos,
            }
        )
    nm = graph.node_map()
    links = []
    for k in sorted(graph.links, key=lambda k: k.id):
        a, b = nm.get(k.from_), nm.get(k.to)
        if a is None or b is None:
            continue
        item: Dict[str, Any] = {
            "id": k.id,
            "from": k.from_,
            "to": k.to,
            "name": k.name,
            "length": k.length,
            "lanes": k.lanes,
            "speed": k.speed,
            "path": [[a.x, a.y], [b.x, b.y]],
            "bearingDegrees": round(
                (math.degrees(math.atan2(b.x - a.x, b.y - a.y)) + 360.0) % 360.0, 1
            ),
        }
        if geo[a.id] and geo[b.id]:
            item["pathLatLon"] = [
                [geo[a.id]["lat"], geo[a.id]["lon"]],
                [geo[b.id]["lat"], geo[b.id]["lon"]],
            ]
        if link_values is not None and k.id in link_values:
            item["value"] = link_values[k.id]
        links.append(item)
    xs = [n["x"] for n in nodes] or [0.0]
    ys = [n["y"] for n in nodes] or [0.0]
    has_geo = bool(nodes) and all("lat" in n for n in nodes)
    out: Dict[str, Any] = {
        "format": MAP_FORMAT,
        "version": 1,
        "name": graph.name,
        "hasGeo": has_geo,
        "boundsLocal": {
            "minX": min(xs),
            "maxX": max(xs),
            "minY": min(ys),
            "maxY": max(ys),
        },
        "nodes": nodes,
        "links": links,
    }
    if has_geo:
        lats, lons = [n["lat"] for n in nodes], [n["lon"] for n in nodes]
        out["boundsLatLon"] = {
            "south": min(lats),
            "north": max(lats),
            "west": min(lons),
            "east": max(lons),
        }
    if link_values is not None:
        out["valueLabel"] = value_label
    return out
