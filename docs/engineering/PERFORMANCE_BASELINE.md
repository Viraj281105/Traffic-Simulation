# Performance baseline

Landing-page regression investigation, 2026-10-29. Base commit `eb01213`
(`viraj-dev`). Backend and simulation performance were **not** measured in
this pass (see §6).

## 1. Environment and method

| Item | Value |
| --- | --- |
| Machine | Windows 11 Enterprise, Intel Core i7-1365U, 16 GB; the user's Docker dev stack was running |
| Browser | Microsoft Edge 156.0.4314.50, `--headless=new`, 1440×900, device pixel ratio 1, software raster |
| Build | Production: `npm run build` (`tsc && vite build`, Vite 8.3.5, Node 24.20.0), served by `vite preview` on :4173 (`.claude/launch.json` → `frontend-preview`) |
| Probe | `node scripts/landing_perf.mjs --url <url> --runs 1` |

`landing_perf.mjs` loads the page with the cache disabled, records LCP, CLS,
long tasks and bytes for 6 s, then scrolls to four positions (hero, story,
compare, finale) and, after 1.5 s to settle, measures a 4 s window with no
input: main-thread task, script, layout and style time from
`Performance.getMetrics`, plus `requestAnimationFrame` and `setInterval`
callbacks counted by an injected probe. `--profile` replaces the window with
a CPU profile (self time per function).

**Comparability.** Absolute numbers moved by up to 3× between sessions on this
machine: a first `HEAD` measurement (taken while the in-app browser pane was
also rendering the animated page) reported 334–505 ms/s idle task time, and a
later one on the same build 163–469 ms/s. Only the **interleaved** runs in §3
(base and modified builds served side by side, alternating, browser pane
closed) are used to judge the change.

## 2. The regression: before vs after the cinematic redesign

`3568a39` (2026-10-28) replaced the landing page with a canvas replay of
recorded engine runs. Its parent was built from `git archive 3568a39^` with
the same `node_modules` (dependencies are unchanged between the two) and
measured with the same probe, three runs each, in one session. Indicative
only (not interleaved):

| Metric (median of 3) | Before (`3568a39^`) | After (`eb01213`) |
| --- | ---: | ---: |
| Idle main-thread task time, by position | 87–144 ms/s | 334–505 ms/s |
| Idle script time | 0.1 ms/s | 195–349 ms/s |
| `requestAnimationFrame` callbacks | 0/s | ≈785/s (13 loops × 60 fps) |
| JS heap at the hero | 2.5 MB | 14.8 MB |
| Long tasks in the first 6 s | 177 ms | 493 ms |
| Bytes transferred (no cache) | 172 KB | 296 KB |
| Canvases | 0 | 7 |

The old page's only continuous cost was CSS animation (60 layouts/s); the new
page runs four replay clocks, seven canvas loops and two camera loops, and
redraws each visible canvas every frame. That is the regression: the page
went from idle to keeping a third or more of the main thread busy.

**Profile** (`--profile`, unminified build, ms of self time per second idle):

| Position | Top entries |
| --- | --- |
| Hero | `poly` 27.9 · `fill` 21.1 · `getBoundingClientRect` 18.3 · `drawScene` 11.1 |
| Story | `fill` 37.3 · `poly` 34.1 · `drawScene` 17.7 · `getBoundingClientRect` 7.3 |
| Compare | `fill` 138.1 · `poly` 74.1 · `drawScene` 55.0 · box `draw` 55.0 · GC 17.8 |
| Finale | `poly` 24.8 · `fill` 18.2 · `drawScene` 12.5 · `getBoundingClientRect` 2.5 |

React rendering does not appear among the top entries; the cost is canvas
path work and raster, plus a forced layout every frame from the hero camera
loop.

## 3. After the fixes: interleaved A/B

Fixes F-01 and F-02 ([REFACTOR_FINDINGS.md](REFACTOR_FINDINGS.md)). Base
build (`eb01213`) on :4174 and modified build on :4173, measured alternately
five times each (`head 1, after 1, …, head 5, after 5`). Medians, with the
range for task time:

| Position | Task ms/s base → after | Script ms/s | Task per frame | Layouts/s | JS heap MB |
| --- | --- | --- | --- | --- | --- |
| Hero | 245 (170–273) → **147** (141–801*) | 138 → 75 | 4.0 → 2.4 ms | 8.8 → 2.5 | 14.4 → 9.2 |
| Story | 192 (173–273) → **169** (158–348*) | 111 → 89 | 3.2 → 2.8 ms | 9.0 → 4.0 | 9.3 → 9.3 |
| Compare | 391 (350–472) → **359** (354–392) | 285 → 245 | 11.5 → 11.1 ms | 6.5 → 4.5 | 17.3 → 9.8 |
| Finale | 213 (186–231) → **185** (158–376*) | 102 → 79 | 3.5 → 3.1 ms | 7.8 → 0.3 | 15.2 → 11.5 |

\* one outlier run per column; medians are robust to it.

