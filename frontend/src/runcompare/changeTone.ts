import type { Tone } from "../components/dashboard/Dashboard";
import { isNum } from "../insights/format";
import type { MetricDiff } from "./types";

/** Whether the change is good, bad or neutral for this metric. */
export function changeTone(m: MetricDiff): { tone: Tone; word: string } {
  if (!isNum(m.delta)) return { tone: "neutral", word: "Not comparable" };
  if (m.delta === 0) return { tone: "neutral", word: "No change" };
  const better = m.lowerIsBetter ? m.delta < 0 : m.delta > 0;
  return better
    ? { tone: "good", word: "Better" }
    : { tone: "warn", word: "Worse" };
}
