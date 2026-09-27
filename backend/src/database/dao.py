import json
import sqlite3
from typing import Any, Dict, Optional, cast


class ConfigurationDAO:
    """DAO for managing simulation configuration items."""

    @staticmethod
    def save(conn: sqlite3.Connection, config_id: str, config: Dict[str, Any]) -> None:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO configurations (id, config_json) VALUES (?, ?);",
                (config_id, json.dumps(config)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def get(conn: sqlite3.Connection, config_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT config_json FROM configurations WHERE id = ?;", (config_id,)
        )
        row = cursor.fetchone()
        if row:
            return cast(Dict[str, Any], json.loads(row["config_json"]))
        return None


def _loads_dict(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decodes a JSON object column; None for NULL, empty or malformed."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


_RUN_COLUMNS = (
    "id, status, elapsed, intersection_type, random_seed, arrival_rate, "
    "duration, batch_id, config_json, summary_metrics_json, git_commit, "
    "provenance_json, name, notes, tags_json, created_at"
)


def _loads_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [t for t in parsed if isinstance(t, str)]


def _decode_run_row(row: sqlite3.Row) -> Dict[str, Any]:
    """A simulation_runs row as a dict, with its JSON columns decoded
    alongside the raw ones (``config``, ``summary_metrics`` and
    ``provenance`` -- the latter None for runs saved before it existed)."""
    data = dict(row)
    data["config"] = _loads_dict(data.get("config_json")) or {}
    data["summary_metrics"] = _loads_dict(data.get("summary_metrics_json")) or {}
    data["provenance"] = _loads_dict(data.get("provenance_json"))
    data["tags"] = _loads_tags(data.get("tags_json"))
    return data


class SimulationRunDAO:
    """DAO for tracking simulation runs with rich metadata, seeds, configs, and summary metrics."""

    @staticmethod
    def save(
        conn: sqlite3.Connection,
        run_id: str,
        status: str,
        elapsed: float,
        intersection_type: str = "unknown",
        random_seed: Optional[int] = None,
        arrival_rate: float = 0.5,
        duration: Optional[float] = None,
        batch_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        summary_metrics: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> None:
        """Inserts or replaces a run.

        ``provenance`` (see src/core/provenance.py ``build_run_provenance``)
        is optional so existing callers keep working; when omitted, the
        ``git_commit``/``provenance_json`` columns stay NULL ("not
        recorded") rather than being filled with a guessed value.
        """
        cursor = conn.cursor()
        git_commit = provenance.get("gitCommitHash") if provenance else None
        provenance_str = json.dumps(provenance) if provenance else None
        config_str = json.dumps(config) if config is not None else "{}"
        metrics_str = (
            json.dumps(summary_metrics) if summary_metrics is not None else "{}"
        )
        seed_val = random_seed if random_seed is not None else 0
        dur_val = duration if duration is not None else elapsed

        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO simulation_runs (
                    id, status, elapsed, intersection_type, random_seed, arrival_rate,
                    duration, batch_id, config_json, summary_metrics_json,
                    git_commit, provenance_json, name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    status,
                    elapsed,
                    intersection_type,
                    seed_val,
                    arrival_rate,
                    dur_val,
                    batch_id,
                    config_str,
                    metrics_str,
                    git_commit,
                    provenance_str,
                    name,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def get(conn: sqlite3.Connection, run_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {_RUN_COLUMNS} FROM simulation_runs WHERE id = ?;",
            (run_id,),
        )
        row = cursor.fetchone()
        return _decode_run_row(row) if row else None

    @staticmethod
    def list_runs(
        conn: sqlite3.Connection,
        limit: int = 50,
        offset: int = 0,
        intersection_type: Optional[str] = None,
        seed: Optional[int] = None,
        batch_id: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        cursor = conn.cursor()
        query = f"SELECT {_RUN_COLUMNS} FROM simulation_runs"
        conditions = []
        params: list[Any] = []

        if intersection_type:
            conditions.append("intersection_type = ?")
            params.append(intersection_type)
        if seed is not None:
            conditions.append("random_seed = ?")
            params.append(seed)
        if batch_id:
            conditions.append("batch_id = ?")
            params.append(batch_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        return [_decode_run_row(r) for r in cursor.fetchall()]

    @staticmethod
    def get_many(
        conn: sqlite3.Connection, run_ids: list[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Fetches several runs by id in one query, keyed by id. Missing
        ids are simply absent from the result."""
        if not run_ids:
            return {}
        placeholders = ", ".join("?" for _ in run_ids)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {_RUN_COLUMNS} FROM simulation_runs WHERE id IN ({placeholders});",
            tuple(run_ids),
        )
        return {r["id"]: _decode_run_row(r) for r in cursor.fetchall()}

    @staticmethod
    def update_metadata(
        conn: sqlite3.Connection,
        run_id: str,
        *,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[list[str]] = None,
        set_name: bool = False,
        set_notes: bool = False,
        set_tags: bool = False,
    ) -> bool:
        """Updates the user-entered labels of a run; only the fields flagged
        with ``set_*`` are written (so a field can also be cleared to NULL).
        Returns False when the run does not exist."""
        assignments: list[str] = []
        params: list[Any] = []
        if set_name:
            assignments.append("name = ?")
            params.append(name)
        if set_notes:
            assignments.append("notes = ?")
            params.append(notes)
        if set_tags:
            assignments.append("tags_json = ?")
            params.append(json.dumps(tags) if tags else None)
        cursor = conn.cursor()
        try:
            if assignments:
                cursor.execute(
                    f"UPDATE simulation_runs SET {', '.join(assignments)} WHERE id = ?;",
                    (*params, run_id),
                )
                updated = cursor.rowcount > 0
            else:
                cursor.execute("SELECT 1 FROM simulation_runs WHERE id = ?;", (run_id,))
                updated = cursor.fetchone() is not None
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return updated

    @staticmethod
    def delete(conn: sqlite3.Connection, run_id: str) -> bool:
        """Deletes a run (its run_metrics rows cascade). Returns whether a
        row was removed."""
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM simulation_runs WHERE id = ?;", (run_id,))
            removed = cursor.rowcount > 0
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return removed


def describe_reproducibility(
    run: Dict[str, Any], include_payload: bool = True
) -> Dict[str, Any]:
    """The reproducibility view of a decoded simulation_runs row.

    Never invents a value: anything a run did not record is None.

    * Runs saved before V1.1 have no provenance, so commit, Python version,
      config source, run mode and timing are None. Their seed column is
      reported as stored, except where the row also has no configuration --
      those rows predate seed/config capture altogether, and their seed is
      only the migration's column default, not a recorded value.
    * A run whose stored config came from the client rather than the
      engine reports the seed only if that config carries one.

    With ``include_payload`` the stored ``config`` (with
    ``simulation.randomSeed`` pinned to the recorded seed, so it restores
    the same arrivals even when the seed was auto-generated at run time)
    and ``summaryMetrics`` are included; without it, only a compact
    summary for listings.
    """
    provenance = run.get("provenance") or None
    config = run.get("config") or {}
    config_available = bool(config)
    config_seed = (config.get("simulation") or {}).get("randomSeed")

    if provenance is None:
        seed = run.get("random_seed") if config_available else None
    elif provenance.get("configSource") == "engine":
        seed = run.get("random_seed")
    else:
        seed = config_seed

    timing = (provenance or {}).get("timing") or {}
    record: Dict[str, Any] = {
        "runId": run.get("id"),
        "name": run.get("name"),
        "notes": run.get("notes"),
        "tags": run.get("tags") or [],
        "batchId": run.get("batch_id"),
        "createdAt": run.get("created_at"),
        "status": run.get("status"),
        "intersectionType": run.get("intersection_type"),
        "provenanceRecorded": provenance is not None,
        "runMode": (provenance or {}).get("runMode"),
        "seed": seed,
        "gitCommitHash": (provenance or {}).get("gitCommitHash"),
        "pythonVersion": (provenance or {}).get("pythonVersion"),
        "configSource": (provenance or {}).get("configSource"),
        "configAvailable": config_available,
        "exactConfig": (provenance or {}).get("configSource") == "engine",
        "timing": {
            "timeStep": timing.get("timeStep"),
            "duration": timing.get("duration"),
            "warmupTime": timing.get("warmupTime"),
            "elapsed": run.get("elapsed") if provenance is not None else None,
        },
    }
    if include_payload:
        restorable: Optional[Dict[str, Any]] = None
        if config_available:
            restorable = json.loads(json.dumps(config))
            if seed is not None:
                restorable.setdefault("simulation", {})["randomSeed"] = seed
        record["config"] = restorable
        record["summaryMetrics"] = run.get("summary_metrics") or {}
    return record


class RunMetricsDAO:
    """DAO for storing and retrieving time-series metrics snapshots."""

    @staticmethod
    def save(
        conn: sqlite3.Connection, run_id: str, tick: int, metrics: Dict[str, Any]
    ) -> None:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO run_metrics (run_id, tick, metrics_json) VALUES (?, ?, ?);",
                (run_id, tick, json.dumps(metrics)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def get_all_for_run(conn: sqlite3.Connection, run_id: str) -> list[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tick, metrics_json FROM run_metrics WHERE run_id = ? ORDER BY tick ASC;",
            (run_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "tick": r["tick"],
                "metrics": cast(Dict[str, Any], json.loads(r["metrics_json"])),
            }
            for r in rows
        ]

    @staticmethod
    def get_latest_for_run(
        conn: sqlite3.Connection, run_id: str
    ) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tick, metrics_json FROM run_metrics WHERE run_id = ? ORDER BY tick DESC LIMIT 1;",
            (run_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "tick": row["tick"],
                "metrics": cast(Dict[str, Any], json.loads(row["metrics_json"])),
            }
        return None


class SweepSessionDAO:
    """DAO for managing traffic volume sweep sessions and comparative benchmark experiments."""

    @staticmethod
    def save(
        conn: sqlite3.Connection,
        session_id: str,
        name: str,
        config: Dict[str, Any],
        results: Dict[str, Any],
    ) -> None:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO sweep_sessions (id, name, config_json, results_json) VALUES (?, ?, ?, ?);",
                (session_id, name, json.dumps(config), json.dumps(results)),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def get(conn: sqlite3.Connection, session_id: str) -> Optional[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json, results_json, created_at FROM sweep_sessions WHERE id = ?;",
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "name": row["name"],
                "config": json.loads(row["config_json"]),
                "results": json.loads(row["results_json"]),
                "created_at": row["created_at"],
            }
        return None

    @staticmethod
    def list_sessions(
        conn: sqlite3.Connection, limit: int = 50, offset: int = 0
    ) -> list[Dict[str, Any]]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, config_json, results_json, created_at FROM sweep_sessions ORDER BY created_at DESC LIMIT ? OFFSET ?;",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "config": json.loads(r["config_json"]),
                "results": json.loads(r["results_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
