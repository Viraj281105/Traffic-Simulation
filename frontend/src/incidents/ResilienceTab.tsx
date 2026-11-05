import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import "../netcommon/network.css";
import { EmptyHint, Panel, Skeleton } from "../components/dashboard/Dashboard";
import { NumberField } from "../netcommon/NumberField";
import { useAction } from "../netcommon/useAction";
import { useLoad } from "../rescommon/useLoad";
import { evaluateResilience, getIncidentCatalogue } from "./api";
import { PresetPicker } from "./PresetPicker";
import { ResilienceView } from "./ResilienceView";
import { scenarioFromPreset } from "./scenario";
import type { IncidentCatalogue, ResilienceResponse } from "./types";

function ResilienceForm({ catalogue }: { catalogue: IncidentCatalogue }) {
  const [presetId, setPresetId] = useState(catalogue.scenarios[0].id);
  const [seedCount, setSeedCount] = useState(3);
  const [state, start] = useAction<ResilienceResponse>(
    "The strategies could not be compared.",
  );
  const preset =
    catalogue.scenarios.find((p) => p.id === presetId) ??
    catalogue.scenarios[0];
  return (
    <div className="nw-stack">
      <PresetPicker
        presets={catalogue.scenarios}
        value={presetId}
        onChange={setPresetId}
      />
      <form
        className="nw-form"
        onSubmit={(event) => {
          event.preventDefault();
          start(() =>
            evaluateResilience({
              preset: preset.id,
              scenario: scenarioFromPreset(preset.scenario),
              duration: preset.duration,
              seedCount,
              strategies: catalogue.strategies,
            }),
          );
        }}
      >
        <NumberField
          label="Seeds (1 to 10)"
          value={seedCount}
          min={1}
          max={10}
          onChange={(v) => {
            setSeedCount(Math.round(v));
          }}
        />
        <button
          type="submit"
          className="nw-btn nw-btn--primary"
          disabled={state.status === "loading"}
        >
          Compare strategies
        </button>
      </form>
      {state.status === "idle" && (
        <EmptyHint icon={<ShieldCheck size={22} />} title="No comparison yet">
          Press Compare strategies. Every strategy runs each seed with and
          without the disruption, so this can take a little while.
        </EmptyHint>
      )}
      {state.status === "loading" && <Skeleton lines={5} />}
      {state.status === "error" && <p role="alert">{state.message}</p>}
      {state.status === "ready" && <ResilienceView result={state.data} />}
    </div>
  );
}

/** Resilience tab: how well each signal strategy copes with a scenario. */
export function ResilienceTab() {
  const catalogue = useLoad(
    getIncidentCatalogue,
    "The scenario catalogue could not be loaded.",
  );
  return (
    <Panel
      id="res-resilience"
      title="Resilience of signal strategies"
      subtitle="How fast and how far each strategy is knocked off its normal performance."
    >
      {catalogue.status === "loading" && <Skeleton lines={4} />}
      {catalogue.status === "error" && <p role="alert">{catalogue.message}</p>}
      {catalogue.status === "ready" &&
        (catalogue.data.scenarios.length > 0 ? (
          <ResilienceForm catalogue={catalogue.data} />
        ) : (
          <p className="nw-muted">The catalogue has no scenarios.</p>
        ))}
    </Panel>
  );
}
