import { useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  APPROACHES,
  OPPOSITE,
  strategyTitle,
  type ApproachName,
  type ApproachSpec,
  type ScenarioDocument,
  type Strategy,
} from "../../scenario/scenarioTypes";
import {
  SCENARIO_PRESETS,
  cloneScenario,
  describeScenario,
  exportScenarioJson,
  localIssues,
  matchesPreset,
  parseScenarioJson,
  presetById,
  presentApproaches,
  possibleMovements,
  ringLanes,
  totalVph,
  type LocalIssue,
} from "../../scenario/scenarioModel";
import { downloadText } from "../../metrics/catalog";
import { JunctionPreview } from "./JunctionPreview";
import { MixEditor } from "./MixEditor";
import type { ValidationState } from "./useScenarioValidation";
import { JUNCTIONS, DURATIONS, STEPS, cap, type Step } from "./builderOptions";
import { NumberField } from "./fields";
import { ApproachLanesCard } from "./ApproachLanesCard";
import { ApproachTrafficCard } from "./ApproachTrafficCard";
import { GeometrySettings } from "./GeometrySettings";
import { AdvancedSettings } from "./AdvancedSettings";
import { EntryControlChoice } from "./EntryControlChoice";
import { StrategySummaryCard } from "./StrategySummaryCard";
import "./ScenarioBuilder.css";

/**
 * The V1.4 scenario builder: the user constructs their own junction — the
 * kind of control, every road's lanes and lane arrows, how busy each road is
 * and where its traffic turns, the vehicle mix and the run — while a live
 * plan, a plain-language summary and the backend's own validation show what
 * will be simulated. Presets are shortcuts into the same editable document.
 */
