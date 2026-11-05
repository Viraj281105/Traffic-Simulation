import { useState } from "react";
import { Flame } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { ScenarioForm } from "../netcommon/ScenarioForm";
import { DEFAULT_SCENARIO } from "../netcommon/scenario";
import { useAction } from "../netcommon/useAction";
import { analyseCongestion, DEFAULT_CONGESTION } from "./api";
import { CongestionView } from "./CongestionView";
import type { CongestionResult } from "./types";

/** The congestion tab: run a grid and see how congestion spread. */
export function CongestionTab() {
  const [percent, setPercent] = useState(DEFAULT_CONGESTION.threshold * 100);
  const [state, start] = useAction<CongestionResult>(
    "The congestion analysis could not be run.",
  );
  return (
    <Panel
      id="nw-congestion"
      title="Congestion spread"
      subtitle="Where congestion starts, how it spreads and where queues back up."
    >
      <div className="nw-stack">
        <ScenarioForm
          initial={{ ...DEFAULT_SCENARIO, vehiclesPerHour: 900 }}
          busy={state.status === "loading"}
          runLabel="Analyse congestion"
          onRun={(scenario) => {
            start(() =>
              analyseCongestion(scenario, {
                threshold: Math.min(100, Math.max(1, percent)) / 100,
              }),
            );
          }}
        >
          <NumberField
            label="Congested when fuller than (%)"
            value={percent}
            min={1}
            max={100}
            onChange={setPercent}
          />
        </ScenarioForm>
        {state.status === "idle" && (
          <EmptyHint icon={<Flame size={22} />} title="No analysis yet">
            Press Analyse congestion. A busier grid shows the spread more
            clearly.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={5} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && <CongestionView result={state.data} />}
      </div>
    </Panel>
  );
}
