"""Regenerate the checked-in ``/api/v3`` contract files.

    cd backend && python -m src.experiments.export_schemas

Writes, under ``shared/schemas/v3/``:

* ``experiment.schema.json``        -- the request document (``urbanflow-experiment`` v1);
* ``uncertainty-spec.schema.json``  -- ``urbanflow-uncertainty-spec`` v1;
* ``manifest.schema.json``          -- the reproducibility manifest (``urbanflow-experiment-manifest`` v1);
* ``openapi.v3.snapshot.json``      -- the ``/api/v3`` part of the app's OpenAPI document.

``tests/experiments/test_contract.py`` fails when any of them is stale, so a contract change cannot ship
without its schema diff (ADR-013 decision 7).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Set, Tuple, Type

from pydantic import BaseModel

from src.uncertainty.spec import UncertaintySpec

from .manifest import ExperimentManifest
from .models import ExperimentRequest

OUT = Path(__file__).resolve().parents[3] / "shared" / "schemas" / "v3"

MODELS: Tuple[Tuple[str, Type[BaseModel]], ...] = (
    ("experiment", ExperimentRequest),
    ("uncertainty-spec", UncertaintySpec),
    ("manifest", ExperimentManifest),
)

OPENAPI_FILE = "openapi.v3.snapshot.json"
_SCHEMA_REF = "#/components/schemas/"


def schemas() -> Dict[str, Any]:
    return {name: model.model_json_schema() for name, model in MODELS}


def _refs(node: Any, found: Set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(_SCHEMA_REF):
            found.add(ref[len(_SCHEMA_REF) :])
        for value in node.values():
            _refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _refs(value, found)


def v3_openapi(full: Dict[str, Any]) -> Dict[str, Any]:
    """The ``/api/v3`` paths of an OpenAPI document and the component schemas they reach.

    Only v3 is snapshotted: ``/api/v1`` and ``/api/v2`` are frozen and guarded by their own tests, and a
    whole-app snapshot would fail on every unrelated change.
    """
    paths = {p: op for p, op in full["paths"].items() if p.startswith("/api/v3/")}
    components = (full.get("components") or {}).get("schemas") or {}
    needed: Set[str] = set()
    _refs(paths, needed)
    queue = list(needed)
    while queue:
        name = queue.pop()
        found: Set[str] = set()
        _refs(components.get(name, {}), found)
        for child in found - needed:
            needed.add(child)
            queue.append(child)
    return {
        "openapi": full["openapi"],
        "info": {"title": "UrbanFlow API v3 (snapshot)", "version": "3"},
        "paths": dict(sorted(paths.items())),
        "components": {
            "schemas": {
                name: components[name] for name in sorted(needed) if name in components
            }
        },
    }


def snapshot() -> Dict[str, Any]:
    from src.main import app

    return v3_openapi(app.openapi())


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, schema in schemas().items():
        (OUT / f"{name}.schema.json").write_bytes(_dump(schema).encode("utf-8"))
        print("wrote", name)
    (OUT / OPENAPI_FILE).write_bytes(_dump(snapshot()).encode("utf-8"))
    print("wrote", OPENAPI_FILE)


if __name__ == "__main__":
    main()
