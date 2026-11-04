"""``/api/v1/metrics/*`` and ``/api/v1/study/sensitivity``: delay and travel
time, fuel / CO2 estimates, time-to-collision, and input sensitivity.

The metrics routes are stateless calculators over data in the request (the
maths lives in metrics/trip_metrics.py and metrics/trajectory_metrics.py). The
sensitivity route runs the simulation (study/sensitivity.py), synchronously or
as a background job.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from src.api.request_limits import compute_slot
from src.api.security import require_api_key
from src.metrics.trajectory_metrics import (
    DEFAULT_TTC_THRESHOLD_S,
    summarize_emissions,
    summarize_ttc,
)
from src.metrics.trip_metrics import summarize_trips
from src.study.limits import check_study_time_step
from src.study.multiseed import default_study_config
from src.study.router import start_job
from src.study.seeds import MAX_SEED
from src.study.sensitivity import (
    PARAMETER_PATHS,
    one_at_a_time,
    simulation_evaluator,
    sobol_lite,
)

router = APIRouter()

MAX_TRIPS = 100_000
MAX_VEHICLES = 5_000
MAX_SAMPLES_PER_SERIES = 100_000
MAX_SENSITIVITY_INPUTS = len(PARAMETER_PATHS)
MAX_SENSITIVITY_SIM_RUNS = 400
MAX_SENSITIVITY_DURATION_SECONDS = 300.0

# metric key -> engine metric names tried in order (study/multiseed.py)
SENSITIVITY_OUTPUTS: Dict[str, Tuple[str, ...]] = {
    "delay": ("averageDelay", "averageWaitTime"),
    "throughput": ("throughput",),
    "queue": ("averageQueueLength",),
}


# ── Delay and travel time ───────────────────────────────────────────────────
class TripRecord(BaseModel):
    travelTimeS: float = Field(ge=0)
    freeFlowTimeS: Optional[float] = Field(default=None, ge=0)
    distanceM: Optional[float] = Field(default=None, ge=0)
    desiredSpeedMps: Optional[float] = Field(default=None, gt=0)


class TripMetricsRequest(BaseModel):
    trips: List[TripRecord] = Field(max_length=MAX_TRIPS)


@router.post("/api/v1/metrics/trips", dependencies=[Depends(require_api_key)])
def trip_metrics(payload: TripMetricsRequest) -> Dict[str, Any]:
    """Travel-time and delay summary of the given trips."""
    return summarize_trips([t.model_dump() for t in payload.trips])


# ── Fuel and CO2 ────────────────────────────────────────────────────────────
class EmissionsRequest(BaseModel):
    dt: float = Field(gt=0, le=10)
    # One speed series (m/s, one sample per dt seconds) per vehicle.
    speedsMps: List[List[float]] = Field(max_length=MAX_VEHICLES)

    @model_validator(mode="after")
    def _bounded(self) -> "EmissionsRequest":
        if any(len(s) > MAX_SAMPLES_PER_SERIES for s in self.speedsMps):
            raise ValueError(f"at most {MAX_SAMPLES_PER_SERIES} samples per vehicle")
        return self


@router.post("/api/v1/metrics/emissions", dependencies=[Depends(require_api_key)])
def emissions(payload: EmissionsRequest) -> Dict[str, Any]:
    """Estimated fuel and CO2 (model estimate, not a measurement)."""
    return summarize_emissions(payload.speedsMps, payload.dt)


# ── Time-to-collision ───────────────────────────────────────────────────────
class TtcSample(BaseModel):
    gapM: float
    followerSpeedMps: float = Field(ge=0)
    leaderSpeedMps: float = Field(ge=0)


class TtcRequest(BaseModel):
    dt: float = Field(gt=0, le=10)
    thresholdS: float = Field(default=DEFAULT_TTC_THRESHOLD_S, gt=0, le=60)
    # One series of samples per leader-follower pair.
    pairs: List[List[TtcSample]] = Field(max_length=MAX_VEHICLES)

    @model_validator(mode="after")
    def _bounded(self) -> "TtcRequest":
        if any(len(p) > MAX_SAMPLES_PER_SERIES for p in self.pairs):
            raise ValueError(f"at most {MAX_SAMPLES_PER_SERIES} samples per pair")
        return self


@router.post("/api/v1/metrics/ttc", dependencies=[Depends(require_api_key)])
def ttc(payload: TtcRequest) -> Dict[str, Any]:
    """Time-to-collision safety proxies (not a crash prediction)."""
    return summarize_ttc(
        [[s.model_dump() for s in pair] for pair in payload.pairs],
        payload.dt,
        payload.thresholdS,
    )


# ── Sensitivity ─────────────────────────────────────────────────────────────
class InputRange(BaseModel):
    low: float
    high: float

    @model_validator(mode="after")
    def _ordered(self) -> "InputRange":
        if self.low >= self.high:
            raise ValueError("low must be less than high")
        return self


class SensitivityRequest(BaseModel):
    """Which input (of ``ranges``) moves ``output`` the most, on one geometry."""

    method: Literal["oat", "sobol"] = "oat"
    geometry: Literal["signal", "roundabout"] = "signal"
    output: Literal["delay", "throughput", "queue"] = "delay"
    # Keys must be among the supported inputs (GET .../sensitivity/inputs).
    ranges: Dict[str, InputRange]
    duration: float = Field(
        default=30.0, ge=1.0, le=MAX_SENSITIVITY_DURATION_SECONDS
    )
    numSeeds: int = Field(default=2, ge=1, le=5)
    # Sobol only: base sample size n; the plan costs n * (k + 2) points.
    sobolSamples: int = Field(default=8, ge=2, le=32)
    seed: int = Field(default=0, ge=0, le=MAX_SEED)
    customConfig: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _valid(self) -> "SensitivityRequest":
        check_study_time_step(self.customConfig)
        if not self.ranges:
            raise ValueError("ranges must name at least one input")
        unknown = sorted(set(self.ranges) - set(PARAMETER_PATHS))
        if unknown:
            raise ValueError(
                f"unsupported inputs {unknown}; supported: {sorted(PARAMETER_PATHS)}"
            )
        k = len(self.ranges)
        points = 1 + 2 * k if self.method == "oat" else self.sobolSamples * (k + 2)
        if points * self.numSeeds > MAX_SENSITIVITY_SIM_RUNS:
            raise ValueError(
                f"{points} points x {self.numSeeds} seeds exceeds "
                f"{MAX_SENSITIVITY_SIM_RUNS} simulation runs; reduce inputs, "
                "seeds or sobolSamples"
            )
        return self


def _run_sensitivity(req: SensitivityRequest) -> Dict[str, Any]:
    base = req.customConfig or default_study_config(req.duration)
    evaluate = simulation_evaluator(
        base,
        req.geometry,
        req.duration,
        SENSITIVITY_OUTPUTS[req.output],
        req.numSeeds,
        req.seed,
    )
    bounds = {n: (r.low, r.high) for n, r in req.ranges.items()}
    if req.method == "oat":
        result = one_at_a_time(evaluate, bounds)
    else:
        result = sobol_lite(evaluate, bounds, req.sobolSamples, req.seed)
    return {
        **result,
        "geometry": req.geometry,
        "output": req.output,
        "duration": req.duration,
        "numSeeds": req.numSeeds,
        "baseSeed": req.seed,
    }


@router.get("/api/v1/study/sensitivity/inputs")
def sensitivity_inputs() -> Dict[str, Any]:
    """The inputs the sensitivity analysis can vary and the outputs it can rank."""
    return {
        "inputs": sorted(PARAMETER_PATHS),
        "outputs": sorted(SENSITIVITY_OUTPUTS),
        "methods": ["oat", "sobol"],
    }


@router.post(
    "/api/v1/study/sensitivity",
    dependencies=[Depends(require_api_key), Depends(compute_slot)],
)
def run_sensitivity(payload: SensitivityRequest) -> Dict[str, Any]:
    return _run_sensitivity(payload)


@router.post(
    "/api/v1/study/sensitivity/jobs",
    status_code=202,
    dependencies=[Depends(require_api_key)],
)
def start_sensitivity_job(payload: SensitivityRequest) -> Dict[str, Any]:
    return start_job("sensitivity", lambda _progress: _run_sensitivity(payload))
