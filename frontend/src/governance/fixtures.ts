/** Contract fixtures for /api/v2/governance: shapes from
 *  backend/src/governance/workflow.py and audit.py. Invented values. */
import type {
  AuditLog,
  AuditVerification,
  Recommendation,
  RecommendationList,
} from "./types";

export const draftFixture: Recommendation = {
  id: "rec-1",
  scenarioRef: "junction-a/peak",
  proposedChange: { greenSeconds: 30 },
  evidenceRefs: [],
  createdBy: "analyst",
  state: "draft",
  submittedBy: null,
  decidedBy: null,
  decisionComment: null,
};

export const submittedFixture: Recommendation = {
  ...draftFixture,
  state: "submitted",
  submittedBy: "analyst",
};

export const approvedFixture: Recommendation = {
  ...submittedFixture,
  state: "approved",
  decidedBy: "reviewer",
  decisionComment: "Looks right.",
};

export const listFixture: RecommendationList = { items: [submittedFixture] };

export const auditFixture: AuditLog = {
  total: 1,
  head: "abc123",
  entries: [
    {
      seq: 0,
      timestamp: 1_700_000_000,
      actor: "analyst",
      action: "recommendation.submitted",
      subject: "rec-1",
      payloadDigest: "d1",
      prevHash: "0",
      hash: "abc123",
    },
  ],
};

export const verifyOkFixture: AuditVerification = {
  ok: true,
  length: 1,
  head: "abc123",
  error: null,
  badSeq: null,
};
