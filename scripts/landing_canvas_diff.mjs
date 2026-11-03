#!/usr/bin/env node
/**
 * Pixel comparison of the landing page's seven canvases between two builds
 * (docs/engineering/PERFORMANCE_BASELINE.md §4).
 *
 * Captures raw RGBA from each canvas in deterministic states and compares:
 *   - hero, story and finale under emulated prefers-reduced-motion (their
 *     clocks and cameras stand still);
 *   - the four Compare tiles in normal motion, paused and scrubbed to t = 20 s
 *     (this path draws from the cached ground layer).
 *
 * Usage (both builds served by `vite preview`, e.g. base on :4174):
 *   node scripts/landing_canvas_diff.mjs --base http://localhost:4174/ \
 *        --head http://localhost:4173/ [--browser <path>]
 *
 * Exits 1 if any canvas differs. Needs Node 22+ (global WebSocket).
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = {};
for (let i = 2; i < process.argv.length; i += 2)
  args[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
if (!args.base || !args.head) {
  console.error("usage: --base <url> --head <url> [--browser <path>]");
  process.exit(2);
}
const BROWSER =
  args.browser ??
  (process.platform === "win32"
    ? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
    : "google-chrome");
const PORT = 9334;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function session(url, reduced) {
  const profile = mkdtempSync(join(tmpdir(), "canvas-diff-"));
  const browser = spawn(
    BROWSER,
    [
      "--headless=new",
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      "--window-size=1440,900",
      "--disable-gpu",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  try {
    let wsUrl;
    for (let i = 0; i < 75 && !wsUrl; i++) {
      try {
        const list = await (
          await fetch(`http://127.0.0.1:${PORT}/json/list`)
        ).json();
        wsUrl = list.find((t) => t.type === "page")?.webSocketDebuggerUrl;
      } catch {}
      if (!wsUrl) await sleep(200);
    }
    if (!wsUrl) throw new Error("browser did not start");
    const ws = new WebSocket(wsUrl);
    await new Promise((r) => (ws.onopen = r));
    let id = 0;
    const waiting = new Map();
    ws.onmessage = (m) => {
      const d = JSON.parse(m.data);
      if (d.id) waiting.get(d.id)?.(d);
    };
    const send = (method, params = {}) =>
      new Promise((r) => {
        const n = ++id;
        waiting.set(n, r);
        ws.send(JSON.stringify({ id: n, method, params }));
      });
    const evaluate = async (expression) =>
      (
        await send("Runtime.evaluate", {
          expression,
          returnByValue: true,
          awaitPromise: true,
        })
      ).result.result.value;
    if (reduced)
      await send("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-reduced-motion", value: "reduce" }],
      });
    await send("Page.navigate", { url });
    await sleep(5000);
    const grab = (sel) =>
      evaluate(`(() => { const c = document.querySelector(${JSON.stringify(sel)});
        if (!c) return null;
        const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let s = ''; for (let i = 0; i < d.length; i += 4096) s += String.fromCharCode.apply(null, d.subarray(i, i + 4096));
        return { w: c.width, h: c.height, b64: btoa(s) }; })()`);
    const out = {};
    if (reduced) {
      const spots = [
        ["hero", ".hero-stage__canvas", "0"],
        [
          "story",
          ".story__canvas",
          "document.getElementById('story').offsetTop + innerHeight",
        ],
        ["finale", ".finale__canvas", "document.body.scrollHeight"],
      ];
      for (const [name, sel, y] of spots) {
        await evaluate(`window.scrollTo(0, ${y})`);
        await sleep(1500);
        out[name] = await grab(sel);
      }
    } else {
      await evaluate(
        "window.scrollTo(0, document.getElementById('compare').offsetTop)",
      );
      await sleep(2500); // playing: the still tile cameras build their cache
      await evaluate("document.querySelector('.transport__btn').click()");
      await sleep(300);
      await evaluate(`(() => { const i = document.querySelector('.transport input[type=range]');
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '20');
        i.dispatchEvent(new Event('input', { bubbles: true })); })()`);
      await sleep(800);
      const n = await evaluate(
        "document.querySelectorAll('.tile__canvas').length",
      );
      for (let i = 0; i < n; i++)
        out[`tile${i}`] = await grab(`.tile:nth-child(${i + 1}) .tile__canvas`);
    }
    ws.close();
    return out;
  } finally {
    browser.kill();
    await sleep(500);
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {}
  }
}

const capture = async (url) => ({
  ...(await session(url, true)),
  ...(await session(url, false)),
});
const base = await capture(args.base);
const head = await capture(args.head);
let failed = 0;
for (const name of Object.keys(base)) {
  const a = base[name] && Buffer.from(base[name].b64, "base64");
  const b = head[name] && Buffer.from(head[name].b64, "base64");
  if (!a || !b || a.length !== b.length) {
    console.log(`${name}: missing or different size`);
    failed++;
    continue;
  }
  let px = 0;
  let max = 0;
  for (let i = 0; i < a.length; i += 4) {
    let d = 0;
    for (let j = 0; j < 4; j++) d = Math.max(d, Math.abs(a[i + j] - b[i + j]));
    if (d) px++;
    max = Math.max(max, d);
  }
  if (px) failed++;
  console.log(
    `${name} ${base[name].w}x${base[name].h}: ${px} of ${a.length / 4} px differ (max channel delta ${max})`,
  );
}
process.exit(failed ? 1 : 0);
