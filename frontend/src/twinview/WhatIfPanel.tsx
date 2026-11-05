import { useId, useState } from "react";
import "../netcommon/network.css";
import { Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { num } from "../netcommon/format";
import { useAction } from "../netcommon/useAction";
import { whatIfTwin } from "./api";
import { signed, whatIfSummary } from "./text";
import type { TwinRequest, TwinScenario, WhatIfResult } from "./types";

/** Scenario form and the baseline-versus-variant result. It reuses the
 *  observations and settings of the comparison above it. */
export function WhatIfPanel({
  base,
  linkIds,
}: {
  base: TwinRequest;
  linkIds: string[];
}) {
  const uid = useId();
  const [closed, setClosed] = useState("");
  const [scale, setScale] = useState(1);
  const [horizon, setHorizon] = useState(1);
  const [state, start] = useAction<WhatIfResult>(
    "The what-if could not be run.",
  );
  const submit = () => {
    const scenario: TwinScenario = {
      closeLinks: closed
        .split(/[\s,]+/)
        .map((s) => s.trim())
        .filter(Boolean),
      demandScale: scale,
    };
    start(() => whatIfTwin(base, scenario, horizon));
  };
  return (
    <div className="nw-stack">
      <form
        className="nw-form"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="uf-field">
          <label className="uf-label" htmlFor={`${uid}-close`}>
            Links to close (ids, comma-separated)
          </label>
          <input
            id={`${uid}-close`}
            className="uf-input"
            value={closed}
            list={`${uid}-links`}
            onChange={(e) => {
              setClosed(e.target.value);
            }}
          />
          <datalist id={`${uid}-links`}>
            {linkIds.map((id) => (
              <option key={id} value={id} />
            ))}
          </datalist>
        </div>
        <NumberField
          label="Demand (1 = as now)"
          value={scale}
          min={0}
          max={10}
          step={0.1}
          onChange={setScale}
        />
        <NumberField
          label="Windows to forecast"
          value={horizon}
          min={1}
          max={12}
          onChange={(v) => {
            setHorizon(Math.round(v));
          }}
        />
        <button
          type="submit"
          className="nw-btn nw-btn--primary"
          disabled={state.status === "loading"}
        >
          {state.status === "loading" ? "Running…" : "Run what-if"}
        </button>
      </form>
      {state.status === "loading" && <Skeleton lines={3} />}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <WhatIfResultView result={state.data} />}
    </div>
  );
}

/** Baseline against variant. */
export function WhatIfResultView({ result: r }: { result: WhatIfResult }) {
  const ids = Object.keys(r.perLink);
  return (
    <div className="nw-stack">
      <p className="nw-headline">{whatIfSummary(r)}</p>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>
            Baseline against the scenario for windows {num(r.window, 0)} to{" "}
            {num(r.window + r.horizonWindows - 1, 0)}, same demand and seed.
          </caption>
          <thead>
            <tr>
              <th scope="col">Measure</th>
              <th scope="col">Baseline</th>
              <th scope="col">Scenario</th>
              <th scope="col">Change</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Vehicles finishing their trip</th>
              <td className="nw-num">{num(r.baseline.completed, 0)}</td>
              <td className="nw-num">{num(r.variant.completed, 0)}</td>
              <td className="nw-num">{signed(r.delta.completed, 0)}</td>
            </tr>
            <tr>
              <th scope="row">Mean delay (s)</th>
              <td className="nw-num">{num(r.baseline.meanDelaySeconds, 1)}</td>
              <td className="nw-num">{num(r.variant.meanDelaySeconds, 1)}</td>
              <td className="nw-num">{signed(r.delta.meanDelaySeconds)}</td>
            </tr>
            <tr>
              <th scope="row">Mean travel time (s)</th>
              <td className="nw-num">{num(r.baseline.meanTravelSeconds, 1)}</td>
              <td className="nw-num">{num(r.variant.meanTravelSeconds, 1)}</td>
              <td className="nw-num">{signed(r.delta.meanTravelSeconds)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="uf-table-wrap nw-scroll">
        <table className="uf-table">
          <caption>Vehicles leaving each link over the forecast.</caption>
          <thead>
            <tr>
              <th scope="col">Link</th>
              <th scope="col">Baseline</th>
              <th scope="col">Scenario</th>
              <th scope="col">Change</th>
              <th scope="col">Change in peak vehicles on link</th>
            </tr>
          </thead>
          <tbody>
            {ids.map((id) => {
              const l = r.perLink[id];
              return (
                <tr key={id}>
                  <th scope="row">{id}</th>
                  <td className="nw-num">{num(l.baseline, 0)}</td>
                  <td className="nw-num">
                    {l.variant === null ? "Closed" : num(l.variant, 0)}
                  </td>
                  <td className="nw-num">{signed(l.delta, 0)}</td>
                  <td className="nw-num">{signed(l.peakOccupancyDelta, 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="nw-muted">
        An uncalibrated model of the network: read the change, not the absolute
        numbers.
      </p>
    </div>
  );
}
