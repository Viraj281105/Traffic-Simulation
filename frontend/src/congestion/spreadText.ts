import { isNum, num } from "../netcommon/format";
import type { CongestionResult } from "./types";

function plural(n: number, one: string, many: string): string {
  return `${num(n, 0)} ${n === 1 ? one : many}`;
}

/** The spread of congestion in plain words. Every number comes from the
 *  server's `spread`, `spillback` and `threshold` fields. */
export function spreadSummary(r: CongestionResult): string[] {
  const { spread, spillback } = r;
  const level = `${num(r.threshold * 100, 0)}%`;
  const out: string[] = [];
  if (spread.congestedLinks === 0 || spread.origin === null) {
    out.push(
      `No link stayed more than ${level} full for ${num(r.minHoldSeconds, 0)} s, so no congestion spread was found.`,
    );
  } else {
    const first = spread.order[0] as (typeof spread.order)[number] | undefined;
    const when = first ? ` at ${num(first.onsetSeconds, 0)} s` : "";
    out.push(
      `Congestion first formed on ${spread.origin}${when}. By the end ${num(spread.congestedLinks, 0)} of ${plural(spread.totalLinks, "link", "links")} had been more than ${level} full for ${num(r.minHoldSeconds, 0)} s or longer.`,
    );
    if (spread.congestedLinks > 1) {
      let reach = `It took ${num(spread.durationSeconds, 0)} s to spread, up to ${plural(spread.maxHops, "link", "links")} from where it started and ${num(spread.maxDistanceFromOriginMeters, 0)} m away.`;
      if (isNum(spread.meanSpeedMps)) {
        reach += ` On average the front moved at ${num(spread.meanSpeedMps, 1)} m/s.`;
      }
      if (isNum(spread.upstreamSpeedMps)) {
        reach += ` Where a queue grew backwards along the road it moved at ${num(spread.upstreamSpeedMps, 1)} m/s.`;
      }
      if (isNum(spread.downstreamSpeedMps)) {
        reach += ` Where it moved forwards it travelled at ${num(spread.downstreamSpeedMps, 1)} m/s.`;
      }
      out.push(reach);
    }
  }
  const s = spillback.summary;
  if (s.events === 0) {
    out.push("No queue backed up into the link behind it (no spillback).");
  } else {
    out.push(
      `Queues backed up (spillback) ${plural(s.events, "time", "times")} on ${plural(s.linksAffected, "link", "links")}, blocking traffic for ${num(s.totalBlockedSeconds, 0)} s in total. The longest lasted ${num(s.longestSeconds, 0)} s and the blockage reached back ${plural(s.maxChainLength, "link", "links")}.`,
    );
  }
  return out;
}
