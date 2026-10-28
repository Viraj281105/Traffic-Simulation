import {
  SCOPES,
  type Scope,
  type TokenMetadata,
} from "../../services/v3/tokens";

const DAY_MS = 86_400_000;

/** Scopes that can change or remove something, as opposed to only reading. */
export const CHANGES_DATA: Record<Scope, boolean> = {
  "experiments:read": false,
  "experiments:run": true,
  "packages:read": false,
  "packages:write": true,
  "tokens:read": false,
  "tokens:manage": true,
};

/** Whole days left until `expiresAt` (never negative). */
export function daysLeft(expiresAt: string, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / DAY_MS));
}

/** Fraction of the token's lifetime that remains, 0–1. */
export function lifeLeft(t: TokenMetadata, now: number): number {
  const total = Date.parse(t.expiresAt) - Date.parse(t.createdAt);
  if (!(total > 0)) return 0;
  return Math.max(0, Math.min(1, (Date.parse(t.expiresAt) - now) / total));
}

/** How many of the listed tokens grant each scope. */
export function scopeCoverage(tokens: TokenMetadata[]): Record<Scope, number> {
  const out = Object.fromEntries(SCOPES.map((s) => [s, 0])) as Record<
    Scope,
    number
  >;
  for (const t of tokens) for (const s of t.scopes) out[s] += 1;
  return out;
}
