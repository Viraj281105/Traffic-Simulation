import { interval, isNum, num, pValueText, withUnit } from "../insights/format";
import type { ComparisonResult, Eligibility } from "./types";

export interface ComparisonWords {
  headline: string;
  sentence: string;
  confidence: string;
  pValue: string;
  method: string;
}

/** The wording of one comparison. Every number comes from the result. */
export function describeComparison(c: ComparisonResult): ComparisonWords {
  const level = `${String(Math.round(c.confidenceLevel * 100))}%`;
  const gap = Math.abs(c.meanDifference);
  const ci = interval(c.ci, c.metric.unit);
  const metric = c.metric.label.toLowerCase();
  const winner = c.verdict === "a_better" ? c.a : c.b;
  const loser = c.verdict === "a_better" ? c.b : c.a;
  const direction = c.metric.lowerIsBetter ? "lower" : "higher";

  let headline: string;
  let sentence: string;
  if (c.verdict === "no_clear_difference") {
    headline = `No clear winner between ${c.a.label} and ${c.b.label}`;
    sentence = `The average gap in ${metric} was ${withUnit(gap, c.metric.unit)}, but the ${level} interval (${ci}) includes zero, so the gap could be chance.`;
  } else {
    headline = `${winner.label} beats ${loser.label}`;
    sentence = `${winner.label} had ${withUnit(gap, c.metric.unit)} ${direction} ${metric} than ${loser.label} on average. We are ${level} confident the true gap is between ${ci}.`;
  }

  const chance = isNum(c.pValue)
    ? `If the two strategies were really equal, a gap this large would appear by chance about ${num(c.pValue * 100, c.pValue < 0.01 ? 2 : 1)}% of the time.`
    : "The p-value is not available.";

  return {
    headline,
    sentence,
    confidence: `${level} confidence interval for the gap: ${ci}.`,
    pValue: `${pValueText(c.pValue)}. ${chance}`,
    method: `Method: ${c.method.test} on ${String(c.pairs)} paired observations. ${c.method.pairing}. Interval: ${c.method.interval}.`,
  };
}

export const ELIGIBILITY_WORDS: Record<
  Eligibility,
  { label: string; text: string }
> = {
  eligible: {
    label: "Eligible",
    text: "Enough evidence to report as a finding.",
  },
  indicative: {
    label: "Indicative",
    text: "A direction worth following up, not yet a firm finding.",
  },
  exploratory: {
    label: "Exploratory",
    text: "Too little data to rely on; use it to plan the next run.",
  },
};
