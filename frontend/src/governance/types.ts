/** Shapes of /api/v2/governance (backend/src/governance/router.py,
 *  workflow.py, audit.py). Copied from the code; see src/CONTRACTS_P7.md.
 *  Advisory only: nothing here applies a recommendation. */

export type RecState =
  "draft" | "submitted" | "approved" | "rejected" | "withdrawn";

export interface Recommendation {
  id: string;
  scenarioRef: string;
  proposedChange: Record<string, unknown>;
  evidenceRefs: string[];
  createdBy: string;
  state: RecState;
  submittedBy: string | null;
  decidedBy: string | null;
  decisionComment: string | null;
}

export interface RecommendationList {
  items: Recommendation[];
}

export interface CreateInput {
  actor: string;
  scenarioRef: string;
  proposedChange: Record<string, unknown>;
  evidenceRefs: string[];
}

export interface TransitionInput {
  actor: string;
  roles: string[];
  to: RecState;
  comment: string | null;
}

export interface AuditEntry {
  seq: number;
  /** Seconds since the epoch. */
  timestamp: number;
  actor: string;
  action: string;
  subject: string;
  payloadDigest: string;
  prevHash: string;
  hash: string;
}

export interface AuditLog {
  total: number;
  head: string;
  entries: AuditEntry[];
}

export interface AuditVerification {
  ok: boolean;
  length: number;
  head: string;
  error: string | null;
  badSeq: number | null;
}
