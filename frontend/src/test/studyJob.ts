import type { StudyJob } from "../services/studyJobs";

/** A study job as the backend reports it once finished (POST …/jobs or
 *  GET /api/v1/study/jobs/{id}), carrying `result`. */
export function completedJob<T>(result: T): StudyJob<T> {
  return {
    jobId: "job-1",
    kind: "test",
    status: "completed",
    progress: {
      phase: "done",
      total: 10,
      completed: 10,
      fraction: 1,
      running: [],
      elapsedSeconds: 12.3,
      etaSeconds: null,
    },
    result,
    error: null,
  };
}
