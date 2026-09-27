# UrbanFlow — Evaluation Metrics: Audit and Authoritative Reference

| | |
|---|---|
| **Status** | §17 (calibration pass) changed the simulation itself; results measured before it are superseded. §1–§14 are the audit of HEAD `5368b26` **before** the fix pass and are kept as the record of what was found. **§15 records what was fixed, what was deliberately not, and the current labels and definitions; §16 classifies every kind of statement UrbanFlow now makes.** Where §2–§14 describe a defect that §15 marks *fixed*, §15 is current. |
| **Audited** | 2026-09-25, branch `viraj-dev`, HEAD `5368b26` |
| **Audience** | Mentor review · project presentation · future developers · researchers using UrbanFlow |
| **Source of truth** | The implementation. Where documentation disagrees, the disagreement is listed in §13 and the code wins. |
| **Companion docs** | [`urbanflow-user-narrative.md`](urbanflow-user-narrative.md) (who the product is for), [`../architecture/07-metric-contract.md`](../architecture/07-metric-contract.md) (older contract; see §13 for drift), [`../reports/comparative_report.md`](../reports/comparative_report.md) and [`../reports/v1-known-limitations.md`](../reports/v1-known-limitations.md) (measured results and model limits) |

## How this audit was done

* Every metric was traced from its frontend label back to the backend line that computes it. Citations are `file:line` (line numbers are as of HEAD and will drift).
* Nothing was assumed to exist because it is common in traffic simulation. A metric appears here only if it is computed or displayed.
* Four behaviours that reading alone could not settle were **checked by running the simulator** (seed 1, 120 s run, 30 s warm-up, 0.15 / 0.3 / 0.6 veh/s, 1 and 2 lanes, via `DualSimulationOrchestrator`). Results are in Appendix A. They are labelled *(verified by run)* where used.
* Wording rule used throughout: "better" is never universal. Each metric is marked *lower-is-less-of-the-thing*, *context-dependent*, or *not a performance measure*.

## Contents

