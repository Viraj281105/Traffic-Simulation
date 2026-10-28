"""``/api/v3/discovery`` routes (W6). Same guards as the rest of ``/api/v3``."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from src.api.auth import PAT_SCOPES, UserIdentity
from src.api.store import AuditStore
from src.experiments.package import PackageTooLarge
from src.experiments.service import ConflictError, NotFound, QuotaExceeded, get_service

from .models import (
    SearchSpec,
    describe_objectives,
    planned_runs,
    planned_simulated_seconds,
)
from .service import DiscoveryService

logger = logging.getLogger(__name__)
_NOT_FOUND = "Search not found"


def _audit(**event: Any) -> None:
    try:
        AuditStore.record_event(**event)
    except Exception:  # noqa: BLE001 - an audit failure never fails the request
        logger.warning("audit event not recorded", exc_info=True)


def create_router(
    user_dependency: Optional[Callable[..., Any]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[DiscoveryService] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v3/discovery",
        tags=["discovery-v3"],
        dependencies=list(dependencies),
    )
    lab = service or DiscoveryService(get_service())

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

    def need(identity: UserIdentity, scope: str) -> None:
        if not identity.has_scope(scope):
            raise HTTPException(status_code=403, detail="Insufficient token scope")

    @router.post("/estimate")
    def estimate(
        spec: SearchSpec = Body(...), identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        """The budget a specification would reserve, without starting anything."""
        need(identity, "experiments:read")
        return {
            "runs": planned_runs(spec),
            "simulatedSeconds": planned_simulated_seconds(spec),
            "specFingerprint": spec.fingerprint(),
            "wallTime": "unverified",
            **describe_objectives(),
        }

    @router.post("/searches", status_code=202)
    def submit(
        spec: SearchSpec = Body(...), identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        """Start a bounded search (a background job); the budget is reserved against today's quota."""
        need(identity, "experiments:run")
        try:
            status = lab.submit(identity.user_id, spec)
        except QuotaExceeded as err:
            _audit(
                user_id=identity.user_id,
                event_type="quota_rejected",
                token_id=identity.token_id,
                details={"quota": str(err)},
            )
            raise HTTPException(status_code=429, detail=str(err)) from err
        _audit(
            user_id=identity.user_id,
            event_type="experiment_submitted",
            token_id=identity.token_id,
            details={"search_id": status["id"], "source": "discovery"},
        )
        return status

    @router.get("/searches")
    def list_searches(
        identity: UserIdentity = Depends(identity_dep),
    ) -> List[Dict[str, Any]]:
        need(identity, "experiments:read")
        return lab.list_for_user(identity.user_id)

    @router.get("/searches/{search_id}")
    def status(
        search_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        need(identity, "experiments:read")
        try:
            return lab.status(identity.user_id, search_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err

    @router.get("/searches/{search_id}/result")
    def result(
        search_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        need(identity, "experiments:read")
        try:
            return lab.result(identity.user_id, search_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err

    @router.post("/searches/{search_id}/cancel", status_code=202)
    def cancel(
        search_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        """Stop at the next batch boundary; the result so far stays consistent and is marked incomplete."""
        need(identity, "experiments:run")
        try:
            view = lab.cancel(identity.user_id, search_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        _audit(
            user_id=identity.user_id,
            event_type="experiment_cancelled",
            token_id=identity.token_id,
            details={"search_id": search_id},
        )
        return view

    @router.get(
        "/searches/{search_id}/package",
        responses={
            200: {
                "content": {"application/zip": {}},
                "description": "The .ufpkg archive.",
            }
        },
    )
    def package(
        search_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Response:
        need(identity, "packages:read")
        try:
            data, filename = lab.package(identity.user_id, search_id)
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
            details={"search_id": search_id, "bytes": len(data)},
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

    return router
