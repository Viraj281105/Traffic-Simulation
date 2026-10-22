/**
 * Strategy Summary & DNA Model (V3.0 W3, ADR-014, V3 Product Strategy §13.6).
 *
 * Provides frontend data contracts and resolution logic for the 4 built-in composable
 * traffic control strategies and their 6 structural descriptor layers:
 * 1. Geometry Constraint
 * 2. Movement Topology
 * 3. Right-of-Way Rule
 * 4. Control Policy
 * 5. Adaptation Logic
 * 6. Priority Overlay
 */

import { isMeteredEntry, type ScenarioDocument } from "./scenarioTypes";
import { presentApproaches, ringLanes } from "./scenarioModel";
import { ADAPTIVE_DEFAULTS } from "../types/config";

export type CanonicalStrategyId =
  | "fixed_time_signal"
  | "adaptive_signal"
  | "conventional_roundabout"
  | "metered_entry_roundabout";

export interface LayerSummary {
  layerIndex: number;
  layerKey:
    | "geometry"
    | "topology"
    | "right_of_way"
    | "control_policy"
    | "adaptation"
    | "priority_overlay";
  layerTitle: string;
  contractValue: string;
  appliedValue: string;
  hasConflict?: boolean;
  conflictMessage?: string;
}

export interface ParameterItem {
  name: string;
  label: string;
  unit: string;
  defaultValue: number | string;
  currentValue: number | string;
  isDefault: boolean;
}

export interface ParameterProvenance {
  totalParameters: number;
  customizedCount: number;
  isAllDefault: boolean;
  parameters: ParameterItem[];
}

export interface StrategyDescriptorView {
  id: CanonicalStrategyId;
  name: string;
  status: "stable" | "experimental";
  description: string;
  fingerprint: string;
  notModelled: string[];
  invariants: string[];
  layers: {
    geometry: {
      intersectionType: "fixed_time_signal" | "roundabout";
      minArms: number;
      maxArms: number;
      circulatingLanes: number[] | null;
    };
    topology: {
      topologyType: "point_based_conflicts" | "zone_based_conflicts";
      supportsUturns: boolean;
    };
    rightOfWay: {
      rule: "signal" | "yield_to_ring" | "signal_over_yield";
      label: string;
    };
    controlPolicy: {
      policy: "fixed_time_phase_plan" | "metering" | "uncontrolled";
      cycleAware: boolean;
      label: string;
    };
    adaptationLogic: {
      logic: "none" | "gap_out_extension";
      deterministic: boolean;
      label: string;
    };
    priorityOverlay: {
      overlay: "none" | "emergency_preemption";
      label: string;
    };
  };
}

export interface CompatibilityIssueView {
  code: string;
  message: string;
  layerIndex?: number;
  suggestion?: string;
}

/**
 * Built-in Strategy Descriptors matching ADR-014 and backend registry.
 * Fingerprints are frozen 16-hex deterministic SHA-256 digests.
 */
export const BUILTIN_STRATEGY_DESCRIPTORS: Record<
  CanonicalStrategyId,
  StrategyDescriptorView
