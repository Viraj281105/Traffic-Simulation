import { useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  APPROACHES,
  MAX_SLOT_DEVIATION,
  MOVEMENTS,
  OPPOSITE,
  SLOT_BEARING,
  STRATEGY_TITLE,
  type ApproachName,
  type ApproachSpec,
  type JunctionType,
  type Movement,
  type ScenarioDocument,
  type Strategy,
} from "../../scenario/scenarioTypes";
import {
  SCENARIO_PRESETS,
  cloneScenario,
  defaultLaneUse,
  describeScenario,
  exportScenarioJson,
  localIssues,
  matchesPreset,
  parseScenarioJson,
  presetById,
  presentApproaches,
  possibleMovements,
  ringLanes,
  signalLaneUse,
  sortMovements,
  totalVph,
  turningShare,
  turningTotal,
  withLaneCount,
  type LocalIssue,
} from "../../scenario/scenarioModel";
import { downloadText } from "../../metrics/catalog";
import { JunctionPreview } from "./JunctionPreview";
import { MixEditor } from "./MixEditor";
import type { ValidationState } from "./useScenarioValidation";
import "./ScenarioBuilder.css";

const JUNCTIONS: { id: JunctionType; title: string; body: string }[] = [
  {
    id: "fixed_time_signal",
    title: "Fixed-time signal",
    body: "Greens follow a timetable, whether or not anyone is waiting.",
  },
  {
    id: "adaptive_signal",
    title: "Adaptive signal",
    body: "Detectors at the stop lines end each green when traffic runs dry.",
  },
  {
    id: "roundabout",
    title: "Roundabout",
    body: "No signal: drivers give way to circulating traffic and enter at gaps.",
  },
];

/** "How busy is this road?" — vehicles per hour per lane. */
const BUSY_LEVELS: { id: string; label: string; perLane: number }[] = [
  { id: "quiet", label: "Quiet", perLane: 120 },
  { id: "moderate", label: "Moderate", perLane: 250 },
  { id: "busy", label: "Busy", perLane: 400 },
  { id: "very-busy", label: "Very busy", perLane: 550 },
];

const DURATIONS = [
  { seconds: 120, label: "2 min" },
  { seconds: 300, label: "5 min" },
  { seconds: 600, label: "10 min" },
];

const GLYPH: Record<Movement, string> = {
  uturn: "↶",
  left: "↰",
  straight: "↑",
  right: "↱",
};
const MOVE_LABEL: Record<Movement, string> = {
  uturn: "U-turn",
  left: "Left",
  straight: "Straight",
  right: "Right",
};

type Step =
  "junction" | "roads" | "traffic" | "vehicles" | "simulation" | "advanced";
