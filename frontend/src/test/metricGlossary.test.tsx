/**
 * The plain-words glossary: it shows every catalog metric, filters, is
 * accessible, matches docs/product/metric-glossary.md, and the catalog covers
 * every numeric key the backend collector emits
 * (shared/metrics/collector-metric-keys.json, kept equal to the collector by
 * backend/tests/metrics/test_metric_key_parity.py).
 *
 * Regenerate the docs page after a catalog change with
 *   UPDATE_GLOSSARY=1 npx vitest run src/test/metricGlossary.test.tsx
 */
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { MetricGlossary } from "../components/research/MetricGlossary";
import { METRICS } from "../metrics/catalog";
import {
  caveatsFor,
  filterGlossary,
  glossaryEntries,
  glossaryMarkdown,
} from "../metrics/glossary";
import { axeViolations } from "./axe";

const ROOT = resolve(__dirname, "../../..");
const DOC = resolve(ROOT, "docs/product/metric-glossary.md");
const KEYS = JSON.parse(
  readFileSync(
    resolve(ROOT, "shared/metrics/collector-metric-keys.json"),
    "utf8",
  ),
) as { numeric: string[]; excluded: Record<string, string> };

describe("metric glossary", () => {
  it("lists every catalog metric once, in plain words", () => {
    render(<MetricGlossary />);
    const entries = glossaryEntries();
    expect(entries).toHaveLength(METRICS.length);
    expect(new Set(entries.map((e) => e.key)).size).toBe(METRICS.length);
    for (const e of entries) {
      expect(e.text.trim().length).toBeGreaterThan(20);
      expect(screen.getByText(e.key, { selector: "code" })).toBeTruthy();
    }
  });

  it("filters by every word, and says when nothing matches", async () => {
    const user = userEvent.setup();
    render(<MetricGlossary />);
    const box = screen.getByRole("searchbox");
    await user.type(box, "fuel");
    expect(screen.getByRole("status").textContent).toMatch(
      /^\d+ of \d+ measures$/,
    );
    expect(screen.getByText("estimatedFuelLitersTotal")).toBeTruthy();
    expect(screen.queryByText("averageDelay")).toBeNull();
    await user.clear(box);
    await user.type(box, "zzzzqqq");
    expect(screen.getByRole("status").textContent).toBe(
      "No measure matches that search.",
    );
  });

  it("filterGlossary needs all words and ignores case", () => {
    const entries = glossaryEntries();
    expect(filterGlossary(entries, "")).toHaveLength(entries.length);
    expect(filterGlossary(entries, "QUEUE signals").length).toBeGreaterThan(0);
    expect(filterGlossary(entries, "queue zzzz")).toHaveLength(0);
  });

  it("carries the catalog's caveats", () => {
    const delay = METRICS.find((m) => m.key === "averageDelay")!;
    expect(caveatsFor(delay)).toContain(
      "Shows “—” until a vehicle has exited after the warm-up.",
    );
    const pet = METRICS.find((m) => m.key === "minPET")!;
    expect(caveatsFor(pet)).toContain("Measured for signals only.");
  });

  it("has no automatically detectable accessibility violations (axe)", async () => {
    const { container } = render(<MetricGlossary />);
    expect(await axeViolations(container)).toEqual([]);
  });

  it("long wording stays inside the entry (no truncation by script)", () => {
    const longest = Math.max(...glossaryEntries().map((e) => e.text.length));
    render(<MetricGlossary />);
    const text = glossaryEntries().find((e) => e.text.length === longest)!.text;
    expect(screen.getByText(text)).toBeTruthy();
  });

  it("matches docs/product/metric-glossary.md", () => {
    const expected = glossaryMarkdown();
    if (process.env.UPDATE_GLOSSARY === "1") writeFileSync(DOC, expected);
    expect(readFileSync(DOC, "utf8").replace(/\r\n/g, "\n")).toBe(expected);
  });
});

describe("catalog ↔ backend metric keys", () => {
  const catalogKeys = new Set<string>(METRICS.map((m) => m.key));

  it("describes every numeric collector key or excludes it with a reason", () => {
    const missing = KEYS.numeric.filter(
      (k) => !catalogKeys.has(k) && !(k in KEYS.excluded),
    );
    expect(
      missing,
      `add to metrics/catalog.ts or the exclusion list: ${missing.join(", ")}`,
    ).toEqual([]);
  });

  it("does not describe a metric the collector no longer emits", () => {
    const stale = [...catalogKeys].filter((k) => !KEYS.numeric.includes(k));
    expect(stale).toEqual([]);
  });

  it("explains every exclusion", () => {
    for (const [key, reason] of Object.entries(KEYS.excluded)) {
      expect(catalogKeys.has(key), key).toBe(false);
      expect(reason.length, key).toBeGreaterThan(20);
    }
  });
});
