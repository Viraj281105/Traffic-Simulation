"""Request model for a planning study (``urbanflow-planning-study`` v1).

Pydantic, ``extra="forbid"``, camelCase -- the same conventions as
``urbanflow-scenario``. Results are plain JSON-able dicts whose shape is
documented in docs/product/decision-support.md and checked by the tests.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Literal, Optional, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PLANNING_STUDY_FORMAT = "urbanflow-planning-study"
PLANNING_RESULT_FORMAT = "urbanflow-planning-result"
SCHEMA_VERSION = 1

INDICATOR_GROUPS = ("performance", "safety", "environmental", "reliability")
MAX_ALTERNATIVES = 6
MAX_SCALES = 5
MAX_SEEDS = 30
MAX_TOTAL_RUNS = 240  # alternatives x scales x seeds

IndicatorGroup = Literal["performance", "safety", "environmental", "reliability"]

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,31}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AlternativeSpec(_Strict):
    """One option under study: a control strategy plus an optional change.

    ``patch`` is a JSON merge-patch (RFC 7386) over a copy of the study's
    scenario document; the patched copy is re-validated by ``ScenarioDocument``
    (unknown fields are rejected) and by ``validate_scenario``.
    """

    id: str
    label: str = Field("", max_length=120)
    strategy: str
    patch: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("id must be 1-32 letters, digits, '-' or '_'")
        return v


class Subject(_Strict):
    scenario: Optional[Dict[str, Any]] = None
    # V1.9 ``urbanflow-network``. Accepted when it holds exactly one junction
    # with an inline scenario (see planning/links.py); give this OR scenario.
    network: Optional[Dict[str, Any]] = None


class CalibrationRef(_Strict):
    """A stored V1.8 run (``POST /api/v2/calibration/runs``) to attach.

    ``useFittedScenario`` takes the scenario that run simulated (observed
    inputs written in) as the subject, so ``subject`` may then be omitted."""

    runId: str = Field(..., min_length=1, max_length=128)
    useFittedScenario: bool = False


class DemandSpec(_Strict):
    scales: List[float] = Field(default_factory=lambda: [1.0])
    growthLabel: Optional[str] = Field(None, max_length=120)

    @field_validator("scales")
    @classmethod
    def _scales(cls, v: List[float]) -> List[float]:
        if not v or len(v) > MAX_SCALES:
            raise ValueError(f"scales needs 1-{MAX_SCALES} values")
        if any(not (0.1 <= s <= 3.0) for s in v):
            raise ValueError("each demand scale must be between 0.1 and 3.0")
        if len(set(v)) != len(v):
            raise ValueError("demand scales must be distinct")
        return [float(s) for s in v]


class Repetitions(_Strict):
    seeds: int = Field(5, ge=1, le=MAX_SEEDS)
    baseSeed: Optional[int] = Field(None, ge=0)
    confidenceLevel: float = Field(0.95, gt=0.5, lt=1.0)


class PlanningStudy(_Strict):
    format: Literal["urbanflow-planning-study"] = "urbanflow-planning-study"
    version: Literal[1] = 1
    name: str = Field("Planning study", max_length=120)
    objective: str = Field("", max_length=500)
    subject: Subject = Field(default_factory=lambda: Subject.model_validate({}))
    calibration: Optional[CalibrationRef] = None
    # First alternative is the baseline. Omitted: the three built-in strategies.
    alternatives: Optional[List[AlternativeSpec]] = None
    demand: DemandSpec = Field(default_factory=lambda: DemandSpec.model_validate({}))
    repetitions: Repetitions = Field(
        default_factory=lambda: Repetitions.model_validate({})
    )
    indicators: List[IndicatorGroup] = Field(
        default_factory=lambda: list(get_args(IndicatorGroup))
    )

    @model_validator(mode="after")
    def _shape(self) -> "PlanningStudy":
        given = [
            self.subject.scenario is not None,
            self.subject.network is not None,
        ]
        fitted = self.calibration is not None and self.calibration.useFittedScenario
        if sum(given) > 1:
            raise ValueError("give subject.scenario or subject.network, not both")
        if fitted and any(given):
            raise ValueError(
                "calibration.useFittedScenario supplies the scenario; "
                "omit subject.scenario / subject.network"
            )
        if not fitted and not any(given):
            raise ValueError(
                "subject.scenario (or subject.network, or calibration with "
                "useFittedScenario) is required"
            )
        if self.alternatives is not None:
            ids = [a.id for a in self.alternatives]
            if not 1 <= len(ids) <= MAX_ALTERNATIVES:
                raise ValueError(f"alternatives needs 1-{MAX_ALTERNATIVES} entries")
            if len(set(ids)) != len(ids):
                raise ValueError("alternative ids must be unique")
            n = len(ids)
        else:
            n = 3
        runs = n * len(self.demand.scales) * self.repetitions.seeds
        if runs > MAX_TOTAL_RUNS:
            raise ValueError(
                f"{runs} simulations requested (alternatives x scales x seeds); "
                f"the limit is {MAX_TOTAL_RUNS}"
            )
        return self


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint_of(value: Any) -> str:
    """16-hex SHA-256 of canonical JSON (same width as scenario_fingerprint)."""
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()[:16]
