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

import logging
from typing import Any, Callable, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from src.api.auth import PAT_SCOPES, UserIdentity
from src.api.contracts_v3 import PackageVerificationReport
from src.api.request_limits import MAX_V2_BODY_BYTES, compute_slot
from src.api.store import AuditStore

from . import limits
from .models import ExperimentList, ExperimentStatus
from .package import PackageTooLarge, inspect_package
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

# A package is uploaded as the raw body: no multipart parser sits in front of the size cap.
_PACKAGE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/octet-stream": {
                "schema": {
                    "type": "string",
                    "format": "binary",
                    "description": "A .ufpkg archive, at most "
                    f"{limits.MAX_PACKAGE_BYTES} bytes.",
                }
            }
        },
    }
}
_PACKAGE_RESPONSE: Dict[int | str, Dict[str, Any]] = {
    200: {
        "content": {
            "application/zip": {"schema": {"type": "string", "format": "binary"}}
        },
        "description": "The .ufpkg archive.",
    }
}

logger = logging.getLogger(__name__)


def _audit(**event: Any) -> None:
    """Record an audit event without ever failing the request: like experiment
    persistence, a broken database must not turn an accepted experiment into an
    error. The failure is logged."""
    try:
        AuditStore.record_event(**event)
    except Exception:
        logger.warning("audit event not recorded", exc_info=True)


def create_router(
    user_dependency: Optional[Callable[..., Any]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[ExperimentService] = None,
) -> APIRouter:
    router = APIRouter(
        prefix=PREFIX, tags=["experiments-v3"], dependencies=list(dependencies)
    )
    svc = service or get_service()

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

    @router.get("/capabilities")
    def capabilities(identity: UserIdentity = Depends(identity_dep)) -> Dict[str, Any]:
        if not identity.has_scope("experiments:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        return svc.capabilities(MAX_V2_BODY_BYTES)

    @router.post("/experiments/validate", openapi_extra=_REQUEST_BODY)
    def validate(
        payload: Dict[str, Any] = Body(...),
        identity: UserIdentity = Depends(identity_dep),
    ) -> Dict[str, Any]:
        """Check a request and report its size without running anything."""
        if not identity.has_scope("experiments:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        return svc.validate(payload)

    @router.post(
        "/experiments",
        status_code=202,
        response_model=ExperimentStatus,
        openapi_extra=_REQUEST_BODY,
    )
    def submit(
        payload: Dict[str, Any] = Body(...),
        identity: UserIdentity = Depends(identity_dep),
    ) -> Dict[str, Any]:
        if not identity.has_scope("experiments:run"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            rec = svc.submit(identity.user_id, payload)
            _audit(
                user_id=identity.user_id,
                event_type="experiment_submitted",
                token_id=identity.token_id,
                details={"experiment_id": rec.get("id"), "name": payload.get("name")},
            )
            return rec
        except ExperimentError as err:
            raise HTTPException(status_code=422, detail={"errors": err.errors}) from err
        except QuotaExceeded as err:
            _audit(
                user_id=identity.user_id,
                event_type="quota_rejected",
                token_id=identity.token_id,
                details={"quota": str(err)},
            )
            raise HTTPException(status_code=429, detail=str(err)) from err

    @router.post(
        "/experiments/{experiment_id}/cancel",
        status_code=202,
        response_model=ExperimentStatus,
    )
    def cancel(
        experiment_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        """Stop a queued or running experiment; repeating the request is harmless."""
        if not identity.has_scope("experiments:run"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            view = svc.cancel(identity.user_id, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        _audit(
            user_id=identity.user_id,
            event_type="experiment_cancelled",
            token_id=identity.token_id,
            details={"experiment_id": experiment_id},
        )
        return view

    @router.post(
        "/experiments/{experiment_id}/resume",
        status_code=202,
        response_model=ExperimentStatus,
    )
    def resume(
        experiment_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        """Run the unfinished part of a cancelled experiment."""
        if not identity.has_scope("experiments:run"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            view = svc.resume(identity.user_id, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ExperimentError as err:
            raise HTTPException(status_code=422, detail={"errors": err.errors}) from err
        except QuotaExceeded as err:
            _audit(
                user_id=identity.user_id,
                event_type="quota_rejected",
                token_id=identity.token_id,
                details={"quota": str(err)},
            )
            raise HTTPException(status_code=429, detail=str(err)) from err
        return view

    @router.get("/experiments/{experiment_id}/package", responses=_PACKAGE_RESPONSE)
    def export_package(
        experiment_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Response:
        """Download a completed experiment as a portable .ufpkg archive."""
        if not identity.has_scope("packages:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            data, filename = svc.export_package(identity.user_id, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except PackageTooLarge as err:
            raise HTTPException(status_code=413, detail=str(err)) from err
        _audit(
            user_id=identity.user_id,
            event_type="package_exported",
            token_id=identity.token_id,
            details={"experiment_id": experiment_id, "bytes": len(data)},
        )
        return Response(
            content=data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @router.post(
        "/packages/verify",
        response_model=PackageVerificationReport,
        openapi_extra=_PACKAGE_BODY,
        dependencies=[Depends(compute_slot)],
    )
    async def verify_package(
        request: Request, identity: UserIdentity = Depends(identity_dep)
    ) -> PackageVerificationReport:
        """Check an uploaded .ufpkg without running anything or storing it."""
        if not identity.has_scope("packages:write"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        body = await request.body()  # capped by the body-size middleware (10 MB)
        report = await run_in_threadpool(inspect_package, body)
        _audit(
            user_id=identity.user_id,
            event_type="package_verified",
            token_id=identity.token_id,
            details={
                "bytes": len(body),
                "kind": report.kind,
                "consistent": report.internallyConsistent,
                "errors": len(report.errors),
            },
        )
        return report

    @router.get("/experiments", response_model=ExperimentList)
    def list_experiments(
        limit: int = Query(limits.DEFAULT_PAGE_SIZE, ge=1, le=100),
        offset: int = Query(0, ge=0),
        identity: UserIdentity = Depends(identity_dep),
    ) -> Dict[str, Any]:
        if not identity.has_scope("experiments:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        return svc.list_experiments(identity.user_id, limit, offset)

    @router.get("/experiments/{experiment_id}", response_model=ExperimentStatus)
    def status(
        experiment_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        if not identity.has_scope("experiments:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            return svc.status(identity.user_id, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err

    @router.get("/experiments/{experiment_id}/result")
    def result(
        experiment_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        if not identity.has_scope("experiments:read"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            return svc.result(identity.user_id, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err

    @router.delete("/experiments/{experiment_id}")
    def delete(
        experiment_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        if not identity.has_scope("experiments:run"):
            raise HTTPException(status_code=403, detail="Insufficient token scope")
        try:
            svc.delete(identity.user_id, experiment_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        return {"id": experiment_id, "deleted": True}

    return router


__all__ = ["PREFIX", "create_router"]
