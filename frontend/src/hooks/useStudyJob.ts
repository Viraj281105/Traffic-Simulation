import { useCallback, useEffect, useRef, useState } from "react";
import { runStudyJob, type StudyProgressSnapshot } from "../services/studyJobs";

/** Runs a backend study job (volume sweep, Monte Carlo) and exposes its live
 *  progress. Polling stops when the job finishes, a new one starts, or the
 *  component unmounts. */
export function useStudyJob() {
  const [progress, setProgress] = useState<StudyProgressSnapshot | null>(null);
  const controller = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );

  const run = useCallback(
    async <T>(route: string, body: unknown): Promise<T> => {
      controller.current?.abort();
      const ctrl = new AbortController();
      controller.current = ctrl;
      setProgress(null);
      try {
        return await runStudyJob<T>(
          route,
          body,
          (job) => {
            setProgress(job.progress);
          },
          ctrl.signal,
        );
      } finally {
        if (controller.current === ctrl) setProgress(null);
      }
    },
    [],
  );

  return { run, progress };
}
