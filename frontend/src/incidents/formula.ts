import { num } from "../netcommon/format";
import type { ResilienceResponse } from "./types";

/** The score formula in words, from the weights the server returned. */
export function formulaText(f: ResilienceResponse["scoreFormula"]): string {
  const w = f.weights;
  return `Score = ${num(w.recovery)} x recovery + ${num(w.throughput)} x throughput + ${num(w.peak)} x peak + ${num(w.area)} x area, a number from 0 to 1 where higher is better.`;
}
