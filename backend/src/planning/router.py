"""``/api/v2/planning`` routes.

``create_router`` takes the auth wiring as arguments so this module imports
nothing from ``main.py`` (no cycle, no edit to shared code). The host app
mounts it with one line::

    from src.planning.router import create_router
    app.include_router(create_router(user_dependency=get_current_user_id,
                                     dependencies=[Depends(require_api_key)]))
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from src.planning.runner import PlanningError
from src.planning.service import NotFound, PlanningService, get_service
from src.study.jobs import TooManyJobsError

PREFIX = "/api/v2/planning"


def create_router(
    user_dependency: Optional[Callable[..., str]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[PlanningService] = None,
) -> APIRouter:
    router = APIRouter(
        prefix=PREFIX, tags=["planning-v2"], dependencies=list(dependencies)
    )
    svc = service or get_service()

    def current_user(user: str = Depends(user_dependency)) -> str:
        return user

    user_dep = current_user if user_dependency else (lambda: "anonymous")

    def _unprocessable(err: PlanningError) -> HTTPException:
        return HTTPException(status_code=422, detail={"errors": err.errors})

    @router.post("/validate")
    def validate(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return svc.validate(payload)

    @router.post("/run")
    def run(
        payload: Dict[str, Any] = Body(...), user: str = Depends(user_dep)
    ) -> Dict[str, Any]:
        try:
            record = svc.run(user, payload)
        except PlanningError as err:
            raise _unprocessable(err) from err
        return svc._public(record, with_result=True)

    @router.post("/jobs", status_code=202)
    def start(
        payload: Dict[str, Any] = Body(...), user: str = Depends(user_dep)
    ) -> Dict[str, Any]:
        try:
            return svc.submit(user, payload)
        except PlanningError as err:
            raise _unprocessable(err) from err
        except TooManyJobsError as err:
            raise HTTPException(status_code=429, detail=str(err)) from err

    @router.get("/{study_id}")
    def get(study_id: str, user: str = Depends(user_dep)) -> Dict[str, Any]:
        try:
            return svc.get(user, study_id)
        except NotFound as err:
            raise HTTPException(
                status_code=404, detail="Planning study not found"
            ) from err

    @router.get("/{study_id}/report")
    def report(
        study_id: str, format: str = "json", user: str = Depends(user_dep)
    ) -> Response:  # noqa: A002
        try:
            out = svc.export(user, study_id, format)
        except NotFound as err:
            raise HTTPException(
                status_code=404, detail="Planning study not found"
            ) from err
        except (PlanningError, ValueError) as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        return Response(
            content=out["content"],
            media_type=out["mediaType"],
            headers={
                "Content-Disposition": f'attachment; filename="{out["filename"]}"'
            },
        )

    @router.post("/{study_id}/reproduce")
    def reproduce(study_id: str, user: str = Depends(user_dep)) -> Dict[str, Any]:
        try:
            return svc.reproduce(user, study_id)
        except NotFound as err:
            raise HTTPException(
                status_code=404, detail="Planning study not found"
            ) from err
        except PlanningError as err:
            raise _unprocessable(err) from err

    return router
