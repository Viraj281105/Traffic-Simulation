"""Advisory-only approval workflow for recommendations (F10).

A transition only changes the recommendation's state and writes an audit
entry. Nothing here applies, deploys or executes a proposed change.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, List, Optional

from src.governance.audit import AuditLog

ROLE_AUTHOR = "author"
ROLE_APPROVER = "approver"


class State(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


ALLOWED: Dict[State, FrozenSet[State]] = {
    State.DRAFT: frozenset({State.SUBMITTED, State.WITHDRAWN}),
    State.SUBMITTED: frozenset({State.APPROVED, State.REJECTED, State.WITHDRAWN}),
    State.APPROVED: frozenset(),
    State.REJECTED: frozenset(),
    State.WITHDRAWN: frozenset(),
}


class GovernanceError(Exception):
    pass


class NotFoundError(GovernanceError):
    pass


class IllegalTransitionError(GovernanceError):
    pass


class PermissionDeniedError(GovernanceError):
    pass


class CommentRequiredError(GovernanceError):
    pass


@dataclass
class Recommendation:
    id: str
    scenario_ref: str
    proposed_change: Dict[str, Any]
    evidence_refs: List[str]
    created_by: str
    state: State = State.DRAFT
    submitted_by: Optional[str] = None
    decided_by: Optional[str] = None
    decision_comment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scenarioRef": self.scenario_ref,
            "proposedChange": self.proposed_change,
            "evidenceRefs": list(self.evidence_refs),
            "createdBy": self.created_by,
            "state": self.state.value,
            "submittedBy": self.submitted_by,
            "decidedBy": self.decided_by,
            "decisionComment": self.decision_comment,
        }


class WorkflowService:
    def __init__(self, log: Optional[AuditLog] = None) -> None:
        self.log = log if log is not None else AuditLog()
        self._items: Dict[str, Recommendation] = {}
        self._lock = threading.Lock()

    def create(
        self,
        actor: str,
        scenario_ref: str,
        proposed_change: Dict[str, Any],
        evidence_refs: Iterable[str] = (),
        rec_id: Optional[str] = None,
    ) -> Recommendation:
        with self._lock:
            rid = rec_id or uuid.uuid4().hex[:12]
            if rid in self._items:
                raise GovernanceError(f"recommendation {rid} already exists")
            rec = Recommendation(
                rid, scenario_ref, dict(proposed_change), list(evidence_refs), actor
            )
            self._items[rid] = rec
            self.log.append(
                actor,
                "recommendation.create",
                rid,
                {"scenarioRef": scenario_ref, "proposedChange": proposed_change},
            )
            return rec

    def get(self, rec_id: str) -> Recommendation:
        try:
            return self._items[rec_id]
        except KeyError:
            raise NotFoundError(f"recommendation {rec_id} not found") from None

    def list(self, state: Optional[State] = None) -> List[Recommendation]:
        items = list(self._items.values())
        return [r for r in items if state is None or r.state == state]

    def transition(
        self,
        rec_id: str,
        to: State,
        actor: str,
        roles: Iterable[str] = (),
        comment: Optional[str] = None,
    ) -> Recommendation:
        """Move to ``to`` (state change plus audit entry only)."""
        role_set = set(roles)
        with self._lock:
            rec = self.get(rec_id)
            if to not in ALLOWED[rec.state]:
                raise IllegalTransitionError(
                    f"cannot go from {rec.state.value} to {to.value}"
                )
            if to in (State.APPROVED, State.REJECTED):
                if ROLE_APPROVER not in role_set:
                    raise PermissionDeniedError("approver role required")
                if actor in (rec.created_by, rec.submitted_by):
                    raise PermissionDeniedError(
                        "submitter cannot decide their own item"
                    )
                if to is State.REJECTED and not (comment and comment.strip()):
                    raise CommentRequiredError(
                        "a reviewer comment is required to reject"
                    )
            elif actor != rec.created_by:
                raise PermissionDeniedError("only the creator can submit or withdraw")
            before = rec.state
            rec.state = to
            if to is State.SUBMITTED:
                rec.submitted_by = actor
            if to in (State.APPROVED, State.REJECTED):
                rec.decided_by = actor
                rec.decision_comment = comment
            self.log.append(
                actor,
                f"recommendation.{to.value}",
                rec_id,
                {"from": before.value, "to": to.value, "comment": comment},
            )
            return rec
