/**
 * Helpers for building, checking, describing and exchanging scenario
 * documents. The backend (POST /api/v1/scenarios/validate) is the authority
 * on what can be simulated; the checks here only make the builder respond
 * instantly — they never adjust what the user entered.
 */
import presetsFile from "./presets.json";
import {
  APPROACHES,
  CORE_MOVEMENTS,
  JUNCTION_STRATEGY,
  MAX_SLOT_DEVIATION,
  MOVEMENTS,
  OPPOSITE,
  SLOT_BEARING,
  SCENARIO_FORMAT,
  SCENARIO_VERSION,
  type ApproachName,
  type ApproachSpec,
  type Movement,
  type ScenarioDocument,
  type Strategy,
  type Turning,
} from "./scenarioTypes";
import {
  VEHICLE_CLASSES,
  describeMix,
  type VehicleMix,
} from "../vehicles/vehicleClasses";
import type { SimulationConfigValues } from "../types/config";

export interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  scenario: ScenarioDocument;
}

export const SCENARIO_PRESETS: ScenarioPreset[] = (
  presetsFile as unknown as { presets: ScenarioPreset[] }
).presets;

export function presetById(id: string): ScenarioPreset | undefined {
  return SCENARIO_PRESETS.find((p) => p.id === id);
}

export function cloneScenario(doc: ScenarioDocument): ScenarioDocument {
  return JSON.parse(JSON.stringify(doc)) as ScenarioDocument;
}

/** A fresh copy of a preset's scenario, ready to edit. */
export function scenarioFromPreset(id: string): ScenarioDocument {
  const preset = presetById(id) ?? SCENARIO_PRESETS[0];
  return cloneScenario(preset.scenario);
}

export const DEFAULT_SCENARIO: ScenarioDocument =
  scenarioFromPreset("typical-urban");

/** True when the document still equals the preset it names. */
export function matchesPreset(doc: ScenarioDocument): boolean {
  const preset = doc.preset ? presetById(doc.preset) : undefined;
  return !!preset && sameScenario(preset.scenario, doc);
}

/** Compares what is simulated (not the name or description). */
export function sameScenario(
  a: ScenarioDocument,
  b: ScenarioDocument,
): boolean {
  const strip = (d: ScenarioDocument) =>
    JSON.stringify({ ...d, name: "", description: "", preset: null });
  return strip(a) === strip(b);
}

// ── Lane use ─────────────────────────────────────────────────────────────

// ── Arms (V1.5) ───────────────────────────────────────────────────────────

/** The slots that have an arm, in display order. */
export function presentApproaches(doc: ScenarioDocument): ApproachName[] {
  return APPROACHES.filter((a) => doc.approaches[a] != null);
}

/** The arms that exist, with their specs. */
export function presentArms(
  doc: ScenarioDocument,
): [ApproachName, ApproachSpec][] {
  return APPROACHES.flatMap((a) => {
    const arm = doc.approaches[a];
    return arm ? [[a, arm] as [ApproachName, ApproachSpec]] : [];
  });
}

/** An arm the caller knows exists (throws for a slot with no road). */
export function armOf(doc: ScenarioDocument, a: ApproachName): ApproachSpec {
  const arm = doc.approaches[a];
  if (!arm) throw new Error(`The scenario has no ${a} arm`);
  return arm;
}

/** The arm's compass bearing: its own, else its slot's. */
export function armBearing(a: ApproachName, arm: ApproachSpec): number {
  return arm.bearing ?? SLOT_BEARING[a];
}

/** Signed difference (degrees) of an arm from its slot, in (-180, 180]. */
export function slotDeviation(a: ApproachName, bearing: number): number {
  const d = (((bearing - SLOT_BEARING[a]) % 360) + 360) % 360;
  return d > 180 ? d - 360 : d;
}

/** The arm's lane width: its own, else the junction's. */
export function armLaneWidth(doc: ScenarioDocument, arm: ApproachSpec): number {
  return arm.laneWidth ?? doc.roads.laneWidth;
}

/** The slot a movement from ``a`` leaves by (right-hand traffic). */
export function movementTarget(a: ApproachName, m: Movement): ApproachName {
  const i = APPROACHES.indexOf(a); // clockwise: north, east, south, west
  const step = { uturn: 0, left: 1, straight: 2, right: 3 }[m];
  return APPROACHES[(i + step) % 4];
}

