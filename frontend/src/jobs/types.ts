/** Shapes of /api/v2/jobs/* (backend/src/jobs/router.py, spec.py, queue.py).
 *  Copied from the code; see src/CONTRACTS_P6.md. Neither route sends a
 *  message: enqueueEnabled is always false and the dry run only validates. */

/** GET /api/v2/jobs/queue-stats (503 when the queue is unavailable). */
export interface QueueStats {
  backend: "sqs" | "memory";
  enqueueEnabled: boolean;
  visible: number;
  inFlight: number;
  deadLetter: number;
}

export interface JobSpec {
  kind: "multi-seed";
  geometry: "signal" | "roundabout";
  numSeeds: number;
  duration: number;
  baseSeed?: number | null;
  config?: Record<string, unknown> | null;
}

/** Body of POST /api/v2/jobs/enqueue-dry-run (camelCase aliases). */
export interface JobRequest {
  run: JobSpec;
  tenant: string;
  runId?: string | null;
  costTags?: Record<string, string>;
  idempotencyKey?: string | null;
  visibilityTimeoutSeconds?: number;
  maxReceives?: number;
}

export interface JobMessage {
  schemaVersion: number;
  jobId: string;
  idempotencyKey: string;
  tenant: string;
  runId: string;
  run: JobSpec;
  costTags: Record<string, string>;
  visibilityTimeoutSeconds: number;
  maxReceives: number;
  enqueuedAt: number;
}

/** POST /api/v2/jobs/enqueue-dry-run (422 with a plain `detail` string when
 *  the job is invalid, for example a missing mandatory cost tag). */
export interface DryRunResponse {
  enqueued: false;
  dryRun: true;
  message: JobMessage;
  messageBytes: number;
}
