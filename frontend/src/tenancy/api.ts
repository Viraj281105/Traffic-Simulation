import { V2, getJson } from "../netcommon/api";
import type { MeResponse, UsageResponse } from "./types";

export function getMe(): Promise<MeResponse> {
  return getJson(`${V2}/tenancy/me`);
}

export function getUsage(): Promise<UsageResponse> {
  return getJson(`${V2}/tenancy/usage`);
}

/** What to tell the person when a tenancy or jobs request is refused. */
export function accessMessage(status: number | null, fallback: string): string {
  if (status === 401 || status === 403 || status === 503) {
    return "This needs a sign-in through an OIDC identity provider whose token carries a tenant claim. The current session does not have one, or tenancy is not configured on this server.";
  }
  return fallback;
}
