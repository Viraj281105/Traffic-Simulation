import { useId, useState } from "react";
import type { SimulationConfigValues } from "../../types/config";
import {
  DEMAND_LEVELS,
  RUN_LENGTHS,
  demandLevelFor,
  signalCycleSeconds,
  vehiclesPerHour,
} from "../../types/config";
import { ConfigurationSidebar } from "../ConfigurationSidebar";
import { duration } from "../../metrics/plainLanguage";

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

  const level = demandLevelFor(draft.arrivalRate);
  const lengthKnown = RUN_LENGTHS.some((l) => l.seconds === draft.duration);
  const ns = draft.nsGreenDuration ?? draft.greenDuration;
  const ew = draft.ewGreenDuration ?? draft.greenDuration;
  const unchanged = JSON.stringify(draft) === JSON.stringify(config);

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
          Counted across all four approaches together. Pick the closest match —
          you can try other levels afterwards.
        </p>
        <div className="choice-grid">
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
                  set("arrivalRate", d.arrivalRate);
                }}
              />
              <span className="choice-title">{d.label}</span>
              <span className="choice-figure">
                ≈ {vehiclesPerHour(d.arrivalRate).toLocaleString()} vehicles /
                hour
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
                  set("lanes", n);
                }}
              />
              {n} {n === 1 ? "lane" : "lanes"}
            </label>
          ))}
        </div>
        {draft.lanes > 1 ? (
          <p className="q-note is-caution" role="note">
            The roundabout is modelled with a single circulating lane, so with
            more than one entry lane its results are indicative only. One lane
            per approach is the comparison the model is calibrated for.
          </p>
        ) : (
          <p className="q-help">
            One lane per approach is the comparison the model is calibrated for.
          </p>
        )}
      </fieldset>

      <fieldset className="guided-question">
        <legend>
          <span className="q-number">3</span> How long should we watch?
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
              Single circulating lane. Drivers give way to circling traffic and
              enter at gaps of at least {draft.criticalGap.toFixed(1)} s.
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
          per approach, for <strong>{duration(draft.duration)}</strong> of
          traffic.
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