> = {
  fixed_time_signal: {
    id: "fixed_time_signal",
    name: "Fixed-Time Signal",
    status: "stable",
    description:
      "Cyclic fixed-duration signal control across orthogonal or multi-leg approaches with conflict points managed by dedicated green phases.",
    fingerprint: "dc4cea8828710979",
    notModelled: [
      "Actuated / demand-responsive extensions",
      "Coordination with upstream junctions",
      "Pedestrian call buttons",
    ],
    invariants: [
      "sum(green + yellow + all_red) == cycle_length",
      "green_time >= min_green",
    ],
    layers: {
      geometry: {
        intersectionType: "fixed_time_signal",
        minArms: 3,
        maxArms: 4,
        circulatingLanes: null,
      },
      topology: {
        topologyType: "point_based_conflicts",
        supportsUturns: true,
      },
      rightOfWay: {
        rule: "signal",
        label: "Signal (dedicated green phases)",
      },
      controlPolicy: {
        policy: "fixed_time_phase_plan",
        cycleAware: true,
        label: "Fixed-time phase plan (cycle-aware)",
      },
      adaptationLogic: {
        logic: "none",
        deterministic: true,
        label: "None (deterministic fixed cycle)",
      },
      priorityOverlay: {
        overlay: "none",
        label: "None (standard FIFO queueing)",
      },
    },
  },
  adaptive_signal: {
    id: "adaptive_signal",
    name: "Adaptive (Actuated) Signal",
    status: "stable",
    description:
      "Traffic-actuated signal control extending green phases based on vehicle detection and gap-out thresholds within bounded cycle limits.",
    fingerprint: "588ee921ecda8e01",
    notModelled: [
      "Queue spillback detection across junctions",
      "Dynamic phase reordering",
      "Emergency preemption",
    ],
    invariants: [
      "min_green <= current_green <= max_green",
      "green extensions stop on gap_out or max_green reach",
    ],
    layers: {
      geometry: {
        intersectionType: "fixed_time_signal",
        minArms: 3,
        maxArms: 4,
        circulatingLanes: null,
      },
      topology: {
        topologyType: "point_based_conflicts",
        supportsUturns: true,
      },
      rightOfWay: {
        rule: "signal",
        label: "Signal (dedicated green phases)",
      },
      controlPolicy: {
        policy: "fixed_time_phase_plan",
        cycleAware: true,
        label: "Fixed-time phase plan (cycle-aware)",
      },
      adaptationLogic: {
        logic: "gap_out_extension",
        deterministic: true,
        label: "Gap-out extension (actuated vehicle detection)",
      },
      priorityOverlay: {
        overlay: "none",
        label: "None (standard FIFO queueing)",
      },
    },
  },
  conventional_roundabout: {
    id: "conventional_roundabout",
    name: "Conventional Roundabout",
    status: "stable",
    description:
      "Self-governing circular junction operating on yield-at-entry (offside priority) without signal control, with continuous circulating flow.",
    fingerprint: "b622164ad2527a01",
    notModelled: [
      "Lane changes within circulating ring",
      "Pedestrian crosswalks on splitter islands",
      "Spiral lane markings",
    ],
    invariants: [
      "Circulating vehicles maintain absolute priority over entry vehicles",
      "Keep-clear zones prevent gridlock inside circulating quadrants",
    ],
    layers: {
      geometry: {
        intersectionType: "roundabout",
        minArms: 3,
        maxArms: 4,
        circulatingLanes: [1, 2],
      },
      topology: {
        topologyType: "zone_based_conflicts",
        supportsUturns: true,
      },
      rightOfWay: {
        rule: "yield_to_ring",
        label: "Yield to ring (offside priority)",
      },
      controlPolicy: {
        policy: "uncontrolled",
        cycleAware: false,
        label: "Uncontrolled (continuous gap acceptance)",
      },
      adaptationLogic: {
        logic: "none",
        deterministic: true,
        label: "None (deterministic gap acceptance)",
      },
      priorityOverlay: {
        overlay: "none",
        label: "None (standard FIFO queueing)",
      },
    },
  },
  metered_entry_roundabout: {
    id: "metered_entry_roundabout",
    name: "Metered-Entry Signalised Roundabout",
    status: "stable",
    description:
      "Hybrid roundabout where signals meter entry onto the circulating carriageway on designated approaches while circulating traffic retains offside priority.",
    fingerprint: "32511c2e97ffc1bb",
    notModelled: [
      "Phased priority / signal-controlled circulation inside the ring",
      "Dynamic metering based on ring occupancy queues",
      "Queue detector setbacks > 150m",
    ],
    invariants: [
      "Metering signal only restricts entry opportunity, circulating traffic retains offside priority",
      "AlwaysOpen default gate reproduces conventional roundabout bit-identically",
    ],
    layers: {
      geometry: {
        intersectionType: "roundabout",
        minArms: 3,
        maxArms: 4,
        circulatingLanes: [1, 2],
      },
      topology: {
        topologyType: "zone_based_conflicts",
        supportsUturns: true,
      },
      rightOfWay: {
        rule: "signal_over_yield",
        label: "Signal over yield (metered entries yield to circulating flow)",
      },
      controlPolicy: {
        policy: "metering",
        cycleAware: true,
        label: "Entry metering (cycle-aware phase plan)",
      },
      adaptationLogic: {
        logic: "none",
        deterministic: true,
        label: "None (fixed-time metering intervals)",
      },
      priorityOverlay: {
        overlay: "none",
        label: "None (standard FIFO queueing)",
      },
    },
  },
};

