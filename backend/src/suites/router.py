"""``/api/suites``: create, list and read suites, run batch experiments into
them and export their runs."""

import io
import uuid
from typing import Annotated, Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from src.api.auth import get_current_user_id, get_current_user_is_admin
from src.api.security import require_api_key
from src.api.validation import check_engine_config_or_400
from src.database.dao import ScenarioSuiteDAO, SimulationRunDAO
from src.database.db import ensure_db_initialized, get_db_connection
from src.live.dashboard_config import compile_dashboard_config
from src.study.batch import run_suite_batch_experiment
from src.study.jobs import TooManyJobsError, jobs
from src.study.limits import (
    MAX_BATCH_SIMULATIONS,
    MAX_MONTE_CARLO_SEEDS,
    MAX_SWEEP_ARRIVAL_RATES,
    StudyArrivalRate,
    check_study_time_step,
)
from src.study.report_generator import generate_suite_csv

router = APIRouter()


class ScenarioSuiteCreate(BaseModel):
    name: str
    description: str
    run_ids: list[str]
    config_variations: Dict[str, Any]


class BatchExperimentRequest(BaseModel):
    # The dashboard's scenario payload (the body of /api/simulation/config),
    # or an engine configuration (one with a "traffic" section).
    baseConfig: Dict[str, Any]
    # The arrival rate is the one parameter a batch varies.
    sweepParameters: Dict[
        Literal["arrivalRate"],
        Annotated[
            list[StudyArrivalRate],
            Field(min_length=1, max_length=MAX_SWEEP_ARRIVAL_RATES),
        ],
    ] = Field(min_length=1)
    numSeeds: int = Field(ge=1, le=MAX_MONTE_CARLO_SEEDS)

    @model_validator(mode="after")
    def _workload_in_bounds(self) -> "BatchExperimentRequest":
        runs = len(self.sweepParameters["arrivalRate"]) * self.numSeeds
        if runs > MAX_BATCH_SIMULATIONS:
            raise ValueError(
                f"A batch may run at most {MAX_BATCH_SIMULATIONS} simulations "
                f"(arrival rates x seeds); this one asks for {runs}"
            )
        return self


def _visible_suite_or_404(
    conn: Any, suite_id: str, user_id: str, is_admin: bool
) -> Dict[str, Any]:
    suite = (
        ScenarioSuiteDAO.get(conn, suite_id)
        if ScenarioSuiteDAO.is_visible(conn, suite_id, user_id, is_admin)
        else None
    )
    if suite is None:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


def _suite_runs(conn: Any, suite: Dict[str, Any]) -> list[Dict[str, Any]]:
    """The suite's run records that still exist, in suite order."""
    runs = []
    for rid in suite["run_ids"]:
        r = SimulationRunDAO.get(conn, rid)
        if r:
            runs.append(r)
    return runs


def _check_runs_can_join_suite(conn: Any, run_ids: list[str], user_id: str) -> None:
    """A new suite may hold only runs that exist, are not another user's and
    are in no other suite (a run records a single ``suite_id``), so a caller
    cannot pull someone else's runs into a suite they can read."""
    for rid in run_ids:
        found = SimulationRunDAO.owner_and_suite(conn, rid)
        owned_by_other = found is not None and found[0] not in (None, user_id)
        if found is None or owned_by_other:
            raise HTTPException(status_code=404, detail=f"Run '{rid}' not found")
        if found[1] is not None:
            raise HTTPException(
                status_code=400, detail=f"Run '{rid}' already belongs to a suite"
            )


def _batch_base_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    """The engine configuration a batch runs, validated like any other run.

    The dashboard sends its flat scenario payload, which is compiled exactly
    as the live comparison compiles it. The batch runner used to receive that
    payload uncompiled and index ``config["traffic"]``, so every batch the
    dashboard started failed in the background job.
    """
    if not isinstance(raw.get("traffic"), dict):
        return compile_dashboard_config(raw, seed_val=0)
    check_engine_config_or_400(raw, raw)
    try:
        check_study_time_step(raw)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return raw


@router.post("/api/suites", dependencies=[Depends(require_api_key)])
def create_suite(
    suite_data: ScenarioSuiteCreate,
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, str]:
    suite_id = str(uuid.uuid4())
    ensure_db_initialized()
    with get_db_connection() as conn:
        _check_runs_can_join_suite(conn, suite_data.run_ids, user_id)
        ScenarioSuiteDAO.save(
            conn,
            suite_id=suite_id,
            name=suite_data.name,
            description=suite_data.description,
            run_ids=suite_data.run_ids,
            config_variations=suite_data.config_variations,
            user_id=user_id,
        )
    return {"id": suite_id}


@router.get("/api/suites")
def list_suites(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id),
    is_admin: bool = Depends(get_current_user_is_admin),
) -> Dict[str, Any]:
    ensure_db_initialized()
    with get_db_connection() as conn:
        suites = ScenarioSuiteDAO.list_suites(
            conn, limit, offset, user_id=user_id, is_admin=is_admin
        )
        return {"suites": suites}


@router.get("/api/suites/{suite_id}")
def get_suite(
    suite_id: str,
    user_id: str = Depends(get_current_user_id),
    is_admin: bool = Depends(get_current_user_is_admin),
) -> Dict[str, Any]:
    ensure_db_initialized()
    with get_db_connection() as conn:
        suite = _visible_suite_or_404(conn, suite_id, user_id, is_admin)
        return {"suite": suite, "runs": _suite_runs(conn, suite)}


@router.post("/api/suites/{suite_id}/batch", dependencies=[Depends(require_api_key)])
def enqueue_suite_batch(
    suite_id: str,
    req: BatchExperimentRequest,
    user_id: str = Depends(get_current_user_id),
    is_admin: bool = Depends(get_current_user_is_admin),
) -> Dict[str, str]:
    base_config = _batch_base_config(req.baseConfig)
    # Checked before any simulation runs, not discovered when the finished
    # runs are attached to it.
    ensure_db_initialized()
    with get_db_connection() as conn:
        suite_owner = ScenarioSuiteDAO.owner_of(conn, suite_id)
        _visible_suite_or_404(conn, suite_id, user_id, is_admin)
    # The runs belong to the suite's owner; an admin running a legacy
    # (unowned) suite owns them, so they are never stored public.
    owner_id = suite_owner or user_id

    arrival_rates = list(req.sweepParameters["arrivalRate"])
    try:
        job = jobs.submit(
            "suite_batch",
            lambda p: run_suite_batch_experiment(
                suite_id=suite_id,
                base_config=base_config,
                arrival_rates=arrival_rates,
                num_seeds=req.numSeeds,
                progress=p,
                owner_id=owner_id,
            ),
        )
    except TooManyJobsError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return {"jobId": job.id}


@router.get("/api/suites/{suite_id}/export/csv")
def export_suite_csv(
    suite_id: str,
    user_id: str = Depends(get_current_user_id),
    is_admin: bool = Depends(get_current_user_is_admin),
) -> StreamingResponse:
    ensure_db_initialized()
    with get_db_connection() as conn:
        suite = _visible_suite_or_404(conn, suite_id, user_id, is_admin)
        runs = _suite_runs(conn, suite)
    csv_data = generate_suite_csv(runs)
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=suite_{suite_id}.csv"},
    )