Frame rate was unchanged (≈60 fps at hero, story and finale; ≈32 fps at
compare in both builds). Page-load metrics did not separate: LCP 2244 ms
(1728–2860) → 2156 ms (1532–2876), long tasks 481 → 583 ms with overlapping
ranges, CLS 0 → 0, transfer 295.9 KB → 295.9 KB. **No load-time improvement is
claimed.**

**Measured:** idle main-thread time −40 % at the hero, −12 % story, −8 %
compare, −13 % finale; forced layouts at the hero and finale nearly gone.
**Not measured:** effect on a GPU-rastered real browser or a high-DPR display.

## 4. Visual equivalence

`drawScene` output was compared as raw RGBA, read with `getImageData`, from
all seven canvases of the base and modified builds: hero, story and finale
under emulated `prefers-reduced-motion` (fixed clocks and cameras), and the
four Compare tiles paused and scrubbed to t = 20 s (this path draws from the
cached ground layer). Base vs base: 0 differing pixels (the capture is
deterministic). Base vs modified: **0 differing pixels** on every canvas. An
intermediate version that merged the lane dashes into one path differed on
0.1 % of pixels (max 8/255) and was reverted.

Reproduce with `node scripts/landing_canvas_diff.mjs --base <url> --head <url>`
(added in checkpoint 2; comparing a build with itself reports 0 differing
pixels on all seven canvases).

**Compare section, checkpoint 2.** The one remaining cheap lever — drawing
only each box's two nearest side faces, as the renderer's comment says only
those are visible — changed 1.2–4 % of pixels by up to 81/255 on every canvas
(hero 15,557 px, tiles ~3,800 px each), so it is a visible change and was
reverted. No further pixel-identical improvement was found; the remaining
options are listed under F-14.

## 5. Build

| Metric | Base | After |
| --- | --- | --- |
| `npm run build` | passes | passes |
| Landing initial JS (gzip) | 124.2 KiB | 124.6 KiB |
| Landing scene chunk (gzip) | 70.7 KiB | 70.7 KiB |
| Dashboard initial JS (gzip) | 193.5 KiB | 193.5 KiB |

Build duration is not compared: the first build was cold (Vite reported
14.75 s) and later ones warm (≈3 s), so the numbers say nothing about the
change.

## 6. Simulation engine (checkpoint 2)

Timing only, the benchmark script's own `run_once` (same scenario builder and
engine path as `scripts/benchmark_signalised_roundabout.py`), seed 1, three
runs each, backend venv (Python 3.14.7), same machine. The script's full mode
adds a `tracemalloc` pass that ran over 25 CPU-minutes at
`--repeats 3 --duration 90 --seeds 1,2` and was stopped, so no memory figure
is reported.

| Layout (from the benchmark) | Variant | Simulated | Wall time per simulated second (min / median) |
| --- | --- | --- | --- |
| 1 ring, 4 arms, 350 veh/h | conventional | 60 s | 7.7 / 7.8 ms |
| 1 ring, 4 arms, 350 veh/h | metered | 60 s | 7.8 / 8.4 ms |
| 2 rings, 4 arms, 1,000 veh/h (saturated) | conventional | 120 s | 106 / 108 ms |
| 2 rings, 4 arms, 1,000 veh/h (saturated) | metered | 120 s | 102 / 106 ms |

`cProfile` of the saturated conventional run (36.6 s under the profiler):
`vehicles/router.py:find_leader` 8.5 s self / 13.3 s cumulative (the
roundabout branch scans every active vehicle for each look-ahead ring lane:
5.4 M `Vehicle.coords` calls, 4.9 M `str.startswith`), then
`predictive_conflicts.compute_braking_distances` 10.9 s cumulative and the
TTC safety metric 4.0 s. Because `vehicle_pool.update` moves each vehicle
before the next one looks for its leader, a per-step index of ring vehicles
would not reproduce the same results; see F-30. No engine change was made.

Backend test suite (`pytest -m "not slow" -n 8 --dist loadfile`, this
machine): 2,439 passed in 4 min 45 s at the start of checkpoint 2.

**Checkpoint 3: ceiling of an exact leader index (F-30).** Saturated
two-ring roundabout, 1,000 veh/h per arm, mixed vehicles (car 0.6, SUV, bus,
truck, motorcycle 0.1 each), seed 3, 120 simulated seconds, alternating runs:

| `find_leader` input | Run 1 | Run 2 |
| --- | --- | --- |
| All active vehicles (current) | 75 ms / sim s | 65 ms / sim s |
| Idealised filter: ring vehicles + everything within 25 m, no maintenance cost | 61 ms / sim s | 60 ms / sim s |

At most a 6–18 % gain, before paying for an index that must be updated as
each vehicle moves. Not pursued (F-30). (This mixed-traffic run is cheaper
per simulated second than the cars-only 2-ring layout in the table above,
which serves more vehicles.)

## 7. Not measured

Dashboard routes: the production build signs in through Cognito, which is not
configured locally, and the dev bypass exists only in the Vite dev server,
whose timings do not represent production. Bundle sizes per route are in the
build output and the budgets. API latency, study throughput and backend
memory remain unmeasured.