/**
 * Maps legacy strategy strings to canonical strategy IDs.
 */
export function toCanonicalStrategyId(
  strategy: string,
  doc?: ScenarioDocument,
): CanonicalStrategyId {
  if (strategy === "roundabout" || strategy === "conventional_roundabout") {
    if (doc && isMeteredEntry(doc)) {
      return "metered_entry_roundabout";
    }
    return "conventional_roundabout";
  }
  if (
    strategy === "metered_entry_roundabout" ||
    strategy === "signalised_roundabout"
  ) {
    return "metered_entry_roundabout";
  }
  if (strategy === "adaptive" || strategy === "adaptive_signal") {
    return "adaptive_signal";
  }
  return "fixed_time_signal";
}

/**
 * Resolves the active strategy ID from the scenario document's structural configuration.
 */
export function resolveActiveStrategyId(
  doc: ScenarioDocument,
): CanonicalStrategyId {
  if (doc.junction.type === "roundabout") {
    return isMeteredEntry(doc)
      ? "metered_entry_roundabout"
      : "conventional_roundabout";
  }
  if (doc.junction.type === "adaptive_signal") {
    return "adaptive_signal";
  }
  return "fixed_time_signal";
}

/**
 * Resolves parameter provenance comparing current document values with descriptor defaults.
 */
