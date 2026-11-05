/**
 * The plain-words metric glossary, derived from the metric catalog so the
 * Research lab view and docs/product/metric-glossary.md cannot drift from it
 * (metricGlossary.test.tsx compares the file with glossaryMarkdown()).
 *
 * Nothing here computes a metric. Wording is the catalog's `plain` text where
 * it has one, otherwise its `description`; the caveats restate flags the
 * catalog already encodes (warm-up, "no data yet", geometry scope).
 */
import {
  ANALYSIS_GROUP,
  ANALYSIS_METRICS,
  METRICS,
  METRIC_GROUPS,
} from "./catalog";
import type { MetricDef, MetricGroupId } from "./catalog";

export type GlossaryGroupId = MetricGroupId | typeof ANALYSIS_GROUP.id;

/** Live-metric groups followed by the analysis group. */
export const GLOSSARY_GROUPS: {
  id: GlossaryGroupId;
  title: string;
  blurb: string;
}[] = [...METRIC_GROUPS, ANALYSIS_GROUP];

export interface GlossaryEntry {
  key: string;
  label: string;
  unit: string;
  group: GlossaryGroupId;
  text: string;
  caveats: string[];
}

export function caveatsFor(def: MetricDef): string[] {
  const out: string[] = [];
  if (def.postWarmup) out.push("Counts only after the warm-up period.");
  if (def.needsExits)
    out.push("Shows “—” until a vehicle has exited after the warm-up.");
  if (def.nullText)
    out.push(`Shows “${def.nullText}” when nothing has been observed.`);
  if (def.appliesTo && def.appliesTo.length === 1)
    out.push(
      def.appliesTo[0] === "fixed_time_signal"
        ? "Measured for signals only."
        : "Measured for roundabouts only.",
    );
  if (def.withinGeometryOnly)
    out.push("Compare only between runs of the same layout and scenario.");
  return out;
}

export function glossaryEntries(): GlossaryEntry[] {
  const live: GlossaryEntry[] = METRICS.map((def) => ({
    key: def.key,
    label: def.label,
    unit: def.unit,
    group: def.group,
    text: def.plain ?? def.description,
    caveats: caveatsFor(def),
  }));
  const analysis: GlossaryEntry[] = ANALYSIS_METRICS.map((def) => ({
    key: def.key,
    label: def.label,
    unit: def.unit,
    group: ANALYSIS_GROUP.id,
    text: def.plain,
    caveats: [],
  }));
  return [...live, ...analysis];
}

/** Entries whose label, key or wording contains every word of `query`. */
export function filterGlossary(
  entries: GlossaryEntry[],
  query: string,
): GlossaryEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return entries;
  return entries.filter((e) => {
    const hay = `${e.label} ${e.key} ${e.text}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

/** docs/product/metric-glossary.md, byte for byte. */
export function glossaryMarkdown(): string {
  const entries = glossaryEntries();
  const lines: string[] = [
    "# Metric glossary",
    "",
    "<!-- Generated from frontend/src/metrics/catalog.ts by glossaryMarkdown() in",
    "     frontend/src/metrics/glossary.ts. Do not edit by hand: change the catalog,",
    "     then run `UPDATE_GLOSSARY=1 npx vitest run src/test/metricGlossary.test.tsx`. -->",
    "",
    "Every measure UrbanFlow reports, in everyday words. Values always come from the",
    "simulation; nothing here is a real-world measurement.",
    "",
  ];
  for (const group of GLOSSARY_GROUPS) {
    lines.push(`## ${group.title}`, "", group.blurb, "");
    for (const e of entries.filter((x) => x.group === group.id)) {
      const unit = e.unit ? ` (${e.unit})` : "";
      lines.push(`### ${e.label}${unit}`, "", `\`${e.key}\``, "", e.text, "");
      for (const c of e.caveats) lines.push(`- ${c}`);
      if (e.caveats.length) lines.push("");
    }
  }
  return lines.join("\n").replace(/\n+$/, "\n");
}
