"""``/api/v1/study/history/runs``: stored simulation runs.

Listing, reading, labelling, exporting, comparing and reproducing the runs in
``simulation_runs``. Built by a factory so this package never imports
``main`` (which mounts it): ``main`` passes its own ``require_api_key`` in.

Access (``src/access.py``): a run saved by a signed-in user belongs to them,
and only they (or an admin) can see, label, export, compare or reproduce it;
anyone else gets the same 404 as for a missing run. Runs with no owner, the
output of studies started without signing in, stay readable by anyone, as
they always were; changing their labels needs an admin. The browser proxy
attaches the API key to every request, so the key alone identifies the proxy,
not a person, and is never treated as an owner.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.access import Caller, can_see
from src.auth import (
    get_current_user_id,
    get_current_user_is_admin,
    get_optional_user_id,
    get_optional_user_is_admin,
)
from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.database.dao import RunMetricsDAO, SimulationRunDAO, describe_reproducibility
from src.database.db import ensure_db_initialized, get_db_connection
from src.database.replay_dao import ReplayDAO
from src.history.export import run_export_csv
from src.history.reproduce import ReproductionError, reproduce_run
from src.request_limits import PageLimit, PageOffset, compute_slot
from src.study.tolerances import delays_are_tied

PREFIX = "/api/v1/study/history/runs"

# Run ids are UUIDs, "sweep_<8 hex>_<sig|rnd>_<rate>" or other simple slugs.
# Anything else (spaces, dots, slashes, unicode) cannot name a stored run and
# is rejected up front as malformed rather than looked up.
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

_MAX_TAGS = 20


class RunComparisonRequest(BaseModel):
    runIdA: str
    runIdB: str


class RunMetadataUpdate(BaseModel):
    """User-entered labels. Omitted fields are left unchanged; ``notes`` and
    ``tags`` can be cleared with null / an empty value."""

    name: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=4000)
    tags: Optional[list[Annotated[str, Field(max_length=32)]]] = Field(
        default=None, max_length=_MAX_TAGS
    )


def optional_caller(
    user_id: Optional[str] = Depends(get_optional_user_id),
    is_admin: bool = Depends(get_optional_user_is_admin),
) -> Caller:
    """The caller of a read route: anonymous, or the signed-in user."""
    return Caller(user_id, is_admin)


def signed_in_caller(
    user_id: str = Depends(get_current_user_id),
    is_admin: bool = Depends(get_current_user_is_admin),
) -> Caller:
    """The caller of a write route, which always needs a signed-in user."""
    return Caller(user_id, is_admin)


def _validate_run_id(run_id: str) -> None:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=400, detail="Malformed run ID")


def _not_found(run_id: Optional[str] = None) -> HTTPException:
    if run_id is None:
        return HTTPException(status_code=404, detail="Simulation run not found")
    return HTTPException(status_code=404, detail=f"Run '{run_id}' not found")


def _visible_run(conn: Any, run_id: str, caller: Caller) -> Dict[str, Any]:
    """The decoded run, or 404 when it is missing or not the caller's."""
    run = SimulationRunDAO.get_visible(conn, run_id, caller)
    if run is None:
        raise _not_found()
    return run


def _run_record(conn: Any, run: Dict[str, Any]) -> Dict[str, Any]:
    """The full reproducibility record of a run plus what the saved-run page
    needs: its name (falling back to the saved replay's name for runs saved
    before names were stored on the run) and whether a dashboard replay
    exists to restore it from."""
    record = describe_reproducibility(run)
    replay = ReplayDAO.get(conn, run["id"])
    if record["name"] is None and replay is not None:
        record["name"] = replay["name"]
    record["savedReplay"] = replay is not None
    return record


