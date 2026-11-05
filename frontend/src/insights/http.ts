/**
 * Shared transport for the Phase 4/5 result screens (comparison, sensitivity,
 * KPIs, run compare, regression, reports, RL, networks).
 *
 * It reuses the /api/v3 transport of the Robustness Lab client, so auth, the
 * 120 s timeout and the server's error envelope behave the same everywhere.
 * The endpoint shapes are the contract in src/CONTRACTS.md.
 */
import {
  ExperimentsApiError,
  getJson,
  postJson,
} from "../services/v3/experiments";

export { getJson, postJson };
export { ExperimentsApiError as InsightsApiError };

export const V3 = "/api/v3";

/** The text to show for a failed request: the server's reasons when it gave
 *  them, otherwise `fallback`. */
export function errorText(err: unknown, fallback: string): string {
  return err instanceof ExperimentsApiError && err.message
    ? err.message
    : fallback;
}

/** True for a "not found" answer, which several screens show as "not ready". */
export function isNotFound(err: unknown): boolean {
  return err instanceof ExperimentsApiError && err.status === 404;
}

/** A query string from the defined entries of `params` (empty if none). */
export function query(
  params: Record<string, string | number | undefined>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}