export function resolveParameterProvenance(
  strategyId: CanonicalStrategyId,
  doc: ScenarioDocument,
): ParameterProvenance {
  const params: ParameterItem[] = [];

  if (strategyId === "fixed_time_signal") {
    const cycle =
      (doc.signal.nsGreenTime ?? doc.signal.greenTime) +
      (doc.signal.ewGreenTime ?? doc.signal.greenTime) +
      doc.signal.yellowTime * 2 +
      doc.signal.allRedTime * 2;
    params.push(
      {
        name: "green_time",
        label: "Green duration",
        unit: "s",
        defaultValue: 25.0,
        currentValue: doc.signal.greenTime,
        isDefault: doc.signal.greenTime === 25.0,
      },
      {
        name: "yellow_time",
        label: "Yellow interval",
        unit: "s",
        defaultValue: 3.0,
        currentValue: doc.signal.yellowTime,
        isDefault: doc.signal.yellowTime === 3.0,
      },
      {
        name: "all_red_time",
        label: "All-red clearance",
        unit: "s",
        defaultValue: 2.0,
        currentValue: doc.signal.allRedTime,
        isDefault: doc.signal.allRedTime === 2.0,
      },
      {
        name: "cycle_time",
        label: "Cycle length",
        unit: "s",
        defaultValue: 60.0,
        currentValue: cycle,
        isDefault: cycle === 60.0,
      },
    );
  } else if (strategyId === "adaptive_signal") {
    const a = doc.signal.adaptive;
    params.push(
      {
        name: "min_green",
        label: "Minimum green",
        unit: "s",
        defaultValue: ADAPTIVE_DEFAULTS.minGreen,
        currentValue: a.minGreen,
        isDefault: a.minGreen === ADAPTIVE_DEFAULTS.minGreen,
      },
      {
        name: "max_green",
        label: "Maximum green",
        unit: "s",
        defaultValue: ADAPTIVE_DEFAULTS.maxGreen,
        currentValue: a.maxGreen,
        isDefault: a.maxGreen === ADAPTIVE_DEFAULTS.maxGreen,
      },
      {
        name: "extension_step",
        label: "Extension step",
        unit: "s",
        defaultValue: ADAPTIVE_DEFAULTS.extensionStep,
        currentValue: a.extensionStep,
        isDefault: a.extensionStep === ADAPTIVE_DEFAULTS.extensionStep,
      },
      {
        name: "detection_distance",
        label: "Detection distance",
        unit: "m",
        defaultValue: ADAPTIVE_DEFAULTS.detectionDistance,
        currentValue: a.detectionDistance,
        isDefault: a.detectionDistance === ADAPTIVE_DEFAULTS.detectionDistance,
      },
    );
  } else if (strategyId === "conventional_roundabout") {
    const rb = doc.roundabout;
    params.push(
      {
        name: "critical_gap",
        label: "Critical headway",
        unit: "s",
        defaultValue: 4.0,
        currentValue: rb.criticalGap,
        isDefault: Math.abs(rb.criticalGap - 4.0) < 0.001,
      },
      {
        name: "follow_up_time",
        label: "Follow-up headway",
        unit: "s",
        defaultValue: 2.5,
        currentValue: rb.followUpTime,
        isDefault: Math.abs(rb.followUpTime - 2.5) < 0.001,
      },
      {
        name: "inner_radius",
        label: "Inner radius",
        unit: "m",
        defaultValue: 10.0,
        currentValue: rb.innerRadius,
        isDefault: rb.innerRadius === 10.0,
      },
      {
        name: "circulating_lanes",
        label: "Circulating lanes",
        unit: "lanes",
        defaultValue: 2,
        currentValue: ringLanes(doc),
        isDefault: rb.circulatingLanes == null,
      },
    );
  } else {
    const m = doc.roundabout.entryMetering;
    const g = m?.phases[0]?.green ?? 20.0;
    const y = m?.yellow ?? 3.0;
    const r = m?.allRed ?? 2.0;
    params.push(
      {
        name: "metering_green",
        label: "Metering green",
        unit: "s",
        defaultValue: 20.0,
        currentValue: g,
        isDefault: g === 20.0,
      },
      {
        name: "metering_yellow",
        label: "Metering yellow",
        unit: "s",
        defaultValue: 3.0,
        currentValue: y,
        isDefault: y === 3.0,
      },
      {
        name: "metering_all_red",
        label: "Metering all-red",
        unit: "s",
        defaultValue: 2.0,
        currentValue: r,
        isDefault: r === 2.0,
      },
      {
        name: "metering_phases",
        label: "Metered phases",
        unit: "phases",
        defaultValue: 2,
        currentValue: m?.phases.length ?? 0,
        isDefault: (m?.phases.length ?? 0) === 2,
      },
    );
  }

  const customized = params.filter((p) => !p.isDefault);
  return {
    totalParameters: params.length,
    customizedCount: customized.length,
    isAllDefault: customized.length === 0,
    parameters: params,
  };
}

/**
 * Resolves the 6 Strategy DNA layers for presentation.
 */
