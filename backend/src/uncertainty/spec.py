"""Uncertainty specification (``urbanflow-uncertainty-spec`` v1) -- Robustness Lab skeleton (B0-5).

Strict pydantic models (``extra="forbid"``, camelCase) describing *which* inputs vary and how. Every
distribution is an **assumption of the analyst** unless ``basis`` says otherwise (strategy section 5.1);
an assumed factor must carry a rationale. The specification is fingerprinted before any run.

No runner and no HTTP exposure here (W1 later work packages). ADR-015 is Accepted; the numeric limits
below (factors, conditions, replications) are the strategy's starting values and may be tuned.
"""

from __future__ import annotations

import hashlib
import json
import math
from statistics import NormalDist
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SPEC_FORMAT = "urbanflow-uncertainty-spec"
SPEC_VERSION = 1

MAX_FACTORS = 12
MAX_CONDITIONS = 1000
MAX_REPLICATIONS = 10

FactorKind = Literal[
    "demand_scale",  # global demand multiplier
    "turning_shift",  # shift of turning share toward one movement, in [-1, 1]
    "mix_shift",  # shift of vehicle-mix share toward heavier classes, in [-1, 1]
    "headway_scale",  # IDM time-headway multiplier (a proxy: the engine has no reaction delay)
    "desired_speed_scale",
    "max_acceleration_scale",
]
DistributionKind = Literal["uniform", "triangular", "truncated_normal", "lognormal"]
Basis = Literal["assumed", "observed", "user"]
# Primary indicators the analysis may compare. All are delays in seconds where lower is better, so
# win/tie/loss has one direction (strategy section 5.3: one pre-declared indicator, no shopping).
PrimaryIndicator = Literal["averageDelay", "medianDelay", "p95Delay"]

# Smallest share of a distribution that must fall inside the factor bounds.
_MIN_BOUNDED_MASS = 1e-3

_SCALE_KINDS = {
    "demand_scale",
    "headway_scale",
    "desired_speed_scale",
    "max_acceleration_scale",
}
_SHIFT_KINDS = {"turning_shift", "mix_shift"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Parameters each distribution kind uses; a parameter that does not belong to the kind is rejected
# rather than ignored (an ignored parameter would look like an assumption that is not being made).
_DISTRIBUTION_PARAMS = {
    "uniform": set(),
    "triangular": {"mode"},
    "truncated_normal": {"mean", "sd"},
    "lognormal": {"mu", "sigma"},
}
_ALL_PARAMS = {"mode", "mean", "sd", "mu", "sigma"}


class Distribution(_Strict):
    kind: DistributionKind
    mode: Optional[float] = None  # triangular
    mean: Optional[float] = None  # truncated_normal
    sd: Optional[float] = Field(None, gt=0)  # truncated_normal
    mu: Optional[float] = (
        None  # lognormal, parameters of the underlying normal (log space)
    )
    sigma: Optional[float] = Field(None, gt=0)  # lognormal

    @model_validator(mode="after")
    def _params_match_kind(self) -> "Distribution":
        given = {name for name in _ALL_PARAMS if getattr(self, name) is not None}
        needed = _DISTRIBUTION_PARAMS[self.kind]
        missing = sorted(needed - given)
        if missing:
            raise ValueError(f"{self.kind} needs {', '.join(missing)}")
        extra = sorted(given - needed)
        if extra:
            raise ValueError(f"{self.kind} does not use {', '.join(extra)}; remove it")
        for name in given:
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be a finite number")
        return self


class Factor(_Strict):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,31}$")
    kind: FactorKind
    distribution: Distribution
    bounds: List[float] = Field(..., min_length=2, max_length=2)
    basis: Basis = "assumed"
    rationale: str = Field("", max_length=500)

    @model_validator(mode="after")
    def _check(self) -> "Factor":
        low, high = self.bounds
        if not all(math.isfinite(b) for b in self.bounds):
            raise ValueError(f"factor '{self.id}': bounds must be finite numbers")
        if not low < high:
            raise ValueError(f"factor '{self.id}': bounds must satisfy low < high")
        if self.kind in _SCALE_KINDS and low <= 0:
            raise ValueError(
                f"factor '{self.id}': a scale factor needs a positive lower bound"
            )
        if self.kind in _SHIFT_KINDS and not (-1.0 <= low and high <= 1.0):
            raise ValueError(
                f"factor '{self.id}': a shift factor must stay within [-1, 1]"
            )
        if self.basis == "assumed" and not self.rationale.strip():
            raise ValueError(
                f"factor '{self.id}': an assumed distribution needs a rationale"
            )
        d = self.distribution
        if d.kind == "triangular":
            assert d.mode is not None  # guaranteed by Distribution
            if not low <= d.mode <= high:
                raise ValueError(
                    f"factor '{self.id}': triangular needs a mode within the bounds"
                )
        elif d.kind == "truncated_normal":
            assert d.mean is not None and d.sd is not None
            self._need_mass(NormalDist(d.mean, d.sd).cdf, low, high)
        elif d.kind == "lognormal":
            assert d.mu is not None and d.sigma is not None
            if low <= 0:
                raise ValueError(
                    f"factor '{self.id}': lognormal needs a positive lower bound"
                )
            self._need_mass(
                NormalDist(d.mu, d.sigma).cdf, math.log(low), math.log(high)
            )
        return self

    def _need_mass(self, cdf: Any, low: float, high: float) -> None:
        """The bounds must hold enough probability for truncated sampling to mean anything."""
        if cdf(high) - cdf(low) < _MIN_BOUNDED_MASS:
            raise ValueError(
                f"factor '{self.id}': the bounds hold almost none of the distribution's "
                "probability; move the bounds or the distribution parameters"
            )


