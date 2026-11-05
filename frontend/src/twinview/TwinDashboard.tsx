import { useId, useState } from "react";
import "../netcommon/network.css";
import { StatGrid, StatTile } from "../components/dashboard/Dashboard";
import { LineChart } from "../netcommon/LineChart";
import { UNAVAILABLE, isNum, num } from "../netcommon/format";
import { alertText } from "./text";
import type { TwinState } from "./types";

function lagText(seconds: number): string {
  if (seconds === 0) return "In step with the observations";
  return seconds > 0
    ? `Prediction runs ${num(seconds, 0)} s early`
    : `Prediction runs ${num(-seconds, 0)} s late`;
}

/** Prediction against observation: error scores, alerts, the network series
 *  and the series of one chosen link. */
export function TwinDashboard({ state }: { state: TwinState }) {
  const uid = useId();
  const c = state.comparison;
  const linkIds = Object.keys(c.perLink);
  const [link, setLink] = useState("");
  const chosen = linkIds.includes(link) ? link : "";
  const times = (w: number) => state.start + w * state.intervalSeconds;

  const networkSeries = [
    {
      id: "pred",
      label: "Predicted (network total)",
      tone: "a" as const,
      points: c.series.map((p) => ({ x: times(p.window), y: p.predicted })),
    },
    {
      id: "obs",
      label: "Observed (network total)",
      tone: "b" as const,
      dashed: true,
      points: c.series.map((p) => ({ x: times(p.window), y: p.observed })),
    },
  ];
  const linkSeries = chosen
    ? [
        {
          id: "lp",
          label: `Predicted on ${chosen}`,
          tone: "a" as const,
          points: state.timeline.map((t) => ({
            x: t.time,
            y: chosen in t.predicted ? t.predicted[chosen] : null,
          })),
        },
        {
          id: "lo",
          label: `Observed on ${chosen}`,
          tone: "b" as const,
          dashed: true,
          points: state.timeline.map((t) => ({
            x: t.time,
            y: chosen in t.observed ? t.observed[chosen] : null,
          })),
        },
      ]
    : [];

  const n = c.network;
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        {c.alert
          ? "The twin has drifted from what was observed."
          : "The twin is tracking what was observed."}
      </p>
      <StatGrid>
        <StatTile
          label="Average miss (MAE)"
          value={isNum(n.mae) ? num(n.mae, 2) : UNAVAILABLE}
          unit={isNum(n.mae) ? "vehicles / window" : undefined}
          hint="Mean size of the difference, network total"
        />
        <StatTile
          label="Average miss (MAPE)"
          value={isNum(n.mape) ? num(n.mape, 1) : UNAVAILABLE}
          unit={isNum(n.mape) ? "%" : undefined}
          hint="As a share of what was observed"
          tone={
            isNum(n.mape) && n.mape > c.alertThresholdPct ? "bad" : "neutral"
          }
        />
        <StatTile
          label="Bias"
          value={
            isNum(n.bias)
              ? `${n.bias > 0 ? "+" : ""}${num(n.bias, 2)}`
              : UNAVAILABLE
          }
          unit={isNum(n.bias) ? "vehicles / window" : undefined}
          hint={
            isNum(n.bias) && n.bias !== 0
              ? n.bias < 0
                ? "Predicts too few vehicles"
                : "Predicts too many vehicles"
              : "Neither too high nor too low"
          }
        />
        <StatTile
          label="Timing"
          value={lagText(n.lagSeconds)}
          hint={`Compared over ${num(n.n, 0)} windows of ${num(state.intervalSeconds, 0)} s`}
        />
      </StatGrid>

      {c.alerts.length > 0 ? (
        <ul className="nw-list" aria-label="Alerts">
          {c.alerts.map((a) => (
            <li key={`${a.kind}-${String(a.window)}`} className="nw-alert">
              {alertText(a, state)}
            </li>
          ))}
        </ul>
      ) : (
        <p>
          No alerts: no window was off by more than{" "}
          {num(c.alertThresholdPct, 0)}%.
        </p>
      )}

      <h3 className="nw-headline">Predicted and observed, whole network</h3>
      <LineChart
        series={networkSeries}
        xLabel="Time (s)"
        yLabel="Vehicles per window"
        ariaLabel="Predicted and observed vehicles per window, summed over the observed links"
      />

      <h3 className="nw-headline">One link</h3>
      <div className="uf-field" style={{ maxWidth: 260 }}>
        <label className="uf-label" htmlFor={`${uid}-link`}>
          Link
        </label>
        <select
          id={`${uid}-link`}
          className="uf-select"
          value={chosen}
          onChange={(e) => {
            setLink(e.target.value);
          }}
        >
          <option value="">Choose a link</option>
          {linkIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
      </div>
      {chosen && (
        <LineChart
          series={linkSeries}
          xLabel="Time (s)"
          yLabel="Vehicles per window"
          ariaLabel={`Predicted and observed vehicles per window on ${chosen}`}
        />
      )}

      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Error scores for each link (vehicles per window; MAPE in percent).
          </caption>
          <thead>
            <tr>
              <th scope="col">Link</th>
              <th scope="col">Windows</th>
              <th scope="col">MAE</th>
              <th scope="col">MAPE (%)</th>
              <th scope="col">Bias</th>
            </tr>
          </thead>
          <tbody>
            {linkIds.map((id) => {
              const s = c.perLink[id];
              return (
                <tr key={id}>
                  <th scope="row">{id}</th>
                  <td className="nw-num">{s.n}</td>
                  <td className="nw-num">{num(s.mae, 2)}</td>
                  <td className="nw-num">{num(s.mape, 1)}</td>
                  <td className="nw-num">{num(s.bias, 2)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="nw-muted">
        Twin of {state.graph}: each window is predicted from the previous
        window&apos;s observed entry counts (seed {state.seed}, warm-up{" "}
        {num(state.warmupSeconds, 0)} s). MAPE skips windows where nothing was
        observed.
      </p>
    </div>
  );
}
