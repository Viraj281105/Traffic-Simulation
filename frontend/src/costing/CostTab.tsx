import { useId, useState } from "react";
import "../netcommon/network.css";
import { Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction, type Action } from "../netcommon/useAction";
import { estimateCost, getRunCost } from "./api";
import type { CostEstimate, RunCost } from "./types";

function money(v: number, currency: string): string {
  return `${v.toLocaleString("en-US", { maximumFractionDigits: 6 })} ${currency}`;
}

function Estimate({ data }: { data: CostEstimate }) {
  return (
    <div className="nw-stack">
      <p className="nw-headline">
        About {money(data.total, data.currency)} ({data.confidence})
      </p>
      <ul className="nw-facts">
        <li>Compute: {money(data.items.compute, data.currency)}</li>
        <li>Storage: {money(data.items.storage, data.currency)}</li>
        <li>Queue: {money(data.items.queue, data.currency)}</li>
      </ul>
      <ul className="nw-facts">
        {data.assumptions.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
    </div>
  );
}

function Outcome<T>({
  state,
  children,
}: {
  state: Action<T>;
  children: (data: T) => React.ReactNode;
}) {
  if (state.status === "loading") return <Skeleton lines={3} />;
  if (state.status === "error") return <p role="alert">{state.message}</p>;
  if (state.status === "ready") return <>{children(state.data)}</>;
  return null;
}

/** Cost tab: an estimate for a planned run and a lookup for a finished one. */
export function CostTab() {
  const [seconds, setSeconds] = useState(600);
  const [weight, setWeight] = useState(1);
  const [spot, setSpot] = useState(false);
  const [gb, setGb] = useState(0);
  const [queue, setQueue] = useState(0);
  const [months, setMonths] = useState(1);
  const [runId, setRunId] = useState("");
  const runField = useId();
  const [est, startEst] = useAction<CostEstimate>(
    "The cost could not be estimated.",
  );
  const [run, startRun] = useAction<RunCost>(
    "The run's cost could not be looked up.",
  );
  return (
    <Panel
      id="coop-cost"
      title="Cost"
      subtitle="Estimate, not a bill: prices are approximate list prices and real charges will differ."
    >
      <div className="nw-stack">
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            startEst(() =>
              estimateCost({
                computeSeconds: seconds,
                vcpuWeight: weight,
                spot,
                storedBytes: Math.round(gb * 1e9),
                queueRequests: Math.round(queue),
                storageMonths: months,
              }),
            );
          }}
        >
          <NumberField
            label="Compute time (s)"
            value={seconds}
            min={0}
            onChange={setSeconds}
          />
          <NumberField
            label="vCPUs used"
            value={weight}
            min={0.5}
            max={1024}
            step={0.5}
            onChange={setWeight}
          />
          <NumberField
            label="Stored data (GB)"
            value={gb}
            min={0}
            onChange={setGb}
          />
          <NumberField
            label="Storage time (months)"
            value={months}
            min={0}
            max={120}
            onChange={setMonths}
          />
          <NumberField
            label="Queue requests"
            value={queue}
            min={0}
            onChange={setQueue}
          />
          <label>
            <input
              type="checkbox"
              checked={spot}
              onChange={(e) => {
                setSpot(e.target.checked);
              }}
            />{" "}
            Use spot (interruptible) pricing
          </label>
          <button
            type="submit"
            className="nw-btn nw-btn--primary"
            disabled={est.status === "loading"}
          >
            Estimate the cost
          </button>
        </form>
        <Outcome state={est}>{(d) => <Estimate data={d} />}</Outcome>
        <h3 className="nw-headline">Cost of a finished run</h3>
        <form
          className="nw-form"
          onSubmit={(e) => {
            e.preventDefault();
            startRun(() => getRunCost(runId.trim(), spot));
          }}
        >
          <div className="uf-field">
            <label className="uf-label" htmlFor={runField}>
              Run id
            </label>
            <input
              id={runField}
              className="uf-input"
              value={runId}
              onChange={(e) => {
                setRunId(e.target.value);
              }}
            />
          </div>
          <button
            type="submit"
            className="nw-btn"
            disabled={runId.trim() === "" || run.status === "loading"}
          >
            Look up the run cost
          </button>
        </form>
        <Outcome state={run}>
          {(d) => (
            <div className="nw-stack">
              <p className="nw-muted">
                Run {d.runId}
                {d.tenant ? ` for ${d.tenant}` : ""}
                {d.day ? ` on ${d.day}` : ""}: {d.computeSeconds} s of compute.
              </p>
              <Estimate data={d} />
            </div>
          )}
        </Outcome>
      </div>
    </Panel>
  );
}
