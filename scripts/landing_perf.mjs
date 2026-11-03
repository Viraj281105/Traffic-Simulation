#!/usr/bin/env node
/**
 * Landing-page performance probe (docs/engineering/PERFORMANCE_BASELINE.md).
 *
 * Drives a headless Chromium (Edge or Chrome) over the DevTools protocol
 * against a *production* build served by `vite preview`, and reports, per run:
 *
 *   - load: LCP, CLS, long tasks and bytes transferred up to 6 s after load;
 *   - idle cost at four scroll positions (hero, story, compare, finale):
 *     main-thread task/script/layout time and requestAnimationFrame and timer
 *     callbacks per second, measured over a fixed window with no input.
 *
 * Usage (frontend built and previewed on :4173 first):
 *   node scripts/landing_perf.mjs [--url http://localhost:4173/] [--runs 3]
 *                                 [--cpu 1] [--browser <path>] [--json out.json]
 *
 * Needs Node 22+ (global WebSocket). Numbers depend on the machine, so only
 * compare runs taken on the same machine with the same flags.
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// --flag value pairs; a flag followed by another flag (or nothing) is "true".
const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const flag = process.argv[i];
  if (!flag.startsWith("--")) continue;
  const next = process.argv[i + 1];
  args[flag.slice(2)] = next && !next.startsWith("--") ? next : "true";
  if (args[flag.slice(2)] === next) i++;
}
const URL_ = args.url ?? "http://localhost:4173/";
const RUNS = Number(args.runs ?? 3);
const CPU = Number(args.cpu ?? 1);
const WINDOW_MS = Number(args.window ?? 4000);
const BROWSER =
  args.browser ??
  (process.platform === "win32"
    ? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    : "google-chrome");
const PORT = 9333;

// Counts rAF and timer callbacks, and records LCP / CLS / long tasks.
const PROBE = `(() => {
  const c = (window.__perf = { raf: 0, timer: 0, lcp: 0, cls: 0, longTasks: 0, longTaskMs: 0 });
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => raf((t) => { c.raf++; cb(t); });
  const si = window.setInterval.bind(window);
  window.setInterval = (cb, ms, ...a) => si((...x) => { c.timer++; cb(...x); }, ms, ...a);
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) c.lcp = e.startTime; })
      .observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) c.cls += e.value; })
      .observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) { c.longTasks++; c.longTaskMs += e.duration; } })
      .observe({ type: "longtask", buffered: true });
  } catch {}
})();`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function cdpConnect() {
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (
        await fetch(`http://127.0.0.1:${PORT}/json/list`)
      ).json();
      const page = list.find((t) => t.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(200);
  }
  throw new Error("browser did not expose a page target");
}

function client(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const waiting = new Map();
  const listeners = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && waiting.has(msg.id)) {
      const { resolve, reject } = waiting.get(msg.id);
      waiting.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    } else if (msg.method) for (const l of listeners) l(msg);
  };
  return new Promise((res) => {
    ws.onopen = () =>
      res({
        send: (method, params = {}) =>
          new Promise((resolve, reject) => {
            const n = ++id;
            waiting.set(n, { resolve, reject });
            ws.send(JSON.stringify({ id: n, method, params }));
          }),
        on: (fn) => listeners.push(fn),
        close: () => ws.close(),
      });
  });
}

async function metrics(cdp) {
  const { metrics: list } = await cdp.send("Performance.getMetrics");
  return Object.fromEntries(list.map((m) => [m.name, m.value]));
}

async function evaluate(cdp, expression) {
  const r = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  return r.result.value;
}

/** Self time per function over one idle window (--profile), top 15. */
async function profileWindow(cdp) {
  await cdp.send("Profiler.enable");
  await cdp.send("Profiler.setSamplingInterval", { interval: 200 });
  await cdp.send("Profiler.start");
  await sleep(WINDOW_MS);
  const { profile } = await cdp.send("Profiler.stop");
  const byId = new Map(profile.nodes.map((n) => [n.id, n]));
  const self = new Map();
  const dt = profile.timeDeltas;
  profile.samples.forEach((id, i) => {
    const f = byId.get(id).callFrame;
    const file = f.url.split("/").pop() || "(native)";
    const key = `${f.functionName || "(anonymous)"} ${file}:${f.lineNumber + 1}`;
    self.set(key, (self.get(key) ?? 0) + (dt[i] ?? 0) / 1000);
  });
  return [...self.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 15)
    .map(([k, ms]) => `${(ms / (WINDOW_MS / 1000)).toFixed(1)} ms/s  ${k}`);
}