export function resolveStrategyLayers(
  strategyId: CanonicalStrategyId,
  doc: ScenarioDocument,
  issues: CompatibilityIssueView[] = [],
): LayerSummary[] {
  const desc = BUILTIN_STRATEGY_DESCRIPTORS[strategyId];
  const arms = presentApproaches(doc);
  const armCount = arms.length;
  const rings = ringLanes(doc);

  const issueByLayer = (idx: number) =>
    issues.find((i) => i.layerIndex === idx);

  // Layer 1: Geometry Constraint
  const l1Issue = issueByLayer(1);
  const geomType =
    doc.junction.type === "roundabout"
      ? "Roundabout"
      : "Signalised intersection";
  const appliedGeom =
    doc.junction.type === "roundabout"
      ? `${geomType} · ${String(armCount)} arms · ${String(rings)} ring lane${rings === 1 ? "" : "s"}`
      : `${geomType} · ${String(armCount)} arms`;

  // Layer 2: Movement Topology
  const l2Issue = issueByLayer(2);
  const appliedTopo =
    desc.layers.topology.topologyType === "zone_based_conflicts"
      ? "Zone-based circulatory conflicts · U-turns supported"
      : "Point-based junction conflicts · U-turns supported";

  // Layer 3: Right-of-Way Rule
  const l3Issue = issueByLayer(3);
  const appliedRoW = desc.layers.rightOfWay.label;

  // Layer 4: Control Policy
  const l4Issue = issueByLayer(4);
  let appliedPolicy = desc.layers.controlPolicy.label;
  if (strategyId === "metered_entry_roundabout") {
    const phases = doc.roundabout.entryMetering?.phases.length ?? 0;
    appliedPolicy = `Entry metering (${String(phases)} phase${phases === 1 ? "" : "s"}) · Offside priority inside ring`;
  } else if (strategyId === "fixed_time_signal") {
    const cycle =
      (doc.signal.nsGreenTime ?? doc.signal.greenTime) +
      (doc.signal.ewGreenTime ?? doc.signal.greenTime) +
      doc.signal.yellowTime * 2 +
      doc.signal.allRedTime * 2;
    appliedPolicy = `Fixed-time phase plan · Cycle ${cycle.toFixed(0)}s`;
  }

  // Layer 5: Adaptation Logic
  const l5Issue = issueByLayer(5);
  let appliedAdaptation = desc.layers.adaptationLogic.label;
  if (strategyId === "adaptive_signal") {
    appliedAdaptation = `Actuated gap-out (${String(doc.signal.adaptive.minGreen)}s–${String(doc.signal.adaptive.maxGreen)}s green bounds)`;
  }

  // Layer 6: Priority Overlay
  const l6Issue = issueByLayer(6);
  const appliedPriority = desc.layers.priorityOverlay.label;

  return [
    {
      layerIndex: 1,
      layerKey: "geometry",
      layerTitle: "Geometry Constraint",
      contractValue:
        desc.layers.geometry.intersectionType === "roundabout"
          ? "Roundabout (3–4 arms, 1–2 circulating lanes)"
          : "Fixed-time signal (3–4 orthogonal arms)",
      appliedValue: appliedGeom,
      hasConflict: !!l1Issue,
      conflictMessage: l1Issue?.message,
    },
    {
      layerIndex: 2,
      layerKey: "topology",
      layerTitle: "Movement Topology",
      contractValue:
        desc.layers.topology.topologyType === "zone_based_conflicts"
          ? "Zone-based conflicts · U-turns supported"
          : "Point-based conflicts · U-turns supported",
      appliedValue: appliedTopo,
      hasConflict: !!l2Issue,
      conflictMessage: l2Issue?.message,
    },
    {
      layerIndex: 3,
      layerKey: "right_of_way",
      layerTitle: "Right-of-Way Rule",
      contractValue: desc.layers.rightOfWay.label,
      appliedValue: appliedRoW,
      hasConflict: !!l3Issue,
      conflictMessage: l3Issue?.message,
    },
    {
      layerIndex: 4,
      layerKey: "control_policy",
      layerTitle: "Control Policy",
      contractValue: desc.layers.controlPolicy.label,
      appliedValue: appliedPolicy,
      hasConflict: !!l4Issue,
      conflictMessage: l4Issue?.message,
    },
    {
      layerIndex: 5,
      layerKey: "adaptation",
      layerTitle: "Adaptation Logic",
      contractValue: desc.layers.adaptationLogic.label,
      appliedValue: appliedAdaptation,
      hasConflict: !!l5Issue,
      conflictMessage: l5Issue?.message,
    },
    {
      layerIndex: 6,
      layerKey: "priority_overlay",
      layerTitle: "Priority Overlay",
      contractValue: desc.layers.priorityOverlay.label,
      appliedValue: appliedPriority,
      hasConflict: !!l6Issue,
      conflictMessage: l6Issue?.message,
    },
  ];
}

/**
 * The Strategy DNA layer (1-6: geometry, movement topology, right-of-way,
 * control policy, adaptation logic, priority overlay) each backend `compat.*`
 * code is shown on. Every entry must be a layer the backend lists for that code
 * (COMPATIBILITY_CODE_LAYERS in strategies/validator.py); a backend test pins
 * the key set and that containment. Unknown codes fall back to layer 1.
 */
