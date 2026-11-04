"""Parquet run store (V3.2 W32, F7): one folder of objects per run, behind a ``StorageBackend``.

Layout, identical on every backend::

    runs/<run id>/manifest.json     the run manifest (src/core/run_manifest.py), as saved
    runs/<run id>/metrics.parquet   one row per record (for example one per seed)

Keeping every run's table in its own Parquet object under one prefix lets a query engine read them
together (``runs/*/metrics.parquet``), which is what the later DuckDB layer will do.

A stored run is immutable: saving an existing run id is refused unless ``overwrite`` is set. The
run id defaults to a hash of the manifest, so saving the same run twice is the same id.

``pyarrow`` is imported only when a table is written or read.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.core.run_manifest import MANIFEST_FORMAT

from .storage import KeyNotFoundError, StorageBackend

RUNS_PREFIX = "runs/"
MANIFEST_NAME = "manifest.json"
METRICS_NAME = "metrics.parquet"

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class RunExistsError(ValueError):
    """The run id is already stored and ``overwrite`` was not set."""


class RunNotFoundError(KeyError):
    """No stored run has this id."""


@dataclass(frozen=True)
class StoredRun:
    run_id: str
    manifest: Dict[str, Any]
    records: List[Dict[str, Any]]


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(
            "run id must be 1-128 characters: letters, digits, '-' and '_', "
            "starting with a letter or digit"
        )
    return run_id


def check_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError(f"manifest format must be {MANIFEST_FORMAT!r}")
    config_hash = manifest.get("configHash")
    if not isinstance(config_hash, str) or len(config_hash) != 64:
        raise ValueError("manifest must carry a 64-hex configHash")


def run_id_for(manifest: Mapping[str, Any]) -> str:
    """A stable id from the manifest: 20 hex of the SHA-256 of its canonical JSON.

    ``createdAt`` is left out so the same run saved at two times keeps one id.
    """
    check_manifest(manifest)
    body = {k: v for k, v in manifest.items() if k != "createdAt"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def _manifest_key(run_id: str) -> str:
    return f"{RUNS_PREFIX}{run_id}/{MANIFEST_NAME}"


def _metrics_key(run_id: str) -> str:
    return f"{RUNS_PREFIX}{run_id}/{METRICS_NAME}"


def _pyarrow() -> Any:
    try:
        import pyarrow
        import pyarrow.parquet
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "the Parquet run store needs pyarrow: pip install pyarrow"
        ) from exc
    return pyarrow


def records_to_parquet(records: Sequence[Mapping[str, Any]]) -> bytes:
    """Encode a list of flat records (one dict per row) as Parquet bytes."""
    pa = _pyarrow()
    table = pa.Table.from_pylist([dict(r) for r in records])
    sink = io.BytesIO()
    pa.parquet.write_table(table, sink, compression="zstd")
    return sink.getvalue()


def parquet_to_records(data: bytes) -> List[Dict[str, Any]]:
    pa = _pyarrow()
    table = pa.parquet.read_table(io.BytesIO(data))
    rows: List[Dict[str, Any]] = table.to_pylist()
    return rows


class RunStore:
    """Save, load and list runs on any ``StorageBackend``."""

    def __init__(self, backend: StorageBackend) -> None:
        self.backend = backend

    def save_run(
        self,
        manifest: Mapping[str, Any],
        records: Sequence[Mapping[str, Any]],
        *,
        run_id: Optional[str] = None,
        overwrite: bool = False,
    ) -> str:
        """Store a run and return its id. ``records`` are flat dicts of JSON-scalar values."""
        check_manifest(manifest)
        rid = validate_run_id(run_id) if run_id is not None else run_id_for(manifest)
        if not overwrite and self.backend.exists(_manifest_key(rid)):
            raise RunExistsError(f"run {rid!r} is already stored")
        # Encode first: a bad record must fail before anything is written.
        table_bytes = records_to_parquet(records)
        manifest_bytes = json.dumps(
            manifest, sort_keys=True, indent=2, default=str
        ).encode()
        # Table first, manifest last: the manifest marks the run as complete.
        self.backend.put(_metrics_key(rid), table_bytes)
        self.backend.put(_manifest_key(rid), manifest_bytes)
        return rid

    def has_run(self, run_id: str) -> bool:
        return self.backend.exists(_manifest_key(validate_run_id(run_id)))

    def load_manifest(self, run_id: str) -> Dict[str, Any]:
        rid = validate_run_id(run_id)
        try:
            data: Dict[str, Any] = json.loads(self.backend.get(_manifest_key(rid)))
        except KeyNotFoundError:
            raise RunNotFoundError(rid) from None
        return data

    def load_run(self, run_id: str) -> StoredRun:
        rid = validate_run_id(run_id)
        manifest = self.load_manifest(rid)
        try:
            records = parquet_to_records(self.backend.get(_metrics_key(rid)))
        except KeyNotFoundError:
            raise RunNotFoundError(rid) from None
        return StoredRun(rid, manifest, records)

    def list_runs(self) -> List[str]:
        """Ids of every complete run (one with a manifest), sorted."""
        ids = set()
        for key in self.backend.list(RUNS_PREFIX):
            parts = key[len(RUNS_PREFIX) :].split("/")
            if len(parts) == 2 and parts[1] == MANIFEST_NAME:
                ids.add(parts[0])
        return sorted(ids)

    def delete_run(self, run_id: str) -> None:
        rid = validate_run_id(run_id)
        # Manifest first: a half-deleted run stops being listed at once.
        self.backend.delete(_manifest_key(rid))
        self.backend.delete(_metrics_key(rid))
