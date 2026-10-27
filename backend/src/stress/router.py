"""``/api/v3/stress`` routes (W8). Same guards as the rest of ``/api/v3``."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException

from src.api.auth import PAT_SCOPES, UserIdentity
from src.experiments.service import ConflictError, NotFound, QuotaExceeded, get_service

from .classify import rules
from .generator import FAMILIES, GENERATOR_VERSION, MAX_SCENARIOS
from .service import BreakpointRequest, StressService, SuiteRequest

_NOT_FOUND = "Job not found"


def create_router(
    user_dependency: Optional[Callable[..., Any]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[StressService] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v3/stress", tags=["stress-v3"], dependencies=list(dependencies)
    )
    lab = service or StressService(get_service())

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

    @router.get("/catalogue")
    def catalogue(identity: UserIdentity = Depends(identity_dep)) -> Dict[str, Any]:
        need(identity, "experiments:read")
        return {
            "generator": GENERATOR_VERSION,
            "families": list(FAMILIES),
            "maxScenarios": MAX_SCENARIOS,
            "failureRules": rules(),
        }

    @router.post("/suites", status_code=202)
    def suite(
        req: SuiteRequest = Body(...), identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        need(identity, "experiments:run")
        try:
            return lab.submit_suite(identity.user_id, req)
        except QuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err

    @router.post("/breakpoints", status_code=202)
    def breakpoints(
        req: BreakpointRequest = Body(...),
        identity: UserIdentity = Depends(identity_dep),
    ) -> Dict[str, Any]:
        need(identity, "experiments:run")
        try:
            return lab.submit_breakpoints(identity.user_id, req)
        except QuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err
        except ConflictError as err:
            raise HTTPException(status_code=422, detail=str(err)) from err

    @router.get("/jobs")
    def jobs(identity: UserIdentity = Depends(identity_dep)) -> List[Dict[str, Any]]:
        need(identity, "experiments:read")
        return lab.list_for_user(identity.user_id)

    @router.get("/jobs/{job_id}")
    def status(
        job_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        need(identity, "experiments:read")
        try:
            return lab.status(identity.user_id, job_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err

    @router.get("/jobs/{job_id}/result")
    def result(
        job_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        need(identity, "experiments:read")
        try:
            return lab.result(identity.user_id, job_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err

    @router.post("/jobs/{job_id}/cancel", status_code=202)
    def cancel(
        job_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> Dict[str, Any]:
        need(identity, "experiments:run")
        try:
            return lab.cancel(identity.user_id, job_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ConflictError as err:
            raise HTTPException(status_code=409, detail=str(err)) from err

    return router
