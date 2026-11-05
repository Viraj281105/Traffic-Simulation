"""``/api/v3`` result-screen routes (the contract in ``frontend/src/CONTRACTS.md``).

``create_router`` takes the auth wiring as arguments so this module imports nothing from ``main.py`` (the
same pattern as ``src/experiments/router.py``)::

    app.include_router(
        build_insights_router(
            user_dependency=get_current_identity,
            dependencies=[Depends(require_api_key)],
        )
    )

Routes are thin: they find the stored data and hand it to a view module in this package, which shapes it.

* ``GET /experiments/{id}/comparison``, ``/sensitivity``, ``/report``: private to the experiment's owner (an
  unknown or someone else's id is 404, like every v3 resource).
* ``GET /runs/{id}/metrics`` and ``/runs/compare``: read the Parquet run store. Stored runs carry no owner,
  so any signed-in caller can read them; they hold aggregate trip rows and a manifest, nothing personal.
* ``GET /regression/nightly``, ``/loadtests/latest``, ``/rl/comparisons/{id}``: read files written by the scripts.
* ``POST /networks/validate`` (multipart) and ``/networks/import/preview`` (JSON): stateless.

404 means "not available yet" (no data, an unusable file, or an id that is not a plain token). Errors use
the shared envelope. All routes need the ``experiments:read`` scope for a personal access token.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from src.api.auth import PAT_SCOPES, UserIdentity
from src.api.request_limits import compute_slot
from src.experiments.service import ExperimentService, get_service
from src.runstore import (
    LocalFileBackend,
    RunNotFoundError,
    RunStore,
    StorageError,
    StoredRun,
)

from . import network_view, osm_preview
from .comparison_view import build_comparison
from .loadtest_view import build_loadtest
from .locations import ResultsLocations, read_json_object, safe_id
from .regression_view import build_nightly
from .report_view import build_report
from .rl_view import build_rl_comparison
from .run_views import run_diff, run_metrics
from .sensitivity_view import build_sensitivity

PREFIX = "/api/v3"
_NOT_AVAILABLE = "Not available yet"
_UPLOAD_CHUNK = 1024 * 1024

logger = logging.getLogger(__name__)


class ImportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field("osm", pattern="^osm$")
    place: Optional[str] = Field(None, max_length=200)
    bbox: Optional[List[float]] = Field(None, min_length=4, max_length=4)
    roadClasses: List[str] = Field(
        ..., min_length=1, max_length=len(osm_preview.ROAD_CLASSES)
    )


def create_router(
    user_dependency: Optional[Callable[..., Any]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[ExperimentService] = None,
    locations: Optional[ResultsLocations] = None,
    overpass_fetch: Optional[osm_preview.Fetcher] = None,
) -> APIRouter:
    router = APIRouter(
        prefix=PREFIX, tags=["insights-v3"], dependencies=list(dependencies)
    )
    svc = service or get_service()
    where = locations or ResultsLocations()
    fetch = overpass_fetch or osm_preview.overpass_fetch

    def current_identity(user: Any = Depends(user_dependency)) -> UserIdentity:
        if isinstance(user, UserIdentity):
            return user
        return UserIdentity(user_id=str(user), auth_type="dev", scopes=PAT_SCOPES)

    identity_dep = (
        current_identity
        if user_dependency
        else (
            lambda: UserIdentity(
                user_id="anonymous", auth_type="dev", scopes=PAT_SCOPES
            )
        )
    )

    def reader(identity: UserIdentity = Depends(identity_dep)) -> UserIdentity:
        if not identity.has_scope("experiments:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        return identity

    def not_available() -> HTTPException:
        return HTTPException(status_code=404, detail=_NOT_AVAILABLE)

    def finished_result(identity: UserIdentity, experiment_id: str) -> Dict[str, Any]:
        """The stored result of the caller's own experiment, or 404."""
        record = svc.store.get(identity.user_id, experiment_id)
        result = record.get("result") if record else None
        if not isinstance(result, dict):
            raise not_available()
        return result

    def load_run(run_id: str) -> StoredRun:
        if safe_id(run_id) is None:
            raise not_available()
        try:
            return RunStore(LocalFileBackend(where.root)).load_run(run_id)
        except (RunNotFoundError, ValueError) as err:
            raise not_available() from err
        except (StorageError, OSError, RuntimeError) as err:
            logger.warning("run store unavailable", exc_info=True)
            raise HTTPException(
                status_code=503, detail="The run store is not available"
            ) from err

    def comparison_for(
        identity: UserIdentity,
        experiment_id: str,
        a: Optional[str] = None,
        b: Optional[str] = None,
        metric: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        result = finished_result(identity, experiment_id)
        path = where.experiment_file(experiment_id, "paired.json")
        doc = read_json_object(path) if path else None
        analysis = result.get("analysis")
        eligibility = (
            (analysis.get("eligibility") or {}).get("class")
            if isinstance(analysis, dict)
            else None
        )
        if doc is None:
            return None
        return build_comparison(experiment_id, doc, eligibility, a, b, metric)

    def sensitivity_for(
        identity: UserIdentity, experiment_id: str, metric: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        finished_result(identity, experiment_id)
        path = where.experiment_file(experiment_id, "sensitivity.json")
        doc = read_json_object(path) if path else None
        return build_sensitivity(experiment_id, doc, metric) if doc else None

    @router.get("/experiments/{experiment_id}/comparison")
    def comparison(
        experiment_id: str,
        a: Optional[str] = Query(None, max_length=64),
        b: Optional[str] = Query(None, max_length=64),
        metric: Optional[str] = Query(None, max_length=64),
        identity: UserIdentity = Depends(reader),
    ) -> Dict[str, Any]:
        out = comparison_for(identity, experiment_id, a, b, metric)
        if out is None:
            raise not_available()
        return out

    @router.get("/experiments/{experiment_id}/sensitivity")
    def sensitivity(
        experiment_id: str,
        metric: Optional[str] = Query(None, max_length=64),
        identity: UserIdentity = Depends(reader),
    ) -> Dict[str, Any]:
        out = sensitivity_for(identity, experiment_id, metric)
        if out is None:
            raise not_available()
        return out

    @router.get("/experiments/{experiment_id}/report")
    def report(
        experiment_id: str, identity: UserIdentity = Depends(reader)
    ) -> Dict[str, Any]:
        result = finished_result(identity, experiment_id)
        record = svc.store.get(identity.user_id, experiment_id) or {}
        paired_path = where.experiment_file(experiment_id, "paired.json")
        paired = read_json_object(paired_path) if paired_path else None
        metrics: Optional[Dict[str, Any]] = None
        run_id = paired.get("metricsRunId") if paired else None
        if isinstance(run_id, str):
            try:
                metrics = run_metrics(load_run(run_id))
            except HTTPException as err:
                if err.status_code != 404:
                    raise
        return build_report(
            experiment_id,
            str(record.get("name") or result.get("name") or experiment_id),
            result,
            comparison_for(identity, experiment_id),
            sensitivity_for(identity, experiment_id),
            metrics,
        )

    # Declared before the {run_id} route so "compare" can never be read as a run id.
    @router.get("/runs/compare")
    def compare_runs(
        a: str = Query(..., max_length=128),
        b: str = Query(..., max_length=128),
        identity: UserIdentity = Depends(reader),
    ) -> Dict[str, Any]:
        return run_diff(load_run(a), load_run(b))

    @router.get("/runs/{run_id}/metrics")
    def metrics_of_run(
        run_id: str, identity: UserIdentity = Depends(reader)
    ) -> Dict[str, Any]:
        return run_metrics(load_run(run_id))

    @router.get("/regression/nightly")
    def nightly(
        limit: int = Query(30, ge=1, le=365),
        identity: UserIdentity = Depends(reader),
    ) -> Dict[str, Any]:
        doc = read_json_object(where.nightly_file())
        out = build_nightly(doc, limit) if doc else None
        if out is None:
            raise not_available()
        return out

    @router.get("/loadtests/latest")
    def loadtest_latest(identity: UserIdentity = Depends(reader)) -> Dict[str, Any]:
        doc = read_json_object(where.loadtest_file())
        out = build_loadtest(doc) if doc else None
        if out is None:
            raise not_available()
        return out

    @router.get("/rl/comparisons/{comparison_id}")
    def rl_comparison(
        comparison_id: str, identity: UserIdentity = Depends(reader)
    ) -> Dict[str, Any]:
        path = where.rl_file(comparison_id)
        doc = read_json_object(path) if path else None
        out = build_rl_comparison(comparison_id, doc) if doc else None
        if out is None:
            raise not_available()
        return out

    @router.post("/networks/validate", dependencies=[Depends(compute_slot)])
    async def validate_network(
        file: UploadFile = File(...),
        format: str = Form("auto"),
        identity: UserIdentity = Depends(reader),
    ) -> Dict[str, Any]:
        if format != "auto" and format not in network_view.FORMATS:
            raise HTTPException(status_code=422, detail="Unknown format")
        name = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
        if file.size is not None and file.size > network_view.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="The file is larger than 50 MB")
        try:
            network_view.check_extension(name)
            data = bytearray()
            while chunk := await file.read(_UPLOAD_CHUNK):
                data += chunk
                if len(data) > network_view.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413, detail="The file is larger than 50 MB"
                    )
            return await run_in_threadpool(
                network_view.validate_upload, name, bytes(data), format
            )
        except network_view.UnsupportedFileTypeError as err:
            raise HTTPException(status_code=415, detail=str(err)) from err

    @router.post("/networks/import/preview", dependencies=[Depends(compute_slot)])
    def preview_import(
        payload: ImportPreviewRequest, identity: UserIdentity = Depends(reader)
    ) -> Dict[str, Any]:
        unknown = [c for c in payload.roadClasses if c not in osm_preview.ROAD_CLASSES]
        if unknown:
            raise HTTPException(
                status_code=422, detail=f"Unknown road class: {unknown[0]}"
            )
        try:
            return osm_preview.preview_area(
                payload.place, payload.bbox, payload.roadClasses, fetch
            )
        except osm_preview.PreviewRequestError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        except osm_preview.PreviewUnavailableError as err:
            raise HTTPException(status_code=503, detail=str(err)) from err
        except osm_preview.PreviewUpstreamError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err

    return router


__all__ = ["PREFIX", "create_router"]
