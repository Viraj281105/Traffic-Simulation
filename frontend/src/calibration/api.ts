import { V2, postJson } from "../netcommon/api";
import type { CalibrationReport, CountsValidation, FitInputs } from "./types";

const BASE = `${V2}/calibration/network-fit`;

function fitBody(inputs: FitInputs): Record<string, unknown> {
  return {
    graph: inputs.graph,
    flows: inputs.flows,
    countsCsv: inputs.countsCsv,
    options: { budget: inputs.budget ?? 150, seed: inputs.seed ?? 1 },
    sim: { duration: inputs.duration ?? 600, seed: inputs.seed ?? 1 },
  };
}

/** POST /api/v2/calibration/network-fit/validate-counts */
export function validateCounts(
  graph: Record<string, unknown>,
  countsCsv: string,
): Promise<CountsValidation> {
  return postJson(`${BASE}/validate-counts`, { graph, countsCsv });
}

/** POST /api/v2/calibration/network-fit */
export function fitNetwork(inputs: FitInputs): Promise<CalibrationReport> {
  return postJson(BASE, fitBody(inputs));
}

/** POST /api/v2/calibration/network-fit/recalibrate: warm-started from the
 *  parameters of an earlier report (`parameters.fitted`). */
export function recalibrateNetwork(
  inputs: FitInputs,
  previous: Record<string, number>,
  windowIntervals?: number,
): Promise<CalibrationReport> {
  return postJson(`${BASE}/recalibrate`, {
    ...fitBody(inputs),
    previous,
    ...(windowIntervals ? { windowIntervals } : {}),
  });
}
