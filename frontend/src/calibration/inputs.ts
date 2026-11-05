import type { FitInputs, FlowInput } from "./types";

export function parseJson(text: string, what: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`The ${what} is not valid JSON.`);
  }
}

export function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Reads the three text boxes into request inputs, or says what is wrong. */
export function readInputs(
  graphText: string,
  flowsText: string,
  countsCsv: string,
): FitInputs {
  const graph = parseJson(graphText, "network");
  if (!isRecord(graph)) throw new Error("The network must be a JSON object.");
  const flows = parseJson(flowsText, "demand list");
  if (!Array.isArray(flows) || flows.length === 0) {
    throw new Error(
      "The demand list must be a JSON list with at least one flow.",
    );
  }
  if (!countsCsv.trim()) throw new Error("Paste or load the counts file.");
  return { graph, flows: flows as FlowInput[], countsCsv };
}
