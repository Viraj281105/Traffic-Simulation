import { UNAVAILABLE, isNum, num } from "../netcommon/format";
import type { TwinAlert, TwinState, WhatIfResult } from "./types";

/** Plain words for one alert. */
export function alertText(a: TwinAlert, state: TwinState): string {
  const limit = `${num(a.thresholdPct, 0)}%`;
  if (a.kind === "overall" || a.window === null) {
    return `Overall the predictions are off by ${num(a.errorPct, 1)}% on average, more than the ${limit} allowed.`;
  }
  const at = state.start + a.window * state.intervalSeconds;
  return `At ${num(at, 0)} s (window ${num(a.window, 0)}) the network total was off by ${num(a.errorPct, 1)}%, more than the ${limit} allowed.`;
}

export function signed(v: number | null, digits = 1, unit = ""): string {
  if (!isNum(v)) return UNAVAILABLE;
  const text = `${v > 0 ? "+" : ""}${num(v, digits)}`;
  return unit ? `${text} ${unit}` : text;
}

/** The scenario's effect in words: closed links, demand, and the change in
 *  throughput and delay against the baseline. */
export function whatIfSummary(r: WhatIfResult): string {
  const parts: string[] = [];
  if (r.scenario.closeLinks.length > 0) {
    parts.push(`closing ${r.scenario.closeLinks.join(", ")}`);
  }
  if (r.scenario.demandScale !== 1) {
    parts.push(`scaling demand to ${num(r.scenario.demandScale * 100, 0)}%`);
  }
  const what = parts.length ? parts.join(" and ") : "making no change";
  const flow =
    r.delta.completed === 0
      ? "the same number of vehicles finish their trips"
      : `${num(Math.abs(r.delta.completed), 0)} ${r.delta.completed < 0 ? "fewer" : "more"} vehicles finish their trips`;
  const delay = isNum(r.delta.meanDelaySeconds)
    ? `, and mean delay changes by ${signed(r.delta.meanDelaySeconds, 1, "s")}`
    : ", and the change in delay cannot be told (no vehicle finished in one of the two runs)";
  const stuck =
    r.variant.unroutable > 0
      ? ` ${num(r.variant.unroutable, 0)} vehicles would have no route.`
      : "";
  return `Over the next ${num(r.horizonWindows, 0)} window${r.horizonWindows === 1 ? "" : "s"}, ${what}: ${flow}${delay}.${stuck}`;
}
