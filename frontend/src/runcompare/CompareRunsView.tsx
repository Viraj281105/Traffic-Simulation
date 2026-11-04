import { useMemo, useState } from "react";
import { GitCompare } from "lucide-react";
import "../insights/Insights.css";
import {
  EmptyHint,
  Panel,
  Pill,
  Skeleton,
} from "../components/dashboard/Dashboard";
import { UNAVAILABLE, dateTime, isNum, num, percent } from "../insights/format";
import { useRemote } from "../insights/useRemote";
import { RUN_ID_PATTERN } from "../routing";
import { compareRuns } from "./api";
import { changeTone } from "./changeTone";
import type { RunDiff } from "./types";

function signed(value: number, digits: number): string {
  return `${value > 0 ? "+" : ""}${num(value, digits)}`;
}

export function RunDiffView({ diff }: { diff: RunDiff }) {
  return (
    <div className="ins-stack">
      <p>
        {diff.sameInputs
          ? "Both runs used the same seed, configuration and inputs, so any difference below comes from the code or model."
          : "The runs differ in their setup (see the manifest table), so the metric differences mix the effect of the change with any chance variation."}
      </p>
      <div className="uf-table-wrap">
        <table className="uf-table">
          <caption>Run manifest: what each run was started with.</caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">{diff.a.label}</th>
              <th scope="col">{diff.b.label}</th>
              <th scope="col">Match</th>
            </tr>
          </thead>
          <tbody>
            {diff.manifest.map((f) => (
              <tr key={f.field}>
                <th scope="row">{f.label}</th>
                <td>{f.a ?? UNAVAILABLE}</td>
                <td>{f.b ?? UNAVAILABLE}</td>
                <td>
                  <Pill tone={f.same ? "good" : "warn"}>
                    {f.same ? "Same" : "Different"}
                  </Pill>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="uf-table-wrap">
        <table className="uf-table">
          <caption>
            Metrics. Change is {diff.b.label} compared with {diff.a.label}.
          </caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col">{diff.a.label}</th>
              <th scope="col">{diff.b.label}</th>
              <th scope="col">Change</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {diff.metrics.map((m) => {
              const change = changeTone(m);
              return (
                <tr key={m.id}>
                  <th scope="row">
                    {m.label}
                    {m.unit ? ` (${m.unit})` : ""}
                  </th>
                  <td>{num(m.a)}</td>
                  <td>{num(m.b)}</td>
                  <td>
                    {isNum(m.delta)
                      ? `${signed(m.delta, 2)}${isNum(m.deltaFraction) ? ` (${m.deltaFraction > 0 ? "+" : ""}${percent(m.deltaFraction, 1)})` : ""}`
                      : UNAVAILABLE}
                  </td>
                  <td>
                    <Pill tone={change.tone}>{change.word}</Pill>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="ins-muted">
        Runs: {diff.a.label} ({dateTime(diff.a.createdAt)}) and {diff.b.label} (
        {dateTime(diff.b.createdAt)}). A single run each has no interval; use an
        experiment for a confidence interval.
      </p>
    </div>
  );
}

/** Pick two saved runs and see what differs. */
export function CompareRunsView({
  initialA = "",
  initialB = "",
}: {
  initialA?: string;
  initialB?: string;
}) {
  const [draftA, setDraftA] = useState(initialA);
  const [draftB, setDraftB] = useState(initialB);
  const [chosen, setChosen] = useState<{ a: string; b: string } | null>(
    RUN_ID_PATTERN.test(initialA) && RUN_ID_PATTERN.test(initialB)
      ? { a: initialA, b: initialB }
      : null,
  );
  const valid = RUN_ID_PATTERN.test(draftA) && RUN_ID_PATTERN.test(draftB);
  const load = useMemo(
    () => (chosen ? () => compareRuns(chosen.a, chosen.b) : null),
    [chosen],
  );
  const state = useRemote(load, "The two runs could not be compared.");

  return (
    <Panel
      id="ins-runcompare"
      title="Compare two runs"
      subtitle="See what differs in setup and in results."
    >
      <form
        className="ins-row"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) setChosen({ a: draftA, b: draftB });
        }}
      >
        <div className="uf-field">
          <label className="uf-label" htmlFor="ins-run-a">
            First run ID
          </label>
          <input
            id="ins-run-a"
            className="uf-input"
            value={draftA}
            onChange={(e) => {
              setDraftA(e.target.value.trim());
            }}
          />
        </div>
        <div className="uf-field">
          <label className="uf-label" htmlFor="ins-run-b">
            Second run ID
          </label>
          <input
            id="ins-run-b"
            className="uf-input"
            value={draftB}
            onChange={(e) => {
              setDraftB(e.target.value.trim());
            }}
          />
        </div>
        <button
          type="submit"
          className="ins-btn ins-btn--primary"
          disabled={!valid}
        >
          Compare
        </button>
      </form>
      {state.status === "idle" && (
        <EmptyHint icon={<GitCompare size={22} />} title="Choose two runs">
          Enter two saved run IDs to see them side by side.
        </EmptyHint>
      )}
      {state.status === "loading" && <Skeleton lines={5} />}
      {state.status === "notFound" && (
        <p role="alert">One of those runs was not found.</p>
      )}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <RunDiffView diff={state.data} />}
    </Panel>
  );
}
