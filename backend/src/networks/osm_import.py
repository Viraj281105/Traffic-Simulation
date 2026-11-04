"""OpenStreetMap import: OSM XML or Overpass JSON text to a :class:`RoadGraph`.

Text in, graph out; no network calls. Ways are split at junctions (nodes
shared by several ways), at way ends and at traffic signals. Only drivable
``highway`` values are kept; everything else is counted and reported.
"""

import json
import math
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.import_common import ImportResult, parse_xml_safely

EARTH_RADIUS = 6371000.0

# highway -> (default speed m/s, default lanes per direction)
DRIVABLE: Dict[str, Tuple[float, int]] = {
    "motorway": (27.78, 2),
    "motorway_link": (16.67, 1),
    "trunk": (22.22, 2),
    "trunk_link": (13.89, 1),
    "primary": (16.67, 2),
    "primary_link": (11.11, 1),
    "secondary": (13.89, 1),
    "secondary_link": (11.11, 1),
    "tertiary": (13.89, 1),
    "tertiary_link": (11.11, 1),
    "unclassified": (11.11, 1),
    "residential": (8.33, 1),
    "living_street": (4.17, 1),
    "service": (5.56, 1),
}


def _haversine(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = (map(math.radians, a), map(math.radians, b))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS * math.asin(math.sqrt(h))


def _parse_speed(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    text = raw.strip().lower()
    try:
        if text.endswith("mph"):
            return float(text[:-3]) * 0.44704
        if text.endswith("km/h"):
            text = text[:-4]
        return float(text) / 3.6
    except ValueError:
        return None


def _read_xml(text: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    root = parse_xml_safely(text)
    if root.tag != "osm":
        raise ValueError(f"Not OSM XML: root element is <{root.tag}>, expected <osm>")
    nodes: Dict[str, Any] = {}
    ways: List[Dict[str, Any]] = []
    for el in root:
        tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
        if el.tag == "node" and el.get("lat") and el.get("lon"):
            nodes[el.get("id")] = (float(el.get("lat")), float(el.get("lon")), tags)
        elif el.tag == "way":
            ways.append(
                {"id": el.get("id"), "nds": [n.get("ref") for n in el.findall("nd")], "tags": tags}
            )
    return nodes, ways


def _read_json(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    nodes: Dict[str, Any] = {}
    ways: List[Dict[str, Any]] = []
    for el in data.get("elements", []):
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            nodes[str(el["id"])] = (el["lat"], el["lon"], el.get("tags") or {})
        elif el.get("type") == "way":
            ways.append(
                {
                    "id": str(el["id"]),
                    "nds": [str(n) for n in el.get("nodes", [])],
                    "tags": el.get("tags") or {},
                }
            )
    return nodes, ways


def import_osm(text: str) -> ImportResult:
    """Parse OSM XML or Overpass JSON (detected from the first character)."""
    result = ImportResult(format="osm")
    try:
        if text.lstrip().startswith("{"):
            data = json.loads(text)
            if not isinstance(data, dict) or "elements" not in data:
                raise ValueError("Not Overpass JSON: no 'elements' list")
            nodes, ways = _read_json(data)
        else:
            nodes, ways = _read_xml(text)
    except (ValueError, json.JSONDecodeError) as err:
        result.errors.append(str(err))
        return result

    skipped: Counter = Counter()
    kept: List[Dict[str, Any]] = []
    for way in ways:
        tags = way["tags"]
        hw = tags.get("highway")
        if hw not in DRIVABLE:
            skipped[hw if hw else "not a road"] += 1
        elif tags.get("access") in ("no", "private") or tags.get("motor_vehicle") == "no":
            skipped["no motor access"] += 1
        elif len(way["nds"]) < 2:
            skipped["fewer than two nodes"] += 1
        else:
            kept.append(way)

    usable: List[Dict[str, Any]] = []
    for way in kept:
        missing = [n for n in way["nds"] if n not in nodes]
        if missing:
            result.messages.append(
                f"Way {way['id']} skipped: it uses {len(missing)} node(s) that are not in the file"
            )
        else:
            usable.append(way)
    if not usable:
        result.errors.append("No drivable roads found in this file")
        if skipped:
            result.messages.append("Skipped: " + _summary(skipped))
        return result

    lat0 = sum(nodes[n][0] for w in usable for n in w["nds"]) / sum(len(w["nds"]) for w in usable)
    lon0 = sum(nodes[n][1] for w in usable for n in w["nds"]) / sum(len(w["nds"]) for w in usable)
    kx = EARTH_RADIUS * math.cos(math.radians(lat0)) * math.pi / 180.0
    ky = EARTH_RADIUS * math.pi / 180.0

    usage: Counter = Counter()
    for way in usable:
        for n in set(way["nds"]):
            usage[n] += 1
    graph_nodes: Dict[str, GraphNode] = {}
    links: List[GraphLink] = []

    def node(osm_id: str, gate: bool) -> None:
        if osm_id in graph_nodes:
            return
        lat, lon, tags = nodes[osm_id]
        graph_nodes[osm_id] = GraphNode(
            id=osm_id,
            x=round((lon - lon0) * kx, 3),
            y=round((lat - lat0) * ky, 3),
            kind="gate" if gate else "junction",
            control="signal" if tags.get("highway") == "traffic_signals" else None,
            lat=lat,
            lon=lon,
        )

    for way in usable:
        tags, nds = way["tags"], way["nds"]
        speed_d, lanes_d = DRIVABLE[tags["highway"]]
        speed = _parse_speed(tags.get("maxspeed")) or speed_d
        speed = min(max(speed, 1.0), 45.0)
        oneway = tags.get("oneway")
        forward, backward = True, True
        if oneway in ("yes", "true", "1") or tags.get("junction") == "roundabout" or (
            tags["highway"] == "motorway" and oneway != "no"
        ):
            backward = False
        elif oneway == "-1":
            forward = False
        lanes = lanes_d
        if tags.get("lanes", "").isdigit():
            total = int(tags["lanes"])
            lanes = total if not (forward and backward) else max(1, total // 2)
        lanes = max(1, min(lanes, 8))
        cuts = [0] + [
            i for i in range(1, len(nds) - 1)
            if usage[nds[i]] >= 2 or nodes[nds[i]][2].get("highway") == "traffic_signals"
        ] + [len(nds) - 1]
        for s, (a, b) in enumerate(zip(cuts, cuts[1:])):
            seg = nds[a : b + 1]
            length = sum(_haversine(nodes[p][:2], nodes[q][:2]) for p, q in zip(seg, seg[1:]))
            if length <= 0 or seg[0] == seg[-1]:
                result.messages.append(f"Way {way['id']} segment {s} skipped: zero length or a closed loop")
                continue
            node(seg[0], usage[seg[0]] == 1 and a == 0)
            node(seg[-1], usage[seg[-1]] == 1 and b == len(nds) - 1)
            name = tags.get("name", "")
            base = f"{way['id']}:{s}"
            if forward:
                links.append(GraphLink(id=base, **{"from": seg[0], "to": seg[-1]},
                                       length=round(length, 3), lanes=lanes, speed=speed, name=name))
            if backward:
                links.append(GraphLink(id=base + "r", **{"from": seg[-1], "to": seg[0]},
                                       length=round(length, 3), lanes=lanes, speed=speed, name=name))
    if skipped:
        result.messages.append("Skipped ways: " + _summary(skipped))
    result.graph = RoadGraph(
        name="OpenStreetMap import",
        source="osm",
        nodes=sorted(graph_nodes.values(), key=lambda n: n.id),
        links=links,
    )
    result.stats = {"ways": len(ways), "waysImported": len(usable), "nodes": len(graph_nodes), "links": len(links)}
    return result


def _summary(counter: Counter) -> str:
    return ", ".join(f"{k} x{v}" for k, v in sorted(counter.items()))
