import type { SuiteResult } from "../../services/v3/stress";

/** Total failures per strategy, summed over every failure rule. */
export function failureSums(result: SuiteResult): Record<string, number> {
  const sums: Record<string, number> = {};
  for (const s of result.strategies) {
    sums[s] = Object.values(result.failureTotals[s] ?? {}).reduce<number>(
      (a, b) => a + (b ?? 0),
      0,
    );
  }
  return sums;
}
