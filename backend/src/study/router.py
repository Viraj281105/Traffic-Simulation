"""``/api/v1/study/*``: volume sweeps, statistical validation, the signal
control comparison and the study report, run synchronously or as background
jobs.

The job routes start the same studies in the background: the POST returns at
once with a job id, and GET /api/v1/study/jobs/{id} reports live progress and
finally the result (study/jobs.py). The dashboards use these; the
synchronous endpoints remain for scripts and existing clients.
"""

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from src.api.request_limits import (
    PageLimit,
    PageOffset,
    compute_slot,
)
from src.api.security import require_api_key
from src.database.dao import SweepSessionDAO
from src.database.db import ensure_db_initialized, get_db_connection
from src.live.dashboard_config import compile_dashboard_config
from src.scenario.config_validation import semantic_config_errors
from src.scenario.documents import STRATEGIES, parse_scenario, validate_scenario
from src.study.control_comparison import (
    run_control_comparison,
    run_scenario_comparison,
)
from src.study.jobs import TooManyJobsError, jobs
from src.study.limits import (
    MAX_CONTROL_COMPARISON_DURATION_SECONDS,
    MAX_CONTROL_COMPARISON_SEEDS,
    MAX_MONTE_CARLO_SEEDS,
    MAX_STUDY_DURATION_SECONDS,
    MAX_SWEEP_ARRIVAL_RATES,
    MIN_STUDY_DURATION_SECONDS,
    StudyArrivalRate,
    check_study_time_step,
)
from src.study.report_generator import (
    generate_study_report_csv,
    generate_study_report_json,
)
from src.study.runner import Progress
from src.study.validation import (
    SUPPORTED_CONFIDENCE_LEVELS,
    run_invariant_checks,
    run_statistical_validation,
)
from src.study.volume_sweep import run_volume_sweep_experiment

router = APIRouter()


class VolumeSweepRequest(BaseModel):
    arrivalRates: list[StudyArrivalRate] | None = Field(
        default=None, max_length=MAX_SWEEP_ARRIVAL_RATES
    )
    duration: float = Field(
        default=60.0, ge=MIN_STUDY_DURATION_SECONDS, le=MAX_STUDY_DURATION_SECONDS
    )
    randomSeed: int = Field(default=42, ge=0)
    name: str = Field(default="Comparative Volume Sweep", max_length=200)
    customConfig: Dict[str, Any] | None = None

    @model_validator(mode="after")
    def _time_step_in_bounds(self) -> "VolumeSweepRequest":
        check_study_time_step(self.customConfig)
        return self


class MonteCarloValidationRequest(BaseModel):
    numSeeds: int = Field(default=5, ge=1, le=MAX_MONTE_CARLO_SEEDS)
    # Confidence level of the intervals and (as alpha = 1 - level) of the
    # significance flags. One of 0.90 / 0.95 / 0.99.
    confidenceLevel: float = Field(default=0.95)
    duration: float = Field(
        default=30.0, ge=MIN_STUDY_DURATION_SECONDS, le=MAX_STUDY_DURATION_SECONDS
    )
    customConfig: Dict[str, Any] | None = None
    # The dashboard's own scenario payload (the body of /api/simulation/config).
    # When given, the study repeats exactly that scenario — same geometry,
    # demand, timings, warm-up and duration — over fresh seeds, so a
    # "how reliable is this result?" check answers for the scenario the user
    # actually ran rather than for a fixed study scenario. Its own duration
    # then applies; ``duration`` and ``customConfig`` are not used with it.
    scenario: Dict[str, Any] | None = None

    @model_validator(mode="after")
    def _time_step_in_bounds(self) -> "MonteCarloValidationRequest":
        check_study_time_step(self.customConfig)
        if self.confidenceLevel not in SUPPORTED_CONFIDENCE_LEVELS:
            raise ValueError(
                f"confidenceLevel must be one of {list(SUPPORTED_CONFIDENCE_LEVELS)}"
            )
        if self.scenario is not None and self.customConfig is not None:
            raise ValueError("Send either scenario or customConfig, not both")
        return self


class RepeatabilityValidationRequest(BaseModel):
    duration: float = Field(
        default=20.0, ge=MIN_STUDY_DURATION_SECONDS, le=MAX_STUDY_DURATION_SECONDS
    )
    randomSeed: int = Field(default=12345, ge=0)


DemandLevelName = Literal["light", "moderate", "busy", "near", "capacity", "over"]


