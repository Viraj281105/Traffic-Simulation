import { Activity } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { ScenarioForm } from "../netcommon/ScenarioForm";
import { DEFAULT_SCENARIO } from "../netcommon/scenario";
import { useAction } from "../netcommon/useAction";
import { simulateNetwork } from "./api";
import { NetworkMetricsPanel } from "./NetworkMetricsPanel";
import type { NetworkMetrics } from "./types";

/** The metrics tab: run a grid and read the network-wide numbers. */
export function MetricsTab() {
  const [state, start] = useAction<NetworkMetrics>(
    "The network could not be simulated.",
  );
  return (
    <Panel
      id="nw-metrics"
      title="Network metrics"
      subtitle="Throughput, delay, queues and the fundamental diagram for a whole network."
    >
      <div className="nw-stack">
        <ScenarioForm
          initial={DEFAULT_SCENARIO}
          busy={state.status === "loading"}
          runLabel="Run network"
          onRun={(scenario) => {
            start(() => simulateNetwork(scenario));
          }}
        />
        {state.status === "idle" && (
          <EmptyHint icon={<Activity size={22} />} title="No run yet">
            Press Run network to simulate the grid and see its metrics.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={5} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && (
          <NetworkMetricsPanel metrics={state.data} />
        )}
      </div>
    </Panel>
  );
}
