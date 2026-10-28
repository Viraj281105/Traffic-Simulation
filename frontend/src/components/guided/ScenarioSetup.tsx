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
import { scenarioAdaptiveSentence } from "../../signals/signalControl";
import { StrategyPicker } from "../../strategies/StrategyPicker";
import {
  selectedStrategies,
  strategyInfo,
  useStrategyCatalog,
} from "../../strategies/strategyCatalog";
import { ResearchLink } from "../research/LabSection";
import "../research/ResearchLab.css";
import { VIEW_ROUTES } from "../../routing";
import { ScenarioBuilder } from "../scenario/ScenarioBuilder";
import { useScenarioValidation } from "../scenario/useScenarioValidation";
import {
  configValuesFromScenario,
  describeScenario,
  sameScenario,
  scenarioFromConfigValues,
} from "../../scenario/scenarioModel";
import {
  DRIVER_AGGRESSION_DISCLAIMER,
  DRIVER_AGGRESSION_INFO,
  DRIVER_AGGRESSION_PROFILES,
  isMeteredEntry,
  type ScenarioDocument,
  type Strategy,
} from "../../scenario/scenarioTypes";

/** A guided run: the configuration to compare, with its strategies. */
export type GuidedRunRequest = SimulationConfigValues;

/** The scenario check validates the junction for each family it will run
 *  as (the builder's strategy names); the metered roundabout is checked as
 *  a roundabout, since it runs the default plan when none is drawn. */
