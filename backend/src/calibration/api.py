"""V1.8 endpoints, ``/api/v2/calibration``.

Built by a factory so this package never imports ``main`` (which mounts it):
``main`` passes its own ``require_api_key`` dependency in, plus the signed-in
user and admin dependencies. Every route needs a signed-in user, because the
browser proxy attaches the API key to every request (so the key alone
identifies the proxy, not a person). Stored runs belong to their creator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.calibration import store
from src.calibration.rating import THRESHOLDS, THRESHOLDS_VERSION
from src.calibration.runner import (
    CalibrationError,
    fitted_scenario,
    run_calibration,
    validate_calibration_request,
)
from src.request_limits import compute_slot


class CalibrationRequest(BaseModel):
    """A ScenarioDocument, an ``urbanflow-observations`` document and options
    (see calibration/models.py). Kept as plain dicts so validation messages
    come from the same strict models the rest of the system uses."""

    scenario: Dict[str, Any]
    observations: Dict[str, Any]
    options: Optional[Dict[str, Any]] = Field(default=None)


def build_router(
    auth: Callable[..., Any],
    user_dependency: Callable[..., str],
    admin_dependency: Callable[..., bool],
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v2/calibration",
        tags=["calibration"],
        dependencies=[Depends(auth), Depends(user_dependency)],
    )

    def not_found(run_id: str) -> HTTPException:
        return HTTPException(
            status_code=404, detail=f"Calibration run '{run_id}' not found"
        )

    @router.get("/thresholds")
    def thresholds() -> Dict[str, Any]:
        """The rating thresholds applied to every comparison."""
        return {"version": THRESHOLDS_VERSION, "thresholds": THRESHOLDS}

    @router.post("/validate")
    def validate(req: CalibrationRequest) -> Dict[str, Any]:
        """Check observations against the scenario without simulating.
        Always 200; an unusable request comes back with ``valid: false``."""
        return validate_calibration_request(req.model_dump())

    @router.post("/runs", status_code=201, dependencies=[Depends(compute_slot)])
    def create_run(
        req: CalibrationRequest, user: str = Depends(user_dependency)
    ) -> Dict[str, Any]:
        """Simulate the scenario over the requested seeds, compare with the
        observations, store and return the result."""
        payload = req.model_dump()
        try:
            result = run_calibration(payload)
        except CalibrationError as err:
            raise HTTPException(status_code=400, detail="; ".join(err.errors))
        return store.save(payload, result, user)

    @router.get("/runs")
    def list_runs(
        limit: int = 50,
        user: str = Depends(user_dependency),
        admin: bool = Depends(admin_dependency),
    ) -> Dict[str, Any]:
        """The caller's runs (every run for an admin)."""
        return {"runs": store.list_runs(user, admin, max(1, min(200, limit)))}

    @router.get("/runs/{run_id}")
    def get_run(
        run_id: str,
        user: str = Depends(user_dependency),
        admin: bool = Depends(admin_dependency),
    ) -> Dict[str, Any]:
        found = store.get_for_user(run_id, user, admin)
        if found is None:
            raise not_found(run_id)
        return found

    @router.delete("/runs/{run_id}")
    def delete_run(
        run_id: str,
        user: str = Depends(user_dependency),
        admin: bool = Depends(admin_dependency),
    ) -> Dict[str, Any]:
        """Delete a stored run and the observations it holds. Planning
        studies that referenced it keep their own copy of its result, but can
        no longer be reproduced."""
        if not store.delete(run_id, user, admin):
            raise not_found(run_id)
        return {"id": run_id, "deleted": True}

    @router.get("/runs/{run_id}/scenario")
    def get_fitted_scenario(
        run_id: str,
        user: str = Depends(user_dependency),
        admin: bool = Depends(admin_dependency),
    ) -> Dict[str, Any]:
        """The scenario this run simulated (observed inputs written in), ready
        to use as a V2.0 planning subject with ``calibration.runId`` set."""
        found = store.get_for_user(run_id, user, admin)
        if found is None:
            raise not_found(run_id)
        result = found["result"]
        return {
            "id": run_id,
            "scenario": fitted_scenario(found["request"]),
            "fingerprint": result["scenario"]["fittedFingerprint"],
            "originalFingerprint": result["scenario"]["fingerprint"],
            "appliedFit": result["appliedFit"],
            "fieldCalibration": result["fieldCalibration"]["status"],
        }

    return router
