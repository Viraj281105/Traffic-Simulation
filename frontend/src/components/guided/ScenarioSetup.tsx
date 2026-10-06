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
  onRun: (config: SimulationConfigValues) => void;
  /** A comparison is already running or paused with the current settings. */
  runInProgress: boolean;
}) {
  const [prevConfig, setPrevConfig] = useState(config);
  const [draft, setDraft] = useState(config);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const demandName = useId();
  const lanesName = useId();
  const mixName = useId();
  const lengthName = useId();

  if (config !== prevConfig) {
    setPrevConfig(config);
    setDraft(config);
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
      </header>

      <fieldset className="guided-question">
        <legend>
          <span className="q-number">1</span> How busy is the junction?
        </legend>
        <p className="q-help">
          Levels are set relative to how much traffic{" "}
          {draft.lanes === 1 ? "a one-lane" : `a ${String(draft.lanes)}-lane`}{" "}
          junction can carry, so they mean the same thing at every lane count.
          Figures are totals across all four approaches.
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
            {vehiclesPerHour(draft.arrivalRate).toLocaleString()} vehicles per
            hour (set in advanced settings).
          </p>
        )}
      </fieldset>

      <fieldset className="guided-question">
        <legend>
          <span className="q-number">2</span> How many lanes does each approach
          have?
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
                    const kept = demandLevelFor(prev.arrivalRate, prev.lanes);
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
          roundabout one circulating ring per lane.
        </p>
        {draft.lanes > 1 && (
          <>
            <p className="q-help">
              Turning traffic keeps to its turn lane; drivers going straight
              change lanes when it saves them time, moving across gradually and
              only into a safe gap.
            </p>
            <p className="q-note is-caution" role="note">
              With more than one lane, results are indicative: drivers leaving
              the roundabout from an inner ring cross the outer one, and the
              model has no lane markings to separate that weave. One lane per
              approach is the calibrated comparison.
            </p>
          </>
        )}
      </fieldset>

      <fieldset className="guided-question">
        <legend>
          <span className="q-number">3</span> What traffic uses the junction?
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
            Each kind of vehicle drives as it does in reality: buses and trucks
            accelerate and brake gently, keep longer gaps and take curves
            slowly; motorcycles are nimble.{" "}
            {hasLongVehicles(draft.vehicleMix) &&
              "Because buses and trucks use it, the junction is laid out for them, as real bus and freight routes are: stop lines sit further back, giving long vehicles room to turn. "}
            Results are indicative: the calibrated comparison is cars only.
          </p>
        ) : (
          <p className="q-help">
            SUVs, buses, trucks and motorcycles can be mixed in; each drives the
            way that kind of vehicle does.
          </p>
        )}
      </fieldset>

      <fieldset className="guided-question">
        <legend>
          <span className="q-number">4</span> How long should we watch?
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
          The simulation plays in real time so you can watch it. The first 30 s
          are a warm-up and are not counted; after that you can look at the
          results so far at any moment.
        </p>
      </fieldset>

      <section className="guided-question" aria-labelledby="options-title">
        <h2 id="options-title" className="as-legend">
          The two options being compared
        </h2>
        <div className="option-pair">
          <div className="option-card is-signal">
            <h3>Traffic signal</h3>
            <p>
              Fixed timetable:{" "}
              {ns === ew
                ? `${String(ns)} s`
                : `${String(ns)} s / ${String(ew)} s`}{" "}
              of green for each direction in turn, a{" "}
              {String(signalCycleSeconds(draft))} s cycle.
            </p>
          </div>
          <div className="option-card is-roundabout">
            <h3>Roundabout</h3>
            <p>
              {draft.lanes === 1
                ? "One circulating lane."
                : `${String(draft.lanes)} circulating lanes.`}{" "}
              Drivers give way to circulating traffic and enter at gaps of at
              least {draft.criticalGap.toFixed(1)} s.
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
          Comparing a traffic signal with a roundabout at{" "}
          <strong>
            ≈ {vehiclesPerHour(draft.arrivalRate).toLocaleString()} vehicles per
            hour
          </strong>
          ,{" "}
          <strong>
            {draft.lanes === 1 ? "one lane" : `${String(draft.lanes)} lanes`}
          </strong>{" "}
          per approach, <strong>{describeMix(draft.vehicleMix)}</strong>, for{" "}
          <strong>{duration(draft.duration)}</strong> of traffic.
        </p>
        <button
          type="button"
          className="guided-primary-btn"
          onClick={() => {
            onRun(draft);
          }}
        >
          {runInProgress && unchanged
            ? "Continue watching →"
            : "Run the comparison →"}
        </button>
        {runInProgress && !unchanged && (
          <p className="q-help">
            Running with new settings starts a fresh comparison.
          </p>
        )}
      </div>

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