class ControlComparisonRequest(BaseModel):
    lanes: int = Field(default=1, ge=1, le=3)
    levels: list[DemandLevelName] | None = Field(
        default=None, min_length=1, max_length=6
    )
    numSeeds: int = Field(default=5, ge=2, le=MAX_CONTROL_COMPARISON_SEEDS)
    baseSeed: int = Field(default=1, ge=0, le=1_000_000)
    duration: float = Field(
        default=300.0, ge=60.0, le=MAX_CONTROL_COMPARISON_DURATION_SECONDS
    )
    # controller.adaptive settings for the adaptive side; defaults if omitted.
    adaptive: Dict[str, Any] | None = None
    vehicleMix: Dict[str, float] | None = None
    confidenceLevel: float = Field(default=0.95)
    # V1.4: study a scenario document instead of the built-in junction. Its
    # own approaches, lanes, traffic, vehicles, duration and seed are used;
    # lanes / levels / duration / adaptive / vehicleMix above must then be
    # left unset (they describe the built-in junction). ``demandScales``
    # optionally repeats the study with all demand scaled.
    scenario: Dict[str, Any] | None = None
    strategies: list[Literal["fixed_time", "adaptive", "roundabout"]] | None = Field(
        default=None, min_length=2, max_length=3
    )
    demandScales: list[float] | None = Field(default=None, min_length=1, max_length=6)

    @model_validator(mode="after")
    def _check(self) -> "ControlComparisonRequest":
        if self.confidenceLevel not in SUPPORTED_CONFIDENCE_LEVELS:
            raise ValueError(
                f"confidenceLevel must be one of {list(SUPPORTED_CONFIDENCE_LEVELS)}"
            )
        if self.scenario is not None:
            built_in = sorted(
                key
                for key in ("lanes", "levels", "duration", "adaptive", "vehicleMix")
                if key in self.model_fields_set
            )
            if built_in:
                raise ValueError(
                    f"{', '.join(built_in)} describe the built-in junction; with a "
                    "scenario, set them in the scenario instead"
                )
            strategies = list(self.strategies or STRATEGIES)
            if len(set(strategies)) != len(strategies):
                raise ValueError("strategies must not repeat")
            for scale in self.demandScales or []:
                if not 0.1 <= scale <= 3.0:
                    raise ValueError("demandScales must each be between 0.1 and 3")
            result = validate_scenario(self.scenario, strategies)
            if not result["valid"]:
                raise ValueError("; ".join(result["errors"]))
            duration = (
                (result.get("scenario") or {}).get("simulation", {}).get("duration", 0)
            )
            if duration > MAX_CONTROL_COMPARISON_DURATION_SECONDS:
                raise ValueError(
                    f"scenario simulation.duration must be at most "
                    f"{MAX_CONTROL_COMPARISON_DURATION_SECONDS:g} s for a study"
                )
            return self
        if self.strategies is not None or self.demandScales is not None:
            raise ValueError("strategies and demandScales apply only with a scenario")
        if self.levels is not None and len(set(self.levels)) != len(self.levels):
            raise ValueError("levels must not repeat")
        probe: Dict[str, Any] = {
            "geometry": {"intersectionType": "fixed_time_signal"},
            "controller": {
                "signalControl": "adaptive",
                "adaptive": self.adaptive or {},
            },
        }
        if self.vehicleMix is not None:
            probe["vehicleGeneration"] = {"vehicleMix": self.vehicleMix}
        errors = semantic_config_errors(probe)
        if errors:
            raise ValueError("; ".join(errors))
        return self


def start_job(kind: str, work: Any) -> Dict[str, Any]:
    """Submits ``work(progress)`` as a background study job (429 when the job
    registry is full)."""
    try:
        return jobs.submit(kind, work).to_dict()
    except TooManyJobsError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


# ── Volume sweeps ───────────────────────────────────────────────────────────
def _run_sweep(
    req: VolumeSweepRequest, progress: Optional[Progress] = None
) -> Dict[str, Any]:
    return run_volume_sweep_experiment(
        arrival_rates=req.arrivalRates,
        duration=req.duration,
        random_seed=req.randomSeed,
        custom_config=req.customConfig,
        name=req.name,
        progress=progress,
    )


@router.post(
    "/api/v1/study/sweeps/run",
    dependencies=[Depends(require_api_key), Depends(compute_slot)],
)
def run_sweep_endpoint(payload: VolumeSweepRequest | None = None) -> Dict[str, Any]:
    """Runs an automated traffic volume sweep comparing Signals vs. Roundabouts."""
    return _run_sweep(payload or VolumeSweepRequest())


