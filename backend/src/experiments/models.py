"""Request document of ``POST /api/v3/experiments`` (``urbanflow-experiment`` v1).

Strict (``extra="forbid"``): an unknown field is rejected by name, never ignored. The scenario and the
alternatives reuse the V2.0 documents, so an experiment is "a planning study plus an uncertainty
specification".
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.planning.models import AlternativeSpec
from src.uncertainty.spec import UncertaintySpec

from .limits import MAX_ALTERNATIVES_PARSED

EXPERIMENT_FORMAT = "urbanflow-experiment"
EXPERIMENT_VERSION = 1
RESULT_FORMAT = "urbanflow-experiment-result"
RESULT_VERSION = 1
# A cancelled experiment's result so far: deliberately not an ``urbanflow-experiment-result``, so a
# client cannot mistake it for a finished, fingerprinted result.
PARTIAL_RESULT_FORMAT = "urbanflow-experiment-partial-result"
PARTIAL_RESULT_VERSION = 1


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["urbanflow-experiment"] = "urbanflow-experiment"
    version: Literal[1] = 1
    name: str = Field("Robustness experiment", max_length=120)
    # An ``urbanflow-scenario`` document (the base junction and its traffic).
    scenario: Dict[str, Any]
    # Omitted: the three built-in strategies on the unchanged scenario, fixed-time first.
    alternatives: Optional[List[AlternativeSpec]] = Field(
        None, max_length=MAX_ALTERNATIVES_PARSED
    )
    # The alternative every other is compared with. Omitted: the first.
    # An alternative id (1-32 characters); bounded because it is echoed back in error messages.
    baseline: Optional[str] = Field(None, max_length=32)
    uncertainty: UncertaintySpec


class RunCounts(BaseModel):
    """Conditions, alternatives, replications and total runs, always reported separately."""

    conditions: int
    alternatives: int
    replications: int
    totalRuns: int


class ExperimentStatus(BaseModel):
    format: Literal["urbanflow-experiment-status"] = "urbanflow-experiment-status"
    version: Literal[1] = 1
    id: str
    name: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    error: Optional[str] = None
    createdAt: str
    counts: Optional[RunCounts] = None
    specFingerprint: Optional[str] = None
    resultAvailable: bool
    # Live while queued or running: phase, simulations finished, fraction, elapsed seconds.
    progress: Optional[Dict[str, Any]] = None


class ExperimentList(BaseModel):
    format: Literal["urbanflow-experiment-list"] = "urbanflow-experiment-list"
    version: Literal[1] = 1
    limit: int
    offset: int
    experiments: List[ExperimentStatus]
