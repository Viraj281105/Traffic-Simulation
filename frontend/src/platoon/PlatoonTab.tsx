import { useState } from "react";
import { Truck } from "lucide-react";
import "../netcommon/network.css";
import {
  EmptyHint,
  Panel,
  Pill,
  Skeleton,
} from "../components/dashboard/Dashboard";
import { num } from "../netcommon/format";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { runPlatoonExperiment } from "./api";
import type { PlatoonExperiment, PlatoonMetricKey } from "./types";

const ROWS: { key: PlatoonMetricKey; label: string; unit: string }[] = [
  { key: "throughputVph", label: "Throughput", unit: "veh/h" },
  { key: "fuelLPer100Km", label: "Fuel", unit: "L/100 km" },
  { key: "co2GPerKm", label: "CO2", unit: "g/km" },
];

function pct(v: number | null): string {
  return v === null ? "Not available" : `${num(v, 1)}%`;
}

function Result({ r }: { r: PlatoonExperiment }) {
  const s = r.safety;
  const collisions = s.platoonCollisions + s.humanCollisions;
  const ss = r.stringStability;
  return (
    <div className="nw-stack">
      <p className="nw-muted">
        {r.label} These are in-model estimates, not measurements.
      </p>
      <p>
        <Pill tone={collisions === 0 ? "good" : "bad"}>
          {collisions === 0
            ? "Safety: no collisions"
            : `Safety: ${String(collisions)} collisions`}
        </Pill>{" "}
        Smallest gap {num(s.platoonMinGapM, 1)} m (platoon) against{" "}
        {num(s.humanMinGapM, 1)} m (human); {s.platoonFallbackEvents} fallback
        events.
      </p>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Platoon (A) against human drivers (B) over seeds{" "}
            {r.seeds.join(", ")}, with the paired 95% interval of the
            difference.
          </caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col">Platoon</th>
              <th scope="col">Human</th>
              <th scope="col">Change</th>
              <th scope="col">Interval of difference</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(({ key, label, unit }) => {
              const m = r.metrics[key];
              return (
                <tr key={key}>
                  <th scope="row">
                    {label} ({unit})
                  </th>
                  <td className="nw-num">{num(m.platoonMean, 1)}</td>
                  <td className="nw-num">{num(m.humanMean, 1)}</td>
                  <td className="nw-num">{pct(m.changePct)}</td>
                  <td className="nw-num">
                    {num(m.comparison.ci_lower, 2)} to{" "}
                    {num(m.comparison.ci_upper, 2)}
                  </td>
                  <td>{m.verdict}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h3 className="nw-headline">String stability</h3>
      <p>
        <Pill tone={ss.stable ? "good" : "warn"}>
          {ss.stable ? "Stable" : "Not stable"}
        </Pill>{" "}
        A speed disturbance is {ss.stable ? "damped" : "amplified"} down a
        string of {ss.vehicles} vehicles: largest step ratio{" "}
        {num(ss.stepRatioMax, 2)}, end-to-end amplification{" "}
        {num(ss.amplification, 2)}. Steady-state capacity is{" "}
        {num(r.throughputSteadyState.cacc, 0)} veh/h for a platoon against{" "}
        {num(r.throughputSteadyState.idm, 0)} veh/h for human drivers.
      </p>
      {r.channelSweep && (
        <div className="uf-table-wrap nw-scroll">
          <table className="uf-table">
            <caption>
              Platoon benefit as the radio link gets slower and lossier.
            </caption>
            <thead>
              <tr>
                <th scope="col">Latency (s)</th>
                <th scope="col">Message loss</th>
                <th scope="col">Fuel change</th>
                <th scope="col">Throughput change</th>
                <th scope="col">Smallest gap (m)</th>
                <th scope="col">Collisions</th>
                <th scope="col">Fallbacks</th>
              </tr>
            </thead>
            <tbody>
              {r.channelSweep.map((c) => (
                <tr
                  key={`${String(c.latencySeconds)}-${String(c.lossProbability)}`}
                >
                  <th scope="row">{num(c.latencySeconds, 2)}</th>
                  <td className="nw-num">{num(c.lossProbability * 100, 0)}%</td>
                  <td className="nw-num">{pct(c.fuelChangePct)}</td>
                  <td className="nw-num">{pct(c.throughputChangePct)}</td>
                  <td className="nw-num">{num(c.minGapM, 1)}</td>
                  <td className="nw-num">{c.collisions}</td>
                  <td className="nw-num">{c.fallbackEvents}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Platoons tab: a CACC platoon against human drivers on one lane. */
export function PlatoonTab() {
  const [vehicles, setVehicles] = useState(10);
  const [duration, setDuration] = useState(200);
  const [latency, setLatency] = useState(0);
  const [loss, setLoss] = useState(0);
  const [seeds, setSeeds] = useState(5);
  const [state, start] = useAction<PlatoonExperiment>(
    "The platoon experiment could not be run.",
  );
  return (
    <Panel
      id="coop-platoon"
      title="Vehicle platoons"
      subtitle="Cooperative cruise control (a tight, radio-linked line of vehicles) compared with the same traffic driven by humans."
    >
      <div className="nw-stack">
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            start(() =>
              runPlatoonExperiment({
                vehicles,
                durationSeconds: duration,
                latencyMs: latency,
                lossProbability: loss,
                seedCount: seeds,
                withSweep: true,
              }),
            );
          }}
        >
          <NumberField
            label="Vehicles (2 to 20)"
            value={vehicles}
            min={2}
            max={20}
            onChange={(v) => {
              setVehicles(Math.round(v));
            }}
          />
          <NumberField
            label="Run length (s)"
            value={duration}
            min={30}
            max={600}
            onChange={setDuration}
          />
          <NumberField
            label="Message latency (ms)"
            value={latency}
            min={0}
            max={2000}
            onChange={setLatency}
          />
          <NumberField
            label="Message loss (0 to 1)"
            value={loss}
            min={0}
            max={1}
            step={0.05}
            onChange={setLoss}
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
            Run the platoon experiment
          </button>
        </form>
        {state.status === "idle" && (
          <EmptyHint icon={<Truck size={22} />} title="No experiment yet">
            Press Run the platoon experiment. It also fills the latency by loss
            table.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={6} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && <Result r={state.data} />}
      </div>
    </Panel>
  );
}
