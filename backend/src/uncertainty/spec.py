"""Uncertainty specification (``urbanflow-uncertainty-spec`` v1) -- Robustness Lab skeleton (B0-5).

Strict pydantic models (``extra="forbid"``, camelCase) describing *which* inputs vary and how. Every
distribution is an **assumption of the analyst** unless ``basis`` says otherwise (strategy section 5.1);
an assumed factor must carry a rationale. The specification is fingerprinted before any run.

Design prototype only: no runner, no analysis, no HTTP exposure. The limits below are proposals from the
V3.0 strategy and are not yet approved.
"""

from __future__ import annotations

import hashlib
import json
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

_SCALE_KINDS = {
    "demand_scale",
    "headway_scale",
    "desired_speed_scale",
    "max_acceleration_scale",
}
_SHIFT_KINDS = {"turning_shift", "mix_shift"}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Distribution(_Strict):
    kind: DistributionKind
    mode: Optional[float] = None  # triangular
    mean: Optional[float] = None  # truncated_normal
    sd: Optional[float] = Field(None, gt=0)  # truncated_normal
    mu: Optional[float] = (
        None  # lognormal, parameters of the underlying normal (log space)
    )
    sigma: Optional[float] = Field(None, gt=0)  # lognormal


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
            if d.mode is None or not low <= d.mode <= high:
                raise ValueError(
                    f"factor '{self.id}': triangular needs a mode within the bounds"
                )
        elif d.kind == "truncated_normal":
            if d.mean is None or d.sd is None:
                raise ValueError(
                    f"factor '{self.id}': truncated_normal needs mean and sd"
                )
        elif d.kind == "lognormal":
            if d.mu is None or d.sigma is None:
                raise ValueError(f"factor '{self.id}': lognormal needs mu and sigma")
            if low <= 0:
                raise ValueError(
                    f"factor '{self.id}': lognormal needs a positive lower bound"
                )
        return self


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
    primaryIndicator: str = Field("averageDelay", max_length=64)
    tieTolerance: Optional[float] = Field(
        None, ge=0
    )  # None: use the study's existing tolerance

    @model_validator(mode="after")
    def _unique_factor_ids(self) -> "UncertaintySpec":
        ids = [f.id for f in self.factors]
        if len(set(ids)) != len(ids):
            raise ValueError("factor ids must be unique")
        return self


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(spec: UncertaintySpec) -> str:
    """16-hex SHA-256 of the canonical specification (same width as the other fingerprints)."""
    payload: Dict[str, Any] = spec.model_dump(mode="json")
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:16]
