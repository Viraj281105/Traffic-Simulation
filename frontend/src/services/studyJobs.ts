import { get, post } from "./api";

/** Live progress of a study job, exactly as the backend reports it
 *  (backend study/runner.py Progress.snapshot). */
export interface StudyProgressSnapshot {
  /** queued → simulating → saving → done */
  phase: "queued" | "simulating" | "saving" | "done";
  /** Simulations in the study (tiers or seeds × both controls). */
  total: number;
  completed: number;
  /** Share of all simulation ticks done, 0–1. */
  fraction: number;
  /** Simulations currently running, e.g. "Tier 3/8 · Roundabout". */
  running: string[];
  elapsedSeconds: number;
  /** Only given once enough work is done for an estimate to mean something. */
  etaSeconds: number | null;
}

export interface StudyJob<T> {
  jobId: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: StudyProgressSnapshot;
  result: T | null;
  error: string | null;
}

export const STUDY_JOB_ROUTES = {
  sweep: "/api/v1/study/sweeps/jobs",
  monteCarlo: "/api/v1/study/validate/monte-carlo/jobs",
  controlComparison: "/api/v1/study/control-comparison/jobs",
} as const;

export const STUDY_POLL_INTERVAL_MS = 1000;

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(signal.reason as Error);
      },
      { once: true },
    );
  });
}

/** Starts a study job and polls it until it finishes, reporting each
 *  progress snapshot. Resolves with the study's result; rejects with the
 *  backend's error, or when `signal` aborts. */
export async function runStudyJob<T>(
  route: string,
  body: unknown,
  onProgress: (job: StudyJob<T>) => void,
  signal: AbortSignal,
): Promise<T> {
  let job = await post<StudyJob<T>>(route, body);
  for (;;) {
    signal.throwIfAborted();
    onProgress(job);
    if (job.status === "completed" && job.result !== null) return job.result;
    if (job.status === "failed") {
      throw new Error(job.error ?? "The study failed");
    }
    await wait(STUDY_POLL_INTERVAL_MS, signal);
    job = await get<StudyJob<T>>(
      `/api/v1/study/jobs/${encodeURIComponent(job.jobId)}`,
    );
  }
}
