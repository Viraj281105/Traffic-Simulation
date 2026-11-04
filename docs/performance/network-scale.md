# Network engine at scale (F5, package 1A)

Measured with `scripts/bench_network.py --legacy-from-git HEAD --profile`, 900 simulated seconds, seed 5, best of 5 repetitions, Python 3.14.7 on Windows 11 (Intel64 Family 6 Model 186), one otherwise idle machine. Numbers are only comparable within one run; rerun the script to reproduce.

## Result

| Scenario | Links | Vehicles entered | Wall time now | Sim s per wall s | Before | Speed-up |
|---|---:|---:|---:|---:|---:|---:|
| Corridor (2 junctions) | 14 | 382 | 0.0057 s | 157,900 | 0.0159 s | 2.8x |
| 3x3 grid (9 junctions) | 48 | 1,183 | 0.0203 s | 44,400 | 0.0573 s | 2.8x |
| 3x4 network (12 junctions) | 62 | 1,321 | 0.0316 s | 28,500 | 0.0748 s | 2.4x |
| 3x4 network, heavy demand | 62 | 2,750 | 0.0445 s | 20,200 | 0.1302 s | 2.9x |
| 6x6 grid (36 junctions) | 168 | 2,346 | 0.0838 s | 10,700 | 0.2578 s | 3.1x |
| 10x10 grid (100 junctions) | 440 | 3,005 | 0.2522 s | 3,600 | 0.4791 s | 1.9x |

The 12-junction network simulates 15 minutes of traffic in about 0.03 to 0.05 s, so the F5 budget (10+ junctions, deterministic, run end to end) is met with a wide margin. Suggested budget to record in ADR-021: a 12-junction, 900 s run completes in under 0.5 s on the development machine (10x headroom over the measurement). Cost is roughly 0.45 to 0.8 microseconds per link per simulated second.

## What was changed

`simulate_network` was profiled first (cProfile, heavy 12-junction run): all the time was inside the one function. The step loop re-did per-step work that does not change during a run, so the optimisation hoists it. Nothing was vectorised with numpy because the engine is a FIFO queue simulation with data-dependent branching (spillback, per-vehicle routes); the per-step work is dominated by Python object handling, and arrays would add conversion cost without removing it.

* Link storage capacity, crossing time, saturation refill and lane cap are computed once per run (they were recomputed per vehicle and per link-step).
* The sorted node order and each node's incoming links, axis and queue are built once (they were re-sorted and re-looked-up every step).
* The signal phase is computed once per step rather than once per incoming link.
* Flows that can never produce a vehicle are dropped from the arrival loop; each flow's arrival probability and free-flow time are computed once.
* `min`/`max` calls on the hot path are plain comparisons.

Results are unchanged: the random draws happen in the same order, the credit arithmetic is the same sequence of floating-point operations, and nodes and links are visited in the same order. This is checked three ways: the benchmark compares every result field against the engine at git `HEAD` (all rows `same: yes`), `tests/networks/test_network_grid.py::test_optimised_engine_results_are_unchanged` pins entered/completed/blocked counts captured before the change, and all earlier `tests/networks` tests (determinism, conservation over seeds and loads, spillback) pass untouched.

Two additive changes to the engine's interface: an optional read-only `observer` argument (called after every step; used by `src/netmetrics`), and two extra result keys, `totalTravelSeconds` and `totalDelaySeconds` (unrounded-sum companions of the existing means).

## Cost of recording

Network metrics and the congestion analysis record per-link occupancy, queue, blocking and departures at every step (`src/netmetrics/recorder.py`, numpy matrices of steps x links). That is a Python loop over links per step, and it costs roughly 3 to 4 times the bare simulation (12-junction: 0.13 s, 36 junctions: 0.27 s, 100 junctions: 0.65 s for 900 s). Memory is bounded by a limit of 6 million step-link cells (about 80 MB); beyond that the API answers 422 and asks for a shorter run.

## Not done

* Partitioned stepping (running regions of the network in separate processes) is not implemented. At 100 junctions the run takes 0.25 s, so partitioning would cost more in coordination than it saves; revisit if networks reach thousands of links or if a per-junction engine replaces the mesoscopic handoff.
* The recorder could be vectorised (only touch links with vehicles) if analysis of very long runs on large networks becomes slow.
* No budget has been written into ADR-021 yet; that edit is outside this package.
