import { useId, useState } from "react";
import type { SimulationConfigValues } from "../../types/config";
import {
  DEMAND_LEVELS,
  RUN_LENGTHS,
  demandLevelFor,
  demandRate,
  demandVph,
  signalCycleSeconds,
  vehiclesPerHour,
} from "../../types/config";
import { ConfigurationSidebar } from "../ConfigurationSidebar";
import { duration } from "../../metrics/plainLanguage";
import {
  MIX_PRESETS,
  describeMix,
  hasLongVehicles,
  mixPresetFor,
} from "../../vehicles/vehicleClasses";
import { VehicleMixBar } from "../VehicleLegend";
import {
  SIGNAL_CONTROL_CHOICES,
  scenarioAdaptiveSentence,
} from "../../signals/signalControl";
import { ScenarioBuilder } from "../scenario/ScenarioBuilder";
import { useScenarioValidation } from "../scenario/useScenarioValidation";
import {
  configValuesFromScenario,
  describeScenario,
  sameScenario,
  scenarioFromConfigValues,
} from "../../scenario/scenarioModel";
import type { ScenarioDocument, Strategy } from "../../scenario/scenarioTypes";

/** A guided run; `isBatch` asks the parent for a batch experiment instead. */
export type GuidedRunRequest = SimulationConfigValues & { isBatch?: boolean };

const LANE_CHOICES = [1, 2, 3];

/** Step 1 of the comparison: the junction described in everyday terms.
 *  Specialist parameters (signal timings, gap acceptance, lane width, the
 *  random seed) stay one click away in the existing settings panel. */
