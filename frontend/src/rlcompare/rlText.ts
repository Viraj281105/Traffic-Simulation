import type { RlComparison } from "./types";

export function rlHeadline(c: RlComparison): string {
  if (c.verdict === "no_clear_difference")
    return `No clear difference between ${c.rl.label} and ${c.fixedTime.label}`;
  return c.verdict === "rl_better"
    ? `${c.rl.label} beats ${c.fixedTime.label}`
    : `${c.fixedTime.label} beats ${c.rl.label}`;
}
