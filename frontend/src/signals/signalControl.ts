/**
 * V1.3 signal control in plain language: the guided question's choices, the
 * live "what the adaptive signal is doing" line, and labels for results.
 * Mirrors the decision rules in backend/src/controllers/adaptive_signal.py.
 */
import type {
  AdaptiveSettings,
  SignalControl,
  SimulationConfigValues,
} from "../types/config";
import { adaptiveSettings, isAdaptive } from "../types/config";
import type {
  AdaptiveSignalState,
  ControllerState,
  SignalDirection,
} from "../types/simulation";

export interface SignalControlChoice {
  id: SignalControl;
  label: string;
  description: string;
}

export const SIGNAL_CONTROL_CHOICES: SignalControlChoice[] = [
  {
    id: "fixed_time",
    label: "On a fixed timetable",
    description:
      "Each direction gets the same green every cycle, whether or not anyone is there.",
  },
  {
    id: "adaptive",
    label: "Responds to traffic",
    description:
      "Detectors at the stop line keep a green going while traffic flows, and end it once the road empties and someone is waiting.",
  },
];

/** Short name of a scenario's signal, for headings and chips. */
export function signalControlLabel(
  config: Pick<SimulationConfigValues, "signalControl">,
): string {
  return isAdaptive(config)
    ? "Signal that responds to traffic"
    : "Fixed-timetable signal";
}

/** One sentence describing how the signal decides, for the setup page. */
export function adaptiveRuleSentence(settings: Required<AdaptiveSettings>) {
  return `Each green lasts at least ${String(settings.minGreen)} s, continues while vehicles keep arriving, and ends once ${String(settings.extensionStep)} s pass with nobody arriving and someone waiting on red — never more than ${String(settings.maxGreen)} s once someone is waiting.`;
}

export function scenarioAdaptiveSentence(config: SimulationConfigValues) {
  return adaptiveRuleSentence(adaptiveSettings(config));
}

const DIRECTION_WORDS: Record<SignalDirection, string> = {
  north: "north",
  south: "south",
  east: "east",
  west: "west",
};

/** Which approaches a phase name gives green to, in words. */
export function phaseApproaches(phase: string | null | undefined): string {
  if (!phase) return "the next direction";
  const group = phase.split("_")[0];
  const named: Record<string, string> = {
    n: "north",
    s: "south",
    e: "east",
    w: "west",
    ns: "north–south",
    sn: "north–south",
    ew: "east–west",
    we: "east–west",
  };
  if (group in named) return named[group];
  if (group in DIRECTION_WORDS)
    return DIRECTION_WORDS[group as SignalDirection];
  return "the next direction";
}

export function adaptiveStateOf(
  controller: ControllerState | undefined,
): AdaptiveSignalState | null {
  if (!controller || controller.type !== "fixed_time_signal") return null;
  return controller.signalControl === "adaptive" && controller.adaptive
    ? controller.adaptive
    : null;
}

/** What the adaptive signal is doing right now, in one plain sentence. */
export function adaptiveStatusText(
  controller: ControllerState | undefined,
): string | null {
  const a = adaptiveStateOf(controller);
  if (!a || controller?.type !== "fixed_time_signal") return null;
  const on = phaseApproaches(controller.currentPhase);
  const waiting = a.phasesWaiting > 0;
  switch (a.status) {
    case "min_green":
      return `Green for ${on}: giving the queue at least ${String(a.minGreen)} s to get moving.`;
    case "extending":
      return waiting
        ? `Holding green for ${on}: traffic is still arriving. Someone is waiting on red, so this green ends within ${String(Math.max(0, Math.ceil(controller.phaseTimeRemaining)))} s at most.`
        : `Holding green for ${on}: traffic is still arriving and nobody is waiting on red.`;
    case "resting":
      return `Green stays with ${on}: nobody is waiting on red, so there is no reason to change.`;
    case "clearance":
      return `Changing: ${phaseApproaches(a.nextPhase)} has traffic waiting. Yellow and all-red first, as always.`;
  }
}
