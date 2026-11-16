import { V2, getJson, postJson } from "../netcommon/api";
import type {
  AuditLog,
  AuditVerification,
  CreateInput,
  Recommendation,
  RecommendationList,
  TransitionInput,
} from "./types";

const BASE = `${V2}/governance`;

/** GET /api/v2/governance/recommendations */
export function listRecommendations(): Promise<RecommendationList> {
  return getJson(`${BASE}/recommendations`);
}

/** POST /api/v2/governance/recommendations (201) */
export function createRecommendation(
  input: CreateInput,
): Promise<Recommendation> {
  return postJson(`${BASE}/recommendations`, input);
}

/** POST /api/v2/governance/recommendations/{id}/transition */
export function transitionRecommendation(
  id: string,
  input: TransitionInput,
): Promise<Recommendation> {
  return postJson(
    `${BASE}/recommendations/${encodeURIComponent(id)}/transition`,
    input,
  );
}

/** GET /api/v2/governance/audit */
export function getAudit(): Promise<AuditLog> {
  return getJson(`${BASE}/audit`);
}

/** GET /api/v2/governance/audit/verify */
export function verifyAudit(): Promise<AuditVerification> {
  return getJson(`${BASE}/audit/verify`);
}
