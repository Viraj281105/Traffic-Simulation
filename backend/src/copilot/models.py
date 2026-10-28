"""Contracts of the Copilot: the intent a proposer produces and the proposal a user confirms."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PROPOSAL_FORMAT = "urbanflow-experiment-proposal"
PROPOSAL_VERSION = 1
INTERPRETATION_FORMAT = "urbanflow-experiment-interpretation"

AlternativeKind = Literal[
    "fixed_time", "adaptive", "roundabout", "signalised_roundabout"
]
DemandLevel = Literal["light", "moderate", "peak", "near_capacity"]
Aggression = Literal["standard", "moderate", "high"]
MixEmphasis = Literal["default", "heavy_vehicles", "two_wheelers"]
Depth = Literal["quick", "standard", "thorough"]
Indicator = Literal["averageDelay", "medianDelay", "p95Delay"]
Provenance = Literal["user", "rule", "model"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExperimentIntent(_Strict):
    """What a proposer may decide. Every field is bounded; the experiment is *built* from it, never
    written by the proposer, so a proposer cannot reach any other part of the request."""

    alternatives: List[AlternativeKind] = Field(..., min_length=2, max_length=4)
    baseline: Optional[AlternativeKind] = None
    aggression: Optional[Aggression] = None
    demand: DemandLevel = "moderate"
    unevenDemand: bool = False
    mix: MixEmphasis = "default"
    depth: Depth = "standard"
    replications: int = Field(2, ge=2, le=5)
    primaryIndicator: Indicator = "averageDelay"
    uncertainAggression: bool = False
    assumptions: List[str] = Field(default_factory=list, max_length=8)
    warnings: List[str] = Field(default_factory=list, max_length=8)
    clarification: Optional[str] = Field(None, max_length=500)


class ProposalIssue(_Strict):
    """A problem found by the validation boundary. ``code`` is stable; ``suggestion`` is a deterministic
    change that would make the proposal valid (applied only as a new proposal, never silently)."""

    code: str
    message: str
    suggestion: Optional[Dict[str, Any]] = None


class ReproducibilityMetadata(_Strict):
    proposer: Literal["deterministic", "model"]
    proposerVersion: str
    provider: Optional[str] = None
    model: Optional[str] = None
    promptTemplateVersion: Optional[str] = None
    catalogueHash: str


class ExperimentProposal(_Strict):
    format: Literal["urbanflow-experiment-proposal"] = "urbanflow-experiment-proposal"
    version: Literal[1] = 1
    id: str
    question: str
    mode: Literal["deterministic", "model"]
    # Why the model was not used, when it was asked for but unavailable ("AI assistance unavailable").
    aiUnavailableReason: Optional[str] = None
    intent: ExperimentIntent
    experiment: Dict[str, Any]
    fieldProvenance: Dict[str, Provenance]
    assumptions: List[str]
    warnings: List[str]
    suggestedChecks: List[str]
    clarification: Optional[str] = None
    estimatedRuns: Optional[int] = None
    estimatedSimulatedSeconds: Optional[float] = None
    # Wall-clock time is not estimated: it has not been measured on this server.
    estimatedWallTime: Literal["unverified"] = "unverified"
    reproducibilityMetadata: ReproducibilityMetadata
    # Set by the backend, never by a proposer.
    validated: bool
    issues: List[ProposalIssue]
    contentHash: str
    createdAt: str
    expiresAt: str
    confirmed: bool = False
    experimentId: Optional[str] = None


class ConfirmRequest(_Strict):
    contentHash: str = Field(..., min_length=64, max_length=64)


class ProposalRequest(_Strict):
    question: str = Field(..., min_length=1, max_length=2000)
    # "auto": the model when one is configured and within budget, else the deterministic proposer.
    mode: Literal["auto", "deterministic"] = "auto"


class InterpretationRequest(_Strict):
    # The alternative the user hopes wins: its unfavourable findings are always listed.
    preferred: Optional[str] = Field(None, max_length=32)
    mode: Literal["auto", "template"] = "auto"
