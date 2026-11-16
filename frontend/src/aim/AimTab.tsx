import { useState } from "react";
import { Route } from "lucide-react";
import "../netcommon/network.css";
import {
  EmptyHint,
  Panel,
  Pill,
  Skeleton,
} from "../components/dashboard/Dashboard";
import { LineChart } from "../netcommon/LineChart";
import { num } from "../netcommon/format";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { runAimComparison } from "./api";
import type { AimResult } from "./types";

function Result({ r }: { r: AimResult }) {
  const delay = r.sweep.map((row) => ({
    x: row.demandVehPerHourPerApproach,
    aim: row.aim.meanDelay,
    signal: row.signal.meanDelay,
    c: row.comparison.meanDelay,
  }));
  const level = r.provenance.confidence * 100;
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        In-model best case: every vehicle is automated and connected, with no
        sensing error, and the baseline is a fixed-time signal, not an optimised
        one. Real roads will not do this well.
      </p>
      <p>
        <Pill tone={r.gateGAim.passed ? "good" : "bad"}>
          {r.gateGAim.passed ? "G-AIM safety: passed" : "G-AIM safety: failed"}
        </Pill>{" "}
        {r.gateGAim.description}.
      </p>
      <LineChart
        series={[
          {
            id: "aim",
            label: "Signal-free (AIM)",
            tone: "a",
            points: delay.map((d) => ({ x: d.x, y: d.aim })),
          },
          {
            id: "signal",
            label: "Fixed-time signal",
            tone: "b",
            points: delay.map((d) => ({ x: d.x, y: d.signal })),
          },
        ]}
        xLabel="Demand (veh/h per approach)"
        yLabel="Mean delay (s)"
        ariaLabel="Mean delay against demand for signal-free and signalised control"
      />
      <LineChart
        series={[
          {
            id: "diff",
            label: "AIM minus signal",
            tone: "a",
            points: delay.map((d) => ({ x: d.x, y: d.c.difference })),
          },
          {
            id: "lo",
            label: `Lower ${num(level, 0)}% bound`,
            tone: "c",
            dashed: true,
            points: delay.map((d) => ({ x: d.x, y: d.c.ci_lower })),
          },
          {
            id: "hi",
            label: `Upper ${num(level, 0)}% bound`,
            tone: "c",
            dashed: true,
            points: delay.map((d) => ({ x: d.x, y: d.c.ci_upper })),
          },
        ]}
        xLabel="Demand (veh/h per approach)"
        yLabel="Delay difference (s)"
        ariaLabel="Paired difference in mean delay, signal-free minus signal, with its interval; below zero favours signal-free"
      />
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Mean delay by demand, with the paired {num(level, 0)}% interval of
            the difference (AIM minus signal; negative favours AIM).
          </caption>
          <thead>
            <tr>
              <th scope="col">Demand (veh/h)</th>
              <th scope="col">AIM delay (s)</th>
              <th scope="col">Signal delay (s)</th>
              <th scope="col">Difference (interval)</th>
              <th scope="col">Safety</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {r.sweep.map((row) => {
              const c = row.comparison.meanDelay;
              return (
                <tr key={row.demandVehPerHourPerApproach}>
                  <th scope="row">{num(row.demandVehPerHourPerApproach, 0)}</th>
                  <td className="nw-num">{num(row.aim.meanDelay, 1)}</td>
                  <td className="nw-num">{num(row.signal.meanDelay, 1)}</td>
                  <td className="nw-num">
                    {num(c.difference, 2)} ({num(c.ci_lower, 2)} to{" "}
                    {num(c.ci_upper, 2)})
                  </td>
                  <td>{row.aim.safety.passed ? "Passed" : "Failed"}</td>
                  <td>{c.verdict}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {r.messageLossStress.length > 0 && (
        <div className="uf-table-wrap nw-scroll">
          <table className="uf-table">
            <caption>
              Message-loss stress at{" "}
              {num(r.provenance.stressDemandVehPerHourPerApproach, 0)} veh/h per
              approach: how signal-free control copes when reservation messages
              are lost.
            </caption>
            <thead>
              <tr>
                <th scope="col">Message loss</th>
                <th scope="col">AIM delay (s)</th>
                <th scope="col">Signal delay (s)</th>
                <th scope="col">Difference (interval)</th>
                <th scope="col">Messages lost</th>
                <th scope="col">Safety</th>
              </tr>
            </thead>
            <tbody>
              {r.messageLossStress.map((row) => {
                const c = row.comparison.meanDelay;
                return (
                  <tr key={row.lossProbability}>
                    <th scope="row">{num(row.lossProbability * 100, 0)}%</th>
                    <td className="nw-num">{num(row.aim.meanDelay, 1)}</td>
                    <td className="nw-num">{num(row.signal.meanDelay, 1)}</td>
                    <td className="nw-num">
                      {num(c.difference, 2)} ({num(c.ci_lower, 2)} to{" "}
                      {num(c.ci_upper, 2)})
                    </td>
                    <td className="nw-num">{num(row.aim.lostMessages, 1)}</td>
                    <td>{row.aim.safety.passed ? "Passed" : "Failed"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <section className="nw-stack" aria-label="Assumptions">
        <h3 className="nw-headline">Assumptions behind these numbers</h3>
        <ul className="nw-facts">
          {r.provenance.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** Signal-free tab: reservation-based intersection against a fixed signal. */
export function AimTab() {
  const [duration, setDuration] = useState(300);
  const [seeds, setSeeds] = useState(5);
  const [state, start] = useAction<AimResult>(
    "The signal-free comparison could not be run.",
  );
  return (
    <Panel
      id="coop-aim"
      title="Signal-free intersection"
      subtitle="Vehicles reserve space in the junction instead of waiting for a green light, compared with a fixed-time signal at several demand levels."
    >
      <div className="nw-stack">
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            start(() =>
              runAimComparison({
                durationSeconds: duration,
                seedCount: seeds,
                demands: [150, 300, 450, 600],
                withLossStress: true,
              }),
            );
          }}
        >
          <NumberField
            label="Run length (s)"
            value={duration}
            min={30}
            max={600}
            onChange={setDuration}
          />
          <NumberField
            label="Seeds (2 to 10)"
            value={seeds}
            min={2}
            max={10}
            onChange={(v) => {
              setSeeds(Math.round(v));
            }}
          />
          <button
            type="submit"
            className="nw-btn nw-btn--primary"
            disabled={state.status === "loading"}
          >
            Run the comparison
          </button>
        </form>
        {state.status === "idle" && (
          <EmptyHint icon={<Route size={22} />} title="No comparison yet">
            Press Run the comparison. It also runs the message-loss stress test.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={6} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && <Result r={state.data} />}
      </div>
    </Panel>
  );
}
