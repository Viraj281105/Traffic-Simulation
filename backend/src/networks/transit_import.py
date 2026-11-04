"""Minimal GTFS and Synchro (UTDF) import.

Both are partial on purpose and say so in ``messages``: GTFS yields stops and
per-route stop sequences and headways (no calendars, shapes or fares);
Synchro UTDF yields per-intersection lanes, volumes and timing from the
``Lanes`` and ``Timeplans`` tables (no phasing detail).
"""

import csv
import io
import zipfile
from typing import Any, Dict, List, Optional

from src.networks.import_common import ImportResult

GTFS_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
MAX_ZIP_BYTES = 20_000_000


def _rows(text: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def _seconds(value: str) -> Optional[int]:
    try:
        h, m, s = (int(p) for p in value.split(":"))
    except ValueError:
        return None
    return h * 3600 + m * 60 + s


def import_gtfs(files: Dict[str, str]) -> ImportResult:
    """``files`` maps file name (``stops.txt``...) to its text."""
    result = ImportResult(format="gtfs")
    missing = [f for f in GTFS_FILES if f not in files]
    if missing:
        result.errors.append(f"GTFS feed is missing required file(s): {', '.join(missing)}")
        return result
    stops: Dict[str, Dict[str, Any]] = {}
    for r in _rows(files["stops.txt"]):
        try:
            stops[r["stop_id"]] = {
                "id": r["stop_id"],
                "name": r.get("stop_name", ""),
                "lat": float(r["stop_lat"]),
                "lon": float(r["stop_lon"]),
            }
        except (KeyError, ValueError):
            result.messages.append(f"Stop {r.get('stop_id', '?')!r} skipped: missing or bad coordinates")
    routes = {r["route_id"]: r for r in _rows(files["routes.txt"]) if r.get("route_id")}
    trips = {r["trip_id"]: r["route_id"] for r in _rows(files["trips.txt"]) if r.get("trip_id")}
    by_trip: Dict[str, List[Dict[str, str]]] = {}
    for r in _rows(files["stop_times.txt"]):
        by_trip.setdefault(r.get("trip_id", ""), []).append(r)

    per_route: Dict[str, List[Dict[str, Any]]] = {}
    for trip_id, rows in sorted(by_trip.items()):
        route_id = trips.get(trip_id)
        if route_id is None or route_id not in routes:
            result.messages.append(f"Trip {trip_id!r} skipped: unknown trip or route")
            continue
        try:
            rows.sort(key=lambda r: int(r["stop_sequence"]))
        except (KeyError, ValueError):
            result.messages.append(f"Trip {trip_id!r} skipped: bad stop_sequence")
            continue
        unknown = [r["stop_id"] for r in rows if r.get("stop_id") not in stops]
        if unknown:
            result.messages.append(f"Trip {trip_id!r} skipped: unknown stop(s) {sorted(set(unknown))}")
            continue
        times = [_seconds(r.get("arrival_time", "")) for r in rows]
        per_route.setdefault(route_id, []).append(
            {
                "tripId": trip_id,
                "stops": [r["stop_id"] for r in rows],
                "start": times[0] if times and times[0] is not None else None,
            }
        )
    out_routes = []
    for route_id in sorted(per_route):
        trip_list = per_route[route_id]
        pattern = max(
            {tuple(t["stops"]) for t in trip_list},
            key=lambda p: (sum(1 for t in trip_list if tuple(t["stops"]) == p), p),
        )
        starts = sorted(t["start"] for t in trip_list if t["start"] is not None)
        gaps = [b - a for a, b in zip(starts, starts[1:]) if b > a]
        r = routes[route_id]
        out_routes.append(
            {
                "id": route_id,
                "name": r.get("route_short_name") or r.get("route_long_name", ""),
                "type": r.get("route_type", ""),
                "stops": list(pattern),
                "trips": len(trip_list),
                "meanHeadwaySeconds": round(sum(gaps) / len(gaps), 1) if gaps else None,
            }
        )
    if not out_routes:
        result.errors.append("No usable transit routes found in this feed")
    result.messages.append(
        "GTFS is read for stops, stop sequences and headways only; calendars, "
        "shapes and fares are ignored. Stops are not yet snapped to the road network"
    )
    result.stats = {
        "stops": len(stops),
        "routes": len(out_routes),
        "trips": sum(r["trips"] for r in out_routes),
        "transit": {"stops": sorted(stops.values(), key=lambda s: s["id"]), "routes": out_routes},
    }
    return result


def import_gtfs_zip(data: bytes) -> ImportResult:
    if len(data) > MAX_ZIP_BYTES:
        r = ImportResult(format="gtfs")
        r.errors.append("GTFS zip is larger than 20 MB")
        return r
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            files = {
                n.rsplit("/", 1)[-1]: zf.read(n).decode("utf-8", "replace")
                for n in zf.namelist()
                if n.endswith(".txt") and zf.getinfo(n).file_size <= MAX_ZIP_BYTES
            }
    except zipfile.BadZipFile:
        r = ImportResult(format="gtfs")
        r.errors.append("Not a valid zip file")
        return r
    return import_gtfs(files)


MOVEMENTS = ("NBL", "NBT", "NBR", "SBL", "SBT", "SBR", "EBL", "EBT", "EBR", "WBL", "WBT", "WBR")
_ARM_OF = {"N": "south", "S": "north", "E": "west", "W": "east"}  # NB traffic enters from the south arm


def _blocks(text: str) -> Dict[str, List[Dict[str, str]]]:
    """Split UTDF text into named tables keyed by their header block name."""
    blocks: Dict[str, List[Dict[str, str]]] = {}
    name: Optional[str] = None
    header: Optional[List[str]] = None
    fresh = True
    for raw in text.lstrip("﻿").splitlines():
        cells = next(csv.reader([raw])) if raw.strip() else []
        cells = [c.strip() for c in cells]
        if not any(cells):
            header = None
            fresh = True
            continue
        nonempty = [c for c in cells if c]
        if len(nonempty) == 1 and header is None and not cells[0].upper() == "RECORDNAME":
            if fresh:  # a second title line is only a description
                name = nonempty[0]
                fresh = False
            continue
        if cells[0].upper() == "RECORDNAME" or (header is None and cells[0].upper() == "INTID"):
            header = [c.upper() for c in cells]
            blocks.setdefault(name or "", [])
            continue
        if header is not None:
            blocks.setdefault(name or "", []).append(dict(zip(header, cells)))
    return blocks


def _num(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


def import_synchro(text: str) -> ImportResult:
    """Read the ``Lanes`` and ``Timeplans`` tables of a UTDF CSV."""
    result = ImportResult(format="synchro")
    blocks = _blocks(text)
    lanes_rows = blocks.get("Lanes", [])
    if not lanes_rows:
        result.errors.append(
            "No 'Lanes' table found: this does not look like a Synchro UTDF CSV export"
        )
        return result
    inters: Dict[str, Dict[str, Any]] = {}
    for row in lanes_rows:
        iid = row.get("INTID", "")
        if not iid:
            continue
        rec = row.get("RECORDNAME", "").lower()
        target = {"lanes": "lanes", "volume": "volumes", "speed": "speeds"}.get(rec)
        if target is None:
            continue
        entry = inters.setdefault(
            iid, {"id": iid, "lanes": {}, "volumes": {}, "speeds": {}, "cycleSeconds": None, "offsetSeconds": None}
        )
        for m in MOVEMENTS:
            if row.get(m, "") != "":
                entry[target][m] = _num(row[m])
    for row in blocks.get("Timeplans", []):
        iid = row.get("INTID", "")
        if iid in inters:
            cyc = row.get("CYCLE LENGTH") or row.get("CYCLELENGTH") or row.get("CYCLE")
            off = row.get("REFERENCE PHASE OFFSET") or row.get("OFFSET")
            if cyc:
                inters[iid]["cycleSeconds"] = _num(cyc)
            if off:
                inters[iid]["offsetSeconds"] = _num(off)
    unsupported = sorted(b for b in blocks if b not in ("Lanes", "Timeplans"))
    if unsupported:
        result.messages.append(
            "Tables not read: " + ", ".join(unsupported) + " (phasing, layout and links need a later import)"
        )
    out = []
    for iid in sorted(inters, key=lambda s: (len(s), s)):
        e = inters[iid]
        approaches: Dict[str, Dict[str, float]] = {}
        for m in MOVEMENTS:
            arm = _ARM_OF[m[0]]
            a = approaches.setdefault(arm, {"lanes": 0.0, "vehiclesPerHour": 0.0})
            a["lanes"] += e["lanes"].get(m, 0.0)
            a["vehiclesPerHour"] += e["volumes"].get(m, 0.0)
        e["approaches"] = {k: v for k, v in approaches.items() if v["lanes"] > 0 or v["vehiclesPerHour"] > 0}
        if not e["approaches"]:
            result.messages.append(f"Intersection {iid} has no lanes or volumes")
        out.append(e)
    result.stats = {"intersections": len(out), "synchro": {"intersections": out}}
    result.messages.append(
        "Synchro import gives per-approach lanes, volumes and cycle/offset; it does not "
        "build a road graph, and phasing detail is not read"
    )
    return result
