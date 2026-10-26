"""``/api/ai/summary``, ``/api/ai/chat`` and ``/api/ai/patch`` routes.

Every route:
* is guarded by ``require_api_key`` (same as existing V1 routes)
* tries the Groq LLM first and falls back to deterministic answers on any error
* never exposes the Groq API key or any internal exception detail to the client
* validates and patches the config through the existing backend schema before
  returning it to the frontend
"""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.ai import fallback as fb
from src.ai import groq_client as gc
from src.ai import prompts
from src.ai.schemas import (
    ChatRequest,
    ChatResponse,
    ConfigPatch,
    PatchRequest,
    SummaryRequest,
    SummaryResponse,
)
from src.api.security import require_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

# ── Shared ───────────────────────────────────────────────────────────────────

def _metrics_context(request_body: Dict[str, Any]) -> str:
    """Compact JSON string of metrics + config for the LLM context window."""
    return json.dumps(
        {"metrics": request_body.get("metrics", {}), "config": request_body.get("config", {})},
        separators=(",", ":"),
    )


def _validate_patch(patch: Dict[str, Any], geometry: str) -> list[str]:
    """Basic range checks on the AI-generated patch fields.

    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []
    float_ranges = {
        "arrivalRate": (0.05, 1.2),
        "duration": (30, 600),
        "laneWidth": (2.5, 4.8),
        "greenDuration": (5, 60),
        "yellowDuration": (2, 8),
        "allRedDuration": (1, 6),
        "nsGreenDuration": (6, 120),
        "ewGreenDuration": (6, 120),
        "criticalGap": (2.0, 6.0),
        "followUpTime": (1.0, 3.5),
    }
    int_ranges = {
        "lanes": (1, 3),
        "randomSeed": (1, 999999),
    }
    for key, (lo, hi) in float_ranges.items():
        if key in patch:
            try:
                val = float(patch[key])
            except (TypeError, ValueError):
                errors.append(f"{key} must be a number")
                continue
            if not lo <= val <= hi:
                errors.append(f"{key} ({val}) must be between {lo} and {hi}")
    for key, (lo, hi) in int_ranges.items():
        if key in patch:
            try:
                val = int(patch[key])
            except (TypeError, ValueError):
                errors.append(f"{key} must be an integer")
                continue
            if not lo <= val <= hi:
                errors.append(f"{key} ({val}) must be between {lo} and {hi}")
    if "signalControl" in patch and patch["signalControl"] not in ("fixed_time", "adaptive"):
        errors.append("signalControl must be 'fixed_time' or 'adaptive'")
    if "vehicleMix" in patch:
        mix = patch["vehicleMix"]
        if isinstance(mix, dict):
            total = sum(float(v) for v in mix.values() if isinstance(v, (int, float)))
            if abs(total - 1.0) > 0.01:
                errors.append(f"vehicleMix shares must sum to 1.0 (got {total:.3f})")
    return errors


# ── Summary ──────────────────────────────────────────────────────────────────

@router.post(
    "/summary",
    response_model=SummaryResponse,
    dependencies=[Depends(require_api_key)],
)
def ai_summary(payload: SummaryRequest) -> SummaryResponse:
    """Generate a plain-English summary of the current simulation results."""
    if not gc.is_configured():
        logger.info("GROQ_API_KEY not set; returning summary fallback")
        return fb.summary_fallback(
            payload.metrics, payload.config, payload.geometry, payload.elapsed_seconds
        )

    user_msg = (
        f"geometry: {payload.geometry}\n"
        f"elapsed: {payload.elapsed_seconds} s\n"
        f"metrics: {json.dumps(payload.metrics, separators=(',', ':'))}\n"
        f"config: {json.dumps(payload.config, separators=(',', ':'))}\n\n"
        "Please summarise this simulation run."
    )

    try:
        result = gc.complete_json(
            prompts.SUMMARY_SYSTEM,
            user_msg,
            prompts.SUMMARY_JSON_SCHEMA,
            max_tokens=600,
        )
        return SummaryResponse(
            summary=str(result.get("summary", ""))[:600],
            bullets=result.get("bullets", []),
            warnings=result.get("warnings", []),
            fallback=False,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Groq summary call failed; using fallback", exc_info=False)
        return fb.summary_fallback(
            payload.metrics, payload.config, payload.geometry, payload.elapsed_seconds
        )


# ── Chat ─────────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_api_key)],
)
def ai_chat(payload: ChatRequest) -> ChatResponse:
    """Answer a natural-language question about the current simulation."""
    if not gc.is_configured():
        logger.info("GROQ_API_KEY not set; returning chat fallback")
        return fb.chat_fallback(payload.question, payload.metrics, payload.config)

    # Build history list for the Groq call
    history = [{"role": t.role, "content": t.content} for t in payload.history]

    context = (
        f"geometry: {payload.geometry}\n"
        f"metrics: {json.dumps(payload.metrics, separators=(',', ':'))}\n"
        f"config: {json.dumps(payload.config, separators=(',', ':'))}\n\n"
        f"User question: {payload.question}"
    )

    try:
        answer = gc.complete(
            prompts.CHAT_SYSTEM,
            context,
            history=history,
            max_tokens=500,
        )
        # Sanitise: reject any response embedding script tags
        if "<script" in answer.lower() or "javascript:" in answer.lower():
            logger.warning("Groq returned suspicious content; using fallback")
            return fb.chat_fallback(payload.question, payload.metrics, payload.config)
        return ChatResponse(answer=answer[:1200], fallback=False)
    except Exception:  # noqa: BLE001
        logger.warning("Groq chat call failed; using fallback", exc_info=False)
        return fb.chat_fallback(payload.question, payload.metrics, payload.config)


# ── Config patch ──────────────────────────────────────────────────────────────

@router.post(
    "/patch",
    response_model=ConfigPatch,
    dependencies=[Depends(require_api_key)],
)
def ai_patch(payload: PatchRequest) -> ConfigPatch:
    """Convert a natural-language instruction into a validated config patch.

    The patch is validated against known field ranges before being returned.
    The frontend must show the before/after preview and ask for explicit
    confirmation before calling ``onApply``.
    """
    if not gc.is_configured():
        logger.info("GROQ_API_KEY not set; returning patch fallback")
        return fb.patch_fallback(payload.instruction, payload.current_config)

    user_msg = (
        f"Current config: {json.dumps(payload.current_config, separators=(',', ':'))}\n"
        f"Geometry: {payload.geometry}\n\n"
        f"Instruction: {payload.instruction}"
    )

    try:
        result = gc.complete_json(
            prompts.PATCH_SYSTEM,
            user_msg,
            prompts.PATCH_JSON_SCHEMA,
            max_tokens=700,
        )
    except Exception:  # noqa: BLE001
        logger.warning("Groq patch call failed; using fallback", exc_info=False)
        return fb.patch_fallback(payload.instruction, payload.current_config)

    patch: Dict[str, Any] = result.get("patch", {})
    assumptions: list[str] = result.get("assumptions", [])
    warnings: list[str] = result.get("warnings", [])
    clarification: str | None = result.get("clarification")

    # Validate generated patch values
    errors = _validate_patch(patch, payload.geometry)
    if errors:
        warnings.extend([f"[Validation] {e}" for e in errors])
        # Strip invalid keys rather than rejecting the whole response
        for e in errors:
            key = e.split("(")[0].strip()
            patch.pop(key, None)

    # Build merged config
    merged = deepcopy(payload.current_config)
    merged.update(patch)

    return ConfigPatch(
        patch=patch,
        merged=merged,
        assumptions=assumptions,
        warnings=warnings,
        clarification=clarification,
        fallback=False,
    )