export function ScenarioBuilder({
  value,
  onChange,
  strategies,
  validation,
  junctionNote,
}: {
  value: ScenarioDocument;
  onChange: (next: ScenarioDocument) => void;
  /** The strategies the scenario will be run with; it is validated for each. */
  strategies: Strategy[];
  /** The backend's verdict for ``value`` (useScenarioValidation). */
  validation: ValidationState;
  /** Explains how the junction type is used in this context. */
  junctionNote?: ReactNode;
}) {
  const present = presentApproaches(value);
  const [selectedSlot, setSelected] = useState<ApproachName>("north");
  const selected = present.includes(selectedSlot)
    ? selectedSlot
    : (present[0] ?? "north");
  // Arms switched off in this session, so switching one back on restores
  // what the user had set rather than a blank road.
  const [removedArms, setRemovedArms] = useState<
    Partial<Record<ApproachName, ApproachSpec>>
  >({});
  const [previewView, setPreviewView] = useState<"signal" | "roundabout">(
    value.junction.type === "roundabout" ? "roundabout" : "signal",
  );
  const [importError, setImportError] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const ids = useId();
  const issues = localIssues(value, strategies);
  const designs =
    validation.status === "done" ? validation.result.design : undefined;
  const design = designs?.roundabout;
  const signalDesign = designs?.fixed_time ?? designs?.adaptive;
  const fromPreset = value.preset ? presetById(value.preset) : undefined;
  const unchangedPreset = matchesPreset(value);

  const update = (mutate: (draft: ScenarioDocument) => void) => {
    const draft = cloneScenario(value);
    mutate(draft);
    onChange(draft);
  };
  const updateArm = (a: ApproachName, change: Partial<ApproachSpec>) => {
    update((d) => {
      const arm = d.approaches[a];
      if (arm) d.approaches[a] = { ...arm, ...change };
    });
  };
  const toggleArm = (a: ApproachName) => {
    const arm = value.approaches[a];
    if (arm) {
      setRemovedArms({ ...removedArms, [a]: arm });
      update((d) => {
        d.approaches[a] = null;
      });
      return;
    }
    const restored = removedArms[a] ?? {
      lanes: 1,
      length: 200,
      vehiclesPerHour: 250,
      turning: { left: 0.2, straight: 0.6, right: 0.2 },
    };
    update((d) => {
      d.approaches[a] = restored;
    });
  };

  const stepIssues = (step: Step): LocalIssue[] =>
    issues.filter((i) => {
      if (step === "junction") return i.where === "junction";
      if (step === "vehicles") return i.where === "vehicles";
      if (step === "simulation") return i.where === "simulation";
      if (step === "roads")
        return (
          APPROACHES.includes(i.where as ApproachName) &&
          /lane|arrow|cross/i.test(i.message)
        );
      if (step === "traffic")
        return (
          APPROACHES.includes(i.where as ApproachName) &&
          !/lane|arrow|cross/i.test(i.message)
        );
      return false;
    });

  const serverErrors =
    validation.status === "done" ? validation.result.errors : [];
  const serverWarnings =
    validation.status === "done" ? validation.result.warnings : [];
  const ready = validation.status === "done" && validation.result.valid;

  const loadPreset = (id: string) => {
    const preset = presetById(id);
    if (!preset) return;
    const doc = cloneScenario(preset.scenario);
    onChange(doc);
    setPreviewView(
      doc.junction.type === "roundabout" ? "roundabout" : "signal",
    );
  };

  const importFile = (file: File) => {
    file
      .text()
      .then((text) => {
        const parsed = parseScenarioJson(text);
        if ("error" in parsed) {
          setImportError(parsed.error);
          return;
        }
        setImportError(null);
        onChange(parsed.scenario);
      })
      .catch(() => {
        setImportError("That file could not be read.");
      });
  };

  return (
    <div className="scenario-builder">
      <div className="sb-main">
        <nav className="sb-steps" aria-label="Scenario sections">
          {STEPS.map((s, i) => {
            const n = stepIssues(s.id).length;
            return (
              <a
                key={s.id}
                href={`#${ids}-${s.id}`}
                className={`sb-step${n ? " has-issues" : ""}`}
              >
                <span className="sb-step-n" aria-hidden="true">
                  {n ? "!" : i + 1}
                </span>
                {s.title}
                {n > 0 && <span className="sr-only"> — {n} to fix</span>}
              </a>
            );
          })}
        </nav>

        {/* 1 · Junction ─────────────────────────────────────────────── */}
        <section className="sb-section" id={`${ids}-junction`}>
          <h3>
            <span className="q-number">1</span> What kind of junction?
          </h3>
          <div className="choice-grid">
            {JUNCTIONS.map((j) => (
              <label
                key={j.id}
                className={`choice-card${value.junction.type === j.id ? " is-selected" : ""}`}
              >
                <input
                  type="radio"
                  name={`${ids}-junction`}
                  checked={value.junction.type === j.id}
                  onChange={() => {
                    update((d) => {
                      d.junction.type = j.id;
                    });
                    setPreviewView(
                      j.id === "roundabout" ? "roundabout" : "signal",
                    );
                  }}
                />
                <span className="choice-title">{j.title}</span>
                <span className="choice-desc">{j.body}</span>
              </label>
            ))}
          </div>
          {junctionNote && <p className="q-help">{junctionNote}</p>}
          <div className="sb-field">
            <span className="sb-field-label">Which roads meet here?</span>
            <div
              className="chip-row"
              role="group"
              aria-label="Arms of the junction"
            >
              {APPROACHES.map((a) => {
                const on = value.approaches[a] != null;
                return (
                  <button
                    key={a}
                    type="button"
                    className={`chip${on ? " is-active" : ""}`}
                    aria-pressed={on}
                    onClick={() => {
                      toggleArm(a);
                    }}
                  >
                    {cap(a)}
                  </button>
                );
              })}
            </div>
            <p className="q-help">
              {present.length === 4
                ? "A crossroads. Switch one road off for a T-junction."
                : present.length === 3
                  ? `A three-arm junction: no ${APPROACHES.filter((a) => !present.includes(a)).join(", ")} road. Nobody can turn towards the missing road; set those turning shares to 0.`
                  : "A junction needs at least three roads."}{" "}
              Real road angles and lane widths are under Advanced.
            </p>
          </div>
          {(strategies.includes("roundabout") ||
            value.junction.type === "roundabout") && (
            <EntryControlChoice value={value} update={update} />
          )}
        </section>

        {/* 2 · Roads & lanes ────────────────────────────────────────── */}
        <section className="sb-section" id={`${ids}-roads`}>
          <h3>
            <span className="q-number">2</span> Roads and lanes
          </h3>
          <p className="q-help">
            Each approach is one direction of traffic arriving at the junction.
            Set its lanes and the arrows painted on them; lane 1 is next to the
            centre line. A signal needs the same number of lanes on opposite
            approaches; a roundabout does not. A U-turn arrow (↶) is only ever
            where you put it.
          </p>
          <div className="sb-approach-grid">
            {present.map((a) => (
              <ApproachLanesCard
                key={a}
                approach={a}
                arm={value.approaches[a] as ApproachSpec}
                hasOpposite={value.approaches[OPPOSITE[a]] != null}
                possible={possibleMovements(value, a)}
                selected={selected === a}
                onSelect={() => {
                  setSelected(a);
                }}
                onChange={(change) => {
                  updateArm(a, change);
                }}
                onCopyOpposite={() => {
                  const other = value.approaches[OPPOSITE[a]];
                  if (!other) return;
                  updateArm(a, {
                    lanes: other.lanes,
                    length: other.length,
                    laneUse: other.laneUse
                      ? other.laneUse.map((l) => [...l])
                      : null,
                    roundaboutLaneUse: other.roundaboutLaneUse
                      ? other.roundaboutLaneUse.map((l) => [...l])
                      : null,
                  });
                }}
                roundaboutUse={design?.laneUse[a]}
                issues={stepIssues("roads").filter((i) => i.where === a)}
              />
            ))}
          </div>
        </section>

        {/* 3 · Traffic ──────────────────────────────────────────────── */}
        <section className="sb-section" id={`${ids}-traffic`}>
          <h3>
            <span className="q-number">3</span> How busy is each road?
          </h3>
          <p className="q-help">
            Pick a level, or type the exact vehicles per hour. Turning shares
            say where that road’s drivers go; each road may also have its own
            vehicle mix. Total:{" "}
            <strong>
              {Math.round(totalVph(value)).toLocaleString()} vehicles per hour
            </strong>
            .
          </p>
          <div className="sb-approach-grid">
            {present.map((a) => (
              <ApproachTrafficCard
                key={a}
                approach={a}
                arm={value.approaches[a] as ApproachSpec}
                possible={possibleMovements(value, a)}
                selected={selected === a}
                onSelect={() => {
                  setSelected(a);
                }}
                onChange={(change) => {
                  updateArm(a, change);
                }}
                issues={stepIssues("traffic").filter((i) => i.where === a)}
              />
            ))}
          </div>
        </section>

        {/* 4 · Vehicles ─────────────────────────────────────────────── */}
        <section className="sb-section" id={`${ids}-vehicles`}>
          <h3>
            <span className="q-number">4</span> What traffic uses the junction?
          </h3>
          <MixEditor
            value={value.vehicles.mix ?? null}
            onChange={(mix) => {
              update((d) => {
                d.vehicles.mix = mix;
              });
            }}
          />
          <p className="q-help">
            “Cars only” is the calibrated population. Any other mix is
            exploratory: bus, truck, SUV and motorcycle parameters are model
            inputs, not calibrated values. Roads with their own mix (step 3) use
            it instead.
          </p>
        </section>

        {/* 5 · Simulation ───────────────────────────────────────────── */}
        <section className="sb-section" id={`${ids}-simulation`}>
          <h3>
            <span className="q-number">5</span> How should it run?
          </h3>
          <div className="sb-field-row">
            <div className="sb-field">
              <span className="sb-field-label">Simulated time</span>
              <div className="chip-row">
                {DURATIONS.map((dur) => (
                  <button
                    key={dur.seconds}
                    type="button"
                    className={`chip${value.simulation.duration === dur.seconds ? " is-active" : ""}`}
                    aria-pressed={value.simulation.duration === dur.seconds}
                    onClick={() => {
                      update((d) => {
                        d.simulation.duration = dur.seconds;
                      });
                    }}
                  >
                    {dur.label}
                  </button>
                ))}
              </div>
            </div>
            <NumberField
              label="Duration"
              unit="s"
              value={value.simulation.duration}
              min={30}
              max={3600}
              step={10}
              onChange={(v) => {
                update((d) => {
                  d.simulation.duration = v;
                });
              }}
            />
            <NumberField
              label="Warm-up (not measured)"
              unit="s"
              value={value.simulation.warmup}
              min={0}
              max={600}
              step={5}
              onChange={(v) => {
                update((d) => {
                  d.simulation.warmup = v;
                });
              }}
            />
            <div className="sb-field">
              <span className="sb-field-label">Random seed</span>
              <div className="sb-inline">
                <input
                  type="number"
                  min={0}
                  aria-label="Random seed"
                  value={value.simulation.seed}
                  onChange={(e) => {
                    update((d) => {
                      d.simulation.seed = Math.max(
                        0,
                        Math.round(Number(e.target.value)),
                      );
                    });
                  }}
                />
                <button
                  type="button"
                  className="pb-btn pb-secondary"
                  onClick={() => {
                    update((d) => {
                      d.simulation.seed = Math.floor(Math.random() * 1_000_000);
                    });
                  }}
                >
                  New seed
                </button>
              </div>
            </div>
            <div className="sb-field">
              <label className="sb-field-label" htmlFor={`${ids}-arrivals`}>
                Arrival pattern
              </label>
              <select
                id={`${ids}-arrivals`}
                value={value.simulation.arrivalPattern}
                onChange={(e) => {
                  update((d) => {
                    d.simulation.arrivalPattern = e.target.value as
                      "poisson" | "uniform";
                  });
                }}
              >
                <option value="poisson">Random (Poisson)</option>
                <option value="uniform">Evenly spaced</option>
              </select>
            </div>
          </div>
          <p className="q-help">
            The seed fixes the arrival sequence: every control in a comparison
            gets exactly the same vehicles at the same moments, and the same
            seed reproduces the run.
          </p>
        </section>

        {/* 6 · Advanced ─────────────────────────────────────────────── */}
        <section className="sb-section" id={`${ids}-advanced`}>
          <details
            className="sb-advanced"
            onToggle={(e) => {
              setAdvancedOpen(e.currentTarget.open);
            }}
          >
            <summary>
              <span className="q-number">6</span> Advanced — junction geometry,
              signal timing, adaptive settings, roundabout design, metered-entry
              timing, roads
            </summary>
            {/* Rendered only while open: the guided steps stay quick. */}
            {advancedOpen && (
              <>
                <GeometrySettings value={value} update={update} />
                <AdvancedSettings value={value} update={update} />
              </>
            )}
          </details>
        </section>
      </div>

      {/* Live panel ───────────────────────────────────────────────────── */}
      <aside className="sb-side" aria-label="Scenario preview and status">
        <div className="sb-card">
          <label className="sb-field-label" htmlFor={`${ids}-name`}>
            Scenario name
          </label>
          <input
            id={`${ids}-name`}
            className="sb-name"
            value={value.name}
            maxLength={120}
            onChange={(e) => {
              update((d) => {
                d.name = e.target.value;
              });
            }}
          />
          <div className="sb-inline">
            <label className="sr-only" htmlFor={`${ids}-preset`}>
              Start from a preset
            </label>
            <select
              id={`${ids}-preset`}
              value=""
              onChange={(e) => {
                if (e.target.value) loadPreset(e.target.value);
              }}
            >
              <option value="">Start from a preset…</option>
              {SCENARIO_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            {fromPreset && !unchangedPreset && (
              <button
                type="button"
                className="pb-btn pb-secondary"
                onClick={() => {
                  loadPreset(fromPreset.id);
                }}
              >
                Reset to “{fromPreset.label}”
              </button>
            )}
          </div>
          <p className="sb-preset-note">
            {fromPreset
              ? unchangedPreset
                ? `Preset: ${fromPreset.label}`
                : `Custom — started from “${fromPreset.label}”`
              : "Custom scenario"}
          </p>
        </div>

        <div className="sb-card sb-preview-card">
          <div className="sb-preview-head">
            <span className="sb-field-label">Plan</span>
            <div className="seg" role="group" aria-label="Preview as">
              {(["signal", "roundabout"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  className={previewView === v ? "is-active" : ""}
                  aria-pressed={previewView === v}
                  onClick={() => {
                    setPreviewView(v);
                  }}
                >
                  {v === "signal" ? "Signal" : "Roundabout"}
                </button>
              ))}
            </div>
          </div>
          <JunctionPreview
            scenario={value}
            view={previewView}
            selected={selected}
            onSelect={setSelected}
            design={previewView === "roundabout" ? design : signalDesign}
          />
          <p className="sb-summary">{describeScenario(value)}</p>
          {previewView === "roundabout" && (
            <p className="q-help">
              {ringLanes(value) === 1
                ? "One circulating lane."
                : "Two circulating lanes: left turns use the inner lane, right turns the outer lane, straight on either. Drivers leaving from the inner lane take turns with outer-lane traffic at each exit. Arrows show the roundabout’s own lane markings."}
            </p>
          )}
        </div>

        <StrategySummaryCard
          scenario={value}
          strategies={strategies}
          serverErrors={serverErrors}
        />

        <div
          className={`sb-card sb-status ${ready ? "is-ready" : serverErrors.length || issues.length ? "is-blocked" : ""}`}
          role="status"
          aria-live="polite"
        >
          <p className="sb-status-title">
            {validation.status === "checking"
              ? "Checking the scenario…"
              : validation.status === "unreachable"
                ? "Cannot reach the simulator to check this scenario."
                : ready
                  ? `Ready to simulate as ${strategies.map((s) => strategyTitle(s, value)).join(", ")}.`
                  : "This configuration cannot currently be simulated:"}
          </p>
          {serverErrors.length > 0 && (
            <ul className="sb-errors">
              {serverErrors.map((e) => (
                <li key={e}>
                  {e}
                  {e.includes("(metering.missing_arm)") &&
                    " Under “How do vehicles enter the roundabout?” in step 1, choose “Rebuild phases for the current roads”."}
                  {e.includes("(compat.adaptive_unsupported_policy)") &&
                    " Adaptive control requires a signalised junction; change the junction type in step 1 or switch to fixed-time control."}
                  {e.includes("(compat.signal_requires_signal_geometry)") &&
                    " Change junction type to a signalised junction in step 1."}
                  {e.includes(
                    "(compat.roundabout_yield_requires_roundabout)",
                  ) && " Change junction type to Roundabout in step 1."}
                </li>
              ))}
            </ul>
          )}
          {validation.status !== "done" && issues.length > 0 && (
            <ul className="sb-errors">
              {issues.map((i) => (
                <li key={`${i.where}-${i.message}`}>
                  {APPROACHES.includes(i.where as ApproachName)
                    ? `${cap(i.where)}: `
                    : ""}
                  {i.message}
                </li>
              ))}
            </ul>
          )}
          {serverWarnings.length > 0 && (
            <ul className="sb-warnings">
              {serverWarnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="sb-card sb-actions">
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => {
              const safe =
                value.name.replace(/[^A-Za-z0-9_-]+/g, "_").slice(0, 60) ||
                "scenario";
              downloadText(
                `${safe}.urbanflow.json`,
                exportScenarioJson(value),
                "application/json",
              );
            }}
          >
            Export scenario
          </button>
          <button
            type="button"
            className="pb-btn pb-secondary"
            onClick={() => fileRef.current?.click()}
          >
            Import scenario…
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="sr-only"
            aria-label="Import a scenario file"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importFile(file);
              e.target.value = "";
            }}
          />
          {importError && (
            <p className="q-note is-caution" role="alert">
              {importError}
            </p>
          )}
        </div>
      </aside>
    </div>
  );
}