async function idleWindow(cdp) {
  if (args.profile) return profileWindow(cdp);
  const before = await metrics(cdp);
  const c0 = await evaluate(cdp, "({...window.__perf})");
  await sleep(WINDOW_MS);
  const after = await metrics(cdp);
  const c1 = await evaluate(cdp, "({...window.__perf})");
  const s = WINDOW_MS / 1000;
  const per = (k) => ((after[k] - before[k]) * 1000) / s; // ms busy per second
  return {
    taskMsPerSec: +per("TaskDuration").toFixed(1),
    scriptMsPerSec: +per("ScriptDuration").toFixed(1),
    layoutMsPerSec: +per("LayoutDuration").toFixed(2),
    styleMsPerSec: +per("RecalcStyleDuration").toFixed(2),
    layoutsPerSec: +((after.LayoutCount - before.LayoutCount) / s).toFixed(1),
    rafPerSec: +((c1.raf - c0.raf) / s).toFixed(1),
    timerPerSec: +((c1.timer - c0.timer) / s).toFixed(1),
    heapMB: +(after.JSHeapUsedSize / 1048576).toFixed(1),
  };
}

async function oneRun() {
  const profile = mkdtempSync(join(tmpdir(), "landing-perf-"));
  const browser = spawn(
    BROWSER,
    [
      "--headless=new",
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      "--window-size=1440,900",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-extensions",
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  try {
    const cdp = await client(await cdpConnect());
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Performance.enable");
    await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
    if (CPU > 1)
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: CPU });
    await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: PROBE });
    let bytes = 0;
    const byType = {};
    const types = new Map();
    cdp.on((m) => {
      if (m.method === "Network.responseReceived")
        types.set(m.params.requestId, m.params.type);
      if (m.method === "Network.loadingFinished") {
        bytes += m.params.encodedDataLength;
        const t = types.get(m.params.requestId) ?? "Other";
        byType[t] = (byType[t] ?? 0) + m.params.encodedDataLength;
      }
    });
    const loaded = new Promise((r) =>
      cdp.on((m) => m.method === "Page.loadEventFired" && r()),
    );
    const t0 = Date.now();
    await cdp.send("Page.navigate", { url: URL_ });
    await loaded;
    const loadMs = Date.now() - t0;
    await sleep(6000);
    const load = await evaluate(cdp, "({...window.__perf})");
    const nav = await evaluate(
      cdp,
      `(() => { const n = performance.getEntriesByType("navigation")[0];
        const fcp = performance.getEntriesByName("first-contentful-paint")[0];
        return { ttfb: n.responseStart, dcl: n.domContentLoadedEventEnd, fcp: fcp ? fcp.startTime : null,
                 domNodes: document.getElementsByTagName("*").length, canvases: document.querySelectorAll("canvas").length }; })()`,
    );
    const result = {
      loadEventMs: loadMs,
      ttfbMs: +nav.ttfb.toFixed(1),
      fcpMs: nav.fcp && +nav.fcp.toFixed(0),
      lcpMs: +load.lcp.toFixed(0),
      dclMs: +nav.dcl.toFixed(0),
      cls: +load.cls.toFixed(4),
      longTasksTo6s: load.longTasks,
      longTaskMsTo6s: +load.longTaskMs.toFixed(0),
      transferKB: +(bytes / 1024).toFixed(1),
      transferKBByType: Object.fromEntries(
        Object.entries(byType).map(([k, v]) => [k, +(v / 1024).toFixed(1)]),
      ),
      domNodes: nav.domNodes,
      canvases: nav.canvases,
      idle: {},
    };
    // Section anchors where the page has them; otherwise (older landing
    // builds) the same fraction of the page height.
    const at = (id, frac, extra = "0") =>
      `(document.getElementById('${id}')?.offsetTop ?? document.body.scrollHeight * ${frac}) + ${extra}`;
    const spots = {
      hero: "0",
      story: at("story", 0.2, "innerHeight"),
      compare: at("compare", 0.5),
      finale: "document.body.scrollHeight",
    };
    for (const [name, y] of Object.entries(spots)) {
      await evaluate(cdp, `window.scrollTo(0, ${y})`);
      await sleep(1500); // let reveals and scroll-linked motion settle
      result.idle[name] = await idleWindow(cdp);
    }
    cdp.close();
    return result;
  } finally {
    browser.kill();
    await sleep(500);
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {}
  }
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
};

const runs = [];
for (let i = 0; i < RUNS; i++) {
  runs.push(await oneRun());
  process.stderr.write(`run ${i + 1}/${RUNS} done\n`);
}
const pick = (f) => median(runs.map(f));
const summary = {
  url: URL_,
  runs: RUNS,
  cpuThrottle: CPU,
  windowMs: WINDOW_MS,
  lcpMs: pick((r) => r.lcpMs),
  fcpMs: pick((r) => r.fcpMs),
  cls: pick((r) => r.cls),
  longTaskMsTo6s: pick((r) => r.longTaskMsTo6s),
  transferKB: pick((r) => r.transferKB),
  domNodes: pick((r) => r.domNodes),
  canvases: pick((r) => r.canvases),
  idle: Object.fromEntries(
    Object.keys(runs[0].idle).map((spot) => [
      spot,
      Object.fromEntries(
        Object.keys(runs[0].idle[spot]).map((k) => [
          k,
          pick((r) => r.idle[spot][k]),
        ]),
      ),
    ]),
  ),
};
console.log(JSON.stringify({ summary, runs }, null, 2));
if (args.json)
  writeFileSync(args.json, JSON.stringify({ summary, runs }, null, 2));
