"""Observed-data documents (``urbanflow-observations`` v1).

Strict like the scenario document: unknown fields are rejected, nothing is
normalised or filled in. A value the user did not observe is simply absent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.scenario import Mix

OBSERVATIONS_FORMAT = "urbanflow-observations"
CALIBRATION_RESULT_FORMAT = "urbanflow-calibration-result"
CALIBRATION_RESULT_VERSION = 1

ApproachName = Literal["north", "south", "east", "west"]
MovementName = Literal["left", "straight", "right", "uturn"]

# Most simulated seconds one calibration run may cost (seeds x duration).
MAX_SIMULATED_SECONDS = 3000.0
MAX_SEEDS = 10
SHARE_SUM_TOLERANCE = 0.02


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Period(_Strict):
    label: str = Field("", max_length=120)
    durationSeconds: float = Field(3600.0, gt=0, le=86400)
    source: str = Field("", max_length=300)


class ApproachFlow(_Strict):
    approach: ApproachName
    vehiclesPerHour: Optional[float] = Field(None, ge=0, le=20000)
    count: Optional[int] = Field(None, ge=0)
    durationSeconds: Optional[float] = Field(None, gt=0, le=86400)

    @model_validator(mode="after")
    def _one_unit(self) -> "ApproachFlow":
        if (self.vehiclesPerHour is None) == (self.count is None):
            raise ValueError("give exactly one of vehiclesPerHour or count")
        return self

    def vph(self, period_seconds: float) -> float:
        if self.vehiclesPerHour is not None:
            return float(self.vehiclesPerHour)
        assert self.count is not None
        return self.count * 3600.0 / (self.durationSeconds or period_seconds)


class TurningObservation(_Strict):
    """One movement's share of its approach, as a share (0-1) or a count."""

    approach: ApproachName
    movement: MovementName
    share: Optional[float] = Field(None, ge=0, le=1)
    count: Optional[int] = Field(None, ge=0)

    @model_validator(mode="after")
    def _one_unit(self) -> "TurningObservation":
        if (self.share is None) == (self.count is None):
            raise ValueError("give exactly one of share or count")
        return self


class SignalObservation(_Strict):
    # Mean green interval per phase, as timed in the field (seconds).
    averageGreenSeconds: float = Field(..., gt=0, le=300)


class QueueObservation(_Strict):
    approach: ApproachName
    meanVehicles: Optional[float] = Field(None, ge=0, le=500)
    maxVehicles: Optional[float] = Field(None, ge=0, le=500)

    @model_validator(mode="after")
    def _some(self) -> "QueueObservation":
        if self.meanVehicles is None and self.maxVehicles is None:
            raise ValueError("give meanVehicles, maxVehicles or both")
        return self


class TravelTimeObservation(_Strict):
    approach: ApproachName
    movement: Optional[MovementName] = None
    meanSeconds: float = Field(..., gt=0, le=3600)
    samples: Optional[int] = Field(None, ge=1)


def _no_duplicates(name: str, keys: List[object]) -> None:
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name}: each approach/movement may be given once")


class ObservationSet(_Strict):
    format: Literal["urbanflow-observations"] = "urbanflow-observations"
    version: Literal[1] = 1
    name: str = Field("Observations", max_length=120)
    period: Period = Field(default_factory=lambda: Period.model_validate({}))
    # If set, must equal the scenario's fingerprint: the observations were
    # collected for exactly this scenario.
    scenarioFingerprint: Optional[str] = Field(None, max_length=64)
    approachFlows: List[ApproachFlow] = Field(default_factory=list)
    turningMovements: List[TurningObservation] = Field(default_factory=list)
    vehicleMix: Optional[Mix] = None
    signal: Optional[SignalObservation] = None
    queues: List[QueueObservation] = Field(default_factory=list)
    travelTimes: List[TravelTimeObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "ObservationSet":
        if not (
            self.approachFlows
            or self.turningMovements
            or self.vehicleMix
            or self.signal
            or self.queues
            or self.travelTimes
        ):
            raise ValueError("no observations: supply at least one series")
        _no_duplicates("approachFlows", [f.approach for f in self.approachFlows])
        _no_duplicates(
            "turningMovements",
            [(t.approach, t.movement) for t in self.turningMovements],
        )
        _no_duplicates("queues", [q.approach for q in self.queues])
        _no_duplicates(
            "travelTimes", [(t.approach, t.movement) for t in self.travelTimes]
        )
        grouped: Dict[str, List[TurningObservation]] = {}
        for t in self.turningMovements:
            grouped.setdefault(t.approach, []).append(t)
        for approach, items in grouped.items():
            kinds = {t.share is not None for t in items}
            if len(kinds) > 1:
                raise ValueError(
                    f"turningMovements for {approach}: use shares or counts, not both"
                )
            if kinds == {True}:
                total = sum(t.share or 0.0 for t in items)
                if abs(total - 1.0) > SHARE_SUM_TOLERANCE:
                    raise ValueError(
                        f"turning shares for {approach} sum to {total:.3f}, "
                        "expected 1 (supply every movement; shares are not rescaled)"
                    )
        if self.vehicleMix is not None:
            total = sum(self.vehicleMix.model_dump().values())
            if abs(total - 1.0) > SHARE_SUM_TOLERANCE:
                raise ValueError(
                    f"vehicleMix shares sum to {total:.3f}, expected 1 (not rescaled)"
                )
        return self

    def flow_vph(self) -> Dict[str, float]:
        return {
            f.approach: f.vph(self.period.durationSeconds) for f in self.approachFlows
        }

    def turning_shares(self) -> Dict[str, Dict[str, float]]:
        """{approach: {movement: share}} over the movements supplied. Counts
        become shares of the movements supplied for that approach."""
        grouped: Dict[str, List[TurningObservation]] = {}
        for t in self.turningMovements:
            grouped.setdefault(t.approach, []).append(t)
        out: Dict[str, Dict[str, float]] = {}
        for approach, items in grouped.items():
            if items[0].share is not None:
                out[approach] = {t.movement: float(t.share or 0.0) for t in items}
            else:
                total = sum(t.count or 0 for t in items)
                out[approach] = {
                    t.movement: (t.count or 0) / total if total else 0.0 for t in items
                }
        return out

    def mix_shares(self) -> Dict[str, float]:
        """The classes the user supplied, with their shares."""
        if self.vehicleMix is None:
            return {}
        given = self.vehicleMix.model_fields_set
        return {
            k: float(v) for k, v in self.vehicleMix.model_dump().items() if k in given
        }


def observations_fingerprint(obs: ObservationSet) -> str:
    """Short stable hash of what was observed (the name is excluded)."""
    body = obs.model_dump(exclude={"name"})
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class CalibrationOptions(_Strict):
    strategy: Optional[Literal["fixed_time", "adaptive", "roundabout"]] = None
    seeds: int = Field(3, ge=1, le=MAX_SEEDS)
    baseSeed: Optional[int] = Field(None, ge=0)
    # Which observed inputs are written into a COPY of the scenario before
    # running. Empty (default): the scenario is simulated exactly as given.
    fit: List[Literal["demand", "turning", "mix"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self) -> "CalibrationOptions":
        if len(set(self.fit)) != len(self.fit):
            raise ValueError("fit must not repeat")
        return self
