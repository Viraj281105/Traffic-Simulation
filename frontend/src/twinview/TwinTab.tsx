import { useId, useState } from "react";
import { Radar } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { compareTwin } from "./api";
import { parseObservations } from "./observations";
import { sampleObservations } from "./sample";
import { TwinDashboard } from "./TwinDashboard";
import type { TwinRequest, TwinState } from "./types";
import { WhatIfPanel } from "./WhatIfPanel";

/** The Twin tab: prediction against observation, and what-if. Uses the
 *  default two-junction corridor unless a network is sent. */
export function TwinTab() {
  const uid = useId();
  const [text, setText] = useState("");
  const [interval, setInterval_] = useState(60);
  const [threshold, setThreshold] = useState(25);
  const [local, setLocal] = useState<string | null>(null);
  const [request, setRequest] = useState<TwinRequest | null>(null);
  const [state, start] = useAction<TwinState>("The twin could not be run.");

  const submit = () => {
    setLocal(null);
    try {
      const observations = parseObservations(text);
      const req: TwinRequest = {
        observations,
        intervalSeconds: interval,
        alertThresholdPct: threshold,
      };
      setRequest(req);
      start(() => compareTwin(req));
    } catch (err) {
      setLocal(
        err instanceof Error ? err.message : "The observations are not usable.",
      );
    }
  };

  return (
    <div className="nw-stack">
      <Panel
        id="nw-twin"
        title="Prediction against observation"
        subtitle="Feed link counts to the twin and see how far its predictions are from them."
      >
        <div className="nw-stack">
          <div className="uf-field">
            <label className="uf-label" htmlFor={`${uid}-obs`}>
              Observations (JSON list of linkId, timestamp, count)
            </label>
            <textarea
              id={`${uid}-obs`}
              className="nw-textarea"
              value={text}
              onChange={(e) => {
                setText(e.target.value);
              }}
            />
          </div>
          <div className="nw-form">
            <NumberField
              label="Window length (s)"
              value={interval}
              min={1}
              max={3600}
              onChange={setInterval_}
            />
            <NumberField
              label="Alert when off by more than (%)"
              value={threshold}
              min={1}
              onChange={setThreshold}
            />
            <button
              type="button"
              className="nw-btn"
              onClick={() => {
                setText(
                  JSON.stringify(sampleObservations(6, interval), null, 2),
                );
                setLocal(null);
              }}
            >
              Insert example observations
            </button>
            <button
              type="button"
              className="nw-btn nw-btn--primary"
              disabled={state.status === "loading"}
              onClick={submit}
            >
              {state.status === "loading" ? "Running…" : "Compare"}
            </button>
          </div>
          {local && <p role="alert">{local}</p>}
          {state.status === "idle" && !local && (
            <EmptyHint icon={<Radar size={22} />} title="Nothing compared yet">
              The example observations are for the two-junction corridor the
              twin uses by default. Insert them and press Compare.
            </EmptyHint>
          )}
          {state.status === "loading" && <Skeleton lines={4} />}
          {state.status === "error" && <p role="alert">{state.message}</p>}
          {state.status === "ready" && <TwinDashboard state={state.data} />}
        </div>
      </Panel>
      <Panel
        id="nw-whatif"
        title="What if"
        subtitle="Close roads or change demand from the latest observation, and see the difference."
      >
        {request && state.status === "ready" ? (
          <WhatIfPanel
            base={request}
            linkIds={Object.keys(state.data.comparison.perLink)}
          />
        ) : (
          <p className="nw-muted">
            Compare some observations first; the what-if starts from the latest
            of them.
          </p>
        )}
      </Panel>
    </div>
  );
}