export function ScenarioSetup({
  config,
  onRun,
  runInProgress,
}: {
  config: SimulationConfigValues;
  onRun: (config: GuidedRunRequest) => void;
  /** A comparison is already running or paused with the current settings. */
  runInProgress: boolean;
}) {
  const [prevConfig, setPrevConfig] = useState(config);
  const [draft, setDraft] = useState(config);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [isBatchMode, setIsBatchMode] = useState(false);
  // V1.4: answer the quick questions, or build the junction in full.
  const [mode, setMode] = useState<"quick" | "custom">(
    config.scenario ? "custom" : "quick",
  );
  const [scenario, setScenario] = useState<ScenarioDocument>(() =>
    scenarioFromConfigValues(config),
  );
  const signalStrategy: Strategy =
    scenario.junction.type === "adaptive_signal" ? "adaptive" : "fixed_time";
  const customStrategies: Strategy[] = [signalStrategy, "roundabout"];
  const scenarioCheck = useScenarioValidation(scenario, customStrategies);
  const demandName = useId();
  const lanesName = useId();
  const mixName = useId();
  const controlName = useId();
  const lengthName = useId();

  if (config !== prevConfig) {
    setPrevConfig(config);
    setDraft(config);
    if (config.scenario) setScenario(scenarioFromConfigValues(config));
  }

  const set = <K extends keyof SimulationConfigValues>(
    key: K,
    value: SimulationConfigValues[K],
  ) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const level = demandLevelFor(draft.arrivalRate, draft.lanes);
  const lengthKnown = RUN_LENGTHS.some((l) => l.seconds === draft.duration);
  const ns = draft.nsGreenDuration ?? draft.greenDuration;
  const ew = draft.ewGreenDuration ?? draft.greenDuration;
  const unchanged = JSON.stringify(draft) === JSON.stringify(config);
  const mixPreset = mixPresetFor(draft.vehicleMix);
  const adaptive = draft.signalControl === "adaptive";

  return (
    <div className="guided-page">
      <header className="guided-intro">
        <p className="guided-eyebrow">Step 1 of 3</p>
        <h1>Describe the junction you want to test</h1>
        <p>
          UrbanFlow will run a <strong>traffic signal</strong> and a{" "}
          <strong>roundabout</strong> on this junction side by side, with
          exactly the same vehicles arriving at exactly the same moments. You
          watch both, then read the results in plain language.
        </p>
        <div
          className="seg setup-mode"
          role="group"
          aria-label="How to describe the junction"
        >
          <button
            type="button"
            className={mode === "quick" ? "is-active" : ""}
            aria-pressed={mode === "quick"}
            onClick={() => {
              setMode("quick");
            }}
          >
            Answer a few questions
          </button>
          <button
            type="button"
            className={mode === "custom" ? "is-active" : ""}
            aria-pressed={mode === "custom"}
            onClick={() => {
              if (mode === "quick")
                setScenario(scenarioFromConfigValues(draft));
              setMode("custom");
            }}
          >
            Build your own junction
          </button>
        </div>
      </header>

      {mode === "custom" ? (
        <>
          <ScenarioBuilder
            value={scenario}
            onChange={setScenario}
            strategies={customStrategies}
            validation={scenarioCheck}
            junctionNote={
              <>
                The comparison always runs a{" "}
                <strong>
                  {signalStrategy === "adaptive"
                    ? "signal that responds to traffic"
                    : "fixed-time signal"}
                </strong>{" "}
                and a <strong>roundabout</strong> on these roads with the same
                traffic. Choose “Adaptive signal” to compare the responsive
                signal instead; three-way studies are in the Research Lab.
              </>
            }
          />
          <div className="guided-cta">
            <p>
              Comparing a{" "}
              {signalStrategy === "adaptive"
                ? "traffic signal that responds to traffic"
                : "traffic signal"}{" "}
              with a roundabout: <strong>{describeScenario(scenario)}</strong>{" "}
              For {duration(scenario.simulation.duration)} of traffic, seed{" "}
              {scenario.simulation.seed}.
            </p>
            <button
              type="button"
              className="guided-primary-btn"
              disabled={
                !(scenarioCheck.status === "done" && scenarioCheck.result.valid)
              }
              onClick={() => {
                onRun(configValuesFromScenario(scenario, draft));
              }}
            >
              {runInProgress &&
              config.scenario &&
              sameScenario(config.scenario, scenario)
                ? "Continue watching →"
                : "Run the comparison →"}
            </button>
            {!(
              scenarioCheck.status === "done" && scenarioCheck.result.valid
            ) && (
              <p className="q-help">
                {scenarioCheck.status === "checking"
                  ? "Checking the scenario…"
                  : "Fix what the scenario panel lists to run this comparison."}
              </p>
            )}
          </div>
        </>
      ) : (
        <>
          <fieldset className="guided-question">
            <legend>
              <span className="q-number">1</span> How busy is the junction?
            </legend>
            <p className="q-help">
              Levels are set relative to how much traffic{" "}
              {draft.lanes === 1
                ? "a one-lane"
                : `a ${String(draft.lanes)}-lane`}{" "}
              junction can carry, so they mean the same thing at every lane
              count. Figures are totals across all four approaches.
            </p>
            <div className="choice-grid choice-grid--levels">
              {DEMAND_LEVELS.map((d) => (
                <label
                  key={d.id}
                  className={`choice-card${level?.id === d.id ? " is-selected" : ""}`}
                >
                  <input
                    type="radio"
                    name={demandName}
                    checked={level?.id === d.id}
                    onChange={() => {
                      set("arrivalRate", demandRate(d, draft.lanes));
                    }}
                  />
                  <span className="choice-title">{d.label}</span>
                  <span className="choice-figure">
                    {demandVph(d, draft.lanes).toLocaleString()} vehicles / hour
                  </span>
                  <span className="choice-desc">{d.description}</span>
                </label>
              ))}
            </div>
            {!level && (
              <p className="q-note">
                Custom traffic level: ≈{" "}
                {vehiclesPerHour(draft.arrivalRate).toLocaleString()} vehicles
                per hour (set in advanced settings).
              </p>
            )}
          </fieldset>

          <fieldset className="guided-question">
            <legend>
              <span className="q-number">2</span> How many lanes does each
              approach have?
            </legend>
            <div className="choice-row">
              {LANE_CHOICES.map((n) => (
                <label
                  key={n}
                  className={`choice-pill${draft.lanes === n ? " is-selected" : ""}`}
                >
                  <input
                    type="radio"
                    name={lanesName}
                    checked={draft.lanes === n}
                    onChange={() => {
                      setDraft((prev) => {
                        const kept = demandLevelFor(
                          prev.arrivalRate,
                          prev.lanes,
                        );
                        return {
                          ...prev,
                          lanes: n,
                          arrivalRate: kept
                            ? demandRate(kept, n)
                            : prev.arrivalRate,
                        };
                      });
                    }}
                  />
                  {n} {n === 1 ? "lane" : "lanes"}
                </label>
              ))}
            </div>
            <p className="q-help">
              Each lane is modelled: the signal gets a lane per movement and the
              roundabout up to two circulating lanes (three approach lanes merge
              onto two).
            </p>
            {draft.lanes > 1 && (
              <>
                <p className="q-help">
                  Turning traffic keeps to its turn lane; drivers going straight
                  change lanes when it saves them time, moving across gradually
                  and only into a safe gap. On the roundabout, left turns use
                  the inner lane and right turns the outer lane.
                </p>
                <p className="q-note is-caution" role="note">
                  With more than one lane, results are indicative: one lane per
                  approach is the calibrated comparison. Drivers leaving the
                  roundabout from the inner ring take turns with outer-ring
                  traffic at each exit, and only start across the outer ring
                  when they can clear it.
                </p>
              </>
            )}
          </fieldset>

          <fieldset className="guided-question">
            <legend>
              <span className="q-number">3</span> What traffic uses the
              junction?
            </legend>
            <div className="choice-grid choice-grid--levels">
              {MIX_PRESETS.map((preset) => (
                <label
                  key={preset.id}
                  className={`choice-card${mixPreset?.id === preset.id ? " is-selected" : ""}`}
                >
                  <input
                    type="radio"
                    name={mixName}
                    checked={mixPreset?.id === preset.id}
                    onChange={() => {
                      set("vehicleMix", preset.mix);
                    }}
                  />
                  <span className="choice-title">{preset.label}</span>
                  <VehicleMixBar mix={preset.mix} />
                  <span className="choice-desc">{preset.description}</span>
                </label>
              ))}
            </div>
            {!mixPreset && (
              <p className="q-note">
                Custom mix: {describeMix(draft.vehicleMix)} (set in advanced
                settings).
              </p>
            )}
            {draft.vehicleMix ? (
              <p className="q-help">
                Each kind of vehicle drives as it does in reality: buses and
                trucks accelerate and brake gently, keep longer gaps and take
                curves slowly; motorcycles are nimble.{" "}
                {hasLongVehicles(draft.vehicleMix) &&
                  "Because buses and trucks use it, the junction is laid out for them, as real bus and freight routes are: stop lines sit further back, giving long vehicles room to turn. "}
                Results are indicative: the calibrated comparison is cars only.
              </p>
            ) : (
              <p className="q-help">
                SUVs, buses, trucks and motorcycles can be mixed in; each drives
                the way that kind of vehicle does.
              </p>
            )}
          </fieldset>

          <fieldset className="guided-question">
            <legend>
              <span className="q-number">4</span> How should the signal respond
              to traffic?
            </legend>
            <div className="choice-grid">
              {SIGNAL_CONTROL_CHOICES.map((choice) => {
                const selected =
                  (draft.signalControl ?? "fixed_time") === choice.id;
                return (
                  <label
                    key={choice.id}
                    className={`choice-card${selected ? " is-selected" : ""}`}
                  >
                    <input
                      type="radio"
                      name={controlName}
                      checked={selected}
                      onChange={() => {
                        set(
                          "signalControl",
                          choice.id === "adaptive" ? "adaptive" : undefined,
                        );
                      }}
                    />
                    <span className="choice-title">{choice.label}</span>
                    <span className="choice-desc">{choice.description}</span>
                  </label>
                );
              })}
            </div>
            <p className="q-help">
              {adaptive
                ? `${scenarioAdaptiveSentence(draft)} Yellow and all-red clearances are never shortened. The roundabout is unchanged.`
                : "Most signals in towns run a fixed timetable. A signal that responds to traffic uses detectors to give green where vehicles are actually waiting."}
            </p>
          </fieldset>

          <fieldset className="guided-question">
            <legend>
              <span className="q-number">5</span> How do drivers behave?
            </legend>
            <div className="choice-grid">
              <label
                className={`choice-card${!draft.unstructuredTraffic ? " is-selected" : ""}`}
              >
                <input
                  type="radio"
                  name="unstructuredTraffic"
                  checked={!draft.unstructuredTraffic}
                  onChange={() => {
                    set("unstructuredTraffic", false);
                  }}
                />
                <span className="choice-title">Structured / Idealistic</span>
                <span className="choice-desc">
                  Perfect drivers following exact rules
                </span>
              </label>
              <label
                className={`choice-card${draft.unstructuredTraffic ? " is-selected" : ""}`}
              >
                <input
                  type="radio"
                  name="unstructuredTraffic"
                  checked={draft.unstructuredTraffic}
                  onChange={() => {
                    set("unstructuredTraffic", true);
                  }}
                />
                <span className="choice-title">Unstructured / Chaotic</span>
                <span className="choice-desc">
                  Realistic driver imperfections (hesitation, variable reaction,
                  blocking)
                </span>
              </label>
            </div>
            {draft.unstructuredTraffic && (
              <label
                className="checkbox-label"
                style={{
                  marginTop: "1rem",
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "center",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={draft.aggressiveTwoWheelers}
                  onChange={(e) => {
                    set("aggressiveTwoWheelers", e.target.checked);
                  }}
                  style={{
                    width: "1.2rem",
                    height: "1.2rem",
                    accentColor: "#e5a910",
                  }}
                />
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span
                    className="choice-title"
                    style={{ fontSize: "1rem", marginBottom: "0.2rem" }}
                  >
                    Aggressive Two-Wheelers
                  </span>
                  <span className="choice-desc" style={{ fontSize: "0.85rem" }}>
                    Scooters will aggressively overtake and enter wherever they
                    see space.
                  </span>
                </div>
              </label>
            )}
          </fieldset>

          <fieldset className="guided-question">
            <legend>
              <span className="q-number">6</span> How long should we watch?
            </legend>
            <div className="choice-grid three">
              {RUN_LENGTHS.map((l) => (
                <label
                  key={l.seconds}
                  className={`choice-card${draft.duration === l.seconds ? " is-selected" : ""}`}
                >
                  <input
                    type="radio"
                    name={lengthName}
                    checked={draft.duration === l.seconds}
                    onChange={() => {
                      set("duration", l.seconds);
                    }}
                  />
                  <span className="choice-title">{l.label}</span>
                  <span className="choice-desc">{l.description}</span>
                </label>
              ))}
            </div>
            {!lengthKnown && (
              <p className="q-note">
                Custom length: {duration(draft.duration)} (set in advanced
                settings).
              </p>
            )}
            <p className="q-help">
              The simulation plays in real time so you can watch it. The first
              30 s are a warm-up and are not counted; after that you can look at
              the results so far at any moment.
            </p>
          </fieldset>

          <section className="guided-question" aria-labelledby="options-title">
            <h2 id="options-title" className="as-legend">
              The two options being compared
            </h2>
            <div className="option-pair">
              <div className="option-card is-signal">
                <h3>
                  {adaptive ? "Traffic signal that responds" : "Traffic signal"}
                </h3>
                {adaptive ? (
                  <p>
                    Detectors at each stop line decide how long each green
                    lasts; north–south and east–west take turns, with the usual
                    yellow and all-red in between.
                  </p>
                ) : (
                  <p>
                    Fixed timetable:{" "}
                    {ns === ew
                      ? `${String(ns)} s`
                      : `${String(ns)} s / ${String(ew)} s`}{" "}
                    of green for each direction in turn, a{" "}
                    {String(signalCycleSeconds(draft))} s cycle.
                  </p>
                )}
              </div>
              <div className="option-card is-roundabout">
                <h3>Roundabout</h3>
                <p>
                  {draft.lanes === 1
                    ? "One circulating lane."
                    : "Two circulating lanes."}{" "}
                  Drivers give way to circulating traffic and enter at gaps of
                  at least {draft.criticalGap.toFixed(1)} s.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="guided-link-btn"
              onClick={() => {
                setAdvancedOpen(true);
              }}
              aria-haspopup="dialog"
            >
              Advanced settings — signal timing, driver behaviour, lane width,
              traffic pattern
            </button>
          </section>

          <div className="guided-cta">
            <p>
              Comparing a{" "}
              {adaptive
                ? "traffic signal that responds to traffic"
                : "traffic signal"}{" "}
              with a roundabout at{" "}
              <strong>
                ≈ {vehiclesPerHour(draft.arrivalRate).toLocaleString()} vehicles
                per hour
              </strong>
              ,{" "}
              <strong>
                {draft.lanes === 1
                  ? "one lane"
                  : `${String(draft.lanes)} lanes`}
              </strong>{" "}
              per approach, <strong>{describeMix(draft.vehicleMix)}</strong>,
              for <strong>{duration(draft.duration)}</strong> of traffic.
            </p>
            <button
              type="button"
              className="guided-primary-btn"
              onClick={() => {
                if (isBatchMode) {
                  // In a real app we'd open a modal to select parameters.
                  // For now, we'll just inform the parent to do a batch run.
                  onRun({ ...draft, scenario: null, isBatch: true });
                } else {
                  onRun({ ...draft, scenario: null });
                }
              }}
            >
              {runInProgress && unchanged && !config.scenario
                ? "Continue watching →"
                : isBatchMode
                  ? "Enqueue Batch Experiment →"
                  : "Run the comparison →"}
            </button>
            <div className="batch-toggle" style={{ marginTop: "1rem" }}>
              <label
                className="checkbox-label"
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "center",
                  cursor: "pointer",
                  justifyContent: "center",
                }}
              >
                <input
                  type="checkbox"
                  checked={isBatchMode}
                  onChange={(e) => {
                    setIsBatchMode(e.target.checked);
                  }}
                  style={{
                    width: "1.2rem",
                    height: "1.2rem",
                    accentColor: "#e5a910",
                  }}
                />
                <span className="choice-title" style={{ fontSize: "1rem" }}>
                  Run as Batch Experiment (Sweeping Demand Levels)
                </span>
              </label>
            </div>
            {runInProgress && !unchanged && !isBatchMode && (
              <p className="q-help">
                Running with new settings starts a fresh comparison.
              </p>
            )}
          </div>
        </>
      )}

      <ConfigurationSidebar
        isOpen={advancedOpen}
        onClose={() => {
          setAdvancedOpen(false);
        }}
        config={draft}
        onApply={(next) => {
          setDraft(next);
          setAdvancedOpen(false);
        }}
        mode="comparative"
        draftOnly
      />
    </div>
  );
}
