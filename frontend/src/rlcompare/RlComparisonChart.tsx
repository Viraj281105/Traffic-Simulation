import { useMemo } from "react";
import { Brain } from "lucide-react";
import "../insights/Insights.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { IntervalPlot } from "../insights/IntervalPlot";
import { interval, num, pValueText, withUnit } from "../insights/format";
import { useRemote } from "../insights/useRemote";
import { getRlComparison } from "./api";
import { rlHeadline } from "./rlText";
import type { RlComparison } from "./types";

export function RlComparisonView({
  comparison: c,
}: {
  comparison: RlComparison;
}) {
  const level = `${String(Math.round(c.confidenceLevel * 100))}%`;
  const rows = c.scenarios.flatMap((s) => [
    {
      id: `${s.scenarioId}-fixed`,
      label: `${s.label}: ${c.fixedTime.label}`,
      value: s.fixedTime.mean,
      ci: s.fixedTime.ci,
      tone: "muted" as const,
    },
    {
      id: `${s.scenarioId}-rl`,
      label: `${s.label}: ${c.rl.label}`,
      value: s.rl.mean,
      ci: s.rl.ci,
      tone: "accent" as const,
    },
  ]);
  return (
    <div className="ins-stack">
      <p className="ins-headline">{rlHeadline(c)}</p>
      <p>
        Overall gap in {c.metric.label.toLowerCase()} ({c.rl.label} minus{" "}
        {c.fixedTime.label}): {withUnit(c.difference.mean, c.metric.unit)}.{" "}
        {level} interval: {interval(c.difference.ci, c.metric.unit)};{" "}
        {pValueText(c.difference.pValue)}.
        {c.metric.lowerIsBetter ? " Lower is better." : " Higher is better."}
      </p>
      <IntervalPlot
        rows={rows}
        unit={c.metric.unit}
        ariaLabel={`${c.metric.label} for ${c.rl.label} and ${c.fixedTime.label} in each scenario, with ${level} confidence intervals`}
      />
      <div className="uf-table-wrap">
        <table className="uf-table">
          <caption>
            Mean {c.metric.label.toLowerCase()} with {level} interval, per
            scenario.
          </caption>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">{c.fixedTime.label}</th>
              <th scope="col">{c.rl.label}</th>
              <th scope="col">Seeds</th>
            </tr>
          </thead>
          <tbody>
            {c.scenarios.map((s) => (
              <tr key={s.scenarioId}>
                <th scope="row">{s.label}</th>
                <td>
                  {num(s.fixedTime.mean)} ({interval(s.fixedTime.ci, "")})
                </td>
                <td>
                  {num(s.rl.mean)} ({interval(s.rl.ci, "")})
                </td>
                <td>{s.rl.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="ins-muted">
        Policy {c.rl.policyId} ({c.rl.algorithm}, {num(c.rl.trainingSteps, 0)}{" "}
        training steps) on {c.junction}.
      </p>
      {c.caveats.length > 0 && (
        <ul className="ins-facts">
          {c.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** RL against fixed-time on one junction, with intervals. */
export function RlComparisonChart({ comparisonId }: { comparisonId: string }) {
  const load = useMemo(
    () => () => getRlComparison(comparisonId),
    [comparisonId],
  );
  const state = useRemote(load, "The RL comparison could not be loaded.");
  return (
    <Panel
      id="ins-rl"
      title="RL against fixed-time"
      subtitle="Same junction, same seeds, with uncertainty."
    >
      {state.status === "loading" && <Skeleton lines={4} />}
      {state.status === "notFound" && (
        <EmptyHint icon={<Brain size={22} />} title="No RL comparison yet">
          That comparison was not found.
        </EmptyHint>
      )}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <RlComparisonView comparison={state.data} />}
    </Panel>
  );
}
