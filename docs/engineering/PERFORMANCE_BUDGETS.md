# Performance budgets

Budgets only for metrics that this repository can measure repeatably. Each
was set from the 2026-10-29 measurements in
[PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) with about 10 % headroom.
Raise a budget only with a reason recorded here.

## Bundle size (deterministic — suitable for CI)

Measured by `node scripts/check_bundle_budgets.mjs` after `npm run build` in
`frontend/`. Sizes are Node `zlib` gzip (default level) of each file, summed
over the scripts and stylesheets an HTML entry loads before any lazy import;
they differ from Vite's printed gzip column by a few per cent. The script
exits 1 when a budget is exceeded.

| Metric | Baseline (gzip KiB) | Budget | Regression detection |
| --- | ---: | ---: | --- |
| Landing (`index.html`) initial JS | 124.6 | 137 | `check_bundle_budgets.mjs` |
| Landing initial CSS | 14.4 | 16 | same |
| Dashboard (`app.html`) initial JS | 193.5 | 213 | same |
| Dashboard initial CSS | 30.2 | 33 | same |
| Landing scene chunk (`scene-*.js`, lazy) | 70.7 | 78 | same |
| Largest other lazy chunk (Recharts `charts-*.js`) | 117.5 | 130 | same |

Wired into CI (checkpoint 2): the `frontend-lint-test` job runs
`npm run build` and then `node ../scripts/check_bundle_budgets.mjs --dist dist`.
It has not yet run on GitHub; the first run confirms it.

## Landing-page main-thread cost (machine-dependent — manual)

Measured by `node scripts/landing_perf.mjs` (headless Edge/Chrome over the
DevTools protocol, 1440×900, production build from `vite preview`). Absolute
numbers depend on the machine and its load, so the budget is a **relative**
one: compare against a build of the base commit on the same machine with
interleaved runs, as PERFORMANCE_BASELINE.md §3 does.

| Metric | Measurement | Budget |
| --- | --- | --- |
| Idle main-thread task time at each of the four scroll positions | `idle.<spot>.taskMsPerSec`, median of ≥ 5 interleaved runs | Not above the base commit's median by more than 10 % |
| Forced layouts while idle at the hero | `idle.hero.layoutsPerSec` | ≤ 3 per second (baseline after F-01: see §3 of the baseline) |
| Cumulative layout shift | `cls` | 0 (baseline 0) |
| Canvas output | pixel diff of the seven canvases against the base commit (method in the baseline doc) | 0 differing pixels for a change that is not meant to alter the picture |

Not budgeted: LCP and long tasks. Over the runs taken here LCP ranged
widely between identical builds (see the baseline doc), so a fixed threshold
would flag noise.

## Simulation step time (machine-dependent — manual)

Baseline in [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) §6: wall time
per simulated second for the benchmark script's layouts (1-ring medium
≈ 7.8 ms, 2-ring saturated ≈ 107 ms on the reference machine).

| Metric | Measurement | Budget |
| --- | --- | --- |
| Wall time per simulated second, each benchmark layout and variant | `run_once` from `scripts/benchmark_signalised_roundabout.py`, min of ≥ 3 runs, base and change interleaved on one machine | Not above the base commit by more than 10 % |
| Simulation results | The golden fingerprint and determinism tests (fast suite; full corpus in the slow job) | Unchanged |

## Not measured yet

API latency, study throughput and backend memory have no budget: no
repeatable benchmark was run. The benchmark script's `tracemalloc` pass is
the starting point for a memory budget, at a smaller configuration than its
defaults (see the baseline §6).