1. [How evaluation works end to end](#1-how-evaluation-works-end-to-end)
2. [Complete metric inventory](#2-complete-metric-inventory) (categories A–J, plus dead code)
3. [Derived and statistical values](#3-derived-and-statistical-values)
4. [Plain-English explanation of every metric](#4-plain-english-explanation-of-every-metric)
5. [Chart and visualisation inventory](#5-chart-and-visualisation-inventory)
6. [User-facing evaluation model](#6-user-facing-evaluation-model)
7. [Researcher evaluation model](#7-researcher-evaluation-model)
8. [Redundancy and overload audit](#8-redundancy-and-overload-audit)
9. [Scientific validity findings](#9-scientific-validity-findings)
10. [Master table](#10-master-table)
11. [Recommended three-level presentation](#11-recommended-three-level-presentation)
12. [Implemented but unused / API-only](#12-implemented-but-unused--api-only)
13. [Documentation vs implementation](#13-documentation-vs-implementation)
14. [Defect register](#14-defect-register)
15. [Resolution of the defect register (fix pass)](#15-resolution-of-the-defect-register-fix-pass)
16. [Evidence classes: what UrbanFlow claims and how](#16-evidence-classes-what-urbanflow-claims-and-how)
- [Appendix A — verification runs](#appendix-a--verification-runs)

---

## 1. How evaluation works end to end

### 1.1 Pipeline

| Stage | What happens | Source |
|---|---|---|
| Scenario | Guided flow sends a flat payload; backend compiles it to an engine config. `directionalSplit` and `totalVehicles` are **not** set by the UI (see D-13, D-24). | `main.py:1158` `_compile_dashboard_config` |
| Paired run | `DualSimulationOrchestrator` builds one signal engine and one roundabout engine from the same config, **same seed**, stepped in lockstep. The roundabout controller block is hard-coded (inner 10 m, outer 20 m, entry 5 m/s, circulating 8 m/s); only `criticalGap` and `followUpTime` are read from the config. | `dual_orchestrator.py:22-159` |
| Collection | One `MetricCollector` per engine. `update()` runs every tick; `get_metrics()` is recomputed on every call (every snapshot, every REST read). | `collector.py:150-531` |
| Warm-up | Ticks before `warmupTime` (default 30 s) are skipped for most accumulators. Vehicle wait/stop counters are baselined at warm-up end so pre-warm-up accrual is subtracted (except fairness, D-14). | `collector.py:173-184, 419-425` |
| Snapshot | `SnapshotBuilder.build()` embeds `metrics` plus `vehicleCounts`, `warmupTime`, per-vehicle telemetry, controller state. | `snapshot/builder.py:172-237` |
| Streaming | WebSocket `/ws/simulation/dual` sends dual snapshots; the frontend keeps a ~1 Hz history of up to 200 points for charts. | `useLiveComparisonHistory.ts:69` |
| Persistence | Runs are saved with `summary_metrics` (the full flat dict), config and provenance; sweeps store each tier's dict. | `main.py:378-443`, `volume_sweep.py:249-279` |
| Studies | Sweep = 1 seed per demand tier. Monte Carlo = N random seeds at one scenario. Both call the same collector. | `study/volume_sweep.py`, `study/validation.py` |

### 1.2 Definitions that apply to almost every metric

* **Post-warm-up exited set** `X`: vehicles with `exit_time ≥ warmupTime` (or no exit time and `spawn_time ≥ warmupTime`). Vehicles that *spawned before* warm-up but *exited after* are included. (`collector.py:281-286`)
* **Waiting** (per vehicle): time accrues whenever `speed < waitSpeedThreshold` (default 0.5 m/s). (`vehicle.py:118-125`)
* **Queued** (per approach): a vehicle on a lane whose id contains `_in_`, first letter n/s/e/w, with `speed < 0.5`. Vehicles queued on the roundabout ring or connectors are **not** counted. (`queue_length.py:6-25`)
* **Stopped**: `speed < 0.1 m/s`, re-armed only after `speed ≥ 0.2 m/s`. (`stop_count.py:6-20`)
* **Signal vs roundabout**: signal has a real `signals_state`; for roundabouts `derive_signals_state` reports every approach permanently green (`controllers/factory.py:39-43`). That single fact drives D-05.

### 1.3 Exposure and export (applies to every collector metric)

Every key in `get_metrics()` reaches: the WebSocket snapshot; `GET /api/v1/simulations/{id}/metrics` (`main.py:660`); the report endpoint JSON/CSV (`main.py:696`); the saved run's `summary_metrics`; the run export JSON and dotted-path CSV (`main.py:1915-1993`); and — for every key in the frontend catalog — the catalog CSVs (`catalog.ts:597-693`) and the "All measurements" tables (`MetricSections.tsx`). The catalog omits only the structural/flag keys (`currentQueueLengths`, `travelTimeReliabilityLowSampleSize`, `ttcThresholdSeconds`, `petThresholdSeconds`, `petApplicable`), which the UI reads separately.

**Study exports are narrower.** Study CSV/JSON carries delay, throughput, queue only (`report_generator.py:181-227`); the frontend sweep CSV has 10 columns (`VolumeAnalysisDashboard.tsx:721-745`); the frontend validation CSV has per-seed rows only (`ValidationDashboard.tsx:387-413`). **No export carries a p-value, Cohen's d or degrees of freedom** (D-28).

---

## 2. Complete metric inventory

Column legend. **Dir.** = what the number means, never "good/bad" unless noted. **Level** = where it appears today: **G** guided results main page, **L** live comparison panel/dialog, **T** "All measurements" tables (specialist), **R** Research Lab. "Main" means G; "Advanced" means L/T/R only.

### A. Traffic efficiency (control-delay family)

All six are computed in one block, `collector.py:345-401`, over the post-warm-up exited set `X`. Per vehicle: `delay = max(0, (exit − max(spawn, W)) − free_flow)`, where `free_flow = Σ(route lane lengths) / max(desired_speed, 1)`; for vehicles that spawned before warm-up `W`, `free_flow` is scaled by (post-W time ÷ total time). If a vehicle has no usable exit time, its `wait_time` is used instead (lines 367-368). Unit: seconds. Values are rounded to 2 dp.

| Key · UI label | Exact definition | Dir. | Level · used in main comparison? | Derived from · caveats |
|---|---|---|---|---|
| `averageDelay` · "Average delay" / "Time lost per driver" | Mean of per-vehicle `delay` over `X` | Higher = more time lost against free-flow *at the driver's own desired speed* (85–105% of the 50 km/h limit since §17; 18–25 m/s before). Context-dependent across geometries (D-06). | **G** (headline card 1, "In short", LOS grade, session table) · yes | Travel time, route length, desired speed. Includes geometric slow-down (roundabout entry 5 m/s). *(Verified by run: roundabout 12.9 s at 0.15 veh/s with 0 s queued time.)* |
| `medianDelay` · "Median delay" | Median of `delay` | as above | L, T | Same population. Robust to outliers; equal to 0 whenever >50 % of drivers pass freely (signal: 0.0 s at 0.15 veh/s) |
| `p95Delay` · "1 in 20 drivers lost more than" | 95th percentile, linear interpolation at index `(n−1)·0.95` | as above, upper tail | **G** (card 1) · yes | With n = 5 it is effectively the maximum. Low-sample flag is keyed to PTI, not to this metric |
| `minDelay` · "Minimum delay" | Smallest `delay` | as above | T (diagnostic, collapsed) | ≈ 0 at the signal (delay is floored at 0) but **never near 0 at the roundabout** *(verified: 2.3-3.4 s even at 0.15 veh/s)*, because every roundabout driver slows to entry speed (D-06) |
| `maxDelay` · "Maximum delay" | Largest `delay` | as above | T; drives the whisker scale | One vehicle. Dominated by outliers |
| `delayStdDev` · "Delay standard deviation" | Sample SD (n−1) of `delay`, centred on the **rounded** mean (`collector.py:391`) | Spread of driver experiences within one run | T; sweep tooltip and envelope | Within-run, **not** run-to-run uncertainty (D-19). Rounded-mean centring is a negligible (<0.005 s) bias |

### B. Driver experience

| Key · UI label | Exact definition | Dir. | Level · main? | Derived from · caveats |
|---|---|---|---|---|
| `averageWaitTime` · "Average queued time" | Mean over `X` of `max(0, wait_time − baseline_at_W)`; `wait_time` accrues `dt` while `speed < 0.5 m/s` (`collector.py:419-429`). s | Higher = more time spent nearly stationary. Lower is less waiting; says nothing about slow-but-moving time | L, T (feeds composites) · **no** | Different quantity from delay: a roundabout driver decelerating to 5 m/s is delayed but not "waiting". *(Verified by run: delay favours signal while queued time favours roundabout at 0.3 veh/s.)* |
| `averageStopsPerVehicle` · "Stops per vehicle" / "Stops per driver" | Mean over `X` of baseline-clipped `stop_count` (`collector.py:430-432`) | Higher = more full stops (speed < 0.1 m/s) per journey | **G** (card 1, "Stop-and-go") · yes | Stop threshold (0.1) differs from wait threshold (0.5): crawling at 0.3 m/s is "waiting" but not a "stop" |
| `totalStops` · "Total stops" | Sum of the same clipped stop counts over `X` (`collector.py:433`) | Count; scales with volume and duration | T | Not normalised for run length or vehicle count, so unsuitable across different-length runs |
| `travelTimeReliability` · "Planning time index" (PTI) | `P95(exit − spawn) / median(exit − spawn)` over `X` (`travel_time.py:36-76`) | Closer to 1.0 = journey times similar across drivers. Not "better" in itself (a uniformly slow junction has PTI 1.0). | L (PTI tab), T · no | Uses raw travel time (not warm-up-clipped, not free-flow-subtracted). Returns 1.0 with no data (UI hides via `needsExits`); `null` if median ≤ 0. |
| `travelTimeReliabilityLowSampleSize` | `n < 20` (`travel_time.py:8`, `collector.py:482-483`) | Boolean flag | G (drives the "few vehicles" caveat) | Only a sample-size flag; not a confidence measure |
| `averageTravelSpeed` · "Current mean speed" | Mean instantaneous speed of active vehicles **now** (`derived_metrics.py:7-11`). m/s | Snapshot, not a run average | L (Mean speed tab) | Includes vehicles on all lanes (approach, junction, exit). Not post-warm-up |
| `speedVarianceIndex` · "Speed variance index" | Time-average over post-W ticks with ≥ 2 vehicles of `CV(t) = σ_v(t) / mean_v(t)`, population SD (`speed_variance.py`, `collector.py:199-202, 453-457`). Dimensionless | Higher = more mixed speeds (stopped and free-flowing vehicles together) | T (diagnostic) | A junction with a standing queue *and* free-flow arrivals scores high regardless of delay. No documented threshold |

### C. Queueing and congestion

| Key · UI label | Exact definition | Dir. | Level · main? | Derived from · caveats |
|---|---|---|---|---|
| `currentQueueLengths` (not in catalog) | `Q_d(now)` per approach: count of vehicles on `*_in_*` lanes with speed < 0.5 (`queue_length.py`) | Instantaneous | L ("Approach queue distribution", "Queues now"), map labels `Q n` | Excludes ring/junction queues; snapshot only |
| `averageQueueLength` · "Average queue per approach" / "Typical queue on one approach" | `mean over 4 approaches of (Σ_t Q_d(t) / n_ticks)` (`collector.py:314-320`). veh | Higher = longer typical standing queue | **G** (card 3) · yes | Approach-only definition; an unused approach dilutes the mean because the 4-way mean always divides by 4 |
| `maxQueueLength` · "Maximum queue" / "Longest queue seen" | `max over approaches and ticks of Q_d(t)` (`collector.py:319`) | One-tick extreme on one approach | **G** (card 3, headline, session table) · yes | Single-tick extreme: noisy; a 1-vehicle difference is common noise |
| `activeAverageQueueLength` · "Average total queue when queued" | Mean of total queue over ticks where total > 0 (`collector.py:321-325`) | Conditional average | L, T | Conditional on a queue existing, so a rarely-queued junction can score higher than a constantly-queued one |
| `queueStdDev` · "Queue standard deviation" | Sample SD of the junction-wide **total** queue per tick (`collector.py:326-332`) | Spread over time | T (diagnostic) | Total (4-approach) queue, unlike `averageQueueLength` |
| `queueStabilityIndex` · "Queue stability index" | `queueStdDev / mean(total queue)`, 3 dp (`collector.py:333-336`) | Higher = queue fluctuates more relative to its mean | L (Traffic flow card), T | Undefined (0.0) when the mean is 0; **explodes when the mean queue is tiny** *(verified: 7.69 for the roundabout at 0.15 veh/s, mean total queue ≈ 0.02)*. **Not** stability in the queueing-theory sense (growth vs equilibrium); it is a coefficient of variation |
| `congestionRecoveryTime` · "Time congested" / "Time with more than 5 vehicles queued" | `Σ dt` over post-W ticks where total queue > 5 (fixed constant, `collector.py:229-230`). s | Higher = longer time above a fixed queue threshold | **G** (card 3, with % of measured time) · yes | The backend name says "recovery" but nothing is recovered; catalog relabels it. Threshold 5 is not configurable and is not scaled to lane count |

### D. Throughput, capacity and demand

| Key · UI label | Exact definition | Dir. | Level · main? | Derived from · caveats |
|---|---|---|---|---|
| `throughput` · "Vehicles served" / "Got through" | `len(X)` — count of vehicles exited post-warm-up (`throughput.py:6-8`). veh | Higher = more vehicles completed the journey in the measured window | **G** (card 2, headline, session table, LiveGuide) · yes | A **count, not a rate**: depends on run length, and includes vehicles that spawned before warm-up |
| `throughputRate` · "Throughput rate" | Exits in `[max(W, t−60), t]` divided by `min(t−W, 60)`, × 60. veh/min (`throughput.py:11-34`) | Recent exit rate | L (Throughput tab), T; feeds both composites | **Last-minute only**. On a finished run it describes the final 60 s, not the run |
| `totalVehiclesSpawned` · "Vehicles generated" | All-time spawner count, **including warm-up** (`collector.py:489`) | Offered demand, until the vehicle cap is reached | L (Demand balance), T | Silently capped at `totalVehicles` (default 200) (D-24) |
| `activeVehicleCount` · "Vehicles in network now" / "Still waiting or moving when the clock stopped" | `len(active_vehicles)` now | Backlog indicator | **G** (card 2, "One side was falling behind") | Snapshot, not a run measure |
| `criticalSaturationVolume` · "Critical saturation volume" | If `throughputRate/60 < arrivalRate`: `throughputRate/60`; else `arrivalRate × (throughput / post-W-spawned)` (`derived_metrics.py:37-74`). veh/s | Bounded above by ≈ the configured arrival rate (D-10) | L (Capacity tab), T · no | Not a capacity estimate: cannot exceed offered load except through ratio > 1 |
| `intersectionUtilization` · "Service utilization" | `100 × service_ticks / demand_ticks`; a tick is "service" when the **mean speed of all active vehicles** > 0.5 m/s (`collector.py:189-193, 494-499`). % | Not utilisation of capacity | L (Capacity ring), T | Saturates at 100 % with modest traffic *(verified: 100 % in 7 of 8 side-runs)* — non-discriminating |
| `idleOpportunityLoss` · "Idle green loss" | Fraction of post-W ticks where ≥ 1 red approach has a queue and every green approach has none (`idle_loss.py:8-43`); UI shows × 100 | Higher = more green time with nothing to serve | **G** (only in "Why did this happen?" if ≥ 5 %), L | **Signal-only by construction.** Roundabout is always 0.0; `1 − 0 = 1` then flatters the roundabout composite (D-05). All-red ticks return False (contract says they count, §13) |
| `spaceFootprintConsumed` · "Junction footprint" | Signal `(2 · max_lanes · laneWidth)²`; roundabout `π · outerRadius²` (`derived_metrics.py:77-101`). m² | Static geometry, not performance | L (Capacity tab), T | **Different definitions per geometry**: crossing box vs outer circle including the central island *(verified by run: 49 m² vs 1,257 m² at 1 lane)* (D-11b) |

`vehicleCounts` (snapshot, not in `metrics`): `active`, `approaching`, `waiting`, `crossing`, `inRoundabout`, `exited` (`builder.py:45-52`). `exited` is **whole-run including warm-up**; it is shown as "Exited (Served) / Whole run" (`VehiclesFlowVisualizer.tsx:65-66`) beside `throughput` "Vehicles served" (post-warm-up) elsewhere (D-12).

### E. Fairness

| Key · UI label | Exact definition | Dir. | Level · main? | Derived from · caveats |
|---|---|---|---|---|
| `directionalFairnessIndex` · "Directional fairness" | Jain's index `(Σx)² / (n·Σx²)` over per-approach **mean `wait_time`** of `X`, approach = first lane of the route; approaches with no exited vehicles excluded, `n` reduced; 1.0 if none or all zero (`fairness.py:6-52`) | 1.0 = every approach waited the same; floor is `1/n` for n approaches with data (0.25 only if all four) | **G** (card 4, with word bands) · yes | Uses **raw** `wait_time`, not the warm-up-clipped value used by `averageWaitTime` (D-14). Approach demand is randomly split per seed when `directionalSplit` is unset (D-13). Tiny n makes it swing wildly *(verified: 0.42 vs 0.65 on 16–18 exits)*. Fairness of *waiting*, not of delay (UI note says "delay", D-14) |

### F. Safety and collisions

All are model outputs and instrumentation-dependent. None is a validated safety ranking (`SafetyTimelineVisualizer.tsx` disclaimer; `collector.py:507-513`).

| Key · UI label | Exact definition | Dir. | Level | Caveats |
|---|---|---|---|---|
| `collisionCount` · "Collisions" | Debounced count of distinct vehicle-pair SAT overlaps since the run began, **including warm-up**; slower vehicle is frozen (`pool.py:350-375`) | Model-integrity signal, **not** predicted crashes | **G** (only inside "How reliable is this?") | Measures model overlap, not risk. Not post-warm-up |
| `minTTC` · "Minimum TTC" | Run-long **running minimum** of constant-velocity time-to-collision over *different-lane* pairs within 50 m (`safety_conflicts.py:90-194`, `collector.py:239-240`). s. `null` if none | Lower = a closer approach occurred | L (Safety tab, TTC line chart) | Catalog text says "following vehicle and its leader" but same-lane pairs are **excluded** (D-13). Running minimum cannot recover: a "trend" chart can only fall |
| `ttcEventCount` · "Low-TTC events" | Number of **tick-level pair observations** with `TTC ≤ ttcThresholdSeconds` (default 1.5 s) (`collector.py:235-243`) | Higher = more close-approach observations | L, T | Counts pair-ticks (0.1 s each), not distinct encounters. One slow crossing = many "events" |
| `ttcSampleCount` · "TTC observations" | Number of pair-ticks with a defined TTC | Coverage, not risk | T (diagnostic) | Differs sharply by geometry *(verified: 41 vs 0 at 0.15 veh/s)* so counts are not comparable across geometries |
| `ttcThresholdSeconds` | `metrics.ttcThresholdSeconds` (default 1.5) | Config echo | Label only | Literature default, unvalidated |
| `minPET` · "Minimum PET" | Smallest gap between one vehicle leaving and a different vehicle entering a signal conflict zone (`ConflictZoneOccupancyTracker`, `safety_conflicts.py:209-296`). s | Lower = tighter sequential crossing | L | **Signal-only**; roundabout not measured |
| `petEventCount` · "Low-PET events" | Number of PET observations `≤ petThresholdSeconds` (default 5.0 s) | Higher = more tight crossings | L, T | A 5 s threshold flags well over half of all observations *(verified: 134 of 222 observations at 0.6 veh/s, 17 of 31 at 0.15 veh/s)* |
| `petSampleCount` · "PET observations" | Count of PET observations | Coverage | T | Signal-only |
| `petThresholdSeconds`, `petApplicable` | Config echo; `True` only when a conflict manager was supplied (signal) | Flags | Drive N/A rendering | `petApplicable=False` means "not measured", never "zero conflicts" |

### G. Simulation and vehicle behaviour (telemetry, not evaluation)

Displayed on maps and in the single-control sidebar; not aggregated into evaluation metrics.

| Item | Definition | Where shown |
|---|---|---|
| Vehicle telemetry (`speed`, `acceleration`, `waitTime`, `stopCount`, `spawnTime`, `exitTime`, `distanceTraveled`) | Per-vehicle values in every snapshot (`builder.py:99-159`); only the last 50 exited vehicles are serialised | Maps (brake lights when `state == waiting`), replay |
| Signal controller state | `currentPhase`, `phaseTimeRemaining`, `cycleNumber`, per-approach colour | `MetricsSidebar.tsx` |
| Roundabout controller state | `circulatingCount` (vehicles on `conn*` lanes), `yieldingCount` (within 5 m of the stop line, speed < 0.5), `gapAcceptance` (= the configured **critical gap parameter**, not a measured value) (`roundabout.py:484-507`) | `MetricsSidebar.tsx:122-124` |
| `warmupTime`, `timestamp`, `tick` | Timing context | Warm-up notices, `isInWarmup()` |

### H. Statistical and reliability measures (multi-seed)

Produced only by the Monte Carlo study (`validation.py`) and read by the reliability check and Validation dashboard. Inputs are exactly three per-seed scalars: `averageDelay`, `throughput` (a count), `averageQueueLength`.

| Item | Definition | Nature |
|---|---|---|
| `mean`, `std`, `min`, `max` | Per-metric over seeds; `std` is sample SD (n−1) (`validation.py:9-26`) | Descriptive |
| `ci95` | `1.96 · std / √n` — **normal (z) multiplier** (`validation.py:18`) | Descriptive interval; too narrow at small n (D-03) |
| `cohensD` | `(mean_signal − mean_roundabout) / √((var_s + var_r)/2)` (`validation.py:133-134`). **Positive = signal higher** | Comparative effect size |
| `pValue`, `degreesOfFreedom`, `significant` | Welch two-sample t-test, Student-t two-tailed p, `significant = p < 0.05` (`validation.py:136-161`) | Inferential (unpaired) |
| Seed win tally | Seeds where roundabout delay < signal delay (`ValidationDashboard.tsx`), and the reliability tally in `readReliability` | Descriptive |
| Reliability verdict | `consistent` if `significant`; else `no-gap` if means within similarity band; else `not-consistent` (`plainLanguage.ts:581-612`) | Decision-support wording |

### I. Study / sweep metrics

From `run_volume_sweep_experiment` (`volume_sweep.py`): one seed per arrival rate; default rates 0.1–0.8 veh/s (`:17`); default 60 s with 15 s warm-up; **2 lanes/approach** (D-09).

| Item | Definition |
|---|---|
| `arrivalRate`, `hourlyVolumeVehPerHour` | Whole-junction rate; `round(rate × 3600)` |
| Per-side `delay`, `delayMedian`, `delayStdDev`, `delayMin`, `delayMax`, `delayP95` | Rounded copies of the collector values |
| `throughput`, `throughputRate`, `queue`, `queueMax`, `queueStdDev` | Collector `throughput` (count), `throughputRate`, `averageQueueLength`, `maxQueueLength`, `queueStdDev` |
| `delayDeltaPercent` | `(round_delay − sig_delay) / max(sig_delay, 0.01) × 100`, 0 if `sig_delay ≤ 0`. **Positive = signal lower** (`volume_sweep.py:283-287`) |
| `throughputDeltaPercent`, `queueDeltaPercent` | Same form with floors 1.0 and 0.1 |
| `winner` | `tie` if `|Δdelay| ≤ 0.2 s` **or** `|Δ%| < 2`; else lower mean delay (`volume_sweep.py:299-305`) |
| `crossoverArrivalRate`, `crossoverHourlyVolume` | The **later** rate of the first adjacent pair whose raw delay difference changes sign; not interpolated; ignores the tie band (`volume_sweep.py:203-210`) |
| Tier tally, "Largest gap" | UI counts of `winner`; tier with largest `|round − sig|` delay |
| Sweep verdict text | `_summarize_sweep_verdict` (`report_generator.py:9-97`) |

### J. Composite / summary metrics

| Item | Definition | Source |
|---|---|---|
| `masterEfficiencyScore` · "Composite score (fixed weights)" | `30·min(1, tpRate/120) + 25·max(0, 1−avgWait/60) + 15·max(0, 1−avgStops/5) + 20·clamp(fairness) + 10·(1−idleLoss)`, /100 (`efficiency.py:4-49`) | Backend, every snapshot |
| Weighted score · "Weighted score (your priorities)" | User-weighted `Σ wᵢ·normᵢ / Σ wᵢ × 100` over queued time (cap 60 s), throughput rate (cap 120 veh/min), avg queue (cap 15), fairness, stops (cap 5) (`scoring.ts:31-68`) | Frontend only; not exported, not stored |

Neither composite is a measurement; both are decision aids built on fixed reference caps (D-05).

---

## 3. Derived and statistical values

This section is the inventory of everything that is **not a raw measurement**. "Nature" uses: **D** descriptive statistic · **C** comparative (two runs/sides) · **I** inferential · **V** visualisation aid · **S** decision-support.

| Derived value | Inputs | Formula / logic | Question it answers | What it does NOT say | Nature · caveat |
|---|---|---|---|---|---|
| Control delay per vehicle | exit/spawn time, route length, desired speed | See §2A | "How much longer than free-flow?" | Whether the time was spent queued | D · geometric delay included (D-06) |
| Mean / median / P95 / min / max / SD of delay | per-vehicle delays | standard | Typical and worst-case experience | Run-to-run variability | D · single run |
| Baseline-clipped wait & stops | wait/stop counters at warm-up | `max(0, x − x_at_W)` | Waiting inside the measured window only | – | D |
| Time-averaged queue (per approach → mean of 4) | per-tick counts | mean of four time-averages | Typical queue | Peak or duration above a level | D |
| Queue SD / QSI | total queue per tick | SD; SD ÷ mean | Queue steadiness | Whether the queue is growing | D · CV, not stability |
| SVI | per-tick speeds | mean over ticks of CV | Speed uniformity | Cause of variation | D |
| PTI | travel times | P95 ÷ median | Budgeting time for a reliable arrival | Absolute speed | D · uses raw travel time |
| Jain's fairness | per-approach mean waits | `(Σx)²/(nΣx²)` | Equity between approaches | Which approach suffers; total delay | D · sensitive to tiny n |
| Utilisation | tick classification | share of ticks with mean speed > 0.5 | Fraction of time traffic was moving on average | Capacity used | D · near-constant 100 % |
| Idle-green loss | signal state, queues | tick share | Wasted green | Cost in seconds | D · signal-only |
| Critical saturation volume | arrival rate, throughput, spawned | see §2D | – (not a capacity estimate) | Capacity | D · misleading name (D-10) |
| Congested time | queue > 5 | `Σ dt` | Duration of heavy queuing | Severity | D |
| Difference Δ (R − S) | two sides' displayed values | `b − a` in the metric's units; `pp` for % (`catalog.ts:553-576`) | "By how much do they differ?" | Which is better; significance | C |
| "About the same / lower / higher" | two values | Similar if `gap ≤ abs` **or** `gap/larger ≤ rel`; tolerances: delay 1 s/5 %, vehicles 3/2 %, queue 0.5/10 %, stops 0.1/10 %, fairness 0.03 (`plainLanguage.ts:124-173`) | Plain-words comparison | Statistical significance | C, S · presentation thresholds only (D-16) |
| LOS grade | average delay, side | HCM bands: signal 10/20/35/55/80, roundabout 10/15/25/35/50 (`plainLanguage.ts:213-233`) | "Is that a long wait?" | HCM LOS (needs v/c and 15-min periods) | S · guided page only; Volume dashboard uses signal bands for both (D-18) |
| Fairness words | Jain index | ≥ 0.95 / 0.85 / 0.70 (`plainLanguage.ts:240-262`) | Plain reading | – | S |
| Headline sentences, "Why did this happen?" | S/R summaries | Rule-based text | Narrative | Causality — several sentences infer cause (e.g. backlog ⇒ "arriving faster than it could clear") | S |
| Time congested % | `congestionRecoveryTime / measured` | ratio (`ResultsReport.tsx:420-423`) | Share of measured time | – | V |
| Demand vs served % | `throughput / totalVehiclesSpawned`, `activeVehicleCount / totalVehiclesSpawned` | ratio, capped (`CapacityDemandVisualizer.tsx:36-43`) | "How much offered demand was served?" | – | V · mixes windows (D-12) |
| Flow-bar shares | `vehicleCounts` | % waiting / junction / cruising | Instantaneous mix | Run average | V |
| Fairness gauge mapping | index | `(f − 0.25) / 0.75` | Dial position | – | V · assumes n = 4 |
| Delay whisker positions | min, median, P95, max, mean | scaled to `max(15, maxDelay)` | Delay spread | Real IQR: the box is **median → P95** | V (comment says IQR) |
| `masterEfficiencyScore` / weighted score | see §2J | Weighted sum of clamped linear scalings | "One number to compare?" | Which is better in general; caps are project-chosen | S (D-05) |
| Δ %, winner, crossover, tier tally, largest gap | sweep per-tier delays | see §2I | Direction of difference by demand | Statistical certainty (one seed each) | C, S (D-02, D-15, D-16) |
| Mean, SD, CI95 | per-seed metrics | see §2H | Central tendency and spread across seeds | Long-run truth | D · z instead of t (D-03) |
| Cohen's d + word bands | two seed samples | pooled-SD standardised mean difference; <0.2 negligible, 0.2 small, 0.5 medium, 0.8 large | Practical size of the gap | Significance | C · unpaired form used on paired seeds (D-17) |
| Welch t, df, p, `significant` | two seed samples | Welch–Satterthwaite; two-tailed Student-t | Could the gap be chance? | Effect size; practical importance | **I** · n = 3–10, three metrics uncorrected (D-17) |
| Verdict banner (all / any / no significance) | three p-values | `every` / `some` of `p < α` | Overall statistical statement | Independence of the three metrics | I, S (D-04, D-17) |
| Seed win rate, tally | seed rows | counts | How often does a side win a seed? | Effect size | D · ties by exact float equality |
| Reproduction check | original vs re-run metrics | `|Δdelay| ≤ 0.05 s`, `|Δthroughput| ≤ 0.1` (`main.py:2137-2162`) | "Does the same seed reproduce?" | Equality of other metrics | Verification |
| Invariant checks | per-tick conservation and speeds; same-seed re-run | see §9 D-08 | Model integrity | Anything about the roundabout engine | Verification (D-08) |
| Run comparison API | two stored runs | Δ delay, Δ %, Δ throughput, Δ queue, Δ total stops, `winner` = lower delay, exact | Programmatic diff | Significance; tie band | C (D-15). Not called by the UI |

---

## 4. Plain-English explanation of every metric

Each row: **Technical** (what is being measured) · **Plain English** (for someone with no traffic-engineering background) · **Practical interpretation** (what a change means for people using the road). "Practical" statements are hedged deliberately; none claims a control is better in general.

### 4.1 Delay and waiting

| Metric | Technical | Plain English | Practical interpretation |
|---|---|---|---|
| Average delay (`averageDelay`) | Mean per-vehicle (actual journey time − journey time at the driver's own desired speed) | How much longer the average journey took than it would through an empty junction | A higher value means drivers spent longer than an unobstructed drive: waiting, slowing to enter a roundabout, or both. It does not tell you which |
| Median delay | 50th percentile of the same | The delay of the "middle" driver | If the median is far below the average, most drivers were fine and a few had a bad time |
| 95th percentile delay | Value below which 95 % of drivers' delays fall | "1 in 20 drivers lost more than this" | The bad-day experience. A large gap over the average means an unpredictable junction |
| Minimum delay | Smallest delay observed | The luckiest driver | Zero at the signal when someone drives straight through; at the roundabout it is never zero because every driver slows to enter |
| Maximum delay | Largest delay observed | The unluckiest driver | One vehicle; treat as an outlier, not a typical experience |
| Delay standard deviation | Sample SD of per-vehicle delay | How different drivers' experiences were | Bigger = less predictable; this is spread *inside one run*, not certainty about the result |
| Average queued time (`averageWaitTime`) | Mean seconds at < 0.5 m/s | Time spent basically stopped | Lower means less standing still. A junction can have high delay but low queued time if traffic keeps rolling slowly |
| Stops per vehicle | Mean count of drops below 0.1 m/s | How many times the average driver had to come to a halt | Each stop costs slowing and re-accelerating time and fuel; fewer usually means smoother driving |
| Total stops | Sum of stops over exited vehicles | Total number of halts | Grows with traffic and run length; compare stops **per** vehicle instead |
| Planning time index | P95 ÷ median journey time | How much extra time you would budget to be sure of arriving on time, relative to a typical trip | 1.0 = trips take about the same each time; 2.0 = allow double the typical time. Says nothing about how long a trip is |
| Low-sample flag | fewer than 20 exited vehicles | "Too few cars finished to trust the spread" | Read the 1-in-20 and fairness figures as rough |
| Current mean speed | Mean speed of every vehicle now | How fast traffic is moving right now | A snapshot: dips while queues form, recovers after |
| Speed variance index | Mean over time of (SD of speeds ÷ mean speed) | How uneven the speeds of cars on the road are | High = stop-start mix; low = everyone moving similarly. Includes free-flowing cars, so it is not a pure "congestion" measure |

### 4.2 Queues and congestion

| Metric | Technical | Plain English | Practical interpretation |
|---|---|---|---|
| Queue length now (per approach) | Vehicles below 0.5 m/s on that approach's inbound lanes | How many cars are lined up waiting on each road right now | Shows which direction is backing up at this moment |
| Average queue per approach | Time-average queue, averaged over four approaches | The typical line of waiting cars on one road | Longer typical lines mean more people waiting more of the time |
| Maximum queue | Largest queue on any approach at any tick | The longest line that ever formed | Shows worst-case back-up; a one-moment extreme, so noisy |
| Average total queue when queued | Mean of the whole-junction queue only over ticks where one existed | How big the line is when there is one | Distinguishes "rarely queues" from "always queues" only if read next to the average |
| Queue standard deviation | Sample SD of the total queue | How much the total line length bounces around | Larger = more surge-and-clear behaviour |
| Queue stability index | Queue SD ÷ mean queue | The bounciness of the line relative to its size | High = queues appear and vanish in bursts; low = steady. Does **not** tell you if the queue is growing |
| Time congested | Seconds with more than 5 vehicles queued in total | How long the junction was properly backed up | Longer = more time in a heavily queued state. The "5" is a fixed rule of thumb |

### 4.3 Throughput, capacity and demand

| Metric | Technical | Plain English | Practical interpretation |
|---|---|---|---|
| Vehicles served | Count exited after warm-up | Cars that made it all the way through | More means more got through in the same time from the same arrivals. Both sides get identical arrivals, so a gap reflects the junction |
| Throughput rate | Exits per minute over the last ≤ 60 s | How fast cars were leaving right at the end | Rises then plateaus as the junction fills; last-minute only |
| Vehicles generated | Cars created since the start | How many cars were fed in (until a 200-car cap) | If it equals the cap, demand was cut off |
| Vehicles in network now | Cars currently on the road | Cars still on their way or stuck | A large number still inside at the end suggests a backlog |
| Critical saturation volume | Estimator ≤ arrival rate (see §2D) | The tool's rough guess at the rate the junction can carry | Do **not** read it as capacity; at low demand it just echoes demand |
| Service utilization | Share of ticks where average speed > 0.5 m/s | The share of the time traffic was, on average, moving | Near 100 % almost always, so it rarely distinguishes anything |
| Idle green loss | Share of ticks a red approach queued while all green approaches were empty | Time the light was green for nobody while someone waited | Only for the signal. Higher = more of the cycle wasted; a roundabout has no green to waste, so "0" is not a win |
| Junction footprint | Area from geometry (see §2D) | How big the junction is | Not like-for-like across geometries; interpret as design context only |
| Vehicle states (approaching / waiting / crossing / in roundabout / exited) | Counts by state in the snapshot | Where every car currently is in its journey | A live picture; "exited" includes warm-up |

### 4.4 Fairness and safety

| Metric | Technical | Plain English | Practical interpretation |
|---|---|---|---|
| Directional fairness | Jain's index of the four approaches' mean waits | Whether every road had to wait about equally | 1.00 = equal waiting; lower = some roads wait far more. Noisy with few cars, and depends on how traffic was randomly split between roads |
| Collisions | Distinct overlapping vehicle pairs | Times two cars ended up in the same space in the model | A sign the model hit a limit in this scenario, **not** a prediction of real crashes |
| Minimum TTC | Smallest constant-speed time-to-collision between different-lane vehicles | The closest call, measured as "how many seconds until impact if nobody changed speed" | A lower minimum means a closer approach happened at least once. Can only ever go down during a run |
| Low-TTC events | Pair-ticks at or below 1.5 s | How many moments a pair was within 1.5 s of impact | More = more near-misses *observations*; one slow encounter counts many times |
| TTC observations | Pair-ticks with a defined TTC | How much data the TTC numbers rest on | Compare only with caution across geometries |
| Minimum PET | Smallest gap between successive vehicles at a signal conflict point | The tightest gap between one car leaving a crossing point and the next arriving | Lower = tighter. Signal only |
| Low-PET events | Crossings with PET at or below 5 s | How many close successive crossings | With a 5 s threshold well over half of all crossings qualify |
| PET observations | Count of PET measurements | Data behind PET | Signal only |

### 4.5 Composite scores

| Metric | Technical | Plain English | Practical interpretation |
|---|---|---|---|
| Composite score (fixed weights) | See §2J | One 0-100 number blending five measures | A weighting choice, not a verdict; inflated for a roundabout by design (D-05) |
| Weighted score (your priorities) | See §2J | A 0-100 number using the priorities you set | Shows what your weights imply; changes only because you moved sliders |

### 4.6 Study, sweep and statistics

| Metric | Technical | Plain English | Practical interpretation |
|---|---|---|---|
| Hourly volume | arrival rate × 3600 | How many cars per hour arrive at the whole junction | Convenient unit for planners |
| Delay Δ % | `(R − S) / S × 100` | How much longer or shorter the roundabout's delay is than the signal's, in percent | Positive means the **signal** had the lower delay. Percentages balloon when the signal delay is tiny |
| Winner / "lower mean delay" | Tie band 0.2 s or 2 %, else lower mean delay | Which side had the lower average delay at that traffic level | One run per level; it is a description of one sample |
| Crossover | First traffic level after the delay ordering flips | Where the lower-delay side changes | A hint about where to look, from a single random pattern per level. Not a capacity boundary |
| Tier tally / largest gap | Counts / max difference | How many traffic levels each side had lower delay / where the gap was widest | Descriptive only |
| Mean and standard deviation across patterns | Over N seeds | The average result and how much it changed between random traffic patterns | Larger SD = more dependence on which cars happened to arrive when |
| 95 % confidence interval | `1.96·SD/√N` | A range around the average that should usually contain the true average | As implemented it is too narrow at small N (D-03) |
| p-value | Welch t-test | How surprising the gap would be if there were really no difference | Small (< 0.05) means unlikely to be luck. Not the size of the gap |
| Cohen's d | Standardised mean difference | How big the gap is compared with normal pattern-to-pattern variation | Words: negligible / small / medium / large; a huge d with n = 5 can still be luck |
| Degrees of freedom | Welch–Satterthwaite | Technical detail of the t-test | Ignore unless reproducing the test |
| Seed win rate / tally | Count of seeds where a side had lower delay | In how many random patterns did each side win? | A quick consistency check; not a test |
| Reliability verdict (consistent / not consistent / about the same) | See §2H | The tool's plain-language reading of the statistics | Wording follows the t-test only |
| Integrity check | Conservation, speed ≥ 0, determinism | Did the simulation behave sanely, and does the same seed give the same answer? | Only the **signal** engine is checked (D-08) |
| Reproduction check | Re-run to same seed, compare delay and throughput | Does re-running this saved run give the same numbers? | A "no" flags a code or config change |

---

## 5. Chart and visualisation inventory

Audience column: **L** layman, **R** researcher, **B** both. "Misleading risk" states what a reader could wrongly conclude.

### 5.1 Guided results and guided live view

| # | Visual · page | Type · axes · series | Metrics | Intended message | Suitability · risk |
|---|---|---|---|---|---|
| G1 | Paired bars in the four "question cards" · Results (`ResultsReport.tsx:52-78`) | Horizontal paired bars; no axis; bar width = value ÷ max of *that row*; series signal, roundabout; min width 2 % | delay, P95, stops · served, in-network · avg queue, max queue, time congested | "Which side is bigger, roughly?" | B. **Bars are scaled per row**, so bar lengths cannot be compared across rows; a 2 % floor can make zero look non-zero |
| G2 | Fairness list · Results | Text + band word | fairness | Plain equity reading | L. Band edges are presentation choices |
| G3 | LOS grade line · Results | Text (A–F + words) | average delay | "Is that a long wait?" | L. HCM bands applied to a delay that includes geometric delay (D-06); HCM assumes 15-min analysis periods |
| G4 | "Scenarios you have run this session" · Results | Table (S · R pairs) | delay, served, longest queue | Compare scenarios side-by-side | L. Pair strings, not a chart |
| G5 | Reliability box + statistics table + per-seed table · Results (`ReliabilityCheck.tsx`) | Verdict table (Consistent / Not consistent / About the same) + numeric tables | delay, throughput, queue across seeds | "Does the difference hold across random patterns?" | B. Depends on z-based CI, unpaired test, n = 5 or 10 (D-03, D-17) |
| G6 | Live guide 3-row table · Watching (`LiveGuide.tsx`) | Table | vehicles waiting now, got through, time lost | Live progress in plain words | L. "Vehicles waiting now" is `vehicleCounts.waiting` (state waiting on any non-junction lane, incl. exit lanes; a stopped vehicle inside the junction/ring counts as crossing/in-roundabout), unlike the queue metric which counts approach lanes only (§1.2) |
| G7 | "All measurements" (`ComparisonSections`) · Results, specialist disclosure | Grouped table: Signal · Roundabout · Δ (R − S) | every catalog metric | Full transparency without ranking | R. Diagnostics group collapsed by default |

### 5.2 Live comparison (side panel and full dialog)

Time axes are simulated time `m:ss` sampled ~once per simulated second; history keeps the last 200 points, so runs longer than ~200 s lose their beginning silently (`useLiveComparisonHistory.ts:69, 116-121`). All time-series plot **running aggregates** (each point is the mean/percentile over all exits *so far*), so they smooth and converge rather than show transients.

| # | Visual (component) | Type · Y axis · series | Metrics | Intended message | Suitability · risk |
|---|---|---|---|---|---|
| L1 | Vehicles now pipeline (`VehiclesFlowVisualizer`) | 4 KPI stages (In network, Waiting, In junction, Exited) with Δ | vehicleCounts | Where cars are now | B. "Exited (Served) — whole run" includes warm-up and differs from "Vehicles served" (D-12) |
| L2 | Live flow bar | Stacked 100 % bar per side: waiting / in junction / cruising | vehicleCounts | Instant mix | L. Signal "in junction" = crossing only; roundabout = crossing + circulating |
| L3 | Delay dynamics (`PerformanceCharts`) | Line; Y = s; avg (compact) plus median and P95 (full) per side | avg/median/P95 delay | Are delays growing or settling? | B. Running mean → lags reality; P95 is noisy at low n |
| L4 | Queued-time trend | Line; Y = s | averageWaitTime | Waiting trend | R. Distinct from delay; the two can diverge (D-07) |
| L5 | Cumulative vehicles served | Area; Y = veh | throughput | Progress of service | B. Cumulative count: lines only diverge slowly |
| L6 | Throughput rate | Line; Y = veh/min | throughputRate | Recent exit rate | R. Rolling 60 s window; jagged at low volume |
| L7 | Mean speed + 0.5 m/s wait threshold | Line + red reference line; Y = m/s | averageTravelSpeed | Speed in the network; line marks "waiting" | B. Instantaneous, dips at every queue |
| L8 | Planning time index + ideal 1.0 line | Line; Y from 0.8; Y = ratio | travelTimeReliability | Journey-time predictability | R. "Ideal 1.00" label implies 1.0 is good in itself |
| L9 | Approach queue distribution | Paired horizontal bars ×4 directions | currentQueueLengths | Which approach is backing up now | B. Instantaneous; repeated in the sidebar "Queues now" |
| L10 | Directional fairness gauges | Semi-circular dials ×2; scale 0.25-1.0 | fairness | Equity at a glance | B. Note text says "equal *delay*"; metric is *wait* (D-14) |
| L11 | Queue parameters / Stops and congestion time lists | Numeric S vs R lists | avg/max/active-avg queue, QSI, stops, total stops, time congested | Detail | R. Six queue-related numbers (§8) |
| L12 | Collision counter cards + event chips (`SafetyTimelineVisualizer`) | Big-number cards and chips at first-seen times | collisionCount | "Did overlaps occur?" | B. Model-integrity signal, whole run including warm-up; label "Zero collisions recorded" reads like a safety result |
| L13 | Minimum TTC trend with threshold line | Line; Y = s; reference line at threshold | minTTC | Approach over time | R. **Running minimum**, so it can only decrease; subtitle claims "Hayward critical cutoff" |
| L14 | Low-TTC and PET cards | Numeric | ttc/pet events, samples, min | Exploratory conflict indicators | R. Different units per metric (pair-ticks vs crossings); PET N/A for roundabouts |
| L15 | Demand vs served balance | Stacked bars per side: served %, in-network %, remaining | throughput, activeVehicleCount, totalVehiclesSpawned | Offered vs served | B. Numerator excludes warm-up exits, denominator includes all spawns (D-12) |
| L16 | Service utilisation rings | Ring dials ×2, 0-100 % | intersectionUtilization | Time flowing | L. Reads as capacity use; is pegged at ~100 % |
| L17 | Critical saturation volume · Idle green loss · Junction footprint cards | Numeric + one progress bar (idle) | CSV, idleOpportunityLoss, footprint | Capacity context | R. Footprint not like-for-like (D-11b); CSV not a capacity |
| L18 | Delay distribution whisker (`DistributionDiagnosticsVisualizer`) | Custom bars: range min→max, box median→P95, dot at mean; X scale = max(15, max delay) | min/median/mean/P95/max delay | Spread of driver delays | R. Box is not an IQR; scale shared across sides but not across time |
| L19 | Dispersion and composite score panel | Numeric + score badges | delay SD, queue SD, QSI, SVI, masterEfficiencyScore | Variability; single-number | R. Composite flattered for roundabout (D-05) |
| L20 | Weighted scoring panel (dialog) (`WeightedScoringPanel`) | Two score bars + 5 sliders + presets | queued time, throughput rate, avg queue, fairness, stops | "What if my priorities differ?" | R. Shown even during warm-up with best-case placeholders (D-05) |
| L21 | Single-control sidebar (`MetricsSidebar`) | Queue bars, chips, tables | queues, counts, controller state, all catalog metrics | Single-run inspection | R |
| L22 | Map overlays | `Q n` per approach; brake lights | queueLength, state | Live picture | B |

### 5.3 Research Lab

| # | Visual (page) | Type · axes · series | Metrics | Intended message | Suitability · risk |
|---|---|---|---|---|---|
| V1 | Delay vs volume (Volume dashboard) | Line; X = veh/h or veh/s (toggle); Y = s; 2 series; optional 4 envelope lines; crossover reference line | delay, delayMin/Max/StdDev | How delay grows with demand | R. Single seed per tier. Envelope is **within-run** min/max or ±σ, not uncertainty (D-19) |
| V2 | Throughput vs volume | Line; Y = veh (count) | throughput | Where service saturates | R. Count per run (duration-dependent), not veh/h |
| V3 | Queue vs volume | Line; Y = veh; optional peak lines | avg queue, max queue | Queue growth | R |
| V4 | Delay Δ % and Queue Δ % vs volume | Line; Y = %; signed | delayDeltaPercent, queueDeltaPercent | Relative gap by demand | R. Legend "+ = signal lower" is counter-intuitive; % explodes when the denominator is small |
| V5 | KPI cards: "Critical Saturation Crossover", tier tally, largest gap, peak volume | Cards | crossover, winner counts, max Δ | Summary | R. First card's name suggests capacity; it is a delay-ordering flip (D-10) |
| V6 | Demand Explorer scrubber with LOS chips | Slider snapped to nearest tier; chips show LOS by delay | delay | Explore a tier | B. LOS uses signal bands for both (D-18) |
| V7 | Results table with delay bar and LOS | Table | delay, throughput, queue, winner, Δ | Per-tier record | R |
| V8 | Tier metrics table (`TierMetrics`) | Full ComparisonSections for one tier | every metric | Full detail at one tier | R |
| V9 | Insights cards and HCM LOS chips | Text and chips | none measured | "Engineering guidance" | **Should not be shown as results**: contains unmeasured claims (D-01) |
| V10 | Verdict banner (Validation dashboard) | Banner (all / partial / no significance) + seed win pill | p-values, seed wins | Overall statistic | R. Hard-coded "α = 0.05" and "95 % CI" text vs selectable confidence (D-04) |
| V11 | CI cards: mean ± CI bars, Cohen's d, p, df, sig badge | Custom bar with CI whisker ×3 metrics | delay, throughput, queue stats | Difference, size and certainty | R. z-based CI (D-03); delta pill coloured green/red (implicit "better") |
| V12 | Seed-by-seed grouped bar chart | Bars; X = seed; Y = selected metric; mean reference lines | per-seed metrics | Consistency across seeds | R. Colour scheme differs from the live panels (blue/emerald vs amber/cyan) |
| V13 | Per-seed table | Table | per-seed delay/throughput/queue, Δ, lower-delay | Raw evidence | R |
| V14 | Methodology cards | Formulas and effect-size bands | – | Explains the tests | R. Prints `CI₉₅ = X̄ ± 1.96 × (σ/√N)`; tab labelled "Proofs" |
| V15 | Integrity check card | Pass/fail bullets | invariants, determinism | Model sanity | R. Claims "both controls" (D-08) |
| V16 | History table; Compare page; Run page | Tables of stored metrics with Δ vs a baseline; reproducibility panel | all catalog metrics | Audit and reproduce | R. Explicit "Δ does not say which is better" |

**Redundant / confusing / poorly labelled** (no redesign proposed here; see §8): L3 and L18 both show avg/median/P95; L9 duplicates L21's "Queues now"; L11 lists six queue numbers; L16 is uninformative; L13 misleading form; V9 must not be presented as data; V5's first card is mislabelled.

---

## 6. User-facing evaluation model

**What UrbanFlow asks a normal user to evaluate:** *"For this junction and this traffic level, given the same cars, how do drivers, queues and throughput compare if the junction is a fixed-time signal versus a roundabout — and how far can I trust that comparison?"* It deliberately does **not** pick a winner (`ResultsReport.tsx:272-276`).

| User question | Metric | Why that metric | Graph / number | Interpretation (never universal) |
|---|---|---|---|---|
| How long do drivers wait? | Average delay (+ LOS word) | Total extra time relative to an unobstructed journey | G1 bar; LOS line | Lower = less time lost against free-flow; part of a roundabout's delay is geometric, not waiting |
| What about the unlucky ones? | 95th percentile delay | Tail experience | G1 bar ("1 in 20") | Big gap over average = unpredictable |
| How often do drivers stop? | Stops per vehicle | Smoothness | G1 bar | Fewer stops = smoother flow |
| How much traffic gets through? | Vehicles served | Output from identical arrivals | G1 bar | More = more cleared in the same time |
| Is a backlog building? | Vehicles still in network | Unserved load | G1 bar ("still waiting or moving") | Larger and growing = demand exceeded service |
| How long do queues get? | Typical queue on one approach; longest queue; time with > 5 queued | Standing queues on approach lanes | G1 bars | Longer/more time = more people waiting; longest = single-moment extreme |
| Is every direction treated alike? | Directional fairness | Equity of waiting across roads | Fairness list with words | 1.00 = equal; low = some roads wait far more; noisy with few cars |
| Why did they differ? | Idle green loss (signal), stops, backlog | Mechanisms | "Why did this happen?" cards | Data-driven lines quote a measurement; the roundabout mechanism text is static |
| Can I trust this? | Collisions, sample-size flag, warm-up, one-seed caveat, lanes caveat | Model limits | Trust list; reliability check | One run = one traffic pattern; the reliability check re-runs with new patterns |
| What if traffic is heavier or lighter? | Session table; "Try quieter / busier" | Sensitivity | Session table | Differences change with demand |
| Is the difference real or luck? | p-value + Cohen's d (as words) | Inference over random patterns | Reliability box | "Consistent" = t-test p < 0.05 at n = 5/10 |

---

## 7. Researcher evaluation model

| Research question | Metric(s) | Statistical method | Visualisation | Interpretation | Limitation |
|---|---|---|---|---|---|
| **Single run:** what happened in this scenario? | Full catalog (§2) | Descriptive statistics only | L3-L19, tables T, `MetricsSidebar` | Observations of one arrival pattern | One realisation; the directional split is random per seed (D-13) |
| **Repeated runs / multi-seed:** does the signal-vs-roundabout difference persist? | delay, throughput (count), average queue | Welch t-test, Cohen's d, mean ± CI, seed tally (`validation.py`) | V10-V13; reliability box | Significant + non-negligible d ⇒ difference unlikely due to arrival randomness *for this scenario* | z-CI (D-03); unpaired test on paired seeds; three metrics uncorrected; n = 3-10; random seeds not user-settable (D-17); only 3 of ~45 metrics |
| **Volume sweep:** how does the comparison change with demand? | delay, throughput, queue per tier; winner; crossover | Tolerance-band classification; sign-change detection | V1-V4, V7 | Shape of delay/throughput vs demand | One seed per tier; no CIs; crossover is an upper-bracket demand, not interpolated; 2-lane default is uncalibrated (D-02, D-09) |
| **Capacity / saturation analysis:** where does the junction stop keeping up? | throughput vs arrival rate, `activeVehicleCount` growth, queue growth | Descriptive; `criticalSaturationVolume` (weak) | V2, V3; L15 | Served rate flattening below offered rate signals saturation | No metric measures capacity directly; `criticalSaturationVolume` cannot exceed offered load (D-10); volume cap 200 (D-24). Use `comparative_report.md §2` method (240 s / 30 s warm-up / veh/h offered vs served) |
| **Statistical validation:** is a claim supportable? | Same three metrics; effect size | Hypothesis test at chosen α | V10-V14 | Provide p, d, CI together | Verdict wording overstates ("Confirmed", "Proofs"); mismatch between selectable α and fixed backend `significant` (D-04) |
| **Reliability checks / reproducibility:** can a result be reproduced and audited? | delay, throughput | Same-seed re-run within 0.05 s / 0.1 veh; provenance (commit, config, seed) | V16, `RunPage`, `IntegrityCheck` | Determinism confirms code/config stability | Only two metrics compared; integrity check covers the signal engine only (D-08) |
| **Safety (exploratory):** do conflict indicators differ? | collisions, TTC family, PET family | Counts and minima | L12-L14 | Exploratory only | Not comparable across geometries (§2F); PET signal-only; thresholds unvalidated |
| **Composite trade-off:** weighting sensitivity | `masterEfficiencyScore`, weighted score | Weighted sums | L19, L20 | How conclusions shift with preferences | Reference caps are project-chosen; placeholders inflate scores (D-05) |

---

## 8. Redundancy and overload audit

**Near-duplicate measures (same idea, several numbers):**
* *Waiting:* `averageDelay`, `averageWaitTime`, `averageStopsPerVehicle`, `totalStops`, `p95Delay`, `averageQueueLength`, `congestionRecoveryTime`. The last three also duplicate one another's message.
* *Queues:* `averageQueueLength`, `maxQueueLength`, `activeAverageQueueLength`, `queueStdDev`, `queueStabilityIndex`, `congestionRecoveryTime`, plus live `currentQueueLengths` in two panels.
* *Throughput:* `throughput`, `throughputRate`, "Exited (Served)", `totalVehiclesSpawned`, `activeVehicleCount`, Demand-vs-served %.
* *Speed variability:* `averageTravelSpeed`, `speedVarianceIndex`, `intersectionUtilization`.
* *Composite:* two different composite scores with different inputs and weights (backend 30/25/15/20/10 with idle loss; frontend 30/30/15/15/10 with queue). They can disagree about which side is ahead.
* *Delay presentation:* delay tab (L3) and whisker (L18) show the same five values; guided card and KPI cards repeat them again.

**Metrics that directly contradict one another in the same run** *(verified by run)*: at 0.3 veh/s, 1 lane, signal vs roundabout: `averageDelay` 7.7 vs 20.6 s (signal lower), but `averageWaitTime` 3.8 vs 1.3 s, `averageQueueLength` 0.76 vs 0.17 and `maxQueueLength` 5 vs 3 (roundabout lower). Nothing in the UI explains why (geometric delay vs queued time, D-06/D-07).

**Researcher-only:** all of `minDelay`, `maxDelay`, `delayStdDev`, `queueStdDev`, `queueStabilityIndex`, `speedVarianceIndex`, `ttcSampleCount`, `petSampleCount`, `criticalSaturationVolume`, `intersectionUtilization`, `spaceFootprintConsumed`, both composites, TTC/PET family, `totalStops`, `activeAverageQueueLength`, PTI, and all of §2H-2I.

**Keep prominent (already on the guided page):** average delay, vehicles served, average queue, stops, backlog (`activeVehicleCount`), fairness — plus the trust caveats. Consider also keeping the *contradiction explanation* prominent (delay vs queued time).

**Terminology too technical for laypeople:** control delay, Jain's index, planning time index, speed/queue "variance/stability" indices, critical saturation volume, service utilisation, TTC/PET, post-encroachment time, Cohen's d, Welch, df, α, CI.

**Easily misunderstood (see §9):** "Service utilization" (reads as capacity use), "Critical saturation volume" and "Critical Saturation Crossover" (neither is capacity), "Idle green loss = 0" for the roundabout (reads as a win), "Collisions" (reads as safety), "Planning time index 1.0 = ideal", "Vehicles generated" (called offered demand but capped), "Exited (Served) — whole run", "Minimum TTC" trend, delay Δ% sign, "Composite score".

**Exposed without enough context:** delay (geometric component), fairness (random directional split), Δ% and crossover (one seed), any Research Lab default (2 lanes, uncalibrated for the roundabout), CI (z-based), composite scores (fixed caps), LOS chips in the Volume dashboard.

**Charts needing better explanation:** L13 (min TTC as a running minimum), L15 (mixed windows), L18 (what the box is), L16 (what 100 % means), V1 (what the envelope is), V4 (sign convention), V5, V9.

---

## 9. Scientific validity findings

Severity: **H** can lead a reader to a wrong conclusion · **M** inconsistent or overclaimed · **L** cosmetic/definition drift.

### H-1 · D-01 — Volume dashboard "Insights" tab contains unmeasured, contradicted claims
`VolumeAnalysisDashboard.tsx:2593-2680`. Hard-coded text: *"Up to 50% reduction in average vehicular delay vs. fixed signals"* (line 2620); *"a multi-phase adaptive traffic signal or turbo-roundabout … is mathematically required"* for volumes above the crossover (2661); *"modern roundabouts provide clear carbon emission reductions, lower fuel consumption, and higher safety margins"* (2662, shown when no crossover was found); badges "Low-Medium Volumes (< Crossover)" versus "High Over-Capacity (> Crossover)" assume which side wins on which side. None of fuel, emissions or safety margin is computed. `docs/reports/comparative_report.md` (§2–§3) finds the opposite: no significant low-demand delay difference, and the signal lower-delay at saturation. The tab is also the only place the UI contradicts its own "no winner" stance.

### H-2 · D-02 — Sweep verdict text hard-codes which side wins where; crossover semantics
`report_generator.py:55-65` writes "Below that point the roundabout had the lower measured delay … at or above it the signal did" whenever a crossover exists and both sides have wins, whichever direction the data actually took. `crossoverArrivalRate` (`volume_sweep.py:203-210`) is the *upper* rate of the first bracket whose raw delay difference changes sign; it ignores the tie band that `winner` uses (`:299-305`), so two tied tiers can create a "crossover"; a difference of exactly 0 does not count. The frontend `crossoverSummary` (`VolumeAnalysisDashboard.tsx:130-151`) is data-driven and correct in direction; the backend text used in the study report is not.

### H-3 · D-03 — 95 % CI uses z = 1.96 while the p-value uses Student's t
`validation.py:18` (`ci95 = 1.96·std/√n`) vs `validation.py:153` (Student-t p-value, Welch df). At n = 5 (df ≈ 4) the correct multiplier is 2.776, so displayed CIs are ≈ 29 % too narrow; at n = 10, 13 % too narrow. Displayed in `ReliabilityCheck.tsx:184-187`, `ValidationDashboard.tsx:1194-1195, 1517`, and in the CIs quoted in `comparative_report.md §2-3`. `test_compare_groups.py:175-191` pins the old formula as "unchanged".

### H-4 · D-04 — Confidence level selector is only partly wired
Validation dashboard offers 90/95/99 % (`ValidationDashboard.tsx:272-275, 430`). CI bars use the selected z and significance badges use the selected α, but the header text is hard-coded "α = 0.05" and "95% confidence intervals" (1069, 1084), and the per-metric "sig-pill"s use the backend's fixed `significant` (`validation.py:154`). At 90 % or 99 % one screen shows two significance conventions.

### H-5 · D-05 — Composite scores are not comparable evaluations
* **Free 10 points for the roundabout.** `idleOpportunityLoss` is structurally 0 for roundabouts (`factory.py:39-43` reports all approaches green; `idle_loss.py:35` then returns False), so `idle_norm = 1` in `efficiency.py:38`. *(Verified: at 0.15 veh/s the roundabout scores 70.5 vs signal 68.0 although its throughput term is smaller, 0.5 vs 0.75 of 30 points.)*
* **Throughput term scores demand.** `tp_norm = min(1, rate/120)`: at 0.3 veh/s (≈ 18 veh/min) it cannot exceed 0.15 regardless of quality; a low-demand scenario forfeits roughly 25 of the 30 throughput points before any junction difference.
* **Best-case placeholders.** Fairness 1.0, wait 0, stops 0 when there are no exits give a high score before anything has been measured; the frontend weighted score (`scoring.ts:31-68`, invoked with raw metrics by `ComparativeDashboard.tsx:542-546`) applies no warm-up or no-exit gate.
* **Two composites, different inputs and weights**, neither documented against the other; both use "average queued time" rather than the headline delay.

### M-1 · D-06 — "Delay" includes geometric slow-down; unlike "waiting"
`collector.py:350-366` uses free-flow at `desired_speed` (default 18–25 m/s), whereas the roundabout controller is configured with `entrySpeed 5.0`, `circulatingSpeed 8.0` (`dual_orchestrator.py:56-64`). *(Verified: roundabout average delay 12.9 s at 0.15 veh/s while `averageWaitTime` is 0.0 s and queue is 0.)* The guided page says "extra time compared with driving through an empty junction at the driver's own speed" (accurate) but then applies HCM LOS bands, and HCM control delay excludes geometric delay. `comparative_report.md §3` records the same sensitivity to approach speed. `07-metric-contract.md` has no definition of `averageDelay` at all.

### M-2 · D-07 — Metrics disagree in direction with no explanation
See §8. This is not a defect in any metric but is the most likely source of user confusion.

### M-3 · D-08 — Integrity check overclaims
`IntegrityCheck.tsx:54-56` says both controls are stepped and checked; `validation.py:338-355` checks mass conservation and negative speeds only on the **signal** engine, determinism only compares signal delay and throughput (`:363-384`), the docstring's invariant 3 ("green exclusivity") is not implemented, and `massConservationValid` is simply "no violations of any kind" (`:395`).

### M-4 · D-09 — Research Lab defaults sit outside the calibrated regime
Sweep and validation defaults use 2 lanes per approach (`volume_sweep.py:48-56`, `validation.py:174-180`, `VolumeAnalysisDashboard.tsx:461`, `ValidationDashboard.tsx:305, 353`) although `v1-known-limitations.md §3` and `comparative_report.md §2` state that only the 1-lane pair is calibrated (single circulating lane). The guided flow warns (`plainLanguage.ts:436-441`, `ScenarioSetup.tsx`); the Research Lab does not. Defaults are also short: sweep 60 s with 15 s warm-up (45 s measured), validation 30 s / 5 s, study report 30 s / 20 s (`report_generator.py:105-108`).

### M-5 · D-10 — "Critical saturation volume" is not a capacity
`derived_metrics.py:37-74`: result is `throughputRate/60` when that is below the arrival rate, else `arrivalRate · throughput / spawned`, hence ≤ offered load (except when the ratio > 1 because pre-warm-up vehicles exit late). The contract calls it "maximum arrival rate … higher is better (more capacity)". The Volume dashboard KPI "Critical Saturation Crossover" (`:1455`) is a different quantity (delay-ordering flip) with a near-identical name.

### M-6 · D-12 — Mixed windows in "served" figures
`CapacityDemandVisualizer.tsx:36-43`: post-warm-up exits ÷ all-time spawns. `VehiclesFlowVisualizer.tsx:65-66`: "Exited (Served) — Whole run" (includes warm-up). `throughput` elsewhere is post-warm-up. Three numbers, two windows, near-identical labels.

### M-7 · D-13 — Safety surrogate definitions and demand split
* Catalog text (`catalog.ts:262, 428`) says TTC is between "a following vehicle and its leader", but `find_ttc_events` excludes same-lane pairs by design (`safety_conflicts.py:148-157`).
* `ttcEventCount` counts pair-ticks (`collector.py:235-243`) while `petEventCount` counts crossings — different units in one panel.
* `minTTC` is a run-long running minimum (`collector.py:239-240`); the "Minimum TTC trend" chart can only decrease.
* Sample counts differ by geometry *(verified: 41 vs 0)*, so counts are not comparable.
* PET threshold 5.0 s tags 55-60 % of all observations *(verified: 134 of 222 at 0.6 veh/s; 17 of 31 at 0.15 veh/s)*, so the count barely discriminates between busy and quiet crossings.
* When `directionalSplit` is not set (guided and dashboard config never set it), the spawner draws random weights in [0.5, 2.0] per approach (`spawner.py:65-77`). Both sides share it, so the comparison stays fair, but fairness, per-approach queues and `maxQueueLength` partly reflect a random demand imbalance the user is not told about *(verified: split 0.14 / 0.35 / 0.33 / 0.18 at seed 1)*.

### M-8 · D-14 — Fairness definition drift
UI note "equal delay across approaches" (`TrafficFlowVisualizer.tsx:197-198`) vs metric = mean **wait** time (`fairness.py`). It uses raw `wait_time` (`fairness.py:30`) whereas `averageWaitTime` subtracts the warm-up baseline (`collector.py:419-425`); 0.25 is the floor only when all four approaches have data.

### M-9 · D-16 / D-15 — Three inconsistent "tie" rules and an exact-equality winner
Sweep: `|Δ| ≤ 0.2 s or < 2 %` (`volume_sweep.py:300`). Guided page: 1 s or 5 % (`plainLanguage.ts:125`). Run comparison API: exact float equality (`main.py:2029-2035`), and its `winner` field returns the `intersection_type` string, ambiguous when both runs are the same type. The API endpoint is not called by the UI (`services/api.ts` has no caller) but is public.

### M-10 · D-17 — Inference used beyond its design
`_compare_groups` is an unpaired Welch test on seeds that are paired by design (same arrivals on both sides; `ResearchHub.tsx` even advertises "paired seeds"). No multiple-comparison correction across the three metrics, verdict logic `every`/`some` treats them as independent although delay, throughput and queue are strongly correlated, defaults n = 3-5, and seeds come from `random.randint` (`validation.py:191`) so a study cannot be repeated (seeds are recorded, not accepted). UI language ("Statistically Significant Divergence Confirmed", "Proofs", "Confirms an inherent … architectural divergence") over-reaches.

### M-11 · D-18 — LOS applied inconsistently
Guided page: roundabout-specific bands (`plainLanguage.ts:213-216`). Volume dashboard: signal bands for both sides (`VolumeAnalysisDashboard.tsx:165-205`), with labels ("Gridlock", "At Capacity") that are not HCM wording. The same roundabout delay can earn a different grade on two screens.

### M-12 · D-19 — "Uncertainty envelopes" are not uncertainty
Toggle "± Range Envelopes" (`VolumeAnalysisDashboard.tsx:1733`) draws per-run min/max or ±σ of individual vehicle delays. They describe spread among drivers in one run, not confidence in the tier's mean.

### L-1 · D-11 — Stale artefacts and non-like-for-like footprint
(a) Two tracked files, `study_report.csv` and `docs/reports/study_report.csv`, contain an all-zero sweep, hourly volume ×4 (1440 for 0.1 veh/s, but the code uses ×3600) and the retired hard-coded recommendation *"Modern roundabouts exhibit significantly superior performance at lower to medium demand"*; a test forbids the code from producing that text, but the files remain. (b) `spaceFootprintConsumed` compares a crossing box to an outer circle (49 m² vs 1,257 m² at 1 lane).

### L-2 · D-20 — Cosmetic/definition drift (see §13)

### L-3 · D-21 — Warm-up banner, history window, whisker naming
`PerformanceCharts.tsx:99` hard-codes "after 30s" although warm-up is configurable; charts drop the first part of runs > ~200 s with no indication; the whisker's "IQR" (`DistributionDiagnosticsVisualizer.tsx:75, 119`, also in `stitch_live_metrics_specification.md`) is median → P95.

### L-4 · D-24 — Silent demand cap of 200 vehicles
`spawner.py:196` stops generation at `totalVehicles` (default 200; `config_models.py:28`); the UI never sets or shows it. The preset "Downtown Peak" (0.7 veh/s × 300 s = 210) already exceeds it (`config.ts:44-45`), so demand is truncated and `totalVehiclesSpawned` is not "offered demand".

### L-5 · D-28 — Inferential values are not exportable
No export contains p-values, Cohen's d or degrees of freedom; the frontend validation CSV omits even the means and CIs.

### Things checked and found sound
* Warm-up handling of averages, stops and throughput; post-warm-up spawned count for CSV (`collector.py:296-300`).
* Jain's index formula and its exclusion of empty approaches (`fairness.py:38-52`).
* PET reported as "not measured" (not zero) for roundabouts everywhere in the catalog and UI (`catalog.ts:499-506`).
* Sweep hourly volume is `rate × 3600` (the earlier ×4 error is fixed) and the CSV labels throughput as a count.
* Welch–Satterthwaite p-value implementation is tested against known critical values (`test_compare_groups.py`).
* The guided page never uses "winner" language and tells users the run is one pattern.

---

## 10. Master table

Level: **1** everyday · **2** detailed comparison · **3** Research Lab (recommended, §11).

| Metric | Plain-English meaning | Unit | Main user question | Main / Advanced | Graph(s) | Research use |
|---|---|---|---|---|---|---|
| `averageDelay` | Extra time per journey vs an empty drive at own speed | s | How long do drivers wait? | Main (1) | G1, L3, L18, V1, V7 | Primary sweep and seed outcome; includes geometric delay |
| `medianDelay` | Middle driver's extra time | s | – | Advanced (2) | L3, L18 | Skew vs mean |
| `p95Delay` | 1-in-20 worst delay | s | Unlucky drivers? | Main today → 2 | G1, L3, L18 | Tail risk (n ≥ 20) |
| `minDelay` / `maxDelay` | Best / worst delay | s | – | Advanced (3) | L18 | Range only |
| `delayStdDev` | Spread of drivers' delays | s | – | Advanced (3) | L19, V1 tooltip | Within-run dispersion |
| `averageWaitTime` | Time nearly stopped | s | How long do drivers stand still? | Advanced (2) | L4 | Complement to delay; feeds composites |
| `averageStopsPerVehicle` | Halts per driver | count | How often do drivers stop? | Main today → 2 | G1, L11 | Smoothness |
| `totalStops` | Halts in total | count | – | Advanced (3) | L11 | Volume-dependent |
| `travelTimeReliability` | Budget time vs typical trip | ratio | Predictable trips? | Advanced (2) | L8 | Reliability (flagged n < 20) |
| `averageTravelSpeed` | Speed right now | m/s | – | Advanced (2) | L7 | Live health |
| `speedVarianceIndex` | Evenness of speeds | ratio | – | Advanced (3) | L19 | Flow smoothness |
| `currentQueueLengths` | Cars queued now per road | veh | Which road is backed up? | Advanced (2) | L9, L21, maps | Snapshot |
| `averageQueueLength` | Typical queue on one road | veh | How long do queues get? | Main (1) | G1, L11, V3 | Sweep and seed outcome |
| `maxQueueLength` | Longest queue ever seen | veh | Worst back-up? | Main today → 2 | G1, V3 | Extreme (noisy) |
| `activeAverageQueueLength` | Queue size when one exists | veh | – | Advanced (3) | L11 | Conditional |
| `queueStdDev`, `queueStabilityIndex` | Bounciness of the queue | veh, ratio | – | Advanced (3) | L11, L19 | Dispersion |
| `congestionRecoveryTime` | Time with > 5 queued | s | How long is it badly backed up? | Main today → 2 | G1, L11 | Duration above threshold |
| `throughput` | Cars that got through | veh | How much traffic gets through? | Main (1) | G1, L5, V2 | Sweep/seed outcome; a count |
| `throughputRate` | Recent exit rate | veh/min | – | Advanced (2) | L6 | Feeds composites; last 60 s |
| `totalVehiclesSpawned` | Cars fed in | veh | (context) | Advanced (3) | L15 | Demand check; capped |
| `activeVehicleCount` | Cars still in the network | veh | Is a backlog building? | Main (1) | G1, L1, L15 | Backlog indicator |
| `criticalSaturationVolume` | Rough served-rate estimate | veh/s | – | Advanced (3) | L17 | Not capacity |
| `intersectionUtilization` | Share of time average speed > 0.5 | % | – | Advanced (3) | L16 | Weak |
| `idleOpportunityLoss` | Green shown to nobody | % (of ticks) | Why did the signal lose time? | Main (conditional) → 2 | G "why", L17 | Signal only |
| `spaceFootprintConsumed` | Geometry area | m² | (context) | Advanced (3) | L17 | Not like-for-like |
| `directionalFairnessIndex` | Even waiting across roads | 0.25-1 | Is every direction treated alike? | Main today → 2 | G2, L10 | Equity (needs n) |
| `collisionCount` | Model overlaps | count | Can I trust the run? | Main (trust flag) | L12 | Integrity, not safety |
| `minTTC`, `ttcEventCount`, `ttcSampleCount` | Close-approach indicators | s, count | – | Advanced (3) | L13, L14 | Exploratory |
| `minPET`, `petEventCount`, `petSampleCount` | Tight sequential crossings (signal) | s, count | – | Advanced (3) | L14 | Exploratory, signal-only |
| `masterEfficiencyScore` | Fixed-weight blend | /100 | – | Advanced (3) | L19 | Not recommended until D-05 addressed |
| Weighted score | Your-weights blend | /100 | – | Advanced (3) | L20 | Preference sensitivity |
| Δ (R − S) | Plain difference | metric unit | By how much do they differ? | Main (table) | G7, V16 | Descriptive |
| Delay Δ %, `winner`, crossover, tier tally | Relative gap and side with lower mean delay by demand | %, label, veh/h | Where does the comparison change? | Advanced (3) | V1-V5, V7 | Single seed per tier |
| mean, SD, CI95 | Average and spread across random patterns | metric unit | – | Advanced (3) | V11 | Uses z (D-03) |
| p-value, `significant` | Could the gap be luck? | prob. | Is the difference real? | Main as words (2) | G5, V10-V11 | Welch, unpaired |
| Cohen's d | Size of the gap vs pattern variation | unitless | – | Main as words (2) | G5, V11 | Effect size |
| Integrity / reproduction result | Model sanity; same seed same answer | pass/fail | Can I trust it? | Advanced (3) | V15, V16 | Determinism |

---

## 11. Recommended three-level presentation

Principle: **do not invent metrics, do not delete metrics, and do not rank the controls.** These recommendations only re-level existing values and are conditional on the defects in §9 being addressed where noted. "Today" describes the current implementation.

### Level 1 — Everyday user (the smallest set that answers the comparison)

| Metric | Today | Why here |
|---|---|---|
| Average delay ("time lost per driver") with an explicit line that it includes slow-down to enter a roundabout | G (card 1) | Answers the primary question; needs the D-06 explanation attached so it is not read as "waiting" |
| Vehicles served + vehicles still in the network | G (card 2) | Output from identical arrivals plus the backlog flag |
| Average queue per approach | G (card 3) | Typical standing queue; the everyday reading of "queues" |
| One trust strip: run length, one traffic pattern, lane caveat, sample-size flag, model overlaps | G (trust list) | Everyday users need a "should I believe this?" line more than extra numbers |

### Level 2 — Detailed comparison ("why do they differ?")

| Metric | Move (from → to) | Reason |
|---|---|---|
| 95th-percentile delay | 1 → 2 | Explains predictability but is unstable below ~20 exits |
| Stops per vehicle | 1 → 2 | A mechanism (stop-and-go), not the outcome |
| Average queued time | new to G (L/T today) → 2 | Resolves the delay-vs-waiting contradiction (D-07) |
| Maximum queue, time congested | 1 → 2 | One-moment extreme and a threshold-based duration are supporting detail |
| Directional fairness (with band words) | 1 → 2 | Meaningful only with enough exits; depends on the random demand split (D-13) |
| Idle green loss (signal-only) | conditional → 2 | Explanatory mechanism, not comparable across geometries |
| Planning time index + sample flag | L/T → 2 | Reliability of journey times for those who ask |
| Throughput rate, current mean speed, per-approach queues, vehicle states | L → 2 | Live-diagnostic |

### Level 3 — Research Lab (full technical and statistical evaluation)

Everything else, unchanged: median/min/max/SD of delay, queue SD/QSI, SVI, utilisation, `criticalSaturationVolume`, footprint, TTC/PET/collision series, both composites, sweep (Δ %, winner, crossover, tier metrics), Monte Carlo statistics, integrity and reproduction, exports.

| Moved to L3 | Reason |
|---|---|
| `intersectionUtilization` | Nearly constant at 100 %; misread as capacity use |
| `criticalSaturationVolume` | Not a capacity estimate (D-10) |
| `spaceFootprintConsumed` | Different definitions per geometry (D-11b); design context only |
| Both composite scores | Depend on fixed caps and structural artefacts (D-05); present as "decision-aid, your priorities" only |
| TTC/PET/collision counts | Exploratory, not comparable across geometries (D-13); keep the existing disclaimer |
| Volume "Insights" tab prose | Not measured (D-01); must not be presented as a result at any level |

**Research Lab must-haves that are missing today:** calibration/lane caveat matching the guided flow (D-09), the direction of Δ, the meaning of the envelope, and inferential values in exports (D-28).

---

## 12. Implemented but unused / API-only

| Item | Where | Status |
|---|---|---|
| `calculate_queue_stability_index` | `derived_metrics.py:14-34` | Dead in production: the collector recomputes QSI inline (`collector.py:333-336`); used only by a test |
| `calculate_average_stops` | `stop_count.py:23-29` | Dead in production |
| `calculate_average_wait_time` | `wait_time.py:6-15` | Reached only as a fallback when there is no delay sample (`collector.py:396`) |
| `calculate_throughput` | `throughput.py:6-8` | Trivial `len()` wrapper |
| 95th-percentile **queue** | contract §2.3 | Not implemented (documented only) |
| `GET /api/v1/study/history/runs/compare` | `main.py:1996-2076` | API-only; the UI builds its own multi-run comparison |
| `GET /api/v1/study/export` (JSON/CSV) | `main.py:2359-2371` | API-only; runs a fresh 16-simulation study; UI CSVs are separate |
| `GET /api/v1/simulations/{id}/report` | `main.py:696-738` | Not called by the UI |
| Sweep `delayMedian`, `delayP95`, `throughputRate` per tier | `volume_sweep.py:316-345` | Stored and shown in tier metrics, not charted |
| `stitch_live_metrics_specification.md` | docs | Design spec; not authoritative |

---

## 13. Documentation vs implementation

| Document / claim | Implementation | Verdict |
|---|---|---|
| `07-metric-contract.md §2.3` lists a 95th-percentile queue | Not emitted | Doc wrong |
| `§2.3` defines `Q_d` by `v.state ∈ {approaching, waiting}` and `v.direction` | Speed < threshold on `*_in_*` lanes by lane-id prefix | Doc imprecise |
| `§4.1` "during all-red phases, if any approach has vehicles, the tick counts as IOL" | `idle_loss.py:35-36` returns False when no approach is green | Doc wrong |
| `§4.2` "Calculated at simulation end" | Computed on every `get_metrics()` | Doc wrong |
| `§4.2` "maximum arrival rate at which queues remain stable; higher is better" | See D-10 | Doc misleading |
| `§6.1` signal footprint `(n_NS·w)(n_EW·w)` (both directions' lanes) | `(2·max(lanes)·w)²` (`derived_metrics.py:99-101`) | Equal only for symmetric lanes |
| `§8` PTI, CSV, footprint "not running" | All are in every snapshot | Doc wrong |
| `§9` example `masterEfficiencyScore: 0.81` | Returns 0-100 (`efficiency.py:49`) | Doc wrong |
| `§2`, `§7` define no delay family, TTC or PET | `averageDelay`, `medianDelay`, `p95Delay`, `minDelay`, `maxDelay`, `delayStdDev`, TTC/PET keys exist (`collector.py:465-526`) | Doc incomplete |
| `§3.1` update frequency "1 Hz" | Every tick (0.1 s default) | Doc wrong |
| `catalog.ts:262, 428` TTC "leader-follower" | Different-lane pairs (`safety_conflicts.py:148-157`) | UI text wrong |
| `TrafficFlowVisualizer.tsx:197-198` "equal delay across approaches" | Wait time (`fairness.py`) | UI text wrong |
| `ResearchHub.tsx` "paired seeds" | Unpaired t-test | Wording misleading |
| `IntegrityCheck.tsx:54-56` "both controls" | Signal engine only | UI text wrong |
| `run_invariant_checks` docstring lists 4 invariants | Three implemented | Docstring wrong |
| `PerformanceCharts.tsx:99` "after 30s" | Warm-up is configurable | UI text wrong |
| `07-metric-contract.md` status "current" | Drift above | Needs update (not done here) |

---

## 14. Defect register

| ID | Sev. | Summary | Evidence |
|---|---|---|---|
| D-01 | H | Volume "Insights" prose states unmeasured/contradicted claims (50 % delay reduction, "mathematically required", emissions, fuel, safety) | `VolumeAnalysisDashboard.tsx:2593-2680`; contradicted by `comparative_report.md §2-3` |
| D-02 | H | Sweep verdict text hard-codes which side wins below/above the crossover; crossover is an upper-bracket, tie-band-blind sign flip | `report_generator.py:55-65`; `volume_sweep.py:203-210, 299-305` |
| D-03 | H | 95 % CI uses z = 1.96 with n = 3-10; p-value uses Student t | `validation.py:18` vs `:153`; `test_compare_groups.py:175-191` |
| D-04 | H | Confidence-level selector changes CI and α in cards but not the header, pills or backend `significant` | `ValidationDashboard.tsx:272-275, 430, 1069, 1084`; `validation.py:154` |
| D-05 | H | Composites: roundabout gets 10 free points, throughput term scores demand, placeholders inflate pre-data scores, two different composites | `efficiency.py:4-49`; `factory.py:39-43`; `idle_loss.py:35`; `scoring.ts:31-68`; `ComparativeDashboard.tsx:542-546` |
| D-06 | M | "Delay" includes geometric slow-down (roundabout entry 5 m/s); LOS bands applied to it; metric contract lacks the definition | `collector.py:350-366`; `dual_orchestrator.py:56-64` |
| D-07 | M | Delay and queued-time/queue metrics point in opposite directions in the same run without explanation | Appendix A |
| D-08 | M | Integrity check overclaims: signal engine only; invariant 3 not implemented | `validation.py:338-395`; `IntegrityCheck.tsx:54-56` |
| D-09 | M | Research Lab and study defaults are 2-lane (uncalibrated for the roundabout), short, single-seed (sweep) | `volume_sweep.py:48-56`; `validation.py:174-180`; UI defaults |
| D-10 | M | `criticalSaturationVolume` cannot exceed offered load; name collides with "Critical Saturation Crossover" | `derived_metrics.py:37-74`; `VolumeAnalysisDashboard.tsx:1455` |
| D-11 | L | (a) stale study_report CSVs with retired recommendation and ×4 volume; (b) footprint definitions differ by geometry | `study_report.csv`, `docs/reports/study_report.csv`; `derived_metrics.py:77-101` |
| D-12 | M | Served ratio mixes post-warm-up exits with all-time spawns; "Exited (Served) whole run" vs "Vehicles served" | `CapacityDemandVisualizer.tsx:36-43`; `VehiclesFlowVisualizer.tsx:65-66` |
| D-13 | M | TTC text wrong; TTC events are pair-ticks; min TTC is a running minimum; PET 5 s non-discriminating; random directional split hidden | `catalog.ts:262, 428`; `collector.py:235-243`; `spawner.py:65-77` |
| D-14 | M | Fairness described as "delay"; uses raw (unclipped) wait; floor 0.25 assumes four approaches | `TrafficFlowVisualizer.tsx:197-198`; `fairness.py:30` |
| D-15 | M | Compare-runs winner uses exact equality and returns geometry string | `main.py:2029-2035` |
| D-16 | M | Three different tie tolerances (0.2 s/2 %, 1 s/5 %, exact) | `volume_sweep.py:300`; `plainLanguage.ts:125`; `main.py:2029` |
| D-17 | M | Unpaired Welch on paired seeds; no multiplicity correction; verdict language overstated; random un-settable seeds | `validation.py:112-161, 191`; `ValidationDashboard.tsx:608, 1066-1069, 1131` |
| D-18 | M | LOS bands differ between guided page and Volume dashboard | `plainLanguage.ts:213-216`; `VolumeAnalysisDashboard.tsx:165-205` |
| D-19 | M | "Uncertainty envelope" is within-run spread | `VolumeAnalysisDashboard.tsx:1733, 216-257` |
| D-20 | L | Contract drift (see §13) | `07-metric-contract.md` |
| D-21 | L | Hard-coded "after 30s"; silent 200-point history truncation; "IQR" mislabel | `PerformanceCharts.tsx:99`; `useLiveComparisonHistory.ts:69`; `DistributionDiagnosticsVisualizer.tsx:75, 119` |
| D-22 | L | Charts plot running aggregates (smoothing) — undocumented on charts | §5.2 |
| D-24 | L | Silent 200-vehicle spawn cap; preset already exceeds it | `spawner.py:196`; `config.ts:44-45` |
| D-28 | L | No export carries p-value, Cohen's d, df | `report_generator.py:181-227`; frontend CSVs |

(D-23, D-25 to D-27 were considered and merged into the entries above.)

---

## 15. Resolution of the defect register (fix pass)

Fix pass 2026-09-25, same branch. Objective: correct calculation → correct statistical interpretation → correct explanation → reproducible documentation, **without changing the simulation**. Verified: the calibrated 1-lane capacity curve (`test_calibrated_capacity_regression`, 18 pinned values) and a 9-point re-run at pristine `HEAD` and at the fixed tree were bit-identical, so no published research number moved (details in `docs/reports/comparative_report.md` revision 2026-09-25).

Priority: **P0** could materially mislead · **P1** statistical/interpretive inconsistency · **P2** presentation/documentation · **P3** cleanup.

| ID | Pri. | Status | What changed | Where |
|---|---|---|---|---|
| D-01 | P0 | **Fixed** | The Volume "Insights" tab was replaced by **"How to read this sweep"**: what was run (tiers, duration, seed, calibration), what this sweep shows (its own tally and change point, computed), and what it cannot show. Removed as unsupported by anything UrbanFlow calculates: "up to 50% reduction in delay", "mathematically required", emissions/fuel/safety-margin claims, and the assumption of which control wins below/above the crossover. | `VolumeAnalysisDashboard.tsx`; test *never presents unmeasured claims* |
| D-02 | P0 | **Fixed** | The verdict is read from the per-tier classification; the direction is taken from the data (signal-first and roundabout-first sweeps are described correctly), ties and *inconclusive* tiers are counted as such, multiple changes are reported as "no single crossover", and every verdict states it is one random pattern per point. The crossover is now the change between two adjacent **decided** tiers (a bracket is reported), so tie-band noise can no longer create one. | `report_generator.py`, `volume_sweep.py::find_delay_crossover`; `test_sweep_verdict_direction.py` |
| D-03 | P1 | **Fixed** | `ci = mean ± t(n−1)·s/√n` (two-sided Student-t), the same distribution as the Welch p-value; t is found by bisection on the p-value routine, matching tables to 4 dp. Output also carries `ciConfidence`, `ciDegreesOfFreedom`, `ciCriticalValue`. | `validation.py::_t_critical/_calculate_stats`; `test_compare_groups.py` |
| D-04 | P1 | **Fixed** | The confidence level (0.90 / 0.95 / 0.99) is sent to the backend, which computes both the interval and `significant` at `alpha = 1 − level`; the UI reads them back (no local z table, no second threshold, no hard-coded "α = 0.05"/"95 %"). | `validation.py`, `main.py`, `ValidationDashboard.tsx` |
| D-05 | P0 | **Fixed (scoped)** | The fixed-weight composite is documented as valid **only within one geometry and scenario**; it is `null` until a vehicle exits after warm-up; it is no longer set side by side across geometries anywhere (comparison tables, comparison/multi-run CSVs, diagnostics card); it is retained for single-run views. The user-weighted score is hidden until warm-up is over and both sides have exits, and its wording states it reflects the chosen weights. Formulas and weights are unchanged (no re-tuning). | `efficiency.py`, `catalog.ts` (`withinGeometryOnly`), `scoring.ts`, `WeightedScoringPanel.tsx` |
| D-06 | P1 | **Fixed (presentation)** | Delay is called "time lost", defined as extra travel time against the driver's own desired speed **including slowing the layout forces**; the definition is stated wherever delay is graded; the LOS wording is "time lost", not "wait". The delay calculation is unchanged. | `catalog.ts`, `plainLanguage.ts`, `ResultsReport.tsx`, `LiveGuide.tsx`, landing copy |
| D-07 | P1 | **Fixed (presentation)** | Queued time appears as its own row next to delay; an always-present explanation "Time lost is not the same as waiting"; a data-driven note when the two point different ways (quoting both values). | `plainLanguage.ts::explanations`, `ResultsReport.tsx` |
| D-08 | P1 | **Fixed** | The integrity check verifies **both** geometries (conservation, non-negative speeds, same-seed reproduction) plus the previously-only-claimed signal green-exclusivity invariant, and reports each geometry separately; a pass on one can no longer read as a pass on both. `massConservationValid` now means only conservation. | `validation.py::run_invariant_checks`, `IntegrityCheck.tsx`; `test_integrity_and_sweep_flags.py`, `IntegrityCheck.test.tsx` |
| D-09 | P1 | **Fixed** | Sweep, validation and CLI defaults are the calibrated 1-lane comparison (the integrity check deliberately keeps its harder 2-lane scenario, since it tests consistency, not results); the dashboards default to 1 lane and label 2 lanes **exploratory**; every study output carries `calibration {calibrated, lanesPerApproach, note}` (an omitted lane count is the engine's 2-lane default and therefore *not* calibrated); the UI shows a banner on exploratory results. | `study/calibration.py`, both dashboards, `ReliabilityCheck.tsx` |
| D-10 | P2 | **Fixed (labels)** | `criticalSaturationVolume` is shown as "Served-rate estimate" and documented as not a capacity; the sweep KPI "Critical Saturation Crossover" became "Where the lower-delay control changes"; `intersectionUtilization` shows as "Time with traffic moving". Backend keys and formulas unchanged. | `catalog.ts`, dashboards, contract §4.2 |
| D-11a | P0 | **Fixed** | Both tracked `study_report.csv` files (root and `docs/reports/`) carried the retired "significantly superior" recommendation and an all-zero sweep; regenerated from the corrected code (see `docs/reports/comparative_report.md` and §16). | `study_report.csv`, `docs/reports/study_report.csv` |
| D-11b | P3 | **Not changed (intentionally)** | Footprint keeps its two geometry-specific definitions (they describe different physical things); it is now described as design context, not a like-for-like comparison. | `catalog.ts`, `CapacityDemandVisualizer.tsx` |
| D-12 | P1 | **Fixed** | "Demand vs. served" uses one window (whole run): exited = generated − in network, so the segments add to 100 %; the stage previously called "Exited (Served)" is "Exited (whole run)" and no longer resembles "Vehicles served" (post-warm-up). | `CapacityDemandVisualizer.tsx`, `VehiclesFlowVisualizer.tsx` |
| D-13 | P2 | **Fixed (text)** | TTC/PET are explained in-app (what is measured, per-tick sampling, running minimum, different-lane pairs only, generous PET threshold, signal-only PET, not a crash probability, not comparable across geometries); catalog text corrected; "Collisions" reworded as model overlaps; trust notes state the road split is set by the traffic pattern. Definitions unchanged. | `catalog.ts`, `SafetyTimelineVisualizer.tsx`, `plainLanguage.ts` |
| D-14 | P1 | **Fixed** | Fairness now subtracts the warm-up baseline exactly as `averageWaitTime` does (same window); UI text says *queued time*, not "delay", and the 1 ÷ n floor. **This changes fairness values** for vehicles active at the warm-up boundary. | `fairness.py`, `collector.py`; `test_composite_and_vehicle_limit.py` |
| D-15 | P1 | **Fixed** | The run-comparison endpoint uses the shared tie rule and says its `winner` is a description of two single runs. | `main.py`, `tolerances.py` |
| D-16 | P1 | **Fixed (unified)** | One "about the same" rule for mean delay everywhere: `≤ 1 s or ≤ 5 % of the larger` (backend `study/tolerances.py`, frontend `SIMILARITY.delay`); sweep tiers, seed tallies, reliability tallies and the run-comparison endpoint all use it. It is a presentation rule, not a test: it never implies significance. *(This replaced the sweep's 0.2 s / 2 % rule and the compare endpoint's exact equality; sweep `winner` labels can differ from before.)* | `tolerances.py`, `plainLanguage.ts`, dashboards |
| D-17 | P1 | **Partly fixed** | Language de-escalated ("statistically supported", never "Confirmed"/"Proofs"; non-significance is never called equality); the method text states unpaired Welch on shared seeds and no multiplicity correction; the study result carries a `method` block. **Not changed:** the test itself (unpaired, uncorrected) and user-unsettable random seeds — changing them alters methodology; recorded under limitations. | `report_generator.py`, `ValidationDashboard.tsx`, `validation.py` |
| D-18 | P1 | **Fixed** | One set of level-of-service bands (`LOS_THRESHOLDS`: signalised for the signal, unsignalised for the roundabout) used by the guided page and the Volume dashboard; HCM-style wording ("Gridlock", "At Capacity") removed. | `plainLanguage.ts`, `VolumeAnalysisDashboard.tsx` |
| D-19 | P2 | **Fixed (labels)** | "± Range Envelopes" → "± Driver spread", explained as within-run spread of individual drivers' delays, not uncertainty about the mean. | `VolumeAnalysisDashboard.tsx` |
| D-20 | P2 | **Fixed** | Contract corrected (§13 list): Q95 removed, all-red rule, CSV/composite semantics, running flags, example score scale, new §7.8–7.10 (delay family, TTC/PET, vehicle limit). | `07-metric-contract.md` |
| D-21 | P2 | **Fixed** | Warm-up banner no longer hard-codes 30 s; charts state they are running values and note when only the last 200 samples are drawn; the delay whisker box is described as median → 95th percentile. | `PerformanceCharts.tsx`, `DistributionDiagnosticsVisualizer.tsx` |
| D-22 | P2 | **Fixed** | Chart note that time series are running aggregates. | `PerformanceCharts.tsx` |
| D-24 | P1 | **Fixed** | Metrics now report `vehicleLimit` / `vehicleLimitReached`; the dashboard compiler and study runners size the limit to the scenario (`demand_vehicle_limit` = expected arrivals × 1.5 + 50, within 200-5000) unless the caller sets one; any run still reaching its limit is flagged (guided caution, sweep banner, tier marked *inconclusive*, seeds listed). Un-truncated runs are bit-identical to before. Measured cost of the larger limit: Appendix B. | `core/limits.py`, `collector.py`, `main.py`, studies |
| D-28 | P3 | **Partly fixed** | The backend study CSV now includes the Welch p-value, Cohen's d, significance and the CI at the run's level. **Not changed:** the frontend sweep/validation CSVs (adding columns would add a feature). | `report_generator.py` |

### 15.1 Definitions and presentation, at a glance

**Definitions changed (values can differ from before):**

| Metric / value | Change |
|---|---|
| `ci95` and the new `ci` (Monte Carlo studies) | Student-t instead of z = 1.96 (about 1.42× wider at n = 5; 1.15× at n = 10) |
| `significant` (Monte Carlo) | Computed at `alpha = 1 − confidenceLevel` (was fixed 0.05); identical at the default 95 % |
| `directionalFairnessIndex` | Warm-up baseline subtracted (same window as `averageWaitTime`) |
| `masterEfficiencyScore` | `null` until a vehicle has exited after warm-up (was a placeholder score); formula unchanged |
| Sweep `winner` | Shared tie rule (1 s / 5 %); new value `inconclusive`; crossover from decided tiers only, with a bracket |
| Sweep / validation / CLI defaults | 1 lane per approach (calibrated) instead of 2 |
| Study `totalVehicles` | Sized to the scenario (was the silent 200) |
| Run-comparison `winner` | Shared tie rule (was exact equality) |

**New output fields** (additive): `vehicleLimit`, `vehicleLimitReached` (metrics); `calibration`, `method`, `confidenceLevel`, `alpha`, `vehicleLimitReachedSeeds` (validation); `calibration`, `tieTolerance`, `seedsPerTier`, `curves.crossoverBracketArrivalRates`, per-run `inconclusiveReason`/`vehicleLimitReached` (sweep); `geometries`, `checked`, `signalGreenExclusivityValid`, `nonNegativeSpeedsValid` (integrity); `evidenceSummary`, `inconclusiveCount`, `directional` (report).

**Presentation-only changes:** delay/queued-time wording and LOS words; catalog descriptions (TTC, PET, footprint, utilisation, saturation, QSI, fairness); composite placement; Volume tab content and KPI names; validation verdict/method wording; chart notes and labels; served-ratio windows.

### 15.2 Silent 200-vehicle cap: investigation

* **What it is.** `traffic.totalVehicles` defaults to 200 (`core/config_models.py`, `vehicles/spawner.py`). After it is reached, no vehicle is generated for the rest of the run.
* **Does it matter?** Yes, for some scenarios. The *published calibrated baseline is not affected*: its regression harness sets `totalVehicles = 5000`. But the dashboards, sweeps and reliability checks ran with the default. Measured (seed 1, 300 s, 30 s warm-up, both geometries): 1 lane at 2,880 veh/h offered generated 187 / 173 vehicles (cap not reached, because entry blocking throttles generation); **2 lanes at 2,880 veh/h reached the cap of 200 on both geometries** with ≈ 240 expected. The preset "Downtown Peak" (0.7 veh/s × 300 s ≈ 210) sits at the edge. Truncation is also not guaranteed to hit both geometries at the same moment, so it can bias exactly the comparison the tool exists to make.
* **Fix.** Flag it (metrics), size it (scenario builders), and mark affected sweep tiers *inconclusive*. The default for raw API callers is unchanged (200).
* **Cost of a larger limit.** Vehicle count is the driver of both CPU and memory (exited vehicles stay in the pool). Measured: Appendix B.

## 16. Evidence classes: what UrbanFlow claims and how

Every user-facing statement now belongs to exactly one class. Anything that does not fit a class was removed.

| Class | Meaning | Where it appears | Wording rule |
|---|---|---|---|
| **1. Calibrated findings** | Produced under the calibrated configuration (1 lane per approach, both geometries collision-free) and pinned by `test_calibrated_capacity_regression` | `docs/reports/comparative_report.md` §2; guided results at 1 lane | May be stated as findings, with their scope |
| **2. Exploratory findings** | Any run outside that configuration (more than one lane: every lane is modelled, but multi-lane roundabout runs are not collision-free, §17) | Research Lab and guided results when lanes > 1 | Always labelled *Exploratory, not calibrated*; never presented as the baseline |
| **3. Descriptive observations** | What one run measured (means, queues, tiers, tallies) | Guided results, live panel, sweep tables/charts, "How to read this sweep" | "Lower mean delay at N of M points (one random pattern each)"; no "wins", no causal claims beyond a quoted measurement |
| **4. Statistically supported findings** | A Welch test at the study's α across ≥ 2 random traffic patterns, reported with p, Cohen's d and Student-t intervals | Reliability check, Statistical validation, report `validationEvidence` | "Statistically supported at α = …" or "not supported: this study cannot distinguish the controls"; never "no difference"/"equal"/"confirmed" |
| **5. Unsupported claims (removed)** | Statements UrbanFlow does not compute or that its own results contradict | — | Removed: 50 % delay reduction; "mathematically required" signal/turbo-roundabout thresholds; emission, fuel and safety-margin claims; roundabout-better-below / signal-better-above as an assumption; "Modern roundabouts exhibit significantly superior performance…" (regenerated reports, CLI text, landing page "takes the lead"/fuel −14.2 %); "Statistically significant divergence confirmed"/"Proofs"; "Equivalence / Parity" for non-significant results; the fixed composite as a "winner" score |

### Verdict-language audit (Phase 3)

Every statement of the form *X is better / wins / reduces Y / is safer / is more efficient / is significantly better* was traced to a metric. Result: none remain that lack support. What remains, and its basis:

| Statement family | Basis (must be a computed value) |
|---|---|
| "Drivers lost less time at the X: N s less per driver" | `averageDelay` difference beyond the shared tie rule; values quoted alongside |
| "The X got N more vehicles through from the same arrivals" | `throughput` difference beyond the tolerance |
| "Lower mean delay: X before, Y after, the change lying between A and B veh/h" | Adjacent decided sweep tiers, with the one-random-pattern caveat |
| "Statistically supported at α = …, the lower mean at the X" | Welch p < α and the two means |
| "Under these weights the X scores N points higher" | User-set weights; followed by "reflects the weights you chose, not a finding" |
| Level-of-service words | HCM delay bands applied to simulated delay, stated as indicative |
| "Both controls got the same vehicles" | Same seed, same spawner sequence (lockstep orchestrator) |

## 17. Calibration pass (2026-09-25b): equal inputs, calibrated demand

This pass **changed the simulation** (unlike §15, which only changed calculations and wording). Every number measured before it is superseded. The bugs are recorded as BUG-21 to BUG-25 in `docs/bug-fix-report.md`, and the re-measured results in `docs/reports/comparative_report.md` (revision 2026-09-25b).

| Issue | Status | What changed |
|---|---|---|
| Unequal speed assumptions (signal traffic visibly faster) | **Fixed** | Desired speed comes from `roads.speedLimit`, 85–105% of 50 km/h, for both geometries (it was 18–25 m/s and the limit was ignored). One lateral-acceleration limit (3 m/s²) applies to every curved path, including signal turns, which had no curve limit before. |
| Roundabout "queues" at light demand | **Fixed (root cause)** | Entering drivers no longer give way to circulating vehicles that leave at an earlier exit. The 60 m approach crawl at `entrySpeed` is now 10 m. Free-flow roundabout delay is 7.7 s at 180 veh/h, down from 13.4 s. |
| Guided and study scenarios were not the calibrated configuration | **Fixed** | One parameter set (IDM a = 2.0, b = 3.0 m/s²; signal 30/4/2 s paired NS/EW; gap 4.0/2.5 s) is used by the calibrated study, the live comparison, the sweep and the validation study. |
| Warm-up contamination in studies | **Fixed** | The sweep (15 s) and validation (5 s) warm-ups are now 30 s, like the calibrated study and the live comparison (a quarter of the run for runs under 120 s). Research Lab defaults are 240 s runs. |
| Demand range too mild; levels unrelated to capacity | **Fixed** | Levels are shares of a measured reference capacity per lane count (the mean of both controls' maximum served flow: 1,250 / 2,180 / 2,620 veh/h for 1 / 2 / 3 lanes). They are Light 25%, Moderate 50%, Busy 75%, Near capacity 90%, At capacity 100% and Over capacity 130%, in `study/calibration.py` and `frontend/src/types/demand.ts`, and a test keeps the two equal. The reference is the same for both controls, so a level favours neither. |
| "The roundabout has a single circulating lane" (UI and docs) | **Corrected** | It was wrong: the network builds one ring per entry lane, and capacity rose with lanes before this pass too. Multi-lane runs stay *exploratory* because the inner-ring-exit weave produces occasional contacts (5 in 54 multi-lane roundabout runs). |

**Definitions unchanged.** Every metric formula, tie rule, LOS band and statistical method is as in §15. Delay is still measured against each driver's own desired speed, so it still includes geometric slowing. Now that both geometries slow for curves under the same rule, that slowing is comparable between them.

**Evidence classes (§16) after this pass.** Class 1 (calibrated findings) is the 1-lane curve pinned by `test_calibrated_capacity_regression` at its 2026-09-25b values. Multi-lane results are Class 2 (exploratory). The guided comparison's default scenario ("Busy", 1 lane) is now the calibrated configuration.

## Appendix A — verification runs

Method: `DualSimulationOrchestrator`, seed 1, `timeStep 0.1`, duration 120 s, warm-up 30 s, default speeds/thresholds, `directionalSplit` unset. Scratch script not committed. Single seed, single duration: the numbers verify **behaviour** (which value is structurally 0, which is pegged), not performance.

| | 0.15 veh/s · 1 lane | | 0.3 veh/s · 1 lane | | 0.6 veh/s · 1 lane | |
|---|---:|---:|---:|---:|---:|---:|
| | Signal | Roundabout | Signal | Roundabout | Signal | Roundabout |
| `averageDelay` (s) | 0.15 | 12.88 | 7.67 | 20.56 | 15.94 | 29.05 |
| `averageWaitTime` (s) | 0.0 | 0.0 | 3.77 | 1.27 | 7.47 | 4.47 |
| `averageQueueLength` | 0.11 | 0.00 | 0.76 | 0.17 | 2.45 | 0.88 |
| `maxQueueLength` | 3 | 1 | 5 | 3 | 12 | 8 |
| `throughput` | 5 | 5 | 16 | 18 | 30 | 29 |
| `directionalFairnessIndex` | 1.00 | 1.00 | 0.42 | 0.65 | 0.56 | 0.45 |
| `idleOpportunityLoss` | 0.279 | **0.000** | 0.214 | **0.000** | 0.000 | **0.000** |
| `masterEfficiencyScore` | 68.0 | 70.5 | 57.0 | 64.4 | 62.8 | 60.9 |
| `intersectionUtilization` (%) | 89.7 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| `spaceFootprintConsumed` (m²) | 49.0 | 1,256.6 | 49.0 | 1,256.6 | 49.0 | 1,256.6 |
| `ttcSampleCount` / `ttcEventCount` | 0 / 0 | 41 / 0 | 152 / 16 | 546 / 30 | 412 / 100 | 1,141 / 25 |
| `petEventCount` / `petSampleCount` / `minPET` | 17 / 31 / 1.30 | – | 67 / – / 0.70 | – | 134 / 222 / 0.70 | – |
| `travelTimeReliabilityLowSampleSize` | true | true | true | true | false | false |
| Directional split (N/S/E/W) | 0.14 / 0.35 / 0.33 / 0.18 (all runs) | | | | | |

2 lanes at 0.3 veh/s: footprint 196 m² vs 1,256.6 m²; `masterEfficiencyScore` 57.6 vs 60.2; roundabout idle loss 0.

What each observation establishes: the roundabout idle-loss is structurally 0 (D-05); delay and queued time/queue disagree in direction at 0.3 veh/s (D-06, D-07); roundabout delay with zero queued time at 0.15 veh/s (D-06); utilisation saturates (D-11/§2D); TTC sample counts differ by geometry and PET events are 55-60 % of all observations (D-13); directional split is unequal by default (D-13); footprints are 49 vs 1,257 m² (D-11b).

---

## Appendix B — cost of a larger vehicle limit (measured)

Dual signal + roundabout run, 2 lanes per approach, 0.8 veh/s, seed 1, headless, one machine (Windows, CPython), sequential runs. "Snapshot build" is the mean cost of one `get_dual_snapshot()` at the end of the run (what live streaming pays every tick, with a 100 ms budget).

| Run | Limit | Vehicles generated (signal / roundabout) | Wall time | Peak process memory | Snapshot build |
|---|---:|---:|---:|---:|---:|
| 300 s | 200 (old default) | 200 / 200 — **truncated** | 36 s | 39.0 MB | 1.5 ms |
| 300 s | 410 (sized to the scenario) | 237 / 237 | 41 s | not read separately (same vehicles as the row below) | 1.9 ms |
| 300 s | 5000 (maximum) | 237 / 237 | 45 s | 39.1 MB | 1.9 ms |
| 1200 s | 5000 | 958 / 768 | 424 s | 44.3 MB (start 36.6) | 5.5 ms |

Reading: memory is driven by vehicles actually generated, not by the limit's value (the 410 and 5000 rows are identical); about 5 KB per vehicle, so the 5000 maximum is about +25 MB. Wall time and snapshot cost grow with the number of vehicles because exited vehicles stay in the pool and the collector re-reads them on each metrics call; that growth exists whether or not a limit is raised. At the realistic scenario sizes (a few hundred vehicles) a live tick costs about 2 ms per snapshot, comfortably inside the 100 ms budget. This is why the limit is sized to the scenario rather than raised globally: raw API callers keep the 200 default, and a run that still reaches its limit is flagged.

Reproduction of the published multi-seed study (seeds 1–5, calibrated harness): every mean, p-value and Cohen's d in `comparative_report.md` §2–§3 was reproduced exactly; the only difference is the interval half-width (Student-t 2.776 instead of 1.96 at n = 5).

