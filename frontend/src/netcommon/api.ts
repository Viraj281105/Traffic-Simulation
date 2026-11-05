/**
 * Transport for the network screens (/app/network). It reuses the /api/v3
 * client of the Robustness Lab, so the bearer token, the 120 s timeout and the
 * server's error envelope behave as everywhere else. The network backends
 * live under /api/v2 (see src/CONTRACTS_P5.md); the transport does not care
 * about the prefix.
 */
import {
  InsightsApiError,
  errorText,
  getJson,
  postJson,
} from "../insights/http";

export { InsightsApiError, errorText, getJson, postJson };

export const V2 = "/api/v2";
export const V3 = "/api/v3";
