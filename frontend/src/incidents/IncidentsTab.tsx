import { useState } from "react";
import { Siren } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { useLoad } from "../rescommon/useLoad";
import { getIncidentCatalogue, simulateIncident } from "./api";
import { IncidentResult } from "./IncidentResult";
import { PresetPicker } from "./PresetPicker";
import { ScenarioEditor } from "./ScenarioEditor";
import { scenarioFromPreset } from "./scenario";
import type {
  IncidentCatalogue,
  Preset,
  Scenario,
  SimulateResponse,
  Strategy,
} from "./types";

const STRATEGY_LABEL: Record<Strategy, string> = {
  fixed_time: "Fixed-time signals",
  max_pressure: "Max-pressure signals",
};

function IncidentForm({ catalogue }: { catalogue: IncidentCatalogue }) {
  const first: Preset = catalogue.scenarios[0];
  const [presetId, setPresetId] = useState(first.id);
  const [scenario, setScenario] = useState<Scenario>(
    scenarioFromPreset(first.scenario),
  );
  const [duration, setDuration] = useState(first.duration);
  const [seed, setSeed] = useState(1);
  const [strategy, setStrategy] = useState<Strategy>(catalogue.strategies[0]);
  const [state, start] = useAction<SimulateResponse>(
    "The disruption could not be simulated.",
  );
  const choose = (id: string) => {
    const p = catalogue.scenarios.find((x) => x.id === id);
    if (!p) return;
    setPresetId(id);
    setScenario(scenarioFromPreset(p.scenario));
    setDuration(p.duration);
  };
  return (
    <div className="nw-stack">
      <PresetPicker
        presets={catalogue.scenarios}
        value={presetId}
        onChange={choose}
      />
      <ScenarioEditor value={scenario} onChange={setScenario} />
      <form
        className="nw-form"
        onSubmit={(event) => {
          event.preventDefault();
          start(() =>
            simulateIncident({
              preset: presetId,
              scenario,
              duration,
              seed,
              strategy,
            }),
          );
        }}
      >
        <NumberField
          label="Run length (s)"
          value={duration}
          min={30}
          max={3600}
          onChange={setDuration}
        />
        <NumberField
          label="Random seed"
          value={seed}
          min={0}
          max={2147483647}
          onChange={(v) => {
            setSeed(Math.round(v));
          }}
        />
        <div className="uf-field">
          <label className="uf-label" htmlFor="inc-strategy">
            Signal strategy
          </label>
          <select
            id="inc-strategy"
            className="uf-select"
            value={strategy}
            onChange={(e) => {
              setStrategy(e.target.value as Strategy);
            }}
          >
            {catalogue.strategies.map((s) => (
              <option key={s} value={s}>
                {STRATEGY_LABEL[s]}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="nw-btn nw-btn--primary"
          disabled={state.status === "loading"}
        >
          Simulate the disruption
        </button>
      </form>
      {state.status === "idle" && (
        <EmptyHint icon={<Siren size={22} />} title="No simulation yet">
          Pick a scenario, adjust it if you like and press Simulate the
          disruption. It runs once with and once without the disruption.
        </EmptyHint>
      )}
      {state.status === "loading" && <Skeleton lines={5} />}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <IncidentResult result={state.data} />}
    </div>
  );
}

/** Incidents tab: scenario presets from the catalogue, the incident, weather
 *  and surge form, and one simulated result against its baseline. */
export function IncidentsTab() {
  const catalogue = useLoad(
    getIncidentCatalogue,
    "The scenario catalogue could not be loaded.",
  );
  return (
    <Panel
      id="res-incidents"
      title="Incidents, weather and surges"
      subtitle="Disrupt a small network and watch how delay builds up and clears."
    >
      {catalogue.status === "loading" && <Skeleton lines={4} />}
      {catalogue.status === "error" && <p role="alert">{catalogue.message}</p>}
      {catalogue.status === "ready" &&
        (catalogue.data.scenarios.length > 0 ? (
          <IncidentForm catalogue={catalogue.data} />
        ) : (
          <p className="nw-muted">The catalogue has no scenarios.</p>
        ))}
    </Panel>
  );
}