class UncertaintySpec(_Strict):
    format: Literal["urbanflow-uncertainty-spec"] = "urbanflow-uncertainty-spec"
    version: Literal[1] = 1
    name: str = Field("Uncertainty specification", max_length=120)
    factors: List[Factor] = Field(..., min_length=1, max_length=MAX_FACTORS)
    conditions: int = Field(..., ge=1, le=MAX_CONDITIONS)  # N sampled conditions
    replications: int = Field(
        2, ge=1, le=MAX_REPLICATIONS
    )  # r engine seeds per condition
    seed: int = Field(..., ge=0, le=2**31 - 1)  # sampling and engine-seed base
    primaryIndicator: PrimaryIndicator = "averageDelay"
    # Tie tolerance tau, in the indicator's unit (seconds). None: the study's existing two-part rule
    # (study/tolerances.py: within 1 s or within 5 % of the larger value).
    tieTolerance: Optional[float] = Field(None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _unique_factor_ids(self) -> "UncertaintySpec":
        ids = [f.id for f in self.factors]
        if len(set(ids)) != len(ids):
            raise ValueError("factor ids must be unique")
        kinds = [f.kind for f in self.factors]
        repeated = sorted({k for k in kinds if kinds.count(k) > 1})
        if repeated:
            raise ValueError(
                f"each factor kind may appear once (factors are global in v1): {repeated}"
            )
        return self


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(spec: UncertaintySpec) -> str:
    """16-hex SHA-256 of what the specification computes (same width as the other fingerprints).

    The display ``name`` is left out, as the scenario fingerprint leaves out a scenario's name: two
    specifications that differ only in their label describe the same experiment.
    """
    payload: Dict[str, Any] = spec.model_dump(mode="json", exclude={"name"})
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:16]


def run_counts(spec: UncertaintySpec, alternatives: int) -> Dict[str, int]:
    """Conditions, replications and total runs, always reported separately (strategy section 5.2)."""
    if alternatives < 1:
        raise ValueError("an experiment needs at least one alternative")
    return {
        "conditions": spec.conditions,
        "alternatives": alternatives,
        "replications": spec.replications,
        "totalRuns": spec.conditions * alternatives * spec.replications,
    }
