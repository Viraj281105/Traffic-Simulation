/**
 * Personal access tokens (backend src/api/tokens_router.py, /api/v3/tokens).
 * A token's secret is shown once, when it is created, and never again.
 */
import { getJson, postJson, ExperimentsApiError } from "./experiments";
import { API_BASE_URL } from "../../config";
import { getAuthToken } from "../../auth/cognito";

export const SCOPES = [
  "experiments:read",
  "experiments:run",
  "packages:read",
  "packages:write",
  "tokens:read",
  "tokens:manage",
] as const;

export type Scope = (typeof SCOPES)[number];

export interface TokenMetadata {
  id: string;
  name: string;
  scopes: Scope[];
  createdAt: string;
  expiresAt: string;
  lastUsedAt: string | null;
}

export interface CreatedToken extends TokenMetadata {
  token: string;
}

export function listTokens(): Promise<{ tokens: TokenMetadata[] }> {
  return getJson("/api/v3/tokens");
}

export function createToken(body: {
  name: string;
  scopes: Scope[];
  expiresInDays: number;
}): Promise<CreatedToken> {
  return postJson("/api/v3/tokens", body);
}

export async function revokeToken(id: string): Promise<void> {
  const token = await getAuthToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(
    `${API_BASE_URL}/api/v3/tokens/${encodeURIComponent(id)}`,
    { method: "DELETE", headers },
  );
  if (!response.ok) {
    throw new ExperimentsApiError(response.status, [
      "The token could not be revoked.",
    ]);
  }
}
