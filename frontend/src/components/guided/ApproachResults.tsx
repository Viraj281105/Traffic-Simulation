import { Fragment, type CSSProperties } from "react";
import type { RunningMetrics } from "../../types/simulation";
import { seconds } from "../../metrics/plainLanguage";
import { APPROACHES } from "../../scenario/scenarioTypes";
import type { ScenarioDocument } from "../../scenario/scenarioTypes";
import type { StrategyInfo } from "../../strategies/strategyCatalog";

type Breakdown = RunningMetrics["approachBreakdown"];

/** One strategy's column in a breakdown table. */
export interface BreakdownColumn<B> {
  strategy: Pick<StrategyInfo, "id" | "name" | "color">;
  breakdown: B;
}

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Per-approach results (V1.4) for a junction the user built: how much traffic
 * each road offered, and under each strategy how many of its drivers got
 * through and the time they lost. An uneven junction — a busy main road, a
 * quiet side street — can look fine on average while one road queues.
 *
 * The figures are the backend's own per-approach split of the delay the
 * headline uses (metrics.approachBreakdown), so they reconcile with it.
 */
export function ApproachResults({
  scenario,
  columns,
}: {
  scenario: ScenarioDocument;
  columns: BreakdownColumn<Breakdown>[];
}) {
  if (!columns.some((c) => c.breakdown)) return null;
  const cell = (b: Breakdown, a: (typeof APPROACHES)[number]) => {
    const entry = b?.[a];
    if (!entry || entry.exited === 0) return <td colSpan={2}>none through</td>;
    return (
      <>
        <td>{String(entry.exited)}</td>
        <td>{seconds(entry.averageDelay)}</td>
      </>
    );
  };
  return (
    <section className="results-section" aria-labelledby="r-approaches">
      <h2 id="r-approaches">Which roads lose the time?</h2>
      <p>
        Your junction is not the same in every direction, so an average can hide
        a road that queues. This splits the result by where drivers came from.
      </p>
      <div className="table-scroll">
        <table className="plain-table">
          <thead>
            <tr>
              <th scope="col" rowSpan={2}>
                Coming from
              </th>
              <th scope="col" rowSpan={2}>
                Lanes · traffic offered
              </th>
              {columns.map((c) => (
                <th
                  scope="colgroup"
                  colSpan={2}
                  key={c.strategy.id}
                  style={
                    { "--strategy-color": c.strategy.color } as CSSProperties
                  }
                >
                  <span className="strategy-label">
                    <span className="strategy-dot" aria-hidden="true" />
                    {c.strategy.name}
                  </span>
                </th>
              ))}
            </tr>
            <tr>
              {columns.map((c) => (
                <FragmentHeads key={c.strategy.id} />
              ))}
            </tr>
          </thead>
          <tbody>
            {APPROACHES.map((a) => {
              // V1.5: a slot with no road has no row.
              const arm = scenario.approaches[a];
              if (!arm) return null;
              return (
                <tr key={a}>
                  <th scope="row">{cap(a)}</th>
                  <td>
                    {arm.lanes} ·{" "}
                    {Math.round(arm.vehiclesPerHour).toLocaleString()} veh/h
                  </td>
                  {columns.map((c) => (
                    <Fragment key={c.strategy.id}>
                      {cell(c.breakdown, a)}
                    </Fragment>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FragmentHeads() {
  return (
    <>
      <th scope="col">Got through</th>
      <th scope="col">Time lost (avg)</th>
    </>
  );
}
