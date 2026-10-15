"""``/api/v3`` routes: experiments and capabilities.

``create_router`` takes the auth wiring as arguments so this module imports nothing from ``main.py``. The
host app mounts it with one call::

    app.include_router(
        build_experiments_router(
            user_dependency=get_current_user_id,
            dependencies=[Depends(require_api_key)],
        )
    )

Every route, ``capabilities`` included, takes the signed-in user: the browser proxy attaches the API key to
every request, so the key alone does not identify a person. There is no administrator dependency: a v3
resource is private to its owner (ADR-013).

Status codes: 202 accepted, 404 unknown *or someone else's* id, 409 wrong state (no result yet, cannot
delete a running experiment), 413 body too large (middleware), 422 invalid request or an experiment-size
quota (the message names the quota), 429 a running/stored-experiments quota.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from . import limits
from .models import ExperimentList, ExperimentStatus
from .service import (
    ConflictError,
    ExperimentError,
    ExperimentService,
    NotFound,
    QuotaExceeded,
    get_service,
)

PREFIX = "/api/v3"
_NOT_FOUND = "Experiment not found"

# The body is read as a plain object so that errors come back as readable messages; its shape is the
# ``urbanflow-experiment`` v1 document (shared/schemas/v3/experiment.schema.json).
_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "title": "ExperimentRequest",
                    "description": "An urbanflow-experiment v1 document; see "
                    "shared/schemas/v3/experiment.schema.json.",
                }
            }
        },
    }
}


def create_router(
    user_dependency: Optional[Callable[..., str]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[ExperimentService] = None,
) -> APIRouter:
    router = APIRouter(
        prefix=PREFIX, tags=["experiments-v3"], dependencies=list(dependencies)
    )
    svc = service or get_service()

    def current_user(user: str = Depends(user_dependency)) -> str:
        return user

    user_dep = current_user if user_dependency else (lambda: "anonymous")

    @router.get("/capabilities")
    def capabilities(user: str = Depends(user_dep)) -> Dict[str, Any]:
        return svc.capabilities()

    @router.post("/experiments/validate", openapi_extra=_REQUEST_BODY)
    def validate(
        payload: Dict[str, Any] = Body(...), user: str = Depends(user_dep)
    ) -> Dict[str, Any]:
        """Check a request and report its size without running anything."""
        return svc.validate(payload)

    @router.post(
        "/experiments",
        status_code=202,
        response_model=ExperimentStatus,
        openapi_extra=_REQUEST_BODY,
    )
    def submit(
        payload: Dict[str, Any] = Body(...), user: str = Depends(user_dep)
    ) -> Dict[str, Any]:
        try:
            return svc.submit(user, payload)
        except ExperimentError as err:
            raise HTTPException(status_code=422, detail={"errors": err.errors}) from err
        except QuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err

    @router.get("/experiments", response_model=ExperimentList)
    def list_experiments(
        limit: int = Query(limits.DEFAULT_PAGE_SIZE, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user: str = Depends(user_dep),
    ) -> Dict[str, Any]:
        return svc.list_experiments(user, limit, offset)

    @router.get("/experiments/{experiment_id}", response_model=ExperimentStatus)
    def status(experiment_id: str, user: str = Depends(user_dep)) -> Dict[str, Any]:
        try:
            return svc.status(user, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err

    @router.get("/experiments/{experiment_id}/result")
    def result(experiment_id: str, user: str = Depends(user_dep)) -> Dict[str, Any]:
        try:
            return svc.result(user, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err

    @router.delete("/experiments/{experiment_id}")
    def delete(experiment_id: str, user: str = Depends(user_dep)) -> Dict[str, Any]:
        try:
            svc.delete(user, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        return {"id": experiment_id, "deleted": True}

    return router


__all__ = ["PREFIX", "create_router"]
