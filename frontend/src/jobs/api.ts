import { V2, getJson, postJson } from "../netcommon/api";
import type { DryRunResponse, JobRequest, QueueStats } from "./types";

export function getQueueStats(): Promise<QueueStats> {
  return getJson(`${V2}/jobs/queue-stats`);
}

/** POST /api/v2/jobs/enqueue-dry-run: validates and returns the message that
 *  would be sent; nothing is enqueued. */
export function enqueueDryRun(request: JobRequest): Promise<DryRunResponse> {
  return postJson(`${V2}/jobs/enqueue-dry-run`, request);
}
