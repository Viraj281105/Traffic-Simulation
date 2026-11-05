import { getRlComparison } from "../rlcompare/api";
import { isEvalDocument } from "./rlText";
import type { RlEvalDocument } from "./types";

/** GET /api/v3/rl/comparisons/{id}: the junction-level RL comparison, shown
 *  next to the network one. */
export { getRlComparison };

/**
 * The network evaluation document has no endpoint yet: it is the JSON that
 * backend/src/rl/network_eval.py (compare_network) writes, and the page opens
 * it from a file or pasted text. Throws a plain sentence when the text is not
 * that document.
 */
export function parseEvalDocument(text: string): RlEvalDocument {
  let doc: unknown;
  try {
    doc = JSON.parse(text);
  } catch {
    throw new Error("That is not valid JSON.");
  }
  if (!isEvalDocument(doc)) {
    throw new Error(
      "That is not a network RL evaluation (format urbanflow-rl-eval with seeds, policies and paired_comparisons).",
    );
  }
  return doc;
}
