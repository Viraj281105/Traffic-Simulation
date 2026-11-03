#!/usr/bin/env node
/**
 * Bundle-size budgets for the production build (docs/engineering/PERFORMANCE_BUDGETS.md).
 *
 * Reads frontend/dist after `npm run build` and sums, per HTML entry, the
 * gzip size of every script and stylesheet the document loads up front
 * (<script src>, <link rel=modulepreload|stylesheet>). Lazy chunks are
 * checked by name. Exits 1 when any budget is exceeded.
 *
 * Usage: node scripts/check_bundle_budgets.mjs [--dist frontend/dist]
 */
import { readFileSync, readdirSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const i = process.argv.indexOf("--dist");
const DIST = i > 0 ? process.argv[i + 1] : "frontend/dist";

// gzip KiB. Set from the 2026-10-29 baseline (PERFORMANCE_BUDGETS.md) with
// roughly 10 % headroom; raise one only with a reason in that document.
const BUDGETS = {
  "landing initial JS": 137, // measured 124.6
  "landing initial CSS": 16, // 14.4
  "dashboard initial JS": 213, // 193.5
  "dashboard initial CSS": 33, // 30.2
  "landing scene chunk": 78, // 70.7
  "largest lazy chunk": 130, // 117.5 (Recharts)
};

const gz = (file) => gzipSync(readFileSync(join(DIST, file))).length / 1024;

function initial(html) {
  const doc = readFileSync(join(DIST, html), "utf8");
  const refs = [
    ...doc.matchAll(/<script[^>]*\bsrc="\/(assets\/[^"]+)"/g),
    ...doc.matchAll(/<link[^>]*\bhref="\/(assets\/[^"]+)"/g),
  ].map((m) => m[1]);
  const unique = [...new Set(refs)];
  const sum = (ext) =>
    unique.filter((f) => f.endsWith(ext)).reduce((a, f) => a + gz(f), 0);
  return { js: sum(".js"), css: sum(".css"), files: unique };
}

const landing = initial("index.html");
const dashboard = initial("app.html");
const eager = new Set([...landing.files, ...dashboard.files]);
const lazy = readdirSync(join(DIST, "assets"))
  .map((f) => `assets/${f}`)
  .filter((f) => f.endsWith(".js") && !eager.has(f));
const scene = lazy.find((f) => /\/scene-[^/]+\.js$/.test(f));
const largest = lazy
  .filter((f) => f !== scene)
  .map((f) => [f, gz(f)])
  .sort((a, b) => b[1] - a[1])[0];

const measured = {
  "landing initial JS": landing.js,
  "landing initial CSS": landing.css,
  "dashboard initial JS": dashboard.js,
  "dashboard initial CSS": dashboard.css,
  "landing scene chunk": scene ? gz(scene) : 0,
  "largest lazy chunk": largest ? largest[1] : 0,
};

let failed = 0;
for (const [name, budget] of Object.entries(BUDGETS)) {
  const v = measured[name];
  const ok = v <= budget;
  if (!ok) failed++;
  const note =
    name === "largest lazy chunk" && largest ? `  (${largest[0]})` : "";
  console.log(
    `${ok ? "ok  " : "OVER"} ${name.padEnd(22)} ${v.toFixed(1).padStart(7)} KiB gzip / budget ${budget} KiB${note}`,
  );
}
process.exit(failed ? 1 : 0);
