import {
  type ComparisonDelta,
  type ScenarioSimulationResult,
} from "./planningTypes";

/**
 * Calculates absolute and percentage change from baseline.
 * lowerIsBetter: true for waiting time, delay, queue, collisions.
 * lowerIsBetter: false for throughput.
 */
export function calculateDelta(
  value: number,
  baselineValue: number,
  lowerIsBetter: boolean,
): ComparisonDelta {
  const absolute = value - baselineValue;
  let percentage: number | null = null;
  if (baselineValue !== 0) {
    percentage = ((value - baselineValue) / baselineValue) * 100;
  }

  let direction: "better" | "worse" | "neutral";
  if (Math.abs(absolute) < 0.001) {
    direction = "neutral";
  } else if (lowerIsBetter) {
    direction = absolute < 0 ? "better" : "worse";
  } else {
    direction = absolute > 0 ? "better" : "worse";
  }

  return {
    absolute: Number(absolute.toFixed(2)),
    percentage: percentage !== null ? Number(percentage.toFixed(1)) : null,
    direction,
  };
}

/**
 * Formats delta badge text, e.g. "+12.4% (+2.1s)"
 */
export function formatDeltaText(
  delta: ComparisonDelta,
  unit: string = "",
): string {
  const sign = delta.absolute > 0 ? "+" : "";
  const absStr = `${sign}${String(delta.absolute)}${unit ? ` ${unit}` : ""}`;
  if (delta.percentage !== null) {
    const pctSign = delta.percentage > 0 ? "+" : "";
    return `${pctSign}${String(delta.percentage)}% (${absStr})`;
  }
  return absStr;
}

/**
 * Builds exportable CSV string comparing scenarios against baseline.
 */
export function exportComparisonCsv(
  experimentName: string,
  baseline: ScenarioSimulationResult,
  results: ScenarioSimulationResult[],
): string {
  const headers = [
    "Scenario Name",
    "Role",
    "Controller Strategy",
    "Volume Scale",
    "Duration (s)",
    "Mean Delay (s)",
    "Delay Delta (s)",
    "Delay Delta (%)",
    "Mean Wait Time (s)",
    "Wait Delta (s)",
    "Throughput (veh)",
    "Throughput Delta (%)",
    "Mean Queue (veh)",
    "Queue Delta (%)",
    "Max Queue (veh)",
    "Max Queue Delta (%)",
    "Collisions",
  ];

  const rows: string[][] = [
    [`Experiment: ${experimentName}`],
    [`Generated: ${new Date().toISOString()}`],
    [],
    headers,
  ];

  for (const res of results) {
    const isBaseline = res.scenarioId === baseline.scenarioId;
    const delayDelta = calculateDelta(
      res.metrics.averageDelay,
      baseline.metrics.averageDelay,
      true,
    );
    const waitDelta = calculateDelta(
      res.metrics.averageWaitTime,
      baseline.metrics.averageWaitTime,
      true,
    );
    const tpDelta = calculateDelta(
      res.metrics.throughput,
      baseline.metrics.throughput,
      false,
    );
    const qDelta = calculateDelta(
      res.metrics.averageQueueLength,
      baseline.metrics.averageQueueLength,
      true,
    );
    const maxQDelta = calculateDelta(
      res.metrics.maxQueueLength,
      baseline.metrics.maxQueueLength,
      true,
    );

    rows.push([
      `"${res.name.replace(/"/g, '""')}"`,
      isBaseline ? "Baseline" : "Intervention",
      res.strategy,
      `x${String(res.volumeScale)}`,
      String(res.duration),
      res.metrics.averageDelay.toFixed(2),
      isBaseline
        ? "—"
        : `${delayDelta.absolute > 0 ? "+" : ""}${delayDelta.absolute.toFixed(2)}`,
      isBaseline
        ? "—"
        : delayDelta.percentage !== null
          ? `${delayDelta.percentage > 0 ? "+" : ""}${delayDelta.percentage.toFixed(1)}%`
          : "—",
      res.metrics.averageWaitTime.toFixed(2),
      isBaseline
        ? "—"
        : `${waitDelta.absolute > 0 ? "+" : ""}${waitDelta.absolute.toFixed(2)}`,
      String(res.metrics.throughput),
      isBaseline
        ? "—"
        : tpDelta.percentage !== null
          ? `${tpDelta.percentage > 0 ? "+" : ""}${tpDelta.percentage.toFixed(1)}%`
          : "—",
      res.metrics.averageQueueLength.toFixed(2),
      isBaseline
        ? "—"
        : qDelta.percentage !== null
          ? `${qDelta.percentage > 0 ? "+" : ""}${qDelta.percentage.toFixed(1)}%`
          : "—",
      String(res.metrics.maxQueueLength),
      isBaseline
        ? "—"
        : maxQDelta.percentage !== null
          ? `${maxQDelta.percentage > 0 ? "+" : ""}${maxQDelta.percentage.toFixed(1)}%`
          : "—",
      String(res.metrics.collisionCount),
    ]);
  }

  return rows.map((r) => r.join(",")).join("\n") + "\n";
}
