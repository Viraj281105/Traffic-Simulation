import { Map as MapIcon } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { ScenarioForm } from "../netcommon/ScenarioForm";
import { DEFAULT_SCENARIO } from "../netcommon/scenario";
import { useAction } from "../netcommon/useAction";
import { simulateNetwork } from "../netmetrics/api";
import type { NetworkMetrics } from "../netmetrics/types";
import { getGrid } from "./api";
import { MapViewer } from "./MapViewer";
import type { GridResponse } from "./types";

type Shown =
  { kind: "layout"; grid: GridResponse } | { kind: "run"; run: NetworkMetrics };

/** The map tab: pick a grid, then see its layout or a run coloured by a link
 *  metric. */
export function MapTab() {
  const [state, start] = useAction<Shown>("The map could not be loaded.");
  return (
    <Panel
      id="nw-map"
      title="Network map"
      subtitle="Local x/y map of a multi-junction network. No map tiles are needed."
    >
      <div className="nw-stack">
        <ScenarioForm
          initial={DEFAULT_SCENARIO}
          busy={state.status === "loading"}
          runLabel="Run and colour the map"
          onRun={(scenario) => {
            start(async () => ({
              kind: "run",
              run: await simulateNetwork(scenario),
            }));
          }}
          secondary={{
            label: "Show layout only",
            onClick: (scenario) => {
              start(async () => ({
                kind: "layout",
                grid: await getGrid(scenario),
              }));
            },
          }}
        />
        {state.status === "idle" && (
          <EmptyHint icon={<MapIcon size={22} />} title="No network shown yet">
            Choose a network and press the button. A run colours the roads by
            how full they were; the layout alone colours them by length, lanes
            or speed.
          </EmptyHint>
        )}
        {state.status === "loading" && <Skeleton lines={5} />}
        {state.status === "error" && <p role="alert">{state.message}</p>}
        {state.status === "ready" && state.data.kind === "layout" && (
          <>
            {state.data.grid.validation.warnings.length > 0 && (
              <ul className="nw-facts">
                {state.data.grid.validation.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            <MapViewer map={state.data.grid.map} />
          </>
        )}
        {state.status === "ready" && state.data.kind === "run" && (
          <>
            {state.data.run.map ? (
              <MapViewer
                map={state.data.run.map}
                perLink={state.data.run.perLink}
              />
            ) : (
              <p role="alert">The server sent no map data for this run.</p>
            )}
            <p className="nw-muted">
              Compare scenarios with this model; its numbers are not predictions
              of the real network.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}
