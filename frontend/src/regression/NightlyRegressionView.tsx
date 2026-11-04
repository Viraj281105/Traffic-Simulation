import { useMemo } from "react";
import { MoonStar } from "lucide-react";
import "../insights/Insights.css";
import {
  EmptyHint,
  Panel,
  Pill,
  Skeleton,
  type Tone,
} from "../components/dashboard/Dashboard";
import { dateTime, num } from "../insights/format";
import { useRemote } from "../insights/useRemote";
import { getNightlyRegression } from "./api";
import type { CheckStatus, NightlyRegression, NightlyRun } from "./types";

const STATUS_WORD: Record<CheckStatus, string> = {
  pass: "Passed",
  fail: "Failed",
  error: "Error",
  skipped: "Skipped",
};
const STATUS_TONE: Record<CheckStatus, Tone> = {
  pass: "good",
  fail: "bad",
  error: "warn",
  skipped: "neutral",
};

function minutes(seconds: number): string {
  return seconds < 90 ? `${num(seconds, 0)} s` : `${num(seconds / 60, 1)} min`;
}

function NightDetail({ run }: { run: NightlyRun }) {
  const problems = run.checks.filter(
    (c) => c.status === "fail" || c.status === "error",
  );
  const passed = run.checks.filter((c) => c.status === "pass").length;
  return (
    <li>
      <h3 className="uf-subhead">
        {dateTime(run.startedAt)}{" "}
        <Pill tone={STATUS_TONE[run.status]}>{STATUS_WORD[run.status]}</Pill>
      </h3>
      <p className="ins-muted">
        Commit {run.gitCommit}. {passed} of {run.checks.length} checks passed.
        Took {minutes(run.durationSeconds)}.
        {run.logUrl ? (
          <>
            {" "}
            <a className="uf-link" href={run.logUrl}>
              Open the run log
            </a>
          </>
        ) : null}
      </p>
      {problems.length > 0 && (
        <ul className="ins-messages">
          {problems.map((c) => (
            <li
              key={c.id}
              className={`ins-message ${c.status === "fail" ? "is-error" : "is-warning"}`}
            >
              <div>
                <strong>{c.name}</strong>
                {c.message ? `: ${c.message}` : ""}
                {c.expected != null && c.actual != null && (
                  <span className="ins-message__where">
                    Expected {num(c.expected)} {c.unit ?? ""}, got{" "}
                    {num(c.actual)} {c.unit ?? ""}
                    {c.tolerance != null
                      ? ` (allowed difference ${num(c.tolerance)})`
                      : ""}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function NightlyRegressionTable({ data }: { data: NightlyRegression }) {
  if (data.runs.length === 0) {
    return (
      <EmptyHint icon={<MoonStar size={22} />} title="No nightly runs yet">
        The first result appears after tonight&apos;s run.
      </EmptyHint>
    );
  }
  const latest = data.runs[0];
  const failing = data.runs.filter((r) => r.status !== "pass").length;
  return (
    <div className="ins-stack">
      <p>
        Latest night:{" "}
        <Pill tone={STATUS_TONE[latest.status]}>
          {STATUS_WORD[latest.status]}
        </Pill>{" "}
        {failing === 0
          ? `All ${String(data.runs.length)} nights shown passed.`
          : `${String(failing)} of the last ${String(data.runs.length)} nights did not pass.`}
      </p>
      <ul className="ins-nights" aria-label="Last nights, newest first">
        {data.runs.map((r) => (
          <li
            key={r.id}
            className={`ins-night is-${r.status}`}
            title={`${dateTime(r.startedAt)}: ${STATUS_WORD[r.status]}`}
            role="img"
            aria-label={`${dateTime(r.startedAt)}: ${STATUS_WORD[r.status]}`}
          />
        ))}
      </ul>
      <div className="uf-table-wrap">
        <table className="uf-table">
          <caption>
            Each night re-runs the golden scenarios and compares them with the
            stored results.
          </caption>
          <thead>
            <tr>
              <th scope="col">Night</th>
              <th scope="col">Result</th>
              <th scope="col">Checks passed</th>
              <th scope="col">Commit</th>
              <th scope="col">Duration</th>
            </tr>
          </thead>
          <tbody>
            {data.runs.map((r) => (
              <tr key={r.id}>
                <th scope="row">{dateTime(r.startedAt)}</th>
                <td>
                  <Pill tone={STATUS_TONE[r.status]}>
                    {STATUS_WORD[r.status]}
                  </Pill>
                </td>
                <td>
                  {r.checks.filter((c) => c.status === "pass").length} /{" "}
                  {r.checks.length}
                </td>
                <td>{r.gitCommit}</td>
                <td>{minutes(r.durationSeconds)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {failing > 0 && (
        <>
          <h3 className="uf-subhead">What went wrong</h3>
          <ul className="ins-stack" style={{ listStyle: "none", padding: 0 }}>
            {data.runs
              .filter((r) => r.status !== "pass")
              .map((r) => (
                <NightDetail key={r.id} run={r} />
              ))}
          </ul>
        </>
      )}
      <p className="ins-muted">Updated {dateTime(data.generatedAt)}.</p>
    </div>
  );
}

/** Nightly regression results. */
export function NightlyRegressionView({ limit = 30 }: { limit?: number }) {
  const load = useMemo(() => () => getNightlyRegression(limit), [limit]);
  const state = useRemote(load, "The nightly results could not be loaded.");
  return (
    <Panel
      id="ins-regression"
      title="Nightly regression"
      subtitle="Does last night's code still give the same answers?"
    >
      {state.status === "loading" && <Skeleton lines={5} />}
      {state.status === "notFound" && (
        <EmptyHint icon={<MoonStar size={22} />} title="No nightly results yet">
          The nightly regression has not reported yet.
        </EmptyHint>
      )}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <NightlyRegressionTable data={state.data} />}
    </Panel>
  );
}
