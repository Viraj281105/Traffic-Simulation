"""``/api/v3/copilot`` routes (W5). Same guards as the rest of ``/api/v3``: API key at the router, a signed-in
user or personal access token per request, scopes per operation, and 404 for anyone else's proposal."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Sequence

from fastapi import APIRouter, Body, Depends, HTTPException

from src.api.auth import PAT_SCOPES, UserIdentity
from src.api.store import AuditStore
from src.experiments.service import (
    ConflictError,
    ExperimentError,
    NotFound,
    QuotaExceeded,
    get_service,
)

from .catalog import catalogue
from .models import (
    ConfirmRequest,
    ExperimentProposal,
    InterpretationRequest,
    ProposalRequest,
)
from .service import CopilotQuotaExceeded, CopilotService, ProposalConflict

logger = logging.getLogger(__name__)

_NOT_FOUND = "Proposal not found"


def create_router(
    user_dependency: Optional[Callable[..., Any]] = None,
    dependencies: Sequence[Any] = (),
    service: Optional[CopilotService] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/v3/copilot", tags=["copilot-v3"], dependencies=list(dependencies)
    )
    copilot = service or CopilotService(get_service())

    def current_identity(user: Any = Depends(user_dependency)) -> UserIdentity:
        if isinstance(user, UserIdentity):
            return user
        return UserIdentity(user_id=str(user), auth_type="dev", scopes=PAT_SCOPES)

    identity_dep = (
        current_identity
        if user_dependency
        else (
            lambda: UserIdentity(
                user_id="anonymous", auth_type="dev", scopes=PAT_SCOPES
            )
        )
    )

    def need(identity: UserIdentity, scope: str) -> None:
        if not identity.has_scope(scope):
            raise HTTPException(status_code=403, detail="Insufficient token scope")

    @router.get("/catalogue")
    def get_catalogue(identity: UserIdentity = Depends(identity_dep)) -> Dict[str, Any]:
        """What a proposal may contain: alternatives, profiles, demand levels, bounds and quotas."""
        need(identity, "experiments:read")
        return catalogue()

    @router.post("/proposals", status_code=201, response_model=ExperimentProposal)
    def create_proposal(
        payload: ProposalRequest = Body(...),
        identity: UserIdentity = Depends(identity_dep),
    ) -> ExperimentProposal:
        """Turn a question into a validated proposal. Nothing runs until the proposal is confirmed."""
        need(identity, "experiments:read")
        try:
            return copilot.propose(identity.user_id, payload.question, payload.mode)
        except CopilotQuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err

    @router.get("/proposals/{proposal_id}", response_model=ExperimentProposal)
    def get_proposal(
        proposal_id: str, identity: UserIdentity = Depends(identity_dep)
    ) -> ExperimentProposal:
        need(identity, "experiments:read")
        try:
            return copilot.get(identity.user_id, proposal_id)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err

    @router.post(
        "/proposals/{proposal_id}/suggestions/{code}",
        status_code=201,
        response_model=ExperimentProposal,
    )
    def apply_suggestion(
        proposal_id: str, code: str, identity: UserIdentity = Depends(identity_dep)
    ) -> ExperimentProposal:
        """A new proposal with one validation suggestion applied; it is validated again."""
        need(identity, "experiments:read")
        try:
            return copilot.apply_suggestion(identity.user_id, proposal_id, code)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ProposalConflict as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except CopilotQuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err

    @router.post("/proposals/{proposal_id}/confirm", status_code=202)
    def confirm(
        proposal_id: str,
        payload: ConfirmRequest = Body(...),
        identity: UserIdentity = Depends(identity_dep),
    ) -> Dict[str, Any]:
        """Submit the proposal's experiment as an ordinary experiment (single use, hash-bound)."""
        need(identity, "experiments:run")
        try:
            status = copilot.confirm(identity.user_id, proposal_id, payload.contentHash)
        except NotFound as err:
            raise HTTPException(status_code=404, detail=_NOT_FOUND) from err
        except ProposalConflict as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except ExperimentError as err:
            raise HTTPException(status_code=422, detail={"errors": err.errors}) from err
        except QuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err
        try:
            AuditStore.record_event(
                user_id=identity.user_id,
                event_type="experiment_submitted",
                token_id=identity.token_id,
                details={
                    "experiment_id": status.get("id"),
                    "source": "copilot",
                    "proposal_id": proposal_id,
                },
            )
        except Exception:  # noqa: BLE001 - an audit failure never fails the request
            logger.warning("audit event not recorded", exc_info=True)
        return status

    @router.post("/experiments/{experiment_id}/interpretation")
    def interpret(
        experiment_id: str,
        payload: Optional[InterpretationRequest] = Body(None),
        identity: UserIdentity = Depends(identity_dep),
    ) -> Dict[str, Any]:
        """Measured evidence, a template summary and (when it passes grounding) a model-written reading."""
        need(identity, "experiments:read")
        request = payload or InterpretationRequest(preferred=None)
        try:
            return copilot.interpret(
                identity.user_id, experiment_id, request.preferred, request.mode
            )
        except NotFound as err:
            raise HTTPException(status_code=404, detail="Experiment not found") from err
        except (ConflictError, ProposalConflict) as err:
            raise HTTPException(status_code=409, detail=str(err)) from err
        except CopilotQuotaExceeded as err:
            raise HTTPException(status_code=429, detail=str(err)) from err

    return router