/** Movements possible from ``a`` given which arms exist. */
export function possibleMovements(
  doc: ScenarioDocument,
  a: ApproachName,
): Movement[] {
  return MOVEMENTS.filter((m) => doc.approaches[movementTarget(a, m)] != null);
}

/** The default lane-use policy (backend roads/lane_config.default_policy_turns). */
export function defaultLaneUse(lanes: number): Movement[][] {
  if (lanes <= 1) return [[...CORE_MOVEMENTS]];
  return Array.from({ length: lanes }, (_, i) => {
    const turns: Movement[] = [];
    if (i === 0) turns.push("left");
    turns.push("straight");
    if (i === lanes - 1) turns.push("right");
    return turns;
  });
}

/** Signal lane arrows of an approach: configured, else the default policy
 *  — without movements outside ``possible`` (V1.5: towards a slot with no
 *  road), exactly as backend lane_config.default_signal_lane_use. A lane
 *  left empty is shown empty, and flagged, never filled with a guess. */
export function signalLaneUse(
  arm: ApproachSpec,
  possible?: Movement[],
): Movement[][] {
  if (arm.laneUse && arm.laneUse.length === arm.lanes) return arm.laneUse;
  const use = defaultLaneUse(arm.lanes);
  return possible
    ? use.map((lane) => lane.filter((m) => possible.includes(m)))
    : use;
}

const ORDER: Record<Movement, number> = {
  uturn: -1,
  left: 0,
  straight: 1,
  right: 2,
};

export function sortMovements(turns: Movement[]): Movement[] {
  return [...new Set(turns)].sort((a, b) => ORDER[a] - ORDER[b]);
}

/** Changing the lane count keeps arrows that still fit and fills the rest
 *  with the default policy; the lane use itself is never "repaired". */
export function withLaneCount(arm: ApproachSpec, lanes: number): ApproachSpec {
  const next: ApproachSpec = { ...arm, lanes };
  if (arm.laneUse)
    next.laneUse = arm.laneUse.length === lanes ? arm.laneUse : null;
  if (arm.roundaboutLaneUse)
    next.roundaboutLaneUse =
      arm.roundaboutLaneUse.length === lanes ? arm.roundaboutLaneUse : null;
  return next;
}

// ── Local checks (instant feedback; the backend has the final word) ───────

export interface LocalIssue {
  /** Where to show it: an approach, "vehicles", "simulation" or "junction". */
  where: ApproachName | "vehicles" | "simulation" | "junction";
  message: string;
}

export function mixTotal(mix: VehicleMix | null | undefined): number {
  if (!mix) return 1;
  return VEHICLE_CLASSES.reduce((sum, c) => sum + (mix[c.id] || 0), 0);
}

export function turningTotal(t: Turning): number {
  return t.left + t.straight + t.right + (t.uturn ?? 0);
}

/** A movement's share of an approach's traffic (an unset U-turn is 0). */
export function turningShare(t: Turning, m: Movement): number {
  return m === "uturn" ? (t.uturn ?? 0) : t[m];
}

const TOLERANCE = 0.01;