@router.post(
    "/api/v1/study/sweeps/jobs",
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
def start_sweep_job(payload: VolumeSweepRequest | None = None) -> Dict[str, Any]:
    req = payload or VolumeSweepRequest()
    return start_job("sweep", lambda progress: _run_sweep(req, progress))


@router.get("/api/v1/study/jobs/{job_id}")
def get_study_job(job_id: str) -> Dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Study job not found")
    return job.to_dict()


@router.get("/api/v1/study/sweeps")
def list_sweeps_endpoint(
    limit: PageLimit = 20, offset: PageOffset = 0
) -> list[Dict[str, Any]]:
    """Lists past volume sweep benchmark experiments."""
    ensure_db_initialized()
    with get_db_connection() as conn:
        return SweepSessionDAO.list_sessions(conn, limit=limit, offset=offset)
    return []


@router.get("/api/v1/study/sweeps/{sweep_id}")
def get_sweep_endpoint(sweep_id: str) -> Dict[str, Any]:
    """Retrieves a specific volume sweep benchmark session."""
    ensure_db_initialized()
    with get_db_connection() as conn:
        session = SweepSessionDAO.get(conn, sweep_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sweep session not found")
        res = dict(session)
        if isinstance(session.get("results"), dict):
            for k, v in session["results"].items():
                if k not in res:
                    res[k] = v
        if "sessionId" not in res:
            res["sessionId"] = res.get("id", sweep_id)
        return res
    raise HTTPException(status_code=500, detail="Database connection error")


# ── Validation ──────────────────────────────────────────────────────────────
@router.post(
    "/api/v1/study/validate/repeatability",
    dependencies=[Depends(require_api_key), Depends(compute_slot)],
)
def validate_repeatability_endpoint(
    payload: RepeatabilityValidationRequest | None = None,
) -> Dict[str, Any]:
    """Verifies physical invariants, mass conservation, and deterministic seed repeatability."""
    req = payload or RepeatabilityValidationRequest()
    return run_invariant_checks(
        duration=req.duration,
        random_seed=req.randomSeed,
    )


@router.post(
    "/api/v1/study/validate/monte-carlo",
    dependencies=[Depends(require_api_key), Depends(compute_slot)],
)
def validate_monte_carlo_endpoint(
    payload: MonteCarloValidationRequest | None = None,
) -> Dict[str, Any]:
    """Runs multi-seed Monte Carlo statistical validation with confidence intervals."""
    return _run_monte_carlo(payload or MonteCarloValidationRequest())


@router.post(
    "/api/v1/study/validate/monte-carlo/jobs",
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
def start_monte_carlo_job(
    payload: MonteCarloValidationRequest | None = None,
) -> Dict[str, Any]:
    req = payload or MonteCarloValidationRequest()
    return start_job(
        "monte-carlo", lambda progress: _run_monte_carlo(req, progress=progress)
    )


def _run_monte_carlo(req: MonteCarloValidationRequest, **extra: Any) -> Dict[str, Any]:
    if req.scenario is not None:
        # Compiled as the comparison view compiles it: the signal side's
        # timings in "controller", the roundabout's gap acceptance in
        # "roundaboutController" (DualSimulationOrchestrator splits them).
        # The seed is a placeholder; every repetition draws its own.
        config = compile_dashboard_config(
            {**req.scenario, "intersectionType": "fixed_time_signal"}, seed_val=0
        )
        return run_statistical_validation(
            config=config,
            num_seeds=req.numSeeds,
            duration=float(config["simulation"]["duration"]),
            confidence_level=req.confidenceLevel,
            **extra,
        )
    return run_statistical_validation(
        config=req.customConfig,
        num_seeds=req.numSeeds,
        duration=req.duration,
        confidence_level=req.confidenceLevel,
        **extra,
    )


# ── Signal control comparison (V1.3) ────────────────────────────────────────
def _run_control_comparison(
    req: ControlComparisonRequest, progress: Optional[Progress] = None
) -> Dict[str, Any]:
    if req.scenario is not None:
        document, _ = parse_scenario(req.scenario)
        return run_scenario_comparison(
            document,
            list(req.strategies or STRATEGIES),
            num_seeds=req.numSeeds,
            # Seeds start from the scenario's own unless baseSeed is given.
            base_seed=req.baseSeed if "baseSeed" in req.model_fields_set else None,
            demand_scales=req.demandScales,
            confidence_level=req.confidenceLevel,
            progress=progress,
        )
    return run_control_comparison(
        lanes=req.lanes,
        levels=list(req.levels) if req.levels else None,
        num_seeds=req.numSeeds,
        base_seed=req.baseSeed,
        duration=req.duration,
        adaptive=req.adaptive,
        vehicle_mix=req.vehicleMix,
        confidence_level=req.confidenceLevel,
        progress=progress,
    )


@router.post(
    "/api/v1/study/control-comparison/run",
    dependencies=[Depends(require_api_key), Depends(compute_slot)],
)
def run_control_comparison_endpoint(
    payload: ControlComparisonRequest | None = None,
) -> Dict[str, Any]:
    """Fixed-time vs adaptive signal vs roundabout, run synchronously."""
    return _run_control_comparison(payload or ControlComparisonRequest())


@router.post(
    "/api/v1/study/control-comparison/jobs",
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
def start_control_comparison_job(
    payload: ControlComparisonRequest | None = None,
) -> Dict[str, Any]:
    req = payload or ControlComparisonRequest()
    return start_job(
        "control-comparison", lambda progress: _run_control_comparison(req, progress)
    )


# Protected like the other study routes: building this report runs a fresh
# 16-simulation volume sweep plus a Monte-Carlo validation and persists the
# sweep to run history. As an open GET it let any caller do both on a deployment
# whose POST study endpoints require the API key.
@router.get(
    "/api/v1/study/export",
    dependencies=[Depends(require_api_key), Depends(compute_slot)],
)
def export_study_report_endpoint(format: str = "json") -> Any:  # noqa: A002
    """Exports full comprehensive validated study dataset in JSON or CSV format."""
    if format.lower() == "csv":
        csv_content = generate_study_report_csv()
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=traffic_simulation_study_v1.csv"
            },
        )
    return generate_study_report_json()
