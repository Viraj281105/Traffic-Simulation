import "../netcommon/network.css";
import { clock, num, percent, withUnit } from "../netcommon/format";
import { BarChart } from "../rescommon/BarChart";
import { formulaText } from "./formula";
import type { ResilienceResponse, Strategy } from "./types";

const STRATEGY_LABEL: Record<Strategy, string> = {
  fixed_time: "Fixed-time signals",
  max_pressure: "Max-pressure signals",
};

/** Strategy comparison: scores with intervals, then every figure in a table. */
export function ResilienceView({ result }: { result: ResilienceResponse }) {
  const entries = (Object.keys(result.strategies) as Strategy[]).flatMap(
    (k) => {
      const s = result.strategies[k];
      return s ? [[k, s] as const] : [];
    },
  );
  const f = result.scoreFormula;
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        Best under this scenario: {STRATEGY_LABEL[result.best]} (over{" "}
        {num(result.seeds.length, 0)} seeds).
      </p>
      <BarChart
        ariaLabel="Resilience score of each signal strategy with its 95 percent interval"
        axisLabel="Resilience score (0 to 1, higher is better)"
        bars={entries.map(([k, s]) => ({
          id: k,
          label: STRATEGY_LABEL[k],
          value: s.score,
          interval: s.scoreInterval,
        }))}
      />
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Resilience figures per strategy, mean over the seeds.
          </caption>
          <thead>
            <tr>
              <th scope="col">Strategy</th>
              <th scope="col">Score</th>
              <th scope="col">95% interval</th>
              <th scope="col">Recovery time</th>
              <th scope="col">Runs recovered</th>
              <th scope="col">Peak delay</th>
              <th scope="col">Peak extra delay</th>
              <th scope="col">Throughput loss</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([k, s]) => (
              <tr key={k}>
                <th scope="row">{STRATEGY_LABEL[k]}</th>
                <td className="nw-num">{num(s.score, 3)}</td>
                <td className="nw-num">
                  {s.scoreInterval
                    ? `${num(s.scoreInterval[0], 3)} to ${num(s.scoreInterval[1], 3)}`
                    : "One seed, no interval"}
                </td>
                <td className="nw-num">
                  {s.recoveryTimeSeconds === null
                    ? "Never recovered"
                    : clock(s.recoveryTimeSeconds)}
                </td>
                <td className="nw-num">
                  {num(s.recoveredRuns, 0)} of {num(s.runs, 0)}
                </td>
                <td className="nw-num">{withUnit(s.peakDelaySeconds, "s")}</td>
                <td className="nw-num">
                  {withUnit(s.peakExcessDelaySeconds, "s")}
                </td>
                <td className="nw-num">{percent(s.throughputLoss, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="nw-stack" aria-label="How the score is worked out">
        <h3 className="nw-headline">How the score is worked out</h3>
        <p>{formulaText(f)}</p>
        <ul className="nw-facts">
          <li>
            Recovery: 1 minus the recovery time over the time left after the
            disruption ends (0 if it never recovered).
          </li>
          <li>
            Throughput: 1 minus the share of finished vehicles lost against the
            undisturbed run.
          </li>
          <li>
            Peak: 1 over 1 plus the peak extra delay divided by{" "}
            {num(f.peakScaleSeconds, 0)} s.
          </li>
          <li>
            Area: 1 over 1 plus the mean extra delay divided by{" "}
            {num(f.areaScaleSeconds, 0)} s.
          </li>
          <li>Interval: {f.interval}.</li>
          <li>
            Recovered means delay stays within{" "}
            {percent(result.tolerance.relative, 0)} plus{" "}
            {num(result.tolerance.absoluteSeconds, 0)} s of the undisturbed run
            for {num(result.tolerance.holdBuckets, 0)} buckets in a row.
          </li>
        </ul>
      </section>
      <p className="nw-alert" role="note">
        In-model only. {result.note} The weights and scales are modelling
        choices, not measurements.
      </p>
    </div>
  );
}