export function localIssues(
  doc: ScenarioDocument,
  strategies: Strategy[],
): LocalIssue[] {
  const issues: LocalIssue[] = [];
  const total = totalVph(doc);
  if (!(total > 0)) {
    issues.push({
      where: "junction",
      message:
        "Every road has 0 vehicles per hour — give at least one some traffic.",
    });
  }
  if (Math.abs(mixTotal(doc.vehicles.mix) - 1) > TOLERANCE) {
    issues.push({
      where: "vehicles",
      message: `The vehicle mix adds up to ${pct(mixTotal(doc.vehicles.mix))}; it must total 100%.`,
    });
  }
  if (doc.simulation.warmup >= doc.simulation.duration) {
    issues.push({
      where: "simulation",
      message:
        "The warm-up must be shorter than the run, or nothing is measured.",
    });
  }
  const signal = strategies.some((s) => s !== "roundabout");
  const arms = presentArms(doc);
  if (arms.length < 3) {
    issues.push({
      where: "junction",
      message: `A junction needs 3 or 4 arms; this one has ${String(arms.length)}. Two arms are a bend in one road, not a junction.`,
    });
  }
  for (const [name, arm] of arms) {
    if (arm.bearing != null) {
      const dev = slotDeviation(name, arm.bearing);
      if (Math.abs(dev) > MAX_SLOT_DEVIATION) {
        issues.push({
          where: name,
          message: `Bearing ${String(arm.bearing)}° is ${String(Math.round(Math.abs(dev)))}° from the ${name} slot (${String(SLOT_BEARING[name])}°); an arm may lie at most ${String(MAX_SLOT_DEVIATION)}° from its slot.`,
        });
      }
    }
    for (const m of MOVEMENTS) {
      if (
        turningShare(arm.turning, m) > 0 &&
        doc.approaches[movementTarget(name, m)] == null
      ) {
        issues.push({
          where: name,
          message: `${pct(turningShare(arm.turning, m))} of this road's traffic turns ${m}, into the ${movementTarget(name, m)} slot, which has no road; set it to 0.`,
        });
      }
    }
    const turning = turningTotal(arm.turning);
    if (Math.abs(turning - 1) > TOLERANCE) {
      issues.push({
        where: name,
        message: `Turning shares add up to ${pct(turning)}; they must total 100%.`,
      });
    }
    if (arm.vehicleMix && Math.abs(mixTotal(arm.vehicleMix) - 1) > TOLERANCE) {
      issues.push({
        where: name,
        message: `This road's own vehicle mix adds up to ${pct(mixTotal(arm.vehicleMix))}; it must total 100%.`,
      });
    }
    if (!signal) continue;
    const opposite = doc.approaches[OPPOSITE[name]];
    if (
      opposite &&
      arm.lanes !== opposite.lanes &&
      (name === "north" || name === "east")
    ) {
      issues.push({
        where: name,
        message: `A signal needs the same number of lanes on ${name} and ${OPPOSITE[name]} (through traffic cannot merge inside the junction); they have ${String(arm.lanes)} and ${String(opposite.lanes)}.`,
      });
    }
    const use = signalLaneUse(arm, possibleMovements(doc, name));
    use.forEach((lane, i) => {
      if (lane.length === 0)
        issues.push({
          where: name,
          message: `Lane ${String(i + 1)} allows no movement.`,
        });
    });
    for (let i = 0; i < use.length - 1; i += 1) {
      const left = use[i];
      const right = use[i + 1];
      if (!left.length || !right.length) continue;
      if (
        Math.max(...left.map((t) => ORDER[t])) >
        Math.min(...right.map((t) => ORDER[t]))
      ) {
        issues.push({
          where: name,
          message: `Lanes ${String(i + 1)} and ${String(i + 2)} cross: arrange arrows U-turn → left → straight → right from the centre line.`,
        });
      }
    }
    for (const turn of MOVEMENTS) {
      if (
        turningShare(arm.turning, turn) > 0 &&
        !use.some((lane) => lane.includes(turn))
      ) {
        issues.push({
          where: name,
          message: `${pct(turningShare(arm.turning, turn))} of this road's traffic turns ${turn}, but no lane allows it.`,
        });
      }
    }
  }
  return issues;
}

function pct(share: number): string {
  return `${String(Math.round(share * 1000) / 10)}%`;
}

// ── Description ───────────────────────────────────────────────────────────

export function totalVph(doc: ScenarioDocument): number {
  return presentArms(doc).reduce(
    (sum, [, arm]) => sum + arm.vehiclesPerHour,
    0,
  );
}

export function widestApproach(doc: ScenarioDocument): number {
  return Math.max(1, ...presentArms(doc).map(([, arm]) => arm.lanes));
}

export function ringLanes(doc: ScenarioDocument): number {
  return doc.roundabout.circulatingLanes ?? widestApproach(doc);
}

/** "3-lane north–south road, 2-lane east–west road" style road summary. */
export function describeRoads(doc: ScenarioDocument): string {
  const road = (a: ApproachName, b: ApproachName, label: string) => {
    const armA = doc.approaches[a];
    const armB = doc.approaches[b];
    if (!armA || !armB) {
      const only = armA ? a : b;
      const arm = armA ?? armB;
      return arm ? `${String(arm.lanes)}-lane ${only} arm` : "";
    }
    const la = armA.lanes;
    const lb = armB.lanes;
    const lanes =
      la === lb ? `${String(la)}-lane` : `${String(la)}/${String(lb)}-lane`;
    return `${lanes} ${label} road`;
  };
  const parts = [
    road("north", "south", "north–south"),
    road("east", "west", "east–west"),
  ].filter(Boolean);
  const arms = presentArms(doc);
  const skewed = arms.some(
    ([a, arm]) => arm.bearing != null && arm.bearing !== SLOT_BEARING[a],
  );
  const prefix =
    arms.length === 3
      ? "Three-arm junction: "
      : skewed
        ? "Skewed junction: "
        : "";
  return `${prefix}${parts.join(", ")}`;
}

