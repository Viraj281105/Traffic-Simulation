"""Pydantic request/response models for /api/ai/* endpoints.

All input strings are stripped and length-limited here so routers stay clean.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# ── Shared ─────────────────────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    role: str  # "user" | "assistant"
    content: str = Field(..., max_length=2000)

    @field_validator("role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v


# ── Summary ─────────────────────────────────────────────────────────────────

class SummaryRequest(BaseModel):
    """POST /api/ai/summary"""

    metrics: Dict[str, Any] = Field(..., description="LiveSnapshot.metrics dict")
    config: Dict[str, Any] = Field(
        ..., description="SimulationConfigValues from the frontend"
    )
    geometry: str = Field("fixed_time_signal")
    elapsed_seconds: Optional[float] = Field(None, ge=0)

    @field_validator("geometry")
    @classmethod
    def _valid_geom(cls, v: str) -> str:
        valid = ("fixed_time_signal", "roundabout", "comparison", "research", "planning")
        if v not in valid:
            raise ValueError(f"geometry must be one of {valid}")
        return v


class SummaryResponse(BaseModel):
    summary: str = Field(..., max_length=600)
    bullets: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    fallback: bool = False


# ── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """POST /api/ai/chat"""

    question: str = Field(..., min_length=1, max_length=500)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    geometry: str = Field("fixed_time_signal")
    history: List[ConversationTurn] = Field(default_factory=list, max_length=10)

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        return v.strip()

    @field_validator("geometry")
    @classmethod
    def _valid_geom(cls, v: str) -> str:
        valid = ("fixed_time_signal", "roundabout", "comparison", "research", "planning")
        if v not in valid:
            raise ValueError(f"geometry must be one of {valid}")
        return v


class ChatResponse(BaseModel):
    answer: str = Field(..., max_length=1200)
    fallback: bool = False


# ── Config patch ─────────────────────────────────────────────────────────────

class PatchRequest(BaseModel):
    """POST /api/ai/patch

    The model converts a natural-language instruction into a partial
    SimulationConfigValues object.  The client shows a before/after preview
    and only calls onApply after the user confirms.
    """

    instruction: str = Field(..., min_length=1, max_length=500)
    current_config: Dict[str, Any] = Field(
        ..., description="Current SimulationConfigValues"
    )
    geometry: str = Field("fixed_time_signal")

    @field_validator("instruction")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("geometry")
    @classmethod
    def _valid_geom(cls, v: str) -> str:
        if v not in ("fixed_time_signal", "roundabout"):
            raise ValueError("geometry must be fixed_time_signal or roundabout")
        return v


class ConfigPatch(BaseModel):
    """The validated, merged config after applying the patch.

    `patch` holds only the keys that changed.  `merged` is the full
    SimulationConfigValues the UI should preview and, after confirmation, apply.
    """

    patch: Dict[str, Any]
    merged: Dict[str, Any]
    assumptions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    clarification: Optional[str] = None
    fallback: bool = False
