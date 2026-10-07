/**
 * Helpers for building, checking, describing and exchanging scenario
 * documents. The backend (POST /api/v1/scenarios/validate) is the authority
 * on what can be simulated; the checks here only make the builder respond
 * instantly — they never adjust what the user entered.
 */
import presetsFile from "./presets.json";
import {
  APPROACHES,
  JUNCTION_STRATEGY,
  MOVEMENTS,
  OPPOSITE,
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

/** The default lane-use policy (backend roads/lane_config.default_policy_turns). */
export function defaultLaneUse(lanes: number): Movement[][] {
  if (lanes <= 1) return [[...MOVEMENTS]];
  return Array.from({ length: lanes }, (_, i) => {
    const turns: Movement[] = [];
    if (i === 0) turns.push("left");
    turns.push("straight");
    if (i === lanes - 1) turns.push("right");
    return turns;
  });
}

/** Signal lane arrows of an approach: configured, else the default policy. */
export function signalLaneUse(arm: ApproachSpec): Movement[][] {
  return arm.laneUse && arm.laneUse.length === arm.lanes
    ? arm.laneUse
    : defaultLaneUse(arm.lanes);
}

const ORDER: Record<Movement, number> = { left: 0, straight: 1, right: 2 };

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
  return t.left + t.straight + t.right;
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
  for (const name of APPROACHES) {
    const arm = doc.approaches[name];
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
    if (arm.lanes !== opposite.lanes && (name === "north" || name === "east")) {
      issues.push({
        where: name,
        message: `A signal needs the same number of lanes on ${name} and ${OPPOSITE[name]} (through traffic cannot merge inside the junction); they have ${String(arm.lanes)} and ${String(opposite.lanes)}.`,
      });
    }
    const use = signalLaneUse(arm);
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
          message: `Lanes ${String(i + 1)} and ${String(i + 2)} cross: arrange arrows left → straight → right from the centre line.`,
        });
      }
    }
    for (const turn of MOVEMENTS) {
      if (arm.turning[turn] > 0 && !use.some((lane) => lane.includes(turn))) {
        issues.push({
          where: name,
          message: `${pct(arm.turning[turn])} of this road's traffic turns ${turn}, but no lane allows it.`,
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
  return APPROACHES.reduce(
    (sum, a) => sum + doc.approaches[a].vehiclesPerHour,
    0,
  );
}

export function widestApproach(doc: ScenarioDocument): number {
  return Math.max(...APPROACHES.map((a) => doc.approaches[a].lanes));
}

export function ringLanes(doc: ScenarioDocument): number {
  return doc.roundabout.circulatingLanes ?? widestApproach(doc);
}

/** "3-lane north–south road, 2-lane east–west road" style road summary. */
export function describeRoads(doc: ScenarioDocument): string {
  const road = (a: ApproachName, b: ApproachName, label: string) => {
    const la = doc.approaches[a].lanes;
    const lb = doc.approaches[b].lanes;
    const lanes =
      la === lb ? `${String(la)}-lane` : `${String(la)}/${String(lb)}-lane`;
    return `${lanes} ${label} road`;
  };
  return `${road("north", "south", "north–south")}, ${road("east", "west", "east–west")}`;
}

/** The busiest approach and how much busier it is than the average. */
export function describeDemand(doc: ScenarioDocument): string {
  const total = totalVph(doc);
  if (!(total > 0)) return "no traffic";
  const busiest = APPROACHES.reduce((a, b) =>
    doc.approaches[b].vehiclesPerHour > doc.approaches[a].vehiclesPerHour
      ? b
      : a,
  );
  const share = doc.approaches[busiest].vehiclesPerHour / total;
  const even = APPROACHES.every(
    (a) =>
      Math.abs(doc.approaches[a].vehiclesPerHour - total / 4) < total * 0.02,
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
    lanes: doc.approaches.north.lanes,
    lanesEastWest:
      doc.approaches.east.lanes !== doc.approaches.north.lanes
        ? doc.approaches.east.lanes
        : null,
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
    base.approaches[a] = {
      ...base.approaches[a],
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

/** Lanes per approach for the maps: the scenario's when one is set. */
export function approachLanes(
  config: SimulationConfigValues,
): Record<ApproachName, number> {
  const doc = config.scenario;
  if (doc) {
    return {
      north: doc.approaches.north.lanes,
      south: doc.approaches.south.lanes,
      east: doc.approaches.east.lanes,
      west: doc.approaches.west.lanes,
    };
  }
  const ew = config.lanesEastWest ?? config.lanes;
  return { north: config.lanes, south: config.lanes, east: ew, west: ew };
}