/** The busiest approach and how much busier it is than the average. */
export function describeDemand(doc: ScenarioDocument): string {
  const total = totalVph(doc);
  if (!(total > 0)) return "no traffic";
  const arms = presentArms(doc);
  const [busiest, busiestArm] = arms.reduce((x, y) =>
    y[1].vehiclesPerHour > x[1].vehiclesPerHour ? y : x,
  );
  const share = busiestArm.vehiclesPerHour / total;
  const even = arms.every(
    ([, arm]) =>
      Math.abs(arm.vehiclesPerHour - total / arms.length) < total * 0.02,
  );
  return even
    ? `${Math.round(total).toLocaleString()} veh/h, spread evenly`
    : `${Math.round(total).toLocaleString()} veh/h, heaviest from the ${busiest} (${String(Math.round(share * 100))}%)`;
}

export function describeScenario(doc: ScenarioDocument): string {
  return `${describeRoads(doc)}; ${describeDemand(doc)}; ${describeMix(doc.vehicles.mix ?? null)}.`;
}

// ── Exchange ──────────────────────────────────────────────────────────────

export function exportScenarioJson(doc: ScenarioDocument): string {
  return `${JSON.stringify(doc, null, 2)}\n`;
}

/** Reads an exported scenario. Only the envelope is checked here — the
 *  backend validates the content, so an import is never silently altered. */
export function parseScenarioJson(
  text: string,
): { scenario: ScenarioDocument } | { error: string } {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return { error: "That file is not valid JSON." };
  }
  if (typeof data !== "object" || data === null) {
    return { error: "That file does not contain a scenario." };
  }
  const obj = data as Record<string, unknown>;
  const body = (
    typeof obj.scenario === "object" &&
    obj.scenario !== null &&
    !("junction" in obj)
      ? obj.scenario
      : obj
  ) as Record<string, unknown>;
  if (body.format !== SCENARIO_FORMAT) {
    return {
      error: `Not an UrbanFlow scenario (format ${JSON.stringify(body.format ?? null)}).`,
    };
  }
  if (body.version !== SCENARIO_VERSION) {
    return {
      error: `Scenario version ${JSON.stringify(body.version ?? null)} is not supported; this app reads version ${String(SCENARIO_VERSION)}.`,
    };
  }
  if (
    typeof body.approaches !== "object" ||
    typeof body.junction !== "object"
  ) {
    return { error: "The scenario is missing its junction or approaches." };
  }
  return { scenario: body as unknown as ScenarioDocument };
}

// ── Bridge to the existing dashboard configuration ───────────────────────

/** Dashboard values that mirror a scenario, so the rest of the app (maps,
 *  guide, results text) describes the scenario being run. The scenario
 *  itself is what the backend runs. */
export function configValuesFromScenario(
  doc: ScenarioDocument,
  prev: SimulationConfigValues,
): SimulationConfigValues {
  const strategy = JUNCTION_STRATEGY[doc.junction.type];
  return {
    ...prev,
    scenario: cloneScenario(doc),
    lanes: (doc.approaches.north ?? doc.approaches.south)?.lanes ?? 1,
    lanesEastWest: (() => {
      const ns = (doc.approaches.north ?? doc.approaches.south)?.lanes ?? 1;
      const ew = (doc.approaches.east ?? doc.approaches.west)?.lanes ?? ns;
      return ew !== ns ? ew : null;
    })(),
    laneWidth: doc.roads.laneWidth,
    arrivalRate: totalVph(doc) / 3600,
    duration: doc.simulation.duration,
    randomSeed: doc.simulation.seed,
    greenDuration: doc.signal.greenTime,
    nsGreenDuration: doc.signal.nsGreenTime ?? null,
    ewGreenDuration: doc.signal.ewGreenTime ?? null,
    yellowDuration: doc.signal.yellowTime,
    allRedDuration: doc.signal.allRedTime,
    criticalGap: doc.roundabout.criticalGap,
    followUpTime: doc.roundabout.followUpTime,
    vehicleMix: doc.vehicles.mix ?? null,
    laneChanging: doc.roads.laneChanging,
    signalControl: strategy === "adaptive" ? "adaptive" : undefined,
    adaptive: { ...doc.signal.adaptive },
  };
}

/** A scenario document describing the quick-setup answers, so the builder
 *  starts from what the user already chose (demand split evenly, the
 *  default turning shares, the same timing, seed and run length). */
