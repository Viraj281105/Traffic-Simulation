"""Proposal lifecycle: propose -> (inspect) -> confirm -> ordinary experiment submission.

Proposals are short-lived, in memory, and belong to their creator: another user's proposal id is a 404.
Confirmation needs the proposal's id *and* its content hash, works once, and only for a proposal the
validation boundary passed; the experiment then goes through ``ExperimentService.submit`` like any other
request (authentication, ownership, quotas and limits all apply).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import secrets
import threading
from typing import Any, Dict, List, Optional, Tuple

from src.experiments.service import ExperimentService, NotFound

from . import interpretation as interp
from .catalog import catalogue_hash
from .llm import (
    PROMPT_TEMPLATE_VERSION,
    interpret_with_model,
    propose_with_model,
)
from .models import (
    INTERPRETATION_FORMAT,
    ExperimentIntent,
    ExperimentProposal,
    Provenance,
    ReproducibilityMetadata,
)
from .proposer import PROPOSER_VERSION, build_experiment, propose_deterministic
from .validation import apply_suggestion, validate_experiment

PROPOSAL_TTL_SECONDS = 30 * 60
MAX_PROPOSALS_PER_USER = 50  # kept at once
DEFAULT_PROPOSALS_PER_DAY = 100
DEFAULT_INTERPRETATIONS_PER_DAY = 100


class CopilotQuotaExceeded(RuntimeError):  # noqa: N818
    pass


class ProposalConflict(RuntimeError):  # noqa: N818
    pass


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def content_hash(experiment: Dict[str, Any]) -> str:
    canonical = json.dumps(experiment, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _limit(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, "").strip() or default))
    except ValueError:
        return default


class CopilotService:
    def __init__(self, experiments: ExperimentService) -> None:
        self.experiments = experiments
        self._lock = threading.Lock()
        self._proposals: Dict[str, Tuple[str, ExperimentProposal]] = {}
        self._daily: Dict[Tuple[str, str, str], int] = {}

    # ---- quotas ------------------------------------------------------------------------------------
    def _count(self, user_id: str, kind: str, limit: int) -> None:
        day = _now().date().isoformat()
        with self._lock:
            for key in [k for k in self._daily if k[2] != day]:
                del self._daily[key]
            key = (user_id, kind, day)
            if self._daily.get(key, 0) >= limit:
                raise CopilotQuotaExceeded(
                    f"quota copilot{kind.capitalize()}PerDay: {limit} {kind} per user per day"
                )
            self._daily[key] = self._daily.get(key, 0) + 1

    # ---- proposals ---------------------------------------------------------------------------------
    def propose(
        self, user_id: str, question: str, mode: str = "auto"
    ) -> ExperimentProposal:
        self._count(
            user_id,
            "proposals",
            _limit("COPILOT_PROPOSALS_PER_DAY", DEFAULT_PROPOSALS_PER_DAY),
        )
        intent: Optional[ExperimentIntent] = None
        provenance: Dict[str, Provenance] = {}
        unavailable: Optional[str] = None
        if mode == "auto":
            intent, provenance, unavailable = propose_with_model(
                question, f"copilot:{user_id}"
            )
        if intent is None:
            intent, provenance = propose_deterministic(question)
            used = "deterministic"
        else:
            used = "model"
        return self._finish(user_id, question, intent, provenance, used, unavailable)

    def _finish(
        self,
        user_id: str,
        question: str,
        intent: ExperimentIntent,
        provenance: Dict[str, Provenance],
        mode: str,
        unavailable: Optional[str],
        experiment: Optional[Dict[str, Any]] = None,
    ) -> ExperimentProposal:
        built, checks = build_experiment(intent, question)
        experiment = experiment or built
        valid, issues, runs, seconds = validate_experiment(experiment)
        now = _now()
        from src.ai import groq_client as gc

        proposal = ExperimentProposal(
            id="prop_" + secrets.token_hex(8),
            question=question,
            mode=mode,  # type: ignore[arg-type]
            aiUnavailableReason=unavailable if mode == "deterministic" else None,
            intent=intent,
            experiment=experiment,
            fieldProvenance=provenance,
            assumptions=list(intent.assumptions),
            warnings=list(intent.warnings),
            suggestedChecks=checks,
            clarification=intent.clarification,
            estimatedRuns=runs,
            estimatedSimulatedSeconds=seconds,
            reproducibilityMetadata=ReproducibilityMetadata(
                proposer=mode,  # type: ignore[arg-type]
                proposerVersion=PROPOSER_VERSION
                if mode == "deterministic"
                else PROMPT_TEMPLATE_VERSION,
                provider="groq" if mode == "model" else None,
                model=gc._MODEL if mode == "model" else None,
                promptTemplateVersion=PROMPT_TEMPLATE_VERSION
                if mode == "model"
                else None,
                catalogueHash=catalogue_hash(),
            ),
            validated=valid,
            issues=issues,
            contentHash=content_hash(experiment),
            createdAt=now.isoformat(),
            expiresAt=(now + _dt.timedelta(seconds=PROPOSAL_TTL_SECONDS)).isoformat(),
        )
        with self._lock:
            self._evict(now)
            mine = [k for k, (owner, _) in self._proposals.items() if owner == user_id]
            for old in mine[: max(0, len(mine) - MAX_PROPOSALS_PER_USER + 1)]:
                del self._proposals[old]
            self._proposals[proposal.id] = (user_id, proposal)
        return proposal

    def _evict(self, now: _dt.datetime) -> None:
        for key in [
            k
            for k, (_, p) in self._proposals.items()
            if _dt.datetime.fromisoformat(p.expiresAt) <= now
        ]:
            del self._proposals[key]

    def get(self, user_id: str, proposal_id: str) -> ExperimentProposal:
        with self._lock:
            self._evict(_now())
            found = self._proposals.get(proposal_id)
        if found is None or found[0] != user_id:
            raise NotFound(proposal_id)
        return found[1]

    def apply_suggestion(
        self, user_id: str, proposal_id: str, code: str
    ) -> ExperimentProposal:
        """A *new* proposal with one validation suggestion applied, validated again (never silent repair)."""
        original = self.get(user_id, proposal_id)
        issue = next(
            (i for i in original.issues if i.code == code and i.suggestion), None
        )
        if issue is None or issue.suggestion is None:
            raise ProposalConflict(
                f"proposal {proposal_id} has no suggestion for {code}"
            )
        self._count(
            user_id,
            "proposals",
            _limit("COPILOT_PROPOSALS_PER_DAY", DEFAULT_PROPOSALS_PER_DAY),
        )
        changed = apply_suggestion(original.experiment, issue.suggestion)
        provenance = dict(original.fieldProvenance)
        for key in issue.suggestion:
            provenance[key] = "rule"
        return self._finish(
            user_id,
            original.question,
            original.intent,
            provenance,
            original.mode,
            original.aiUnavailableReason,
            experiment=changed,
        )

    def confirm(
        self, user_id: str, proposal_id: str, given_hash: str
    ) -> Dict[str, Any]:
        """Submit a validated proposal's experiment. Single use; bound to the creator and content hash."""
        with self._lock:
            self._evict(_now())
            found = self._proposals.get(proposal_id)
            if found is None or found[0] != user_id:
                raise NotFound(proposal_id)
            proposal = found[1]
            if proposal.confirmed:
                raise ProposalConflict("this proposal was already confirmed")
            if not secrets.compare_digest(proposal.contentHash, given_hash):
                raise ProposalConflict("the content hash does not match this proposal")
            if not proposal.validated:
                raise ProposalConflict(
                    "this proposal did not pass validation and cannot be submitted"
                )
            if content_hash(proposal.experiment) != proposal.contentHash:
                raise ProposalConflict("the proposal changed after it was validated")
            proposal.confirmed = (
                True  # reserved before submitting: a second confirm is refused
            )
        try:
            status = self.experiments.submit(user_id, proposal.experiment)
        except Exception:
            with self._lock:
                proposal.confirmed = False
            raise
        with self._lock:
            proposal.experimentId = status["id"]
        return status

    # ---- interpretation ----------------------------------------------------------------------------
    def interpret(
        self,
        user_id: str,
        experiment_id: str,
        preferred: Optional[str],
        mode: str = "auto",
    ) -> Dict[str, Any]:
        result = self.experiments.result(user_id, experiment_id)
        if result.get("format") != "urbanflow-experiment-result":
            raise ProposalConflict("only a completed experiment can be interpreted")
        self._count(
            user_id,
            "interpretations",
            _limit("COPILOT_INTERPRETATIONS_PER_DAY", DEFAULT_INTERPRETATIONS_PER_DAY),
        )
        evidence = interp.build_evidence(result)
        if preferred is not None and preferred not in evidence["alternatives"]:
            raise ProposalConflict(
                f"{preferred!r} is not an alternative of this experiment"
            )
        template = interp.template_summary(evidence, preferred)
        mandatory = interp.mandatory_sections(evidence, preferred)
        out: Dict[str, Any] = {
            "format": INTERPRETATION_FORMAT,
            "version": 1,
            "experimentId": experiment_id,
            "measured": evidence,
            "template": template,
            "interpretation": None,
            "unfavourableFindings": interp.unfavourable_findings(evidence, preferred),
            "aiUnavailableReason": None,
        }
        if mode == "template":
            return out
        text, reason = interpret_with_model(
            {"evidence": evidence, "preferred": preferred}, f"copilot:{user_id}"
        )
        if text is None:
            out["aiUnavailableReason"] = reason
            return out
        ok, ungrounded = interp.grounding_check(text, evidence)
        if not ok:
            out["aiUnavailableReason"] = (
                "the model's text cited numbers that are not in the measured results, so it is not shown"
            )
            out["grounding"] = {"passed": False, "ungroundedCount": len(ungrounded)}
            return out
        out["interpretation"] = {
            "label": "Model-generated interpretation",
            "text": text + "\n\n" + "\n".join(mandatory),
            "grounding": {"passed": True},
        }
        return out

    def list_for_user(self, user_id: str) -> List[ExperimentProposal]:
        with self._lock:
            self._evict(_now())
            return [p for owner, p in self._proposals.values() if owner == user_id]
