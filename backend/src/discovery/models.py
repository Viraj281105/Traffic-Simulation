"""Contracts of the Discovery Lab: the declared regime and the search specification."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

SEARCH_FORMAT = "urbanflow-discovery-search"
RESULT_FORMAT = "urbanflow-discovery-result"
SEARCH_VERSION = 1

# Objectives, all minimised internally (throughput is negated). The engine records no 95th-percentile
# queue and no hard-braking count, so the queue objective is the maximum queue and the safety proxy is
# TTC near misses per 1,000 vehicles that finished; a run with any collision is infeasible.
OBJECTIVES = ("averageDelay", "throughput", "maxQueueLength", "nearMissesPer1000")
OBJECTIVE_DIRECTIONS = {
    "averageDelay": "min",
    "throughput": "max",
    "maxQueueLength": "min",
    "nearMissesPer1000": "min",
}

Strategy = Literal["fixed_time", "adaptive", "roundabout", "signalised_roundabout"]
BASELINES = ("fixed_time", "adaptive", "roundabout")
ALL_STRATEGIES: Tuple[Strategy, ...] = (
    "fixed_time",
    "adaptive",
    "roundabout",
    "signalised_roundabout",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Regime(_Strict):
    """The traffic the candidates are tuned for (uncertainty is ignored during the search)."""

    name: str = Field("Declared regime", max_length=120)
    vehiclesPerHour: int = Field(600, ge=100, le=1200)  # per arm
    unevenDemand: bool = False  # north/south carry 1.4x, east/west 0.6x
    lanesPerArm: int = Field(1, ge=1, le=2)
    aggression: Optional[Literal["standard", "moderate", "high"]] = None
    mix: Literal["default", "heavy_vehicles", "two_wheelers"] = "default"
    duration: float = Field(150.0, ge=60, le=600)
    warmup: float = Field(30.0, ge=0, le=120)

    @model_validator(mode="after")
    def _warmup(self) -> "Regime":
        if self.warmup >= self.duration:
            raise ValueError("warmup must be shorter than duration")
        return self


class Budget(_Strict):
    population: int = Field(10, ge=4, le=24)
    generations: int = Field(6, ge=1, le=20)
    tuningSeeds: int = Field(2, ge=1, le=3)
    selectionSeeds: int = Field(3, ge=2, le=5)
    heldOutSeeds: int = Field(10, ge=10, le=20)
    paretoCap: int = Field(
        6, ge=2, le=8
    )  # Pareto members re-evaluated on the selection seeds
    shortlist: int = Field(3, ge=1, le=4)  # candidates taken to the held-out evaluation
    unseenGrid: bool = True


class SearchSpec(_Strict):
    format: Literal["urbanflow-discovery-search"] = "urbanflow-discovery-search"
    version: Literal[1] = 1
    name: str = Field("Discovery search", max_length=120)
    regime: Regime = Field(default_factory=lambda: Regime.model_validate({}))
    budget: Budget = Field(default_factory=lambda: Budget.model_validate({}))
    seed: int = Field(1, ge=0, le=2**31 - 1)
    strategies: List[Strategy] = Field(
        default_factory=lambda: list(ALL_STRATEGIES), min_length=1, max_length=4
    )

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.model_dump(mode="json", exclude={"name"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


UNSEEN_DEMAND_SCALES = (0.8, 1.2)
UNSEEN_AGGRESSION = ("standard", "high")
UNSEEN_SEEDS = 2


def planned_runs(spec: SearchSpec) -> int:
    """The most simulation runs the search can use. The budget is a hard stop: it is never exceeded."""
    b = spec.budget
    finalists = b.shortlist + len(BASELINES)
    runs = b.population * b.generations * b.tuningSeeds
    runs += b.paretoCap * b.selectionSeeds
    runs += finalists * b.heldOutSeeds
    if b.unseenGrid:
        runs += (
            finalists
            * len(UNSEEN_DEMAND_SCALES)
            * len(UNSEEN_AGGRESSION)
            * UNSEEN_SEEDS
        )
    return runs


def planned_simulated_seconds(spec: SearchSpec) -> float:
    return planned_runs(spec) * float(spec.regime.duration)


def describe_objectives() -> Dict[str, Any]:
    return {
        "objectives": list(OBJECTIVES),
        "directions": OBJECTIVE_DIRECTIONS,
        "constraint": "a run with any collision makes the candidate infeasible",
        "note": "Safety proxies are model outputs, not predictions of real crashes.",
    }