export function scenarioFromConfigValues(
  config: SimulationConfigValues,
): ScenarioDocument {
  if (config.scenario) return cloneScenario(config.scenario);
  const base = scenarioFromPreset("calibrated-baseline");
  const perApproach = (config.arrivalRate * 3600) / 4;
  const ew = config.lanesEastWest ?? config.lanes;
  for (const a of APPROACHES) {
    const lanes = a === "east" || a === "west" ? ew : config.lanes;
    const arm = base.approaches[a];
    if (!arm) continue;
    base.approaches[a] = {
      ...arm,
      lanes,
      vehiclesPerHour: Math.round(perApproach),
    };
  }
  base.name = "My junction";
  base.description = "";
  base.preset = null;
  base.junction.type =
    config.signalControl === "adaptive"
      ? "adaptive_signal"
      : "fixed_time_signal";
  base.roads.laneWidth = config.laneWidth;
  base.roads.laneChanging = config.laneChanging ?? true;
  base.vehicles.mix = config.vehicleMix ?? null;
  base.signal.greenTime = config.greenDuration;
  base.signal.nsGreenTime = config.nsGreenDuration ?? null;
  base.signal.ewGreenTime = config.ewGreenDuration ?? null;
  base.signal.yellowTime = config.yellowDuration;
  base.signal.allRedTime = config.allRedDuration;
  base.signal.adaptive = {
    ...base.signal.adaptive,
    ...(config.adaptive ?? {}),
  };
  base.roundabout.criticalGap = config.criticalGap;
  base.roundabout.followUpTime = config.followUpTime;
  base.simulation.duration = config.duration;
  base.simulation.seed = config.randomSeed;
  return base;
}

/** Lanes per approach for the maps: the scenario's when one is set (0 for
 *  a slot with no arm, V1.5). */
export function approachLanes(
  config: SimulationConfigValues,
): Record<ApproachName, number> {
  const doc = config.scenario;
  if (doc) {
    return {
      north: doc.approaches.north?.lanes ?? 0,
      south: doc.approaches.south?.lanes ?? 0,
      east: doc.approaches.east?.lanes ?? 0,
      west: doc.approaches.west?.lanes ?? 0,
    };
  }
  const ew = config.lanesEastWest ?? config.lanes;
  return { north: config.lanes, south: config.lanes, east: ew, west: ew };
}

// ── Geometry preview (mirrors backend roads/junction_geometry.py) ──────────

/** Distance from the conflict area to a signal stop line (m), cars only;
 *  backend SIGNAL_STOP_LINE_SETBACK. The server's resolved design, when
 *  available, includes the extra set-back for long vehicles. */
const SIGNAL_STOP_LINE_SETBACK = 3.5;
/** Backend ROUNDABOUT_ENTRY_SETBACK. */
const ROUNDABOUT_ENTRY_SETBACK = 4.0;

function bearingDifference(a: number, b: number): number {
  const d = Math.abs(((a - b) % 360) + 360) % 360;
  return Math.min(d, 360 - d);
}

/** Centre-to-stop-line distance of every arm, by the backend's rule: the
 *  square box sized to the widest road, and on a skewed junction each arm
 *  moved out until it is clear of every road crossing it. */
export function stopLineDistances(
  doc: ScenarioDocument,
  roundabout: boolean,
): Partial<Record<ApproachName, number>> {
  const arms = presentArms(doc);
  const out: Partial<Record<ApproachName, number>> = {};
  if (roundabout) {
    for (const [a] of arms)
      out[a] = doc.roundabout.outerRadius + ROUNDABOUT_ENTRY_SETBACK;
    return out;
  }
  const half = (arm: ApproachSpec) => arm.lanes * armLaneWidth(doc, arm);
  const floor = Math.max(0, ...arms.map(([, arm]) => half(arm)));
  const skewed = arms.some(
    ([a, arm]) => arm.bearing != null && arm.bearing % 360 !== SLOT_BEARING[a],
  );
  for (const [a, arm] of arms) {
    let need = floor;
    if (skewed) {
      for (const [b, other] of arms) {
        if (b === a || b === OPPOSITE[a]) continue;
        const theta =
          (bearingDifference(armBearing(a, arm), armBearing(b, other)) *
            Math.PI) /
          180;
        need = Math.max(
          need,
          (half(other) + half(arm) * Math.abs(Math.cos(theta))) /
            Math.abs(Math.sin(theta)),
        );
      }
    }
    out[a] = need + SIGNAL_STOP_LINE_SETBACK;
  }
  return out;
}
