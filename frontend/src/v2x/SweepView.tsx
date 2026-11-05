import "../netcommon/network.css";
import { LineChart, type LineSeries } from "../netcommon/LineChart";
import { num, percent } from "../netcommon/format";
import { KEYS, METRIC_LABEL, TONES, changeText } from "./labels";
import type { SweepRow, V2xExperiment } from "./types";

function series(sweep: SweepRow[]): LineSeries[] {
  return KEYS.map((k, i) => ({
    id: k,
    label: METRIC_LABEL[k].label,
    tone: TONES[i],
    dashed: i > 1,
    points: sweep.map((r) => ({
      x: r.penetration * 100,
      y: r.metrics[k].changePct,
    })),
  }));
}

/** Penetration sweep: change against the non-connected baseline (negative is
 *  a benefit), the per-vehicle numbers with paired intervals, and how many
 *  messages arrived. */
export function SweepView({ result }: { result: V2xExperiment }) {
  const full = [...result.sweep].sort(
    (a, b) => b.penetration - a.penetration,
  )[0];
  const first = full.metrics.delaySeconds;
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        With {percent(full.penetration)} of vehicles connected, delay changes by{" "}
        {first.changePct === null
          ? "an amount not available"
          : `${num(first.changePct, 1)}%`}{" "}
        against no connected vehicles.
      </p>
      <LineChart
        series={series(result.sweep)}
        xLabel="Connected vehicles (%)"
        yLabel="Change against baseline (%)"
        ariaLabel="Change in delay, stops, fuel and CO2 against the baseline as more vehicles are connected; below zero is a benefit"
      />
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Change per vehicle, cooperative minus baseline, with the paired{" "}
            {percent(result.provenance.confidence)} interval. Negative is a
            benefit.
          </caption>
          <thead>
            <tr>
              <th scope="col">Connected</th>
              {KEYS.map((k) => (
                <th key={k} scope="col">
                  {METRIC_LABEL[k].label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.sweep.map((r) => (
              <tr key={r.penetration}>
                <th scope="row">{percent(r.penetration)}</th>
                {KEYS.map((k) => (
                  <td key={k} className="nw-num">
                    {changeText(r.metrics[k], METRIC_LABEL[k].unit)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>Messages by share of connected vehicles.</caption>
          <thead>
            <tr>
              <th scope="col">Connected</th>
              <th scope="col">Delivery ratio</th>
              <th scope="col">Mean age when used</th>
              <th scope="col">Messages sent</th>
              <th scope="col">Stops avoided</th>
            </tr>
          </thead>
          <tbody>
            {result.sweep.map((r) => (
              <tr key={r.penetration}>
                <th scope="row">{percent(r.penetration)}</th>
                <td className="nw-num">
                  {r.messageDeliveryRatio === null
                    ? "No messages"
                    : percent(r.messageDeliveryRatio, 1)}
                </td>
                <td className="nw-num">
                  {r.meanMessageAgeAtUseSeconds === null
                    ? "Not available"
                    : `${num(r.meanMessageAgeAtUseSeconds, 2)} s`}
                </td>
                <td className="nw-num">{num(r.messagesAttempted, 0)}</td>
                <td className="nw-num">{num(r.stopsAvoided, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
