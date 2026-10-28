/** Option tables and labels shared by the scenario builder's steps. */
import { type JunctionType, type Movement } from "../../scenario/scenarioTypes";

export const JUNCTIONS: { id: JunctionType; title: string; body: string }[] = [
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
    body: "Drivers give way to circulating traffic and enter at gaps; signals on the entries are optional.",
  },
];

/** "How busy is this road?" — vehicles per hour per lane. */
export const BUSY_LEVELS: { id: string; label: string; perLane: number }[] = [
  { id: "quiet", label: "Quiet", perLane: 120 },
  { id: "moderate", label: "Moderate", perLane: 250 },
  { id: "busy", label: "Busy", perLane: 400 },
  { id: "very-busy", label: "Very busy", perLane: 550 },
];

export const DURATIONS = [
  { seconds: 120, label: "2 min" },
  { seconds: 300, label: "5 min" },
  { seconds: 600, label: "10 min" },
];

export const GLYPH: Record<Movement, string> = {
  uturn: "↶",
  left: "↰",
  straight: "↑",
  right: "↱",
};
export const MOVE_LABEL: Record<Movement, string> = {
  uturn: "U-turn",
  left: "Left",
  straight: "Straight",
  right: "Right",
};

export type Step =
  "junction" | "roads" | "traffic" | "vehicles" | "simulation" | "advanced";
export const STEPS: { id: Step; title: string }[] = [
  { id: "junction", title: "Junction" },
  { id: "roads", title: "Roads & lanes" },
  { id: "traffic", title: "Traffic" },
  { id: "vehicles", title: "Vehicles" },
  { id: "simulation", title: "Simulation" },
  { id: "advanced", title: "Advanced" },
];

export function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