function builderStrategies(ids: string[]): Strategy[] {
  const out = new Set<Strategy>();
  for (const id of ids) {
    if (id === "adaptive_signal") out.add("adaptive");
    else if (strategyInfo(id).family === "roundabout") out.add("roundabout");
    else out.add("fixed_time");
  }
  return out.size ? [...out] : ["fixed_time", "roundabout"];
}

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
  const catalog = useStrategyCatalog();
  // V1.4: answer the quick questions, or build the junction in full.
  const [mode, setMode] = useState<"quick" | "custom">(
    config.scenario ? "custom" : "quick",
  );
  const [scenario, setScenario] = useState<ScenarioDocument>(() =>
    scenarioFromConfigValues(config),
  );
  const chosen = selectedStrategies(
    draft.strategies,
    catalog.status === "ready" ? catalog.catalog : null,
  );
  const chosenNames = chosen.map((id) => strategyInfo(id).name);
  const comparing =
    chosenNames.length === 0
      ? "no strategy yet"
      : chosenNames.length === 1
        ? chosenNames[0]
        : `${chosenNames.slice(0, -1).join(", ")} and ${chosenNames[chosenNames.length - 1]}`;
  const canRun = catalog.status === "ready" && chosen.length > 0;
  const runLabel =
    chosen.length > 1
      ? `Run ${String(chosen.length)} strategies →`
      : "Run the simulation →";
  const customStrategies = builderStrategies(chosen);
  const scenarioCheck = useScenarioValidation(scenario, customStrategies);
  const demandName = useId();
  const lanesName = useId();
  const mixName = useId();
  const lengthName = useId();
  const aggressionName = useId();
  const aggressionHeadingId = useId();

  if (config !== prevConfig) {
    setPrevConfig(config);
    setDraft(config);
    if (config.scenario) setScenario(scenarioFromConfigValues(config));
  }

  const strategyDetails: Record<string, React.ReactNode> = {
    fixed_time_signal: `Timetable: ${
      (draft.nsGreenDuration ?? draft.greenDuration) ===
      (draft.ewGreenDuration ?? draft.greenDuration)
        ? `${String(draft.nsGreenDuration ?? draft.greenDuration)} s`
        : `${String(draft.nsGreenDuration ?? draft.greenDuration)} s / ${String(draft.ewGreenDuration ?? draft.greenDuration)} s`
    } green each way, a ${String(signalCycleSeconds(draft))} s cycle.`,
    adaptive_signal: scenarioAdaptiveSentence(draft),
    conventional_roundabout: `${draft.lanes === 1 ? "One circulating lane" : "Two circulating lanes"}; drivers enter at gaps of at least ${draft.criticalGap.toFixed(1)} s.`,
    metered_entry_roundabout:
      mode === "custom" && isMeteredEntry(scenario)
        ? "Entry signals: the plan set in the junction builder."
        : "Entry signals: north–south, then east–west, 20 s greens.",
  };

  const set = <K extends keyof SimulationConfigValues>(
    key: K,
    value: SimulationConfigValues[K],
  ) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  const level = demandLevelFor(draft.arrivalRate, draft.lanes);
  const lengthKnown = RUN_LENGTHS.some((l) => l.seconds === draft.duration);
  const unchanged = JSON.stringify(draft) === JSON.stringify(config);
  const mixPreset = mixPresetFor(draft.vehicleMix);

  return (
    <div className="guided-page">
      <header className="guided-intro">
        <p className="guided-eyebrow">Step 1 of 3</p>
        <h1>Describe the junction you want to test</h1>
        <p>
          Pick the ways of controlling the junction you want to compare.
          UrbanFlow runs them side by side with exactly the same vehicles
          arriving at exactly the same moments; you watch them, then read the
          results in plain language.
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

      <StrategyPicker
        catalog={catalog}
        value={chosen}
        onChange={(next) => {
          set("strategies", next);
        }}
        details={strategyDetails}
      />

      {mode === "custom" ? (
        <>
          <ScenarioBuilder
            value={scenario}
            onChange={setScenario}
            strategies={customStrategies}
            validation={scenarioCheck}
            junctionNote={
              <>
                The comparison runs the strategies chosen above on these roads
                with the same traffic; the junction type here sets the layout
                you preview. A metered roundabout uses the entry-signal plan set
                below
                {isMeteredEntry(scenario)
                  ? ""
                  : " once you add one, or a default north–south / east–west plan"}
                .
              </>
            }
          />
          <div className="guided-cta">
            <p>
              Comparing <strong>{comparing}</strong>:{" "}
              <strong>{describeScenario(scenario)}</strong> For{" "}
              {duration(scenario.simulation.duration)} of traffic, seed{" "}
              {scenario.simulation.seed}.
            </p>
            <button
              type="button"
              className="guided-primary-btn"
              disabled={
                !canRun ||
                !(scenarioCheck.status === "done" && scenarioCheck.result.valid)
              }
              onClick={() => {
                onRun({
                  ...configValuesFromScenario(scenario, draft),
                  strategies: chosen,
                });
              }}
            >
              {runInProgress &&
              config.scenario &&
              sameScenario(config.scenario, scenario)
                ? "Continue watching →"
                : runLabel}
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
              <span className="q-number">4</span> How do drivers behave?
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
              <label className="q-toggle">
                <input
                  type="checkbox"
                  checked={draft.aggressiveTwoWheelers}
                  onChange={(e) => {
                    set("aggressiveTwoWheelers", e.target.checked);
                  }}
                />
                <span className="q-toggle-text">
                  <span className="choice-title">Aggressive two-wheelers</span>
                  <span className="choice-desc">
                    Scooters overtake and enter wherever they see space.
                  </span>
                </span>
              </label>
            )}

            <div
              className="q-subsection"
              role="radiogroup"
              aria-labelledby={aggressionHeadingId}
            >
              <span className="q-subtitle" id={aggressionHeadingId}>
                Driver aggression
              </span>
              <div className="choice-grid choice-grid--levels">
                {DRIVER_AGGRESSION_PROFILES.map((profile) => {
                  const info = DRIVER_AGGRESSION_INFO[profile];
                  const isSelected =
                    (draft.driverAggression ?? "standard") === profile;
                  return (
                    <label
                      key={profile}
                      className={`choice-card${isSelected ? " is-selected" : ""}`}
                    >
                      <input
                        type="radio"
                        name={aggressionName}
                        checked={isSelected}
                        onChange={() => {
                          set("driverAggression", profile);
                        }}
                      />
                      <span className="choice-title">{info.label}</span>
                      <span className="choice-figure">{info.levers}</span>
                      <span className="choice-desc">{info.summary}</span>
                    </label>
                  );
                })}
              </div>
              <p className="q-note is-assumption">
                {DRIVER_AGGRESSION_DISCLAIMER}. T is the following headway, s₀
                the gap to a stopped vehicle, a the launch acceleration.
              </p>
            </div>
          </fieldset>

          <fieldset className="guided-question">
            <legend>
              <span className="q-number">5</span> How long should we watch?
            </legend>
            <div className="choice-grid choice-grid--levels">
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

          <div className="setup-advanced">
            <button
              type="button"
              className="pb-btn pb-secondary"
              onClick={() => {
                setAdvancedOpen(true);
              }}
              aria-haspopup="dialog"
            >
              Advanced settings
            </button>
            <span className="q-help">
              Signal timing, gap acceptance, lane width and the traffic pattern.
            </span>
          </div>

          <div className="guided-cta">
            <p>
              Comparing <strong>{comparing}</strong> at{" "}
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
              per approach, <strong>{describeMix(draft.vehicleMix)}</strong>
              {draft.driverAggression &&
                draft.driverAggression !== "standard" && (
                  <>
                    ,{" "}
                    <strong>{draft.driverAggression} driver aggression</strong>
                  </>
                )}
              , for <strong>{duration(draft.duration)}</strong> of traffic.
            </p>
            <button
              type="button"
              className="guided-primary-btn"
              disabled={!canRun}
              onClick={() => {
                onRun({ ...draft, scenario: null, strategies: chosen });
              }}
            >
              {runInProgress && unchanged && !config.scenario
                ? "Continue watching →"
                : runLabel}
            </button>
            {runInProgress && !unchanged && (
              <p className="q-help">
                Running with new settings starts a fresh comparison.
              </p>
            )}
            <p className="q-help">
              Want every traffic level at once?{" "}
              <ResearchLink to={VIEW_ROUTES.volume}>
                Traffic-level sweep
              </ResearchLink>
            </p>
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
