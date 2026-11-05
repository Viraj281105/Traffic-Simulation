/** Contract fixtures for /api/v2/jobs/*. Invented values. */
import type { DryRunResponse, QueueStats } from "./types";

export const queueStatsFixture: QueueStats = {
  backend: "memory",
  enqueueEnabled: false,
  visible: 3,
  inFlight: 1,
  deadLetter: 0,
};

export const dryRunFixture: DryRunResponse = {
  enqueued: false,
  dryRun: true,
  message: {
    schemaVersion: 1,
    jobId: "0123456789abcdef",
    idempotencyKey: "abc123",
    tenant: "acme",
    runId: "run0123456789abcdef01",
    run: {
      kind: "multi-seed",
      geometry: "signal",
      numSeeds: 5,
      duration: 30,
      baseSeed: null,
      config: null,
    },
    costTags: {
      project: "urbanflow",
      env: "staging",
      owner: "team",
      tenant: "acme",
      "run-id": "run0123456789abcdef01",
    },
    visibilityTimeoutSeconds: 900,
    maxReceives: 3,
    enqueuedAt: 1790000000,
  },
  messageBytes: 412,
};
