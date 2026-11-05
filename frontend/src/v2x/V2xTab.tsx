import { useState } from "react";
import { Radio } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { runV2xExperiment } from "./api";
import { SensitivityHeatmap } from "./SensitivityHeatmap";
import { SweepView } from "./SweepView";
import type { V2xExperiment } from "./types";

/** Cooperation tab: how much connected vehicles help as their share grows,
 *  how late or lost messages erode that, and the assumptions behind it. */
export function V2xTab() {
  const [rows, setRows] = useState(3);
  const [cols, setCols] = useState(3);
  const [vph, setVph] = useState(300);
  const [duration, setDuration] = useState(600);
  const [seeds, setSeeds] = useState(5);
  const [latency, setLatency] = useState(100);
  const [loss, setLoss] = useState(0.1);
  const [state, start] = useAction<V2xExperiment>(
    "The cooperation experiment could not be run.",
  );
  return (
    <Panel
      id="res-v2x"
      title="Connected vehicles"
      subtitle="Vehicles that receive signal timings and hazard warnings, compared with the same traffic without them."
    >
      <div className="nw-stack">
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            start(() =>
              runV2xExperiment({
                rows,
                cols,
                vehiclesPerHour: vph,
                duration,
                seedCount: seeds,
                latencyMs: latency,
                lossProbability: loss,
                withSensitivity: true,
              }),
            );
          }}
        >
          <NumberField
            label="Grid rows (1 to 5)"
            value={rows}
            min={1}
            max={5}
            onChange={(v) => {
              setRows(Math.round(v));
            }}
          />
          <NumberField
            label="Grid columns (1 to 5)"
            value={cols}
            min={1}
            max={5}
            onChange={(v) => {
              setCols(Math.round(v));
            }}
          />
          <NumberField
            label="Vehicles per hour per entry"
            value={vph}
            min={0}
            max={3600}
            onChange={setVph}
          />
          <NumberField
            label="Run length (s)"
            value={duration}
            min={30}
            max={900}
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
          <NumberField
            label="Message latency (ms)"
            value={latency}
            min={0}
            max={10000}
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
          <button
            type="submit"
            className="nw-btn nw-btn--primary"
            disabled={state.status === "loading"}
          >
            Run the experiment
          </button>
        </form>
        {state.status === "idle" && (
          <EmptyHint icon={<Radio size={22} />} title="No experiment yet">
            Press Run the experiment. It also fills the latency by loss grid.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={6} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && (
          <div className="nw-stack">
            <SweepView result={state.data} />
            {state.data.sensitivity && (
              <>
                <h3 className="nw-headline">Late and lost messages</h3>
                <SensitivityHeatmap grid={state.data.sensitivity} />
              </>
            )}
            <section className="nw-stack" aria-label="Assumptions">
              <h3 className="nw-headline">Assumptions behind these numbers</h3>
              <ul className="nw-facts">
                {state.data.provenance.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
              <p className="nw-muted">
                Seeds {state.data.provenance.seeds.join(", ")}; run length{" "}
                {state.data.provenance.durationSeconds} s. In-model only: not a
                prediction of real connected-vehicle benefits.
              </p>
            </section>
          </div>
        )}
      </div>
    </Panel>
  );
}
