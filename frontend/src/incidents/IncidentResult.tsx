import "../netcommon/network.css";
import { LineChart, type LineSeries } from "../netcommon/LineChart";
import { clock, num, percent, withUnit } from "../netcommon/format";
import type { DisruptionRun, SimulateResponse } from "./types";

function delaySeries(
  id: string,
  label: string,
  run: DisruptionRun,
  tone: "a" | "d",
  dashed: boolean,
): LineSeries {
  return {
    id,
    label,
    tone,
    dashed,
    points: run.series.time.map((x, i) => ({
      x,
      y: run.series.meanAccruedDelay[i] ?? null,
    })),
  };
}

/** What one simulated disruption did: the delay curve with the undisturbed
 *  run drawn over it, and the recovery figures as text. */
export function IncidentResult({ result }: { result: SimulateResponse }) {
  const { run, baseline, metrics } = result;
  const series = [
    delaySeries("scenario", "With the disruption", run, "a", false),
    ...(baseline
      ? [delaySeries("baseline", "Without it (baseline)", baseline, "d", true)]
      : []),
  ];
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        {result.network.name}: {num(run.completed, 0)} vehicles finished
        {baseline
          ? ` against ${num(baseline.completed, 0)} without the disruption`
          : ""}
        .
      </p>
      <LineChart
        series={series}
        xLabel="Time (s)"
        yLabel="Mean delay so far (s)"
        ariaLabel="Mean accrued delay of the vehicles in the network over time, with the disruption and without it"
      />
      {metrics ? (
        <ul className="nw-facts" aria-label="Recovery figures">
          <li>
            Recovery time:{" "}
            {metrics.recovered
              ? clock(metrics.recoveryTimeSeconds)
              : "not recovered before the run ended"}
          </li>
          <li>Peak delay: {withUnit(metrics.peakDelaySeconds, "s")}</li>
          <li>
            Peak extra delay over baseline:{" "}
            {withUnit(metrics.peakExcessDelaySeconds, "s")}
          </li>
          <li>Throughput loss: {percent(metrics.throughputLoss, 1)}</li>
          <li>Resilience score: {num(metrics.score, 2)} out of 1</li>
        </ul>
      ) : baseline ? (
        <p className="nw-alert" role="status">
          Recovery could not be measured: the disruption ends too close to the
          end of the run. Lengthen the run or shorten the disruption.
        </p>
      ) : null}
      <ul className="nw-facts" aria-label="Run counters">
        <li>
          Mean delay per finished vehicle: {withUnit(run.meanDelaySeconds, "s")}
        </li>
        <li>Turned away at entry: {num(run.blockedAtEntry, 0)}</li>
        <li>Vehicles rerouted: {num(run.reroutedVehicles, 0)}</li>
        <li>
          Vehicle count balanced: {run.conserved ? "yes" : "no, report this"}
        </li>
      </ul>
      <p className="nw-muted">
        In-model only: these figures compare scenarios inside the simulation
        model, they are not predictions.
      </p>
    </div>
  );
}
