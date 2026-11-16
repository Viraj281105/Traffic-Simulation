"""``/api/v2/governance``: advisory-only recommendations, audit log, shadow report.

State lives in an app-level ``WorkflowService``; tests swap it through the
``get_service`` dependency. Nothing here applies a recommendation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src.governance.shadow import ShadowRecord, shadow_report
from src.governance.workflow import (
    CommentRequiredError,
    GovernanceError,
    IllegalTransitionError,
    NotFoundError,
    PermissionDeniedError,
    State,
    WorkflowService,
)

router = APIRouter(prefix="/api/v2/governance", tags=["governance"])

_service = WorkflowService()


def get_service() -> WorkflowService:
    return _service


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RecommendationIn(_In):
    actor: str = Field(..., min_length=1, max_length=128)
    id: Optional[str] = Field(None, min_length=1, max_length=64)
    scenario_ref: str = Field(..., alias="scenarioRef", min_length=1, max_length=256)
    proposed_change: Dict[str, Any] = Field(..., alias="proposedChange")
    evidence_refs: List[str] = Field(
        default_factory=list, alias="evidenceRefs", max_length=100
    )


class TransitionIn(_In):
    actor: str = Field(..., min_length=1, max_length=128)
    roles: List[str] = Field(default_factory=list, max_length=20)
    to: State
    comment: Optional[str] = Field(None, max_length=2000)


class ShadowRecordIn(_In):
    interval: str = Field(..., min_length=1, max_length=128)
    recommended: str = Field(..., min_length=1, max_length=128)
    predicted_costs: Dict[str, float] = Field(..., alias="predictedCosts")
    chosen: Optional[str] = None
    observed_cost: Optional[float] = Field(None, alias="observedCost")


class ShadowReportIn(_In):
    records: List[ShadowRecordIn] = Field(..., max_length=10000)


@router.post("/recommendations", status_code=201)
def create_recommendation(
    payload: RecommendationIn, svc: WorkflowService = Depends(get_service)
) -> Dict[str, Any]:
    try:
        rec = svc.create(
            payload.actor,
            payload.scenario_ref,
            payload.proposed_change,
            payload.evidence_refs,
            payload.id,
        )
    except GovernanceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return rec.to_dict()


@router.get("/recommendations")
def list_recommendations(
    state: Optional[State] = None, svc: WorkflowService = Depends(get_service)
) -> Dict[str, Any]:
    return {"items": [r.to_dict() for r in svc.list(state)]}


@router.post("/recommendations/{rec_id}/transition")
def transition_recommendation(
    rec_id: str, payload: TransitionIn, svc: WorkflowService = Depends(get_service)
) -> Dict[str, Any]:
    try:
        rec = svc.transition(
            rec_id, payload.to, payload.actor, payload.roles, payload.comment
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CommentRequiredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return rec.to_dict()


@router.get("/audit")
def get_audit(
    limit: int = Query(200, ge=1, le=5000), svc: WorkflowService = Depends(get_service)
) -> Dict[str, Any]:
    entries = svc.log.entries()
    return {
        "total": len(entries),
        "head": svc.log.head(),
        "entries": [e.to_dict() for e in entries[-limit:]],
    }


@router.get("/audit/verify")
def verify_audit(
    expected_head: Optional[str] = Query(None, alias="expectedHead"),
    expected_length: Optional[int] = Query(None, alias="expectedLength", ge=0),
    svc: WorkflowService = Depends(get_service),
) -> Dict[str, Any]:
    return svc.log.verify(expected_head, expected_length).to_dict()


@router.post("/shadow/report")
def post_shadow_report(payload: ShadowReportIn) -> Dict[str, Any]:
    return shadow_report(
        [
            ShadowRecord(
                r.interval, r.recommended, r.predicted_costs, r.chosen, r.observed_cost
            )
            for r in payload.records
        ]
    )