const STEPS: { id: Step; title: string }[] = [
  { id: "junction", title: "Junction" },
  { id: "roads", title: "Roads & lanes" },
  { id: "traffic", title: "Traffic" },
  { id: "vehicles", title: "Vehicles" },
  { id: "simulation", title: "Simulation" },
  { id: "advanced", title: "Advanced" },
];

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

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
              signal timing, adaptive settings, roundabout design, roads
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
                  ? `Ready to simulate as ${strategies.map((s) => STRATEGY_TITLE[s]).join(", ")}.`
                  : "This configuration cannot currently be simulated:"}
          </p>
          {serverErrors.length > 0 && (
            <ul className="sb-errors">
              {serverErrors.map((e) => (
                <li key={e}>{e}</li>
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

// ── Pieces ──────────────────────────────────────────────────────────────

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step,
  unit,
  placeholder,
}: {
  label: string;
  value: number | null | undefined;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="sb-field">
      <label className="sb-field-label" htmlFor={id}>
        {label}
      </label>
      <div className="sb-inline">
        <input
          id={id}
          type="number"
          value={value ?? ""}
          placeholder={placeholder}
          min={min}
          max={max}
          step={step}
          onChange={(e) => {
            if (e.target.value !== "") onChange(Number(e.target.value));
          }}
        />
        {unit && <span className="sb-unit">{unit}</span>}
      </div>
    </div>
  );
}

function Stepper({
  value,
  min,
  max,
  onChange,
  label,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  label: string;
}) {
  return (
    <div className="stepper" role="group" aria-label={label}>
      <button
        type="button"
        aria-label={`Fewer ${label.toLowerCase()}`}
        disabled={value <= min}
        onClick={() => {
          onChange(value - 1);
        }}
      >
        −
      </button>
      <span aria-live="polite">{value}</span>
      <button
        type="button"
        aria-label={`More ${label.toLowerCase()}`}
        disabled={value >= max}
        onClick={() => {
          onChange(value + 1);
        }}
      >
        +
      </button>
    </div>
  );
}

function LaneArrowEditor({
  lanes,
  use,
  onChange,
  caption,
}: {
  lanes: number;
  use: Movement[][];
  onChange: (use: Movement[][]) => void;
  caption: string;
}) {
  return (
    <div className="lane-editor" role="group" aria-label={caption}>
      {Array.from({ length: lanes }, (_, i) => {
        const turns = use[i] ?? [];
        return (
          <div key={i} className="lane-card">
            <span className="lane-card-n">Lane {i + 1}</span>
            <span className="lane-card-glyphs" aria-hidden="true">
              {turns.length ? turns.map((t) => GLYPH[t]).join("") : "∅"}
            </span>
            <div className="lane-card-toggles">
              {MOVEMENTS.map((m) => {
                const on = turns.includes(m);
                return (
                  <button
                    key={m}
                    type="button"
                    className={`lane-toggle${on ? " is-on" : ""}`}
                    aria-pressed={on}
                    aria-label={`Lane ${String(i + 1)}: ${MOVE_LABEL[m]}`}
                    title={MOVE_LABEL[m]}
                    onClick={() => {
                      const next = use.map((l) => [...l]);
                      next[i] = sortMovements(
                        on ? turns.filter((t) => t !== m) : [...turns, m],
                      );
                      onChange(next);
                    }}
                  >
                    {GLYPH[m]}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ApproachLanesCard({
  approach,
  arm,
  hasOpposite,
  selected,
  onSelect,
  onChange,
  onCopyOpposite,
  roundaboutUse,
  issues,
}: {
  approach: ApproachName;
  arm: ApproachSpec;
  hasOpposite: boolean;
  selected: boolean;
  onSelect: () => void;
  onChange: (change: Partial<ApproachSpec>) => void;
  onCopyOpposite: () => void;
  roundaboutUse?: Movement[][];
  issues: LocalIssue[];
}) {
  const [editRoundabout, setEditRoundabout] = useState(!!arm.roundaboutLaneUse);
  const signalUse = signalLaneUse(arm);
  return (
    <div
      className={`approach-card${selected ? " is-selected" : ""}${issues.length ? " has-issues" : ""}`}
      onFocusCapture={onSelect}
      onClick={onSelect}
    >
      <div className="approach-card-head">
        <h4>{cap(approach)}</h4>
        <Stepper
          label="Lanes"
          value={arm.lanes}
          min={1}
          max={4}
          onChange={(lanes) => {
            onChange(withLaneCount(arm, lanes));
          }}
        />
      </div>
      <div className="sb-inline sb-small">
        <label>
          Length{" "}
          <input
            type="number"
            min={60}
            max={1000}
            step={10}
            value={arm.length}
            aria-label={`${approach} approach length (m)`}
            onChange={(e) => {
              if (e.target.value !== "")
                onChange({ length: Number(e.target.value) });
            }}
          />{" "}
          m
        </label>
        {hasOpposite && (
          <button type="button" className="link-btn" onClick={onCopyOpposite}>
            Same as {OPPOSITE[approach]}
          </button>
        )}
      </div>
      <div className="sb-subhead">
        <span>Signal lane arrows</span>
        {arm.laneUse ? (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              onChange({ laneUse: null });
            }}
          >
            Use default arrows
          </button>
        ) : (
          <span className="sb-muted">default</span>
        )}
      </div>
      <LaneArrowEditor
        lanes={arm.lanes}
        use={signalUse}
        caption={`${approach} signal lane arrows`}
        onChange={(use) => {
          onChange({ laneUse: use });
        }}
      />
      <div className="sb-subhead">
        <span>Roundabout lane markings</span>
        <button
          type="button"
          className="link-btn"
          onClick={() => {
            if (editRoundabout) onChange({ roundaboutLaneUse: null });
            else
              onChange({
                roundaboutLaneUse:
                  roundaboutUse && roundaboutUse.length === arm.lanes
                    ? roundaboutUse.map((l) => [...l])
                    : defaultLaneUse(arm.lanes),
              });
            setEditRoundabout(!editRoundabout);
          }}
        >
          {editRoundabout ? "Make automatic" : "Edit"}
        </button>
      </div>
      {editRoundabout && arm.roundaboutLaneUse ? (
        <LaneArrowEditor
          lanes={arm.lanes}
          use={arm.roundaboutLaneUse}
          caption={`${approach} roundabout lane markings`}
          onChange={(use) => {
            onChange({ roundaboutLaneUse: use });
          }}
        />
      ) : (
        <p className="sb-muted sb-small">
          Automatic
          {roundaboutUse
            ? `: ${roundaboutUse.map((l, i) => `lane ${String(i + 1)} ${l.map((t) => GLYPH[t]).join("")}`).join(", ")}`
            : ""}
        </p>
      )}
      {issues.map((i) => (
        <p key={i.message} className="q-note is-caution sb-small">
          {i.message}
        </p>
      ))}
    </div>
  );
}

function ApproachTrafficCard({
  approach,
  arm,
  possible,
  selected,
  onSelect,
  onChange,
  issues,
}: {
  approach: ApproachName;
  arm: ApproachSpec;
  /** Movements that lead to a road that exists (V1.5). */
  possible: Movement[];
  selected: boolean;
  onSelect: () => void;
  onChange: (change: Partial<ApproachSpec>) => void;
  issues: LocalIssue[];
}) {
  const level = BUSY_LEVELS.find(
    (l) => Math.abs(l.perLane * arm.lanes - arm.vehiclesPerHour) < 1,
  );
  const turning = turningTotal(arm.turning);
  return (
    <div
      className={`approach-card${selected ? " is-selected" : ""}${issues.length ? " has-issues" : ""}`}
      onFocusCapture={onSelect}
      onClick={onSelect}
    >
      <div className="approach-card-head">
        <h4>{cap(approach)}</h4>
        <span className="sb-muted sb-small">
          {arm.lanes} lane{arm.lanes === 1 ? "" : "s"}
        </span>
      </div>
      <div className="chip-row">
        {BUSY_LEVELS.map((l) => (
          <button
            key={l.id}
            type="button"
            className={`chip${level?.id === l.id ? " is-active" : ""}`}
            aria-pressed={level?.id === l.id}
            onClick={() => {
              onChange({ vehiclesPerHour: l.perLane * arm.lanes });
            }}
          >
            {l.label}
          </button>
        ))}
      </div>
      <div className="sb-inline sb-small">
        <label>
          <input
            type="number"
            min={0}
            max={7200}
            step={10}
            value={Math.round(arm.vehiclesPerHour)}
            aria-label={`${approach} vehicles per hour`}
            onChange={(e) => {
              if (e.target.value !== "")
                onChange({
                  vehiclesPerHour: Math.max(0, Number(e.target.value)),
                });
            }}
          />{" "}
          vehicles / hour
        </label>
        <span className="sb-muted">
          ≈ {Math.round(arm.vehiclesPerHour / arm.lanes)} per lane
        </span>
      </div>
      <div className="sb-subhead">
        <span>Where do drivers go?</span>
        <span className={Math.abs(turning - 1) <= 0.01 ? "sb-ok" : "sb-bad"}>
          {Math.round(turning * 100)}%
        </span>
      </div>
      <div className="turning-row">
        {MOVEMENTS.filter(
          // A U-turn share is offered once a lane allows U-turns (or the
          // road already has one), so the guided view stays simple.
          (m) =>
            (m !== "uturn" ||
              turningShare(arm.turning, m) > 0 ||
              signalLaneUse(arm).some((l) => l.includes("uturn")) ||
              (arm.roundaboutLaneUse ?? []).some((l) => l.includes("uturn"))) &&
            (possible.includes(m) || turningShare(arm.turning, m) > 0),
        ).map((m) => (
          <label key={m} className="turning-field">
            <span>
              {GLYPH[m]} {MOVE_LABEL[m]}
            </span>
            <input
              type="number"
              min={0}
              max={100}
              step={5}
              value={Math.round(turningShare(arm.turning, m) * 1000) / 10}
              aria-label={`${approach}: share turning ${m} (%)`}
              onChange={(e) => {
                if (e.target.value === "") return;
                onChange({
                  turning: {
                    ...arm.turning,
                    [m]:
                      Math.max(0, Math.min(100, Number(e.target.value))) / 100,
                  },
                });
              }}
            />
          </label>
        ))}
      </div>
      <details className="sb-own-mix" open={!!arm.vehicleMix}>
        <summary>Own vehicle mix for this road</summary>
        {arm.vehicleMix ? (
          <>
            <MixEditor
              value={arm.vehicleMix}
              allowCarsOnlyNull={false}
              label={`${cap(approach)} mix`}
              onChange={(mix) => {
                onChange({ vehicleMix: mix });
              }}
            />
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                onChange({ vehicleMix: null });
              }}
            >
              Use the junction’s mix
            </button>
          </>
        ) : (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              onChange({
                vehicleMix: {
                  car: 0.7,
                  suv: 0.1,
                  bus: 0.1,
                  truck: 0.05,
                  motorcycle: 0.05,
                },
              });
            }}
          >
            Give this road its own mix
          </button>
        )}
      </details>
      {issues.map((i) => (
        <p key={i.message} className="q-note is-caution sb-small">
          {i.message}
        </p>
      ))}
    </div>
  );
}

function GeometrySettings({
  value,
  update,
}: {
  value: ScenarioDocument;
  update: (mutate: (d: ScenarioDocument) => void) => void;
}) {
  return (
    <fieldset className="sb-geometry">
      <legend>Junction geometry (real-world layout)</legend>
      <p className="q-help">
        The compass bearing each road leaves the junction on, and its own lane
        width. Each road may lie up to {MAX_SLOT_DEVIATION}° from its compass
        direction, so left, straight and right keep their meaning; a layout that
        cannot be represented is rejected with the reason, never bent to fit.
      </p>
      <div className="sb-geometry-rows">
        {presentApproaches(value).map((a) => {
          const arm = value.approaches[a] as ApproachSpec;
          return (
            <div key={a} className="sb-geometry-row">
              <span className="sb-field-label">{cap(a)}</span>
              <NumberField
                label="Bearing"
                unit="°"
                value={arm.bearing ?? SLOT_BEARING[a]}
                min={0}
                max={359.9}
                step={1}
                onChange={(v) => {
                  update((d) => {
                    const own = d.approaches[a];
                    if (own) own.bearing = ((v % 360) + 360) % 360;
                  });
                }}
              />
              <NumberField
                label="Lane width"
                unit="m"
                value={arm.laneWidth ?? value.roads.laneWidth}
                min={2.6}
                max={5}
                step={0.1}
                onChange={(v) => {
                  update((d) => {
                    const own = d.approaches[a];
                    if (own) own.laneWidth = v;
                  });
                }}
              />
              {(arm.bearing != null || arm.laneWidth != null) && (
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    update((d) => {
                      const own = d.approaches[a];
                      if (own) {
                        own.bearing = null;
                        own.laneWidth = null;
                      }
                    });
                  }}
                >
                  Compass axis, junction lane width
                </button>
              )}
            </div>
          );
        })}
      </div>
    </fieldset>
  );
}

function AdvancedSettings({
  value,
  update,
}: {
  value: ScenarioDocument;
  update: (mutate: (d: ScenarioDocument) => void) => void;
}) {
  const sig = value.signal;
  const rb = value.roundabout;
  return (
    <div className="sb-advanced-grid">
      <fieldset>
        <legend>Signal timing (both signals)</legend>
        <NumberField
          label="Green (both roads)"
          unit="s"
          value={sig.greenTime}
          min={6}
          max={120}
          onChange={(v) => {
            update((d) => {
              d.signal.greenTime = v;
            });
          }}
        />
        <NumberField
          label="North–south green"
          unit="s"
          placeholder="same"
          value={sig.nsGreenTime}
          min={6}
          max={120}
          onChange={(v) => {
            update((d) => {
              d.signal.nsGreenTime = v;
            });
          }}
        />
        <NumberField
          label="East–west green"
          unit="s"
          placeholder="same"
          value={sig.ewGreenTime}
          min={6}
          max={120}
          onChange={(v) => {
            update((d) => {
              d.signal.ewGreenTime = v;
            });
          }}
        />
        <NumberField
          label="Yellow"
          unit="s"
          value={sig.yellowTime}
          min={2.5}
          max={8}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.signal.yellowTime = v;
            });
          }}
        />
        <NumberField
          label="All-red"
          unit="s"
          value={sig.allRedTime}
          min={0}
          max={5}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.signal.allRedTime = v;
            });
          }}
        />
        {(sig.nsGreenTime != null || sig.ewGreenTime != null) && (
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              update((d) => {
                d.signal.nsGreenTime = null;
                d.signal.ewGreenTime = null;
              });
            }}
          >
            Same green for both roads
          </button>
        )}
      </fieldset>
      <fieldset>
        <legend>Adaptive signal</legend>
        <NumberField
          label="Minimum green"
          unit="s"
          value={sig.adaptive.minGreen}
          min={5}
          max={60}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.minGreen = v;
            });
          }}
        />
        <NumberField
          label="Maximum green"
          unit="s"
          value={sig.adaptive.maxGreen}
          min={10}
          max={180}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.maxGreen = v;
            });
          }}
        />
        <NumberField
          label="Passage time"
          unit="s"
          value={sig.adaptive.extensionStep}
          min={0.5}
          max={10}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.extensionStep = v;
            });
          }}
        />
        <NumberField
          label="Detection zone"
          unit="m"
          value={sig.adaptive.detectionDistance}
          min={5}
          max={200}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.detectionDistance = v;
            });
          }}
        />
        <NumberField
          label="Vehicles to call"
          value={sig.adaptive.demandThreshold}
          min={1}
          max={20}
          onChange={(v) => {
            update((d) => {
              d.signal.adaptive.demandThreshold = Math.round(v);
            });
          }}
        />
      </fieldset>
      <fieldset>
        <legend>Roundabout design</legend>
        <div className="sb-field">
          <span className="sb-field-label">Circulating lanes</span>
          <div className="chip-row">
            {([null, 1, 2] as const).map((n) => (
              <button
                key={String(n)}
                type="button"
                className={`chip${(rb.circulatingLanes ?? null) === n ? " is-active" : ""}`}
                aria-pressed={(rb.circulatingLanes ?? null) === n}
                onClick={() => {
                  update((d) => {
                    d.roundabout.circulatingLanes = n;
                  });
                }}
              >
                {n === null ? "Automatic" : String(n)}
              </button>
            ))}
          </div>
        </div>
        <NumberField
          label="Island radius"
          unit="m"
          value={rb.innerRadius}
          min={6}
          max={50}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.innerRadius = v;
            });
          }}
        />
        <NumberField
          label="Outer radius"
          unit="m"
          value={rb.outerRadius}
          min={8}
          max={80}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.outerRadius = v;
            });
          }}
        />
        <NumberField
          label="Critical gap"
          unit="s"
          value={rb.criticalGap}
          min={1}
          max={10}
          step={0.1}
          onChange={(v) => {
            update((d) => {
              d.roundabout.criticalGap = v;
            });
          }}
        />
        <NumberField
          label="Follow-up time"
          unit="s"
          value={rb.followUpTime}
          min={0.5}
          max={10}
          step={0.1}
          onChange={(v) => {
            update((d) => {
              d.roundabout.followUpTime = v;
            });
          }}
        />
        <NumberField
          label="Entry speed"
          unit="m/s"
          value={rb.entrySpeed}
          min={1}
          max={15}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.entrySpeed = v;
            });
          }}
        />
        <NumberField
          label="Circulating speed"
          unit="m/s"
          value={rb.circulatingSpeed}
          min={2}
          max={15}
          step={0.5}
          onChange={(v) => {
            update((d) => {
              d.roundabout.circulatingSpeed = v;
            });
          }}
        />
      </fieldset>
      <fieldset>
        <legend>Roads</legend>
        <NumberField
          label="Lane width"
          unit="m"
          value={value.roads.laneWidth}
          min={2.6}
          max={5}
          step={0.1}
          onChange={(v) => {
            update((d) => {
              d.roads.laneWidth = v;
            });
          }}
        />
        <NumberField
          label="Speed limit"
          unit="km/h"
          value={Math.round(value.roads.speedLimit * 3.6)}
          min={10}
          max={108}
          step={5}
          onChange={(v) => {
            update((d) => {
              d.roads.speedLimit = Math.round((v / 3.6) * 100) / 100;
            });
          }}
        />
        <label className="sb-check">
          <input
            type="checkbox"
            checked={value.roads.laneChanging}
            onChange={(e) => {
              update((d) => {
                d.roads.laneChanging = e.target.checked;
              });
            }}
          />
          Drivers change lanes on multi-lane approaches
        </label>
      </fieldset>
    </div>
  );
}
