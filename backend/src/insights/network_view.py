"""``ValidationResult``: check an uploaded network file with the existing importers.

Reuses ``src.networks`` (the same importers and graph validation as ``/api/v2/network-graphs``), then words
the outcome as the upload screen's messages. Nothing is stored (``uploadId`` is always null).

* ``auto`` is decided from the file name and a look at the first bytes; a file that cannot be recognised
  is answered with ``valid: false`` and a message, not an error status.
* A file name with an extension the importers do not read is refused as unsupported (415 in the router).
* GeoJSON has no importer yet: the answer is ``valid: false`` with code ``unsupported_format``.
* GTFS and Synchro files carry no road graph, so ``summary`` is null for them; the importer's own notes
  are passed on as ``info`` messages.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.networks.import_common import ImportResult
from src.networks.osm_import import import_osm
from src.networks.sumo_io import import_sumo
from src.networks.transit_import import import_gtfs_zip, import_synchro

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
FORMATS = ("osm", "sumo", "geojson", "gtfs", "synchro")
ALLOWED_EXTENSIONS = (
    ".osm",
    ".xml",
    ".json",
    ".geojson",
    ".zip",
    ".txt",
    ".csv",
    ".syn",
)
_SNIFF_BYTES = 4096


class UnsupportedFileTypeError(ValueError):
    """The file name or content is not something any importer reads."""


def check_extension(filename: str) -> None:
    lower = filename.lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise UnsupportedFileTypeError(
            "Unsupported file type; use .osm, .xml, .json, .geojson, .zip, .txt, .csv or .syn"
        )


def detect_format(filename: str, data: bytes) -> Optional[str]:
    lower = filename.lower()
    head = data[:_SNIFF_BYTES]
    if head.startswith(b"PK"):
        return "gtfs"
    text = head.decode("utf-8", errors="replace").lstrip("﻿").lstrip().lower()
    if text.startswith("<"):
        if "<osm" in text:
            return "osm"
        if "<net" in text:
            return "sumo"
        return None
    if text.startswith("{"):
        if '"elements"' in text:
            return "osm"
        if '"featurecollection"' in text or '"geometry"' in text or '"feature"' in text:
            return "geojson"
        return None
    if lower.endswith((".txt", ".csv", ".syn")) and text:
        return "synchro"
    return None


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise UnsupportedFileTypeError("The file is not text in UTF-8") from err


def make_message(
    severity: str, code: str, message: str, hint: Optional[str] = None
) -> Dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "message": message,
        "line": None,
        "element": None,
        "hint": hint,
    }


def _run_importer(fmt: str, data: bytes) -> ImportResult:
    try:
        if fmt == "gtfs":
            return import_gtfs_zip(data)
        text = _decode(data)
        if fmt == "osm":
            return import_osm(text)
        if fmt == "sumo":
            return import_sumo(text)
        return import_synchro(text)
    except UnsupportedFileTypeError:
        raise
    except Exception:
        logger.warning("network importer failed", exc_info=True)
        result = ImportResult(format=fmt)
        result.errors.append("The file could not be read as this format")
        return result


def validate_upload(filename: str, data: bytes, requested: str) -> Dict[str, Any]:
    """The ``ValidationResult`` for an uploaded file."""
    name = filename or "upload"
    if not data:
        raise UnsupportedFileTypeError("The file is empty")
    fmt: Optional[str] = requested if requested in FORMATS else detect_format(name, data)
    if fmt is None:
        return {
            "uploadId": None,
            "filename": name,
            "format": "osm",
            "valid": False,
            "summary": None,
            "messages": [
                make_message(
                    "error",
                    "unrecognised_format",
                    "The file does not look like OpenStreetMap, SUMO, GeoJSON, GTFS or Synchro data.",
                    "Choose the format from the list instead of automatic detection.",
                )
            ],
        }
    if fmt == "geojson":
        return {
            "uploadId": None,
            "filename": name,
            "format": "geojson",
            "valid": False,
            "summary": None,
            "messages": [
                make_message(
                    "error",
                    "unsupported_format",
                    "GeoJSON networks cannot be imported yet.",
                    "Export the roads as OpenStreetMap XML or a SUMO network instead.",
                )
            ],
        }

    result = _run_importer(fmt, data)
    payload = result.to_json()
    validation = payload["validation"] or {}
    messages: List[Dict[str, Any]] = []
    messages += [make_message("error", "import_error", e) for e in payload["errors"]]
    messages += [make_message("error", "invalid_network", e) for e in validation.get("errors", [])]
    messages += [
        make_message("warning", "network_warning", w) for w in validation.get("warnings", [])
    ]
    messages += [make_message("info", "import_note", m) for m in payload["messages"]]
    stats = validation.get("stats") or {}
    summary: Optional[Dict[str, Any]] = None
    if payload["graph"] is not None and stats:
        summary = {
            "nodes": stats["nodes"],
            "links": stats["links"],
            "junctions": stats["junctions"],
            "totalLengthKm": stats["totalLengthMeters"] / 1000.0,
        }
    valid = bool(payload["ok"]) and bool(validation.get("valid", payload["graph"] is None))
    return {
        "uploadId": None,
        "filename": name,
        "format": fmt,
        "valid": valid,
        "summary": summary,
        "messages": messages,
    }