export const COMPAT_CODE_LAYER_INDEX: Readonly<Record<string, number>> = {
  "compat.signal_requires_signal_geometry": 1,
  "compat.roundabout_yield_requires_roundabout": 1,
  "compat.phased_priority_unsupported": 3,
  "compat.signal_requires_point_topology": 2,
  "compat.roundabout_requires_zone_topology": 2,
  "compat.roundabout_requires_circulating_lanes": 1,
  "compat.signal_forbids_circulating_lanes": 1,
  "compat.arms_range_invalid": 1,
  "compat.signal_row_requires_phase_plan": 4,
  "compat.yield_to_ring_requires_uncontrolled": 4,
  "compat.signal_over_yield_requires_metering": 4,
  "compat.adaptive_unsupported_policy": 5,
  "compat.uncontrolled_cannot_be_cycle_aware": 4,
  "compat.priority_overlay_unsupported": 6,
  "compat.unknown_strategy": 4,
  "compat.strategy_config_mismatch": 1,
};

/**
 * Evaluates strategy compatibility against scenario configuration, integrating
 * any backend diagnostic codes (compat.*) if returned.
 */
export function evaluateStrategyCompatibility(
  strategyId: CanonicalStrategyId,
  doc: ScenarioDocument,
  serverErrors: string[] = [],
): CompatibilityIssueView[] {
  const issues: CompatibilityIssueView[] = [];
  const arms = presentApproaches(doc);

  // 1. Arms count check
  if (arms.length < 3 || arms.length > 4) {
    issues.push({
      code: "compat.arms_range_invalid",
      message: `Junction has ${String(arms.length)} arms; strategy supports 3 or 4 arms only.`,
      layerIndex: 1,
      suggestion: "Enable 3 or 4 approaches in step 1.",
    });
  }

  // 2. Geometry & Strategy alignment check
  if (
    (strategyId === "conventional_roundabout" ||
      strategyId === "metered_entry_roundabout") &&
    doc.junction.type !== "roundabout"
  ) {
    issues.push({
      code: "compat.roundabout_yield_requires_roundabout",
      message: "Roundabout strategy requires roundabout geometry.",
      layerIndex: 1,
      suggestion: "Change junction type to Roundabout in step 1.",
    });
  }

  if (
    (strategyId === "fixed_time_signal" || strategyId === "adaptive_signal") &&
    doc.junction.type === "roundabout"
  ) {
    issues.push({
      code: "compat.signal_requires_signal_geometry",
      message: "Signal strategy requires signalised junction geometry.",
      layerIndex: 1,
      suggestion: "Change junction type to Signal in step 1.",
    });
  }

  // 3. Adaptive on any roundabout: the backend rejects it for unmetered and
  // metered-entry rings alike (no adaptive signalised roundabout in V3.0).
  if (strategyId === "adaptive_signal" && doc.junction.type === "roundabout") {
    issues.push({
      code: "compat.adaptive_unsupported_policy",
      message:
        "Adaptive detectors require a signalised junction; they are not available on a roundabout.",
      layerIndex: 5,
      suggestion: "Switch to a signalised junction or use fixed-time control.",
    });
  }

  // 4. Circulating lanes check
  if (doc.junction.type === "roundabout") {
    const rings = ringLanes(doc);
    if (rings < 1 || rings > 2) {
      issues.push({
        code: "compat.roundabout_requires_circulating_lanes",
        message: `Circulating ring has ${String(rings)} lanes; only 1 or 2 circulating lanes are supported.`,
        layerIndex: 1,
        suggestion: "Set circulating lanes to 1 or 2 in Advanced settings.",
      });
    }
  }

  // 5. Integrate server-reported compatibility errors
  for (const err of serverErrors) {
    const match = err.match(/\((compat\.[a-z_]+)\)/);
    if (match) {
      const code = match[1];
      const existing = issues.find((i) => i.code === code);
      if (existing) {
        existing.message = err;
      } else {
        issues.push({
          code,
          message: err,
          layerIndex: COMPAT_CODE_LAYER_INDEX[code] ?? 1,
        });
      }
    }
  }

  return issues;
}
