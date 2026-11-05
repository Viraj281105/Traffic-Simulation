"""``ImportPreview``: the roads of an area, from an Overpass server, before anything is imported.

The Overpass server is the only outside service involved. Its URL comes from ``URBANFLOW_OVERPASS_URL``
(an ``https`` URL); when it is not set the preview is unavailable (the router answers 503) and nothing is
fetched. The query is built here from validated fields only, and the reply is capped in size and read as
JSON. Nothing is stored.

Road classes are the six the screen offers; a ``*_link`` road counts under its parent class. Lanes and
speed limit are ``null`` when the map has no tag for them: no default is filled in. A large area is thinned
to ``MAX_LINKS_SHOWN`` roads (higher classes first, then longer roads) and ``stats.linksShown`` says so.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.networks.osm_import import _haversine, _parse_speed

from .network_view import make_message

logger = logging.getLogger(__name__)

OVERPASS_URL_ENV = "URBANFLOW_OVERPASS_URL"
ROAD_CLASSES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
)
MAX_BBOX_AREA_DEG2 = 0.01
MAX_LINKS_SHOWN = 3000
MAX_RESPONSE_BYTES = 50 * 1024 * 1024
FETCH_TIMEOUT_S = 30
_PLACE_RE = re.compile(r"^[^\"\\\x00-\x1f]{1,200}$")

Fetcher = Callable[[str], str]


class PreviewUnavailableError(RuntimeError):
    """No Overpass server is configured."""


class PreviewUpstreamError(RuntimeError):
    """The Overpass server did not answer usably."""


class PreviewRequestError(ValueError):
    """The request names no usable area."""


def place_is_valid(place: str) -> bool:
    return bool(_PLACE_RE.fullmatch(place.strip())) and bool(place.strip())


def check_bbox(bbox: Sequence[float]) -> Tuple[float, float, float, float]:
    if len(bbox) != 4:
        raise PreviewRequestError("bbox needs four numbers: west, south, east, north")
    west, south, east, north = (float(v) for v in bbox)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise PreviewRequestError(
            "bbox must be [west, south, east, north] in degrees with west < east and south < north"
        )
    if (east - west) * (north - south) > MAX_BBOX_AREA_DEG2:
        raise PreviewRequestError(
            f"The area is too large to preview; keep it under {MAX_BBOX_AREA_DEG2} square degrees"
        )
    return west, south, east, north


def build_query(
    place: Optional[str],
    bbox: Optional[Tuple[float, float, float, float]],
    classes: Sequence[str],
) -> str:
    kinds = "|".join(f"{c}|{c}_link" for c in classes)
    selector = f'["highway"~"^({kinds})$"]'
    if bbox is not None:
        west, south, east, north = bbox
        body = f"way{selector}({south},{west},{north},{east});"
        head = "[out:json][timeout:25];"
    else:
        assert place is not None
        head = (
            f'[out:json][timeout:25];area["name"="{place.strip()}"]'
            '["boundary"="administrative"]->.a;'
        )
        body = f"way(area.a){selector};"
    return f"{head}({body});(._;>;);out body;"


def overpass_fetch(query: str) -> str:
    """POST the query to the configured Overpass server; the text of its reply."""
    url = os.environ.get(OVERPASS_URL_ENV, "")
    if not url:
        raise PreviewUnavailableError(
            "Road import from OpenStreetMap is not set up on this server"
        )
    if not url.lower().startswith("https://"):
        raise PreviewUnavailableError("The configured Overpass server must use https")
    request = urllib.request.Request(  # noqa: S310 - https only, URL from the environment
        url,
        data=("data=" + urllib.parse.quote(query, safe="")).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_S) as reply:  # noqa: S310
            raw = reply.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        logger.warning("Overpass request failed", exc_info=True)
        raise PreviewUpstreamError("The map server did not answer") from err
    if len(raw) > MAX_RESPONSE_BYTES:
        raise PreviewUpstreamError("The map server's answer was too large")
    return str(raw.decode("utf-8", errors="replace"))


def _road_class(highway: str) -> Optional[str]:
    base = highway[:-5] if highway.endswith("_link") else highway
    return base if base in ROAD_CLASSES else None


def _lanes(tags: Dict[str, Any]) -> Optional[int]:
    raw = tags.get("lanes")
    return int(raw) if isinstance(raw, str) and raw.isdigit() and int(raw) > 0 else None


def _speed_kmh(tags: Dict[str, Any]) -> Optional[float]:
    mps = _parse_speed(
        tags.get("maxspeed") if isinstance(tags.get("maxspeed"), str) else None
    )
    return round(mps * 3.6, 1) if mps is not None else None


def build_preview(
    reply_text: str,
    area: str,
    request_bbox: Optional[Tuple[float, float, float, float]],
    classes: Sequence[str],
) -> Dict[str, Any]:
    try:
        data = json.loads(reply_text)
    except ValueError as err:
        raise PreviewUpstreamError("The map server's answer was not readable") from err
    elements = data.get("elements") if isinstance(data, dict) else None
    if not isinstance(elements, list):
        raise PreviewUpstreamError("The map server's answer had no map data")

    nodes: Dict[int, Tuple[float, float, Dict[str, Any]]] = {}
    ways: List[Dict[str, Any]] = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        if el.get("type") == "node" and "lat" in el and "lon" in el:
            node_tags = el.get("tags")
            nodes[el["id"]] = (
                el["lat"],
                el["lon"],
                node_tags if isinstance(node_tags, dict) else {},
            )
        elif el.get("type") == "way":
            ways.append(el)

    links: List[Dict[str, Any]] = []
    used: Dict[int, Tuple[float, float, Dict[str, Any]]] = {}
    incomplete = 0
    for way in ways:
        raw_tags = way.get("tags")
        tags: Dict[str, Any] = raw_tags if isinstance(raw_tags, dict) else {}
        road_class = _road_class(str(tags.get("highway", "")))
        refs = way.get("nodes")
        if (
            road_class is None
            or road_class not in classes
            or not isinstance(refs, list)
        ):
            continue
        if len(refs) < 2 or any(r not in nodes for r in refs):
            incomplete += 1
            continue
        pts = [nodes[r] for r in refs]
        length = sum(
            _haversine((p[0], p[1]), (q[0], q[1])) for p, q in zip(pts, pts[1:])
        )
        for r in refs:
            used[r] = nodes[r]
        links.append(
            {
                "id": f"w{way.get('id')}",
                "roadClass": road_class,
                "lanes": _lanes(tags),
                "speedLimitKmh": _speed_kmh(tags),
                "lengthM": round(length, 1),
                "geometry": [[p[1], p[0]] for p in pts],
            }
        )
    if not links:
        raise PreviewRequestError(
            "No roads of the chosen classes were found in this area"
        )

    messages: List[Dict[str, Any]] = []
    if incomplete:
        messages.append(
            make_message(
                "warning",
                "incomplete_road",
                f"{incomplete} road(s) were left out because the map data for them was incomplete.",
            )
        )
    shown = links
    if len(links) > MAX_LINKS_SHOWN:
        rank = {c: i for i, c in enumerate(ROAD_CLASSES)}
        shown = sorted(links, key=lambda k: (rank[k["roadClass"]], -k["lengthM"]))[
            :MAX_LINKS_SHOWN
        ]
        messages.append(
            make_message(
                "info",
                "thinned",
                f"Showing {MAX_LINKS_SHOWN} of {len(links)} roads: the major roads first.",
            )
        )
    lats = [p[0] for p in used.values()]
    lons = [p[1] for p in used.values()]
    bbox = request_bbox or (min(lons), min(lats), max(lons), max(lats))
    key = json.dumps([area, list(bbox), sorted(classes)], sort_keys=True)
    return {
        "previewId": hashlib.sha256(key.encode()).hexdigest()[:16],
        "area": area,
        "bbox": list(bbox),
        "stats": {
            "nodes": len(used),
            "links": len(links),
            "signalisedJunctions": sum(
                1 for p in used.values() if p[2].get("highway") == "traffic_signals"
            ),
            "totalLengthKm": sum(k["lengthM"] for k in links) / 1000.0,
            "linksShown": len(shown),
        },
        "links": shown,
        "messages": messages,
    }


def preview_area(
    place: Optional[str],
    bbox: Optional[Sequence[float]],
    classes: Sequence[str],
    fetch: Fetcher,
) -> Dict[str, Any]:
    if (place is None) == (bbox is None):
        raise PreviewRequestError(
            "Send either a place name or a bounding box, not both"
        )
    checked: Optional[Tuple[float, float, float, float]] = None
    if bbox is not None:
        checked = check_bbox(bbox)
        area = (
            f"{checked[0]:.4f}, {checked[1]:.4f} to {checked[2]:.4f}, {checked[3]:.4f}"
        )
    else:
        assert place is not None
        if not place_is_valid(place):
            raise PreviewRequestError(
                "The place name has characters that cannot be searched"
            )
        area = place.strip()
    if not classes:
        raise PreviewRequestError("Choose at least one road class")
    return build_preview(
        fetch(build_query(place, checked, classes)), area, checked, classes
    )
