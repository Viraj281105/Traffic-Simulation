import type { ReactNode } from "react";
import type { StudyProgressSnapshot } from "../../services/studyJobs";
import { formatDuration } from "../../utils/time";
import { LoaderMark } from "./Loader";

const PHASE_TEXT = {
  queued: "Starting simulation workers…",
  saving: "Saving results…",
  done: "Finishing…",
} as const;

/** Live progress of a long-running study (volume sweep, Monte Carlo). Every
 *  number is the backend's own count: simulations finished, ticks done,
 *  what is running now and time elapsed. The estimate appears only once the
 *  backend has enough completed work to extrapolate from. */
export function StudyProgress({
  title,
  progress,
  className = "",
}: {
  title: ReactNode;
  progress: StudyProgressSnapshot | null;
  className?: string;
}) {
  const percent = progress ? Math.round(progress.fraction * 100) : 0;
  const running = progress?.running ?? [];
  const phase =
    !progress || progress.phase === "queued"
      ? PHASE_TEXT.queued
      : progress.phase === "simulating"
        ? null
        : PHASE_TEXT[progress.phase];

  return (
    <div
      className={`study-progress ${className}`.trim()}
      role="status"
      aria-live="polite"
    >
      <div className="study-progress__head">
        <LoaderMark size={22} />
        <strong className="study-progress__title">{title}</strong>
        {progress && progress.total > 0 && (
          <span className="study-progress__count">
            {progress.completed} / {progress.total} simulations complete
          </span>
        )}
      </div>
      <div
        className="study-progress__bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="Simulation progress"
      >
        <span style={{ width: `${percent.toString()}%` }} />
      </div>
      <div className="study-progress__meta">
        <span>
          {phase ??
            (running.length > 0
              ? `Running: ${running.slice(0, 3).join(", ")}${
                  running.length > 3
                    ? ` +${(running.length - 3).toString()} more`
                    : ""
                }`
              : "Waiting for a free worker…")}
        </span>
        {progress && (
          <span className="study-progress__times">
            {percent}% · Elapsed {formatDuration(progress.elapsedSeconds)}
            {progress.etaSeconds !== null &&
              ` · ~${formatDuration(progress.etaSeconds)} remaining`}
          </span>
        )}
      </div>
    </div>
  );
}