def _clean_tags(tags: Optional[list[str]]) -> list[str]:
    """Trimmed, non-empty, de-duplicated (case-insensitively, first spelling
    kept) tags in their given order."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in tags or []:
        t = " ".join(tag.split())
        if t and t.lower() not in seen:
            seen.add(t.lower())
            cleaned.append(t)
    return cleaned


def _metric(metrics: Dict[str, Any], *keys: str) -> Optional[float]:
    """The first of ``keys`` that holds a number, else None. A missing value
    is unavailable, never 0 (the evidence-not-a-verdict rule)."""
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _delta(a: Optional[float], b: Optional[float], digits: int) -> Optional[float]:
    return None if a is None or b is None else round(b - a, digits)


def compare_runs(
    run_a: Dict[str, Any], run_b: Dict[str, Any], id_a: str, id_b: str
) -> Dict[str, Any]:
    """Side-by-side deltas (B minus A) of two stored runs.

    A delta is null when either run lacks the metric -- for example a
    signal-vs-roundabout comparison run, whose metrics are stored per
    geometry -- and the "winner" is then ``"unavailable"``, never a result
    computed from a substituted 0.
    """
    metrics_a = run_a.get("summary_metrics") or {}
    metrics_b = run_b.get("summary_metrics") or {}

    delay_a = _metric(metrics_a, "averageDelay", "averageWaitTime")
    delay_b = _metric(metrics_b, "averageDelay", "averageWaitTime")
    tp_a, tp_b = _metric(metrics_a, "throughput"), _metric(metrics_b, "throughput")
    q_a = _metric(metrics_a, "averageQueueLength")
    q_b = _metric(metrics_b, "averageQueueLength")
    stops_a, stops_b = (
        _metric(metrics_a, "totalStops"),
        _metric(metrics_b, "totalStops"),
    )

    delay_delta_pct: Optional[float] = None
    if delay_a is not None and delay_b is not None and delay_a > 0:
        delay_delta_pct = round(((delay_b - delay_a) / delay_a) * 100, 1)

    # Which run had the lower MEAN DELAY -- a description of these two
    # single runs, not a ranking or a significance statement. "About the
    # same" uses the one shared tie rule (study/tolerances.py), so this
    # endpoint agrees with the sweep and the guided results page.
    winner: str
    if delay_a is None or delay_b is None:
        winner = "unavailable"
    elif delays_are_tied(delay_a, delay_b):
        winner = "tie"
    elif delay_a < delay_b:
        winner = run_a.get("intersection_type") or id_a
    else:
        winner = run_b.get("intersection_type") or id_b

    stops_delta = _delta(stops_a, stops_b, 0)
    return {
        "runA": {
            "id": id_a,
            "intersectionType": run_a.get("intersection_type"),
            "seed": run_a.get("random_seed"),
            "arrivalRate": run_a.get("arrival_rate"),
            "metrics": metrics_a,
        },
        "runB": {
            "id": id_b,
            "intersectionType": run_b.get("intersection_type"),
            "seed": run_b.get("random_seed"),
            "arrivalRate": run_b.get("arrival_rate"),
            "metrics": metrics_b,
        },
        "comparison": {
            "delayDelta": _delta(delay_a, delay_b, 2),
            "delayDeltaPercent": delay_delta_pct,
            "throughputDelta": _delta(tp_a, tp_b, 1),
            "queueDelta": _delta(q_a, q_b, 1),
            "stopsDelta": None if stops_delta is None else int(stops_delta),
            "winner": winner,
            "winnerBasis": (
                "lower mean delay between these two single runs; "
                "'tie' when within the shared tie tolerance; 'unavailable' "
                "when either run has no single mean delay (e.g. a comparison "
                "run, which stores metrics per geometry). Descriptive "
                "only: not a significance test."
            ),
        },
        "identicalSeed": run_a.get("random_seed") == run_b.get("random_seed"),
        "seed": run_a.get("random_seed")
        if run_a.get("random_seed") == run_b.get("random_seed")
        else None,
    }


def build_router(require_api_key: Callable[..., Any]) -> APIRouter:
    router = APIRouter(prefix=PREFIX, tags=["history"])

    @router.get("")
    def list_simulation_runs_endpoint(
        limit: PageLimit = 50,
        offset: PageOffset = 0,
        intersection_type: str | None = None,
        seed: int | None = None,
        batch_id: str | None = None,
        caller: Caller = Depends(optional_caller),
    ) -> list[Dict[str, Any]]:
        """Past runs the caller can see, with their status, metrics and
        filters: unowned runs, plus the caller's own (every run for an admin)."""
        ensure_db_initialized()
        with get_db_connection() as conn:
            return SimulationRunDAO.list_runs(
                conn,
                limit=limit,
                offset=offset,
                intersection_type=intersection_type,
                seed=seed,
                batch_id=batch_id,
                caller=caller,
            )

    @router.get("/{run_id}")
    def get_simulation_run_endpoint(
        run_id: str, caller: Caller = Depends(optional_caller)
    ) -> Dict[str, Any]:
        """Metadata and time-series metrics for one run."""
        ensure_db_initialized()
        with get_db_connection() as conn:
            run = _visible_run(conn, run_id, caller)
            metrics = RunMetricsDAO.get_all_for_run(conn, run_id)
            return {"run": run, "metricsTimeline": metrics}

    @router.get("/{run_id}/reproducibility")
    def get_run_reproducibility_endpoint(
        run_id: str, caller: Caller = Depends(optional_caller)
    ) -> Dict[str, Any]:
        """Everything needed to re-run a stored experiment exactly: its config
        (seed pinned), seed, git commit, Python version, timing and summary
        metrics, plus its name, notes and tags. Fields a run never recorded
        (runs saved before V1.1) are null."""
        _validate_run_id(run_id)
        ensure_db_initialized()
        with get_db_connection() as conn:
            return _run_record(conn, _visible_run(conn, run_id, caller))

    @router.patch("/{run_id}", dependencies=[Depends(require_api_key)])
    def update_run_metadata_endpoint(
        run_id: str,
        payload: RunMetadataUpdate,
        caller: Caller = Depends(signed_in_caller),
    ) -> Dict[str, Any]:
        """Renames a run and sets its notes/tags. Touches only these labels --
        never the stored configuration, seed, provenance or metrics. Only the
        run's owner (or an admin) may; an unowned run's labels need an admin."""
        _validate_run_id(run_id)
        provided = payload.model_fields_set
        name: Optional[str] = None
        if "name" in provided:
            name = (payload.name or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="Run name cannot be empty")
        notes = (payload.notes or "").strip() or None
        tags = _clean_tags(payload.tags)
        ensure_db_initialized()
        with get_db_connection() as conn:
            exists, owner = SimulationRunDAO.owner_of(conn, run_id)
            if not exists or not can_see(owner, caller, unowned_public=True):
                raise _not_found()
            if not can_see(owner, caller, unowned_public=False):
                # Readable by everyone, so nothing is hidden by saying so.
                raise HTTPException(
                    status_code=403,
                    detail="Only an admin can change the labels of a shared run",
                )
            SimulationRunDAO.update_metadata(
                conn,
                run_id,
                name=name,
                notes=notes,
                tags=tags,
                set_name="name" in provided,
                set_notes="notes" in provided,
                set_tags="tags" in provided,
            )
            if name is not None:
                # Keep the History list (saved_replays) showing the same name.
                ReplayDAO.rename(conn, run_id, name)
            return _run_record(conn, _visible_run(conn, run_id, caller))

    @router.get("/{run_id}/export")
    def export_run_endpoint(
        run_id: str,
        format: str = "json",  # noqa: A002
        caller: Caller = Depends(optional_caller),
    ) -> Any:
        """Downloads one stored run as JSON or CSV: identity, name/notes/tags,
        seed, provenance, timing, the exact stored configuration and its stored
        metrics (raw backend keys and units; see the metric catalog for labels).
        Values the run never recorded are null (JSON) or empty (CSV)."""
        _validate_run_id(run_id)
        fmt = format.lower()
        if fmt not in ("json", "csv"):
            raise HTTPException(
                status_code=400, detail="format must be 'json' or 'csv'"
            )
        ensure_db_initialized()
        with get_db_connection() as conn:
            record = _run_record(conn, _visible_run(conn, run_id, caller))
            timeline = RunMetricsDAO.get_all_for_run(conn, run_id)
        filename = f"run_{run_id}.{fmt}"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        if fmt == "csv":
            return StreamingResponse(
                iter([run_export_csv(record)]),
                media_type="text/csv; charset=utf-8",
                headers=headers,
            )
        return JSONResponse(
            content={
                "exportFormat": "traffic-simulation-run",
                "exportVersion": 1,
                "exportedAt": datetime.now(timezone.utc).isoformat(),
                # The server producing this file -- distinct from the run's own
                # recorded provenance inside "run".
                "exportedBy": {
                    "gitCommitHash": GIT_COMMIT_HASH,
                    "pythonVersion": PYTHON_VERSION,
                },
                "run": record,
                "metricsTimeline": timeline,
            },
            headers=headers,
        )

    @router.post("/compare")
    def compare_runs_endpoint(
        payload: RunComparisonRequest, caller: Caller = Depends(optional_caller)
    ) -> Dict[str, Any]:
        """Compares two stored runs side by side (see ``compare_runs``)."""
        ensure_db_initialized()
        with get_db_connection() as conn:
            run_a = SimulationRunDAO.get_visible(conn, payload.runIdA, caller)
            if run_a is None:
                raise _not_found(payload.runIdA)
            run_b = SimulationRunDAO.get_visible(conn, payload.runIdB, caller)
            if run_b is None:
                raise _not_found(payload.runIdB)
        return compare_runs(run_a, run_b, payload.runIdA, payload.runIdB)

    @router.post(
        "/{run_id}/reproduce",
        dependencies=[Depends(require_api_key), Depends(compute_slot)],
    )
    def reproduce_run_endpoint(
        run_id: str, caller: Caller = Depends(optional_caller)
    ) -> Dict[str, Any]:
        """Re-executes a stored run headlessly and compares key metrics
        (``src/history/reproduce.py``). Never modifies the stored run."""
        ensure_db_initialized()
        with get_db_connection() as conn:
            run = SimulationRunDAO.get_visible(conn, run_id, caller)
        if run is None:
            raise HTTPException(
                status_code=404, detail=f"Simulation run '{run_id}' not found"
            )
        try:
            return reproduce_run(run)
        except ReproductionError as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    return router
