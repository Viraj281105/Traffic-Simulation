"""V1.8 endpoints, ``/api/v2/calibration``.

Built by a factory so this package never imports ``main`` (which mounts it):
``main`` passes its own ``require_api_key`` dependency in.
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


class CalibrationRequest(BaseModel):
    """A ScenarioDocument, an ``urbanflow-observations`` document and options
    (see calibration/models.py). Kept as plain dicts so validation messages
    come from the same strict models the rest of the system uses."""

    scenario: Dict[str, Any]
    observations: Dict[str, Any]
    options: Optional[Dict[str, Any]] = Field(default=None)


def build_router(auth: Callable[..., Any]) -> APIRouter:
    router = APIRouter(
        prefix="/api/v2/calibration",
        tags=["calibration"],
        dependencies=[Depends(auth)],
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

    @router.post("/runs", status_code=201)
    def create_run(req: CalibrationRequest) -> Dict[str, Any]:
        """Simulate the scenario over the requested seeds, compare with the
        observations, store and return the result."""
        payload = req.model_dump()
        try:
            result = run_calibration(payload)
        except CalibrationError as err:
            raise HTTPException(status_code=400, detail="; ".join(err.errors))
        return store.save(payload, result)

    @router.get("/runs")
    def list_runs(limit: int = 50) -> Dict[str, Any]:
        return {"runs": store.list_runs(max(1, min(200, limit)))}

    @router.get("/runs/{run_id}")
    def get_run(run_id: str) -> Dict[str, Any]:
        found = store.get(run_id)
        if found is None:
            raise HTTPException(
                status_code=404, detail=f"Calibration run '{run_id}' not found"
            )
        return found

    @router.get("/runs/{run_id}/scenario")
    def get_fitted_scenario(run_id: str) -> Dict[str, Any]:
        """The scenario this run simulated (observed inputs written in), ready
        to use as a V2.0 planning subject with ``calibration.runId`` set."""
        found = store.get(run_id)
        if found is None:
            raise HTTPException(
                status_code=404, detail=f"Calibration run '{run_id}' not found"
            )
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
