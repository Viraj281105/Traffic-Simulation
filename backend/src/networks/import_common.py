"""Shared bits for the importers: result type and a safe XML parser."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.networks.graph import RoadGraph, serialize_graph, validate_graph


@dataclass
class ImportResult:
    """``graph`` is None when nothing usable was read; ``errors`` then says why.
    ``messages`` are non-fatal notes about what was skipped or assumed."""

    format: str
    graph: Optional[RoadGraph] = None
    errors: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        validation = validate_graph(self.graph) if self.graph is not None else None
        return {
            "format": self.format,
            "ok": not self.errors,
            "errors": list(self.errors),
            "messages": list(self.messages),
            "stats": dict(self.stats),
            "graph": serialize_graph(self.graph) if self.graph is not None else None,
            "validation": validation,
        }


def parse_xml_safely(text: str) -> ET.Element:
    """Parse XML from an untrusted upload. DTDs and entities are refused
    outright (entity expansion attacks); other errors raise ``ValueError``
    with a readable message."""
    head = text.lstrip()[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in text.upper():
        raise ValueError("XML with a DOCTYPE or entity declarations is not accepted")
    try:
        return ET.fromstring(text)
    except ET.ParseError as err:
        raise ValueError(f"Not well-formed XML: {err}") from err
