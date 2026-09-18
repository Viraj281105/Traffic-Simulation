# Traffic-Simulation Product & Engineering Roadmap

> **Document Type:** Canonical Living Planning & Architecture Document  
> **Target System:** Traffic-Simulation (Intersection Control Comparison Platform)  
> **Current Version:** V1.0.0 (Stable Baseline)  
> **Next Version:** V1.1.0 (Reproducible Traffic-Analysis & Experimentation Platform)  
> **Last Updated:** 2026-09-15  
> **Status:** Active & Authoritative

---

## Table of Contents

1. [Roadmap Purpose](#1-roadmap-purpose)
2. [Product Vision](#2-product-vision)
3. [Current Version — V1.0 Baseline](#3-current-version--v10-baseline)
4. [Next Release — V1.1 Product Direction](#4-next-release--v11-product-direction)
   - [4.1 Experiment Reproducibility](#41-experiment-reproducibility)
   - [4.2 Better Experiment History & Management](#42-better-experiment-history--management)
   - [4.3 Metric Reliability & Scientific Quality](#43-metric-reliability--scientific-quality)
   - [4.4 More Powerful Traffic Experiments (Volume Sweeps)](#44-more-powerful-traffic-experiments-volume-sweeps)
   - [4.5 Better Configuration System & Presets](#45-better-configuration-system--presets)
   - [4.6 More Realistic Fixed-Time Signal Control](#46-more-realistic-fixed-time-signal-control)
   - [4.7 Powerful Comparison & Trade-Off Analytics](#47-powerful-comparison--trade-off-analytics)
   - [4.8 Production-Grade Backend & Platform Hardening](#48-production-grade-backend--platform-hardening)
   - [4.9 Frontend Architecture & UX Quality](#49-frontend-architecture--ux-quality)
   - [4.10 Standardized Reporting & Results Presentation](#410-standardized-reporting--results-presentation)
   - [4.11 Additional Evaluated V1.1 Features](#411-additional-evaluated-v11-features)
5. [V1.1 Implementation Priority Order](#5-v11-implementation-priority-order)
6. [V1.1 Release Definition of Done](#6-v11-release-definition-of-done)
7. [V1.2 / Near-Future Incremental Ideas](#7-v12--near-future-incremental-ideas)
8. [V2 — Advanced Simulation Engine & Geometry](#8-v2--advanced-simulation-engine--geometry)
9. [Long-Term Vision (V3+)](#9-long-term-vision-v3)
10. [Deferred / Explicitly Not Now Log](#10-deferred--explicitly-not-now-log)
11. [Completed Work & Release History](#11-completed-work--release-history)
12. [Architectural Decision Log](#12-architectural-decision-log)
13. [How to Maintain This Roadmap](#13-how-to-maintain-this-roadmap)

---

## 1. Roadmap Purpose

This document is the single, persistent, authoritative product and engineering roadmap for the **Traffic-Simulation** project.

It bridges product strategy, engineering architecture, and scientific rigor. Its goal is to prevent fragmented planning, avoid rework, and ensure that every contributor—human engineer or autonomous AI agent—understands:
- What the system already does today.
- What is being built next and why.
- What is intentionally deferred to future versions.
- The architectural decisions that must not be accidentally undone.

This document is designed to be **updated in place** as releases ship. Rather than creating new, disconnected planning files for V1.1, V1.2, and V2, teams will update this document, preserving the historical continuity and decision log across the lifetime of the project.

---

## 2. Product Vision

### Where We Are Coming From
In its initial stage, Traffic-Simulation was developed as an impressive, high-fidelity interactive simulation demo comparing a 4-leg Fixed-Time Signalized Intersection against a Modern Single-Lane Roundabout.

### Where We Are Going
Traffic-Simulation is evolving into a **reproducible, scientifically defensible traffic-analysis and experimentation platform**.

The platform enables traffic engineers, urban planners, civil engineering researchers, and software engineers to:
1. **Model & Compare:** Benchmark intersection control strategies side-by-side under identical microscopic vehicle dynamics and arrival distributions.
2. **Experiment at Scale:** Run systematic volume sweeps, Monte Carlo seed matrices, and capacity stress tests without manual overhead.
3. **Defend the Numbers:** Rely on metrics that adhere to transparent mathematical standards, physical conservation laws, and statistical confidence intervals.
4. **Reproduce Exactly:** Share and replay any historical experiment run with bitwise deterministic verification.
5. **Communicate Findings:** Generate presentation-ready comparative reports, trade-off summaries, and data exports suitable for executive briefings and academic review.

---

## 3. Current Version — V1.0 Baseline

The V1.0 release establishes the verified, stable baseline of the platform. All V1.1 work builds directly on top of this foundation.

### 3.1 Current System Capabilities

```
┌────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                  │
│   Vite + React 18 + TypeScript + HTML5 Canvas Viewports + Recharts     │
│  - Configuration Sidebar (Compact scenario inputs & preset parameters) │
│  - Dual Canvas Visualizer (Side-by-side animated vehicle graphics)     │
│  - Metrics Sidebar & Comparative Dashboard (Live 10-metric counters)   │
│  - Volume Analysis Dashboard (Volume sweep curves & crossover points)  │
│  - Validation Dashboard (Physical invariants & Monte Carlo checks)     │
│  - History Dashboard (SQLite-backed runs, replays & comparisons)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP REST + WebSockets (10 Hz)
┌───────────────────────────────────▼────────────────────────────────────┐
│                              BACKEND                                   │
│            FastAPI + Python 3.11 + SQLite (WAL Mode)                   │
│  - Simulation Engine (Discrete-time loop, dt = 0.1s)                   │
│  - Intelligent Driver Model (IDM car-following acceleration)           │
│  - Vehicle Spawner (Poisson arrival process & uniform distributions)   │
│  - Intersection Controllers (Polymorphic BaseController registry):     │
│      * FixedTimeSignalController (N/S & E/W green/yellow/red phases)   │
│      * RoundaboutController (Yield-line time-gap acceptance logic)     │
│  - MetricCollector (10 standardized metrics with warmup filter)        │
│  - Safety Net: Separating Axis Theorem (SAT) debounced collision audit │
│  - Study Engine (Volume sweeps, Monte Carlo statistical validator)     │
│  - Persistence DAOs (Runs, Tick Metrics, Sweeps, Configs, Replays)     │
└────────────────────────────────────────────────────────────────────────┘
```

#### Core Simulation & Physics
- **Engine Loop:** Discrete-time simulation clock (`backend/src/core/clock.py`, `backend/src/core/engine.py`) executing fixed time steps ($\Delta t = 0.1\,\text{s}$).
- **Microscopic Physics:** Intelligent Driver Model (`backend/src/vehicles/idm.py`) governing longitudinal vehicle acceleration, free-flow acceleration, comfortable deceleration, and gap maintenance.
- **Vehicle Spawner:** Poisson process spawner (`backend/src/vehicles/spawner.py`) utilizing independent pseudo-random seeds per approach.
- **Intersection Geometries:** Standard 4-leg intersection with configurable approach length ($200\,\text{m}$ default) and lane width ($3.5\,\text{m}$ default).
- **Controllers (`backend/src/controllers/`):**
  - `FixedTimeSignalController`: Rigid phase cycling (North/South Green $\rightarrow$ Yellow $\rightarrow$ East/West Green $\rightarrow$ Yellow $\rightarrow$ All Red).
  - `RoundaboutController`: Priority-to-circulating yield rules with critical time-gap evaluation ($3.0\,\text{s}$ critical headway, $2.0\,\text{s}$ follow-up headway).

#### Metrics Collection & Scientific Invariants
- **Real-Time Aggregator:** `MetricCollector` (`backend/src/metrics/collector.py`) computing running values every tick.
- **Ten Core Metrics:** Average Delay / Wait Time, Total Throughput, Rolling Throughput Rate, Queue Length Statistics (mean, max, standard deviation), Stop Count (with hysteresis speed threshold $0.5\,\text{m/s}$), Speed Variance Index, Travel Time Reliability (Buffer Index & Planning Time Index), Directional Fairness (Jain's Fairness Index across approaches), Space Footprint Consumption, and Debounced Collision Event Count.
- **Warmup Filtering:** Excludes initial startup cycle (`warmupTime` seconds) from final statistics to eliminate empty-grid bias.
- **Validation Engine (`backend/src/study/validation.py`):**
  - *Invariant Checks:* Mass conservation test ($\text{spawned} = \text{active} + \text{exited}$), non-negative velocities, queue boundary constraints.
  - *Statistical Engine:* Multi-seed Monte Carlo engine with Student's $t$-distribution $95\%$ confidence intervals and Cohen's $d$ effect size calculations.

#### Networking, API & Persistence
- **Dual Communication Strategy:**
  - *WebSockets:* 10 Hz snapshot streaming via `/ws/v1/stream?simulationId=...` (programmatic), `/ws/simulation/live` (interactive single view), and `/ws/simulation/dual` (interactive side-by-side comparison).
  - *REST API:* FastAPI router with configuration validation, playback lifecycle control, historical run retrieval, volume sweep execution, and export routes.
- **Persistence (`backend/src/database/`):** SQLite database in WAL mode with 5-second busy timeout. Stores `configurations`, `simulation_runs`, `run_metrics`, `sweep_sessions`, and `saved_replays`.
- **Hardening & Security:** CORS environment allowlist, optional bearer API key authentication (`require_api_key`), structured `HTTPException` error envelopes, and container health checks.

### 3.2 V1.0 Status & Frozen Baseline
V1.0 represents a **frozen functional baseline**. The underlying IDM acceleration equations, single-integer `lanesPerApproach` configuration contract, and core controller registry contracts are locked. V1.1 will extend, wrap, and enrich these capabilities without breaking existing regression test suites.

---

## 4. Next Release — V1.1 Product Direction

### Release Vision
Transform Traffic-Simulation into a **reproducible traffic-analysis and experimentation platform**. 

Where V1.0 allowed users to watch an animated comparison, V1.1 empowers users to **run rigorous comparative studies, explain why one strategy outperforms another across different traffic volumes, and reproduce every finding deterministically**.

---

### 4.1 Experiment Reproducibility

> **Plain-Language Meaning:** If you run an experiment today, save it, and re-run it tomorrow with the same settings and seed, you must get the exact same numbers.

- **Status:** Partially Complete (Backend headless runner exists; requires UI integration & deep verification)
- **Priority:** P0 (Highest)
- **Why:** Without provable reproducibility, traffic simulation results cannot be trusted for engineering or scientific decisions.
- **Current V1 Capability:**
  - `SimulationEngine` accepts a deterministic integer `randomSeed`.
  - Database table `simulation_runs` records `random_seed`, complete `config` JSON, `duration`, and `summary_metrics`.
  - Endpoint `POST /api/v1/study/history/runs/{run_id}/reproduce` executes a headless re-run and verifies if `averageDelay` and `throughput` match within loose thresholds ($0.05\,\text{s}$ and $0.1\,\text{veh/hr}$).
- **V1.1 Addition:**
  - **Bitwise State Checksums:** Compute a rolling MD5/SHA256 checksum of vehicle positions and metric vectors across the simulation run to guarantee identical execution.
  - **Strict Determinism Flag:** Expose explicit `isDeterministic: boolean` and detailed delta breakdowns on all reproduced runs.
  - **Frontend Verification Badge:** Add a one-click "Reproduce & Verify" action in `HistoryDashboard.tsx` displaying a clear visual badge: `Verified Deterministic ✅` or `Discrepancy Detected ⚠️`.
  - **Reproducibility Manifest:** Package random seed, Python runtime version, git commit hash, and scenario configuration into every saved run.
- **User Benefit:** Users can cite simulation results with total confidence that any colleague can re-run the scenario and achieve the identical result.
- **Technical Areas:** Backend (`src/main.py`, `src/study/validation.py`), Database (`simulation_runs`), Frontend (`HistoryDashboard.tsx`).
- **Dependencies:** None (builds directly on existing DAO and reproduction endpoint).
- **Definition of Done:**
  - Re-running any stored historical run via the API returns $100\%$ matching vehicle exit counts, exact throughput, and delay matching to $4$ decimal places.
  - UI displays reproduction status with discrepancy reports if tolerances fail.
  - Integration tests pass verifying that independent seeds diverge while identical seeds reproduce identically.
- **Future Extension (V1.2+):** Visual side-by-side "Ghost Vehicle" overlay comparing original and reproduced trajectories simultaneously on canvas.

---

### 4.2 Better Experiment History & Management

> **Plain-Language Meaning:** Users should be able to browse past simulation runs, filter them, search for specific scenarios, and inspect their full configurations without opening raw database files.

- **Status:** Planned (Basic table exists; lacks filtering, search, and configuration inspection)
- **Priority:** P0
- **Why:** Users currently accumulate simulation runs in SQLite but have limited tools to search, organize, or understand past results.
- **Current V1 Capability:**
  - `simulation_runs` SQLite table stores historical runs.
  - `GET /api/v1/study/history/runs` supports basic pagination (`limit`, `offset`) and simple filters (`intersection_type`, `seed`, `batch_id`).
  - Frontend `HistoryDashboard.tsx` renders a basic tabular list of past runs.
- **V1.1 Addition:**
  - **Multi-Dimensional Search & Filtering:** Filter runs by date range, arrival rate bracket, intersection type, duration, tags, and execution status.
  - **Configuration Inspector Modal:** Open any historical run to inspect its complete parameters (geometry, IDM physics, signal timings) with formatted JSON and a visual summary card.
  - **Run Tagging & Metadata:** Allow users to name runs (e.g., "Peak Hour Base Case") and assign descriptive tags (e.g., `baseline`, `heavy-traffic`, `signal-tuning`).
  - **Multi-Run Comparison Selector:** Checkbox selection of any two runs from history to trigger an instant comparative delta view.
- **User Benefit:** Transforms a raw database dump into a well-organized personal laboratory notebook of traffic experiments.
- **Technical Areas:** Backend (`src/main.py`, `src/database/dao.py`), Frontend (`HistoryDashboard.tsx`, `HistoryDashboard.css`).
- **Dependencies:** Database schema update adding `name` and `tags` columns to `simulation_runs`.
- **Definition of Done:**
  - Users can search runs by keyword, filter by intersection type and arrival rate, and sort by date or throughput.
  - Clicking any run opens an Inspector displaying complete configuration, summary metrics, and validation flags.
  - Selecting two runs renders a side-by-side metric comparison table.
- **Future Extension (V1.2+):** Bulk archive, tag management, and SQLite database backup/restore directly from the web interface.

---

### 4.3 Metric Reliability & Scientific Quality

> **Plain-Language Meaning:** Every number shown by the simulator must have a clear definition, transparent formula, explicit physical units, and warnings when statistical sample sizes are too low.

- **Status:** Planned / In Progress (Audit completed; requires contract documentation sync and low-sample alerts)
- **Priority:** P0
- **Why:** In traffic engineering, showing an average wait time of $12.4\,\text{s}$ based on only $3$ vehicles is misleading. Metrics must be defensible.
- **Current V1 Capability:**
  - Comprehensive metric engine in `backend/src/metrics/collector.py`.
  - Formal documentation in `docs/architecture/07-metric-contract.md` detailing formulas for wait time, throughput, queue length, stop count, speed variance, reliability, and fairness.
  - `warmupTime` filter eliminating initial grid startup bias.
  - Statistical Monte Carlo validation with Student's $t$-test confidence intervals (`backend/src/study/validation.py`).
- **V1.1 Addition:**
  - **Low-Sample Warning Badges:** When completed vehicle count $N < 15$ in a run or approach, flag metrics in the UI with a `Low Sample Size` alert indicator explaining that statistical variance is high.
  - **Metric Provenance Tagging:** Categorize each displayed metric explicitly:
    - *Directly Measured:* Elapsed time ($s$), vehicle exit count ($veh$), physical queue length ($m$).
    - *Derived / Modeled:* Jain's Fairness Index ($0.0 - 1.0$), Speed Variance Index, Planning Time Index (95th percentile travel time / free-flow time).
  - **Explicit Units Across Entire Surface:** Standardize all labels and payloads with formal units: seconds ($s$), vehicles per hour ($veh/h$), meters per second squared ($m/s^2$), and meters ($m$).
  - **In-App Formula Tooltips:** Interactive info icons beside every metric in the dashboard linking to its mathematical definition and calculation methodology.
- **User Benefit:** Elevates the tool from an approximate visualizer to an academically credible platform capable of supporting engineering reports.
- **Technical Areas:** Backend (`src/metrics/collector.py`), Shared Contracts (`shared/schemas/metrics.schema.json`), Frontend (`MetricsSidebar.tsx`, `ComparativeDashboard.tsx`).
- **Dependencies:** None.
- **Definition of Done:**
  - All metrics displayed in the frontend display explicit physical units.
  - Runs with $N < 15$ vehicles show amber low-sample warnings.
  - Hovering over any metric displays a formula explanation and provenance tag.
  - Automated tests verify that low-sample thresholds trigger properly under sparse arrival rates.
- **Future Extension (V1.2+):** Dynamic 95% confidence interval bands displayed directly alongside live running metric charts.

---

### 4.4 More Powerful Traffic Experiments (Volume Sweeps)

> **Plain-Language Meaning:** Automatically run simulations across a ladder of traffic volumes (e.g., 400 to 2000 vehicles/hour) to find the exact point where a roundabout becomes worse than a traffic signal.

- **Status:** Partially Complete (Backend volume sweep script & dashboard exist; needs multi-seed confidence bands & custom volume ladders)
- **Priority:** P0
- **Why:** Single-volume comparisons only show a snapshot. Real transportation decisions depend on how an intersection performs across varying demand levels from quiet midday to peak rush hour.
- **Current V1 Capability:**
  - `backend/src/study/volume_sweep.py` runs paired simulations for signal and roundabout across default arrival rates ($0.1$ to $0.8\,\text{veh/s}$).
  - SQLite table `sweep_sessions` stores sweep inputs, paired run IDs, and summary records.
  - Frontend `VolumeAnalysisDashboard.tsx` renders delay vs. volume curves and identifies empirical crossover points.
- **V1.1 Addition:**
  - **Customizable Volume Ladders:** Allow users to define start volume, end volume, and step size (e.g., $400 \rightarrow 800 \rightarrow 1200 \rightarrow 1600 \rightarrow 2000\,\text{veh/h}$) from the UI.
  - **Multi-Seed Volume Sweeps:** Run $K$ random seeds (e.g., $K = 5$) for each volume step to generate standard error bars and confidence ribbons on the comparison curves.
  - **Automated Crossover Intelligence:** Compute and display an executive verdict:
    > *"Modern Roundabout delivers up to 34% lower delay below 1,350 veh/h. Above 1,550 veh/h, Fixed-Time Signal sustains 18% higher throughput due to circulation gridlock in single-lane roundabout geometry."*
  - **Asymmetric Demand Sweeps:** Allow holding major-street volume constant while stepping minor-street volume to model arterial cross-streets.
- **User Benefit:** Delivers the primary analytical graph requested by traffic engineers when deciding between a roundabout and a signalized junction.
- **Technical Areas:** Backend (`src/study/volume_sweep.py`, `src/main.py`), Frontend (`VolumeAnalysisDashboard.tsx`, `VolumeAnalysisDashboard.css`).
- **Dependencies:** Multi-seed execution engine (`src/study/validation.py`).
- **Definition of Done:**
  - Users can configure custom volume ranges and step sizes from the frontend.
  - Volume curves render with statistical confidence intervals when multi-seed sweeps are executed.
  - The system automatically highlights the crossover point and outputs a textual summary of capacity thresholds.
- **Future Extension (V1.2+):** Parallelized headless execution of volume steps utilizing multi-core CPU workers.

---

### 4.5 Better Configuration System & Presets

> **Plain-Language Meaning:** Provide pre-packaged realistic intersection setups (like "Quiet Suburban" or "Heavy Urban Peak") and give helpful error messages if a user enters an impossible number.

- **Status:** Planned
- **Priority:** P1
- **Why:** Manually tuning arrival rates, phase times, and approach dimensions from scratch is tedious and error-prone for non-expert users.
- **Current V1 Capability:**
  - JSON schema in `shared/schemas/config.schema.json` and Pydantic models in `backend/src/core/config_models.py`.
  - Endpoint `POST /api/v1/configs/validate` validates payloads against the schema.
  - Sidebar inputs in `ConfigurationSidebar.tsx` allow raw adjustments.
- **V1.1 Addition:**
  - **Standardized Scenario Presets:** Ship built-in, professionally calibrated presets:
    1. *Low-Demand Suburban:* $400\,\text{veh/h}$, balanced $50/50$ directional split, $1$ lane, low turning fractions.
    2. *Medium Urban Collector:* $1,000\,\text{veh/h}$, balanced flow, moderate left turns, $2$ lanes.
    3. *Heavy Commuter Peak:* $1,800\,\text{veh/h}$, heavy major arterial ($70/30$ split), high congestion risk.
    4. *High Left-Turn Conflict:* $1,200\,\text{veh/h}$, high left-turn ratios testing signal phase efficiency vs. roundabout circulating yield delay.
  - **Saved User Configurations:** Allow users to save their own custom configurations to SQLite and reload them with one click.
  - **Field-Level Validation Highlights:** Translate backend schema errors into specific highlighted input fields in `ConfigurationSidebar.tsx` with friendly explanations (e.g., *"Yellow time must be at least 3.0 seconds for physical stopping safety"*).
- **User Benefit:** Eliminates setup friction, enabling instant demonstrations and reliable baseline benchmarks in seconds.
- **Technical Areas:** Shared (`config.schema.json`), Backend (`config_models.py`), Frontend (`ConfigurationSidebar.tsx`, `ConfigurationSidebar.css`).
- **Dependencies:** None.
- **Definition of Done:**
  - Minimum 4 presets available in the sidebar dropdown.
  - Selecting a preset populates all geometric, traffic, and controller fields correctly.
  - Invalid inputs produce inline red borders and descriptive validation warnings without application crashes.
- **Future Extension (V1.2+):** Configuration export/import via standalone `.traffic.json` configuration files.

---

### 4.6 More Realistic Fixed-Time Signal Control

> **Plain-Language Meaning:** Enhance the traffic signal model with realistic timing phases and offsets without turning V1.1 into a full research project on smart AI signals.

- **Status:** Planned
- **Priority:** P1
- **Why:** The V1.0 signal controller uses a basic 2-phase green/yellow cycle. Realistic fixed-time signals require standard clearance intervals and configurable phase splits.
- **Current V1 Capability:**
  - `FixedTimeSignalController` (`backend/src/controllers/fixed_time.py`) cycles North/South and East/West phases.
  - Configurable `greenTime`, `yellowTime`, and `allRedTime`.
  - Canvas overlay draws colored stop-bars and current active phase countdown.
- **V1.1 Addition:**
  - **Configurable Phase Splits:** Allow independent green times for North/South vs. East/West approaches to model asymmetric traffic demand realistically.
  - **Phase Clearance Intervals:** Enforce physical minimum clearance equations based on approach speed and lane width (preventing unsafe instantaneous red transitions).
  - **Cycle Offset Setting:** Introduce an `offsetSeconds` parameter ($0$ to cycle length) to shift cycle start times (laying groundwork for future corridor green wave coordination).
  - **Dedicated Left-Turn Phasing Option:** Support an optional protected left-turn phase configuration in the fixed-time sequence.
  - *Boundary Rule:* Actuated/detector-based signals and Reinforcement Learning control are **strictly deferred to V2**.
- **User Benefit:** Allows accurate modeling of real-world municipal signal timing sheets without destabilizing the comparative baseline.
- **Technical Areas:** Backend (`src/controllers/fixed_time.py`, `src/core/config_models.py`), Frontend (`ConfigurationSidebar.tsx`, `IntersectionCanvas.tsx`).
- **Dependencies:** Config schema extension for directional signal timings.
- **Definition of Done:**
  - Signal controller accurately executes asymmetric phase times (e.g., N/S Green = $45\,\text{s}$, E/W Green = $25\,\text{s}$).
  - All-red clearance intervals clear the intersection conflict zone completely before conflicting greens activate.
  - Visualizer displays active phase names and remaining phase seconds.
- **Future Extension (V2):** Actuated demand-responsive signals utilizing virtual inductive loop detectors.

---

### 4.7 Powerful Comparison & Trade-Off Analytics

> **Plain-Language Meaning:** The system should tell users which intersection performed better, by what percentage, and explain the trade-offs instead of just showing numbers.

- **Status:** Partially Complete (Basic comparison endpoint exists; lacks multi-metric trade-off evaluation)
- **Priority:** P0
- **Why:** Raw numbers require manual interpretation. An executive or engineer needs to know: *"Which option won, by how much, and what is the trade-off?"*
- **Current V1 Capability:**
  - Side-by-side interactive execution (`DualSimulationOrchestrator`).
  - Comparative metrics sidebar showing real-time counters.
  - `POST /api/v1/study/history/runs/compare` computing percentage deltas between two runs.
  - `WeightedScoringPanel.tsx` calculating aggregate scores based on customizable user weights.
- **V1.1 Addition:**
  - **Automated Metric Winner Engine:** Evaluate comparisons across all 10 dimensions with transparent delta indicators:
    - *Roundabout:* $24.2\%$ lower average delay ($\Delta = -5.3\,\text{s}$) 🟢
    - *Roundabout:* $38.1\%$ fewer full stops ($\Delta = -182\,\text{stops}$) 🟢
    - *Signal:* $12.5\%$ lower queue length variance during saturation 🟢
    - *Signal:* $65.0\%$ smaller physical footprint ($225\,\text{m}^2$ vs. $645\,\text{m}^2$) 🟢
  - **Nuanced Executive Verdict:** Avoid naive single "winner" declarations when metrics conflict. Output a balanced synthesis:
    > *"Verdict: Roundabout provides superior operational efficiency and driver convenience at this volume level, but requires 2.8x more land area than the signalized alternative."*
  - **Statistical Significance Indicators:** Cross-reference observed differences against Monte Carlo standard deviations to flag whether improvements are statistically significant ($p < 0.05$) or within random simulation noise.
- **User Benefit:** Directly answers the user's ultimate engineering question with defensible, publication-grade comparative insights.
- **Technical Areas:** Backend (`src/study/report_generator.py`, `src/main.py`), Frontend (`ComparativeDashboard.tsx`, `WeightedScoringPanel.tsx`).
- **Dependencies:** Metric contract reliability updates (§4.3).
- **Definition of Done:**
  - Comparison views highlight winner badges and percentage improvements per metric.
  - The UI generates an automated plain-language executive trade-off summary.
  - Conflicting metrics (e.g., lower delay vs. larger space consumption) are explicitly balanced in the verdict.
- **Future Extension (V1.2+):** Radar/Spider charts comparing multi-dimensional trade-offs graphically.

---

### 4.8 Production-Grade Backend & Platform Hardening

> **Plain-Language Meaning:** Ensure the backend runs smoothly, handles errors safely, limits simultaneous resource consumption, and does not crash during long experiments.

- **Status:** Partially Complete (CORS, API key, and basic concurrency safeguards exist; needs active simulation throttling and session GC)
- **Priority:** P1
- **Why:** Running automated sweeps and simultaneous browser connections can saturate server resources if lifecycles are unmanaged.
- **Current V1 Capability:**
  - Thread-safe `SnapshotBuffer` with concurrency locks.
  - SQLite configured in WAL mode with a 5-second busy timeout and thread-safe connection pooling.
  - Uniform `HTTPException` error formatting envelope.
  - Optional `require_api_key` bearer authentication for mutating routes.
  - Docker health check on `/health` endpoint.
- **V1.1 Addition:**
  - **Simulation Concurrency Semaphore:** Enforce a strict server-wide limit on concurrent active simulations (e.g., maximum 4 concurrent running engines) to prevent CPU starvation. Excess requests receive HTTP 429 (`SIMULATION_LIMIT_REACHED`).
  - **Orphan Session Garbage Collection:** Background scavenger task terminating in-memory simulation sessions that have received no WebSocket heartbeat or REST interaction for $> 5\,\text{minutes}$.
  - **Structured JSON Logging:** Standardize application logs into structured JSON format with contextual attributes (`simulation_id`, `request_id`, `client_ip`) for production observability.
  - **Graceful Shutdown Signal Handling:** Trap `SIGTERM` and `SIGINT` to safely stop active engine threads and commit pending SQLite transactions cleanly.
- **User Benefit:** Ensures rock-solid reliability during live demonstrations and automated batch executions on cloud servers.
- **Technical Areas:** Backend (`src/main.py`, `src/core/engine.py`, `src/database/db.py`), Docker (`docker-compose.yml`).
- **Dependencies:** None.
- **Definition of Done:**
  - Launching more than the configured maximum concurrent simulations returns clean HTTP 429 errors without crashing the server.
  - Abandoned browser sessions are automatically reclaimed after 5 minutes of inactivity.
  - Unit and integration tests verify server stability under concurrent load.
- **Future Extension (V1.2+):** Prometheus/OpenTelemetry metric instrumentation endpoint (`/metrics`).

---

### 4.9 Frontend Architecture & UX Quality

> **Plain-Language Meaning:** Clean up the frontend codebase, make components easier to maintain, eliminate code duplication, and improve user interface responsiveness.

- **Status:** Planned
- **Priority:** P1
- **Why:** Fast feature prototyping created several massive monolith components (e.g., `VolumeAnalysisDashboard.tsx` at $> 1,000$ lines) and duplicated export routines that increase technical debt.
- **Current V1 Capability:**
  - Responsive React 18 TypeScript dashboard with dark-mode aesthetic.
  - Canvas visualizer with pan/zoom controls.
  - Working dashboards for Live, Comparative, Volume Analysis, Validation, and History.
- **V1.1 Addition:**
  - **Modular Component Decomposition:** Break oversized components (`VolumeAnalysisDashboard.tsx`, `ValidationDashboard.tsx`) into focused sub-components (e.g., `VolumeCurveChart`, `CrossoverSummaryCard`, `ParameterControlBar`).
  - **Consolidated Export Service:** Extract duplicated CSV and JSON generation logic from individual dashboards into a centralized, unit-tested `services/exportService.ts`.
  - **Strict Type Safety & Zero Any:** Eliminate remaining `any` casts in frontend API handlers; align TypeScript models strictly with `shared/schemas/`.
  - **User Experience Polish:**
    - Global simulation keyboard shortcuts: `Space` (Play/Pause), `R` (Reset), `S` (Single Step), `D` (Toggle Dual View).
    - Clear WebSocket reconnect banners with exponential backoff status.
    - Accessible color contrast and focus rings on all interactive buttons.
- **User Benefit:** A smoother, faster, more responsive user interface that is significantly easier for future developers to extend.
- **Technical Areas:** Frontend (`src/components/`, `src/services/`, `src/types/`).
- **Dependencies:** None.
- **Definition of Done:**
  - Monolithic components refactored into files under 400 lines each.
  - TypeScript build passes with zero `any` compiler warnings.
  - Keyboard shortcuts function reliably across all dashboard tabs.
- **Future Extension (V1.2+):** Configurable multi-monitor / full-screen kiosk presentation mode.

---

### 4.10 Standardized Reporting & Results Presentation

> **Plain-Language Meaning:** Allow users to export a clean, professional summary of their simulation results that is ready to present to stakeholders or include in a research paper.

- **Status:** Planned / Partially Complete (Raw CSV export exists; needs comprehensive summary packages)
- **Priority:** P1
- **Why:** Simulations are useless if their results cannot be easily communicated to clients, professors, or municipal leaders.
- **Current V1 Capability:**
  - `backend/src/study/report_generator.py` exports CSV summaries.
  - `GET /api/v1/study/export?format=csv` downloads volume sweep results.
  - Raw JSON report endpoint `GET /api/v1/simulations/{id}/report`.
- **V1.1 Addition:**
  - **Standardized "Experiment Summary Package":** Single-click download generating a self-contained `.zip` or directory bundle containing:
    1. `executive_summary.md`: Human-readable comparative findings with verdict.
    2. `reproducibility_manifest.json`: Exact seed, runtime environment, and scenario configuration.
    3. `metrics_summary.csv`: Full tabular metrics for spreadsheet analysis.
    4. `timeline_data.json`: Tick-by-tick time-series data for custom charting.
  - **Printable Clean HTML / PDF Summary:** A styled, printable report view formatted with clean typography, key metric tables, and embedded comparison charts.
- **User Benefit:** Users can generate polished project deliverables directly from the software without manual data assembly in Excel.
- **Technical Areas:** Backend (`src/study/report_generator.py`), Frontend (`src/services/exportService.ts`, `src/components/`).
- **Dependencies:** Comparative analytics engine (§4.7).
- **Definition of Done:**
  - Users can export a complete Experiment Summary Package from any completed run or volume sweep.
  - The generated report includes metadata, methodology, metric tables, and clear conclusion text.
- **Future Extension (V1.2+):** Automated server-side PDF compilation using Weasyprint or headless browser rendering.

---

### 4.11 Additional Evaluated V1.1 Features

The following additional ideas have been evaluated and classified according to their value and complexity:

| Feature Concept | Description | Classification | Target Version |
| :--- | :--- | :--- | :--- |
| **A. Scenario Presets** | Library of standard traffic scenarios (Suburban, Urban Arterial, Peak). | **V1.1 Core** (P1) | V1.1.0 |
| **B. Multi-Seed Batch Sweeps** | Running multiple seeds per volume step to produce confidence ribbons. | **V1.1 Core** (P0) | V1.1.0 |
| **C. Comparison Workspace** | Multi-run selection and comparison directly within History view. | **V1.1 Core** (P0) | V1.1.0 |
| **D. Executive Report Generation**| Automated markdown/HTML comparative narrative synthesis. | **V1.1 Core** (P1) | V1.1.0 |
| **E. Canvas Visual Enhancements** | Heatmap speed overlay and queue tail indicators on canvas. | **V1.1 Nice-to-Have** (P2) | V1.1.0 / V1.2 |
| **F. Experiment Metadata / Tags** | Custom run names, author notes, and categorization tags in SQLite. | **V1.1 Core** (P1) | V1.1.0 |
| **G. Shareable Experiment Manifest**| Exportable JSON descriptor enabling peer verification of any run. | **V1.1 Core** (P1) | V1.1.0 |
| **H. Concurrency Throttling** | Semaphore-based server execution limits with HTTP 429 guards. | **V1.1 Core** (P1) | V1.1.0 |
| **I. Structured JSON Logging** | Standardized JSON log emission with correlation IDs. | **V1.1 Nice-to-Have** (P2) | V1.1.0 / V1.2 |
| **J. Presentation / Demo Mode** | Clean full-screen interface hiding sidebars for live stage presentations. | **V1.1 Nice-to-Have** (P2) | V1.1.0 / V1.2 |

---

## 5. V1.1 Implementation Priority Order

To ensure systematic progress without destabilizing the stable baseline, V1.1 features must be implemented in the following chronological sequence:

```
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: TRUST & FOUNDATIONS                                           │
│ 1. Complete Reproducibility Verification & Manifest Checksums (§4.1)   │
│ 2. Run History Management, Filtering, Search & Tagging (§4.2, §4.11-F) │
│ 3. Multi-Run Comparison Workspace (§4.2, §4.11-C)                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: SCIENTIFIC RIGOR & COMPARATIVE INTELLIGENCE                   │
│ 4. Metric Reliability: Units, Low-Sample Alerts & In-App Formulas (§4.3│
│ 5. Automated Multi-Metric Comparison & Executive Trade-Offs (§4.7)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: EXPERIMENTATION POWER & USABILITY                             │
│ 6. Multi-Seed Volume Sweeps with Statistical Confidence Bands (§4.4)   │
│ 7. Standard Scenario Presets Library & Field Validation Polish (§4.5)  │
│ 8. Directional Phase Splits & Clearance Timing for Fixed Signal (§4.6) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: PLATFORM HARDENING & REPORTING                                │
│ 9. Server Concurrency Limits & Orphan Session Garbage Collector (§4.8) │
│ 10. Standardized Experiment Summary Package & Export Service (§4.10)   │
│ 11. Frontend Codebase De-monolithing & Keyboard Controls (§4.9)        │
│ 12. Polish, Presentation Demo Mode & Release Validation (§4.11-J)      │
└────────────────────────────────────────────────────────────────────────┘
```

**Rationale for Priority:**
- *Phase 1* establishes the bedrock of scientific trust (reproducibility and experiment recall).
- *Phase 2* guarantees that every displayed metric is mathematically defensible and comparative verdicts are transparent.
- *Phase 3* builds on that trust to deliver the marquee analytical tools (multi-seed volume sweeps and presets).
- *Phase 4* packages the entire platform with production stability, clean reporting, and maintainable frontend architecture.

---

## 6. V1.1 Release Definition of Done

A release to V1.1.0 requires all the following criteria to be satisfied:

### 1. Functionality & Science
- [ ] Any historical run can be reproduced headlessly with $100\%$ vehicle conservation and matching delay/throughput metrics.
- [ ] Multi-seed volume sweeps execute successfully, displaying delay and throughput curves with standard error / confidence intervals.
- [ ] Low-sample size warnings ($N < 15$) display on all affected metrics.
- [ ] At least 4 realistic scenario presets are selectable from the UI and execute without configuration errors.
- [ ] Comparisons provide both individual metric deltas and an automated plain-language trade-off summary.
- [ ] Fixed-time signals support asymmetric green splits between North/South and East/West.

### 2. Testing & Quality Assurance
- [ ] All existing backend pytest unit, integration, and concurrency tests pass ($100\%$ green).
- [ ] New automated tests verify deterministic reproduction checksums across consecutive runs.
- [ ] New automated tests verify volume sweep execution and multi-seed statistical calculations.
- [ ] Frontend TypeScript builds cleanly with zero compile errors and zero `any` types in API clients.
- [ ] Vitest frontend unit tests pass for all refactored modular components and export services.

### 3. Concurrency, Performance & Security
- [ ] Backend enforces concurrency limits, rejecting excess simulation runs with HTTP 429.
- [ ] Orphan simulation sessions are automatically purged after 5 minutes of inactivity.
- [ ] SQLite operations complete cleanly under simultaneous read/write load without database lock errors.

### 4. Documentation & Release Packaging
- [ ] `docs/operations.md` updated with all new endpoints and preset parameters.
- [ ] `docs/architecture/07-metric-contract.md` synchronized with low-sample threshold definitions.
- [ ] Docker Compose build (`docker compose up --build`) initializes cleanly with healthy frontend and backend containers.
- [ ] `docs/ROADMAP.md` updated to reflect completed V1.1 scope in the Release History section.

---

## 7. V1.2 / Near-Future Incremental Ideas

Features that provide genuine product value but are intentionally excluded from V1.1 to maintain delivery velocity:

1. **Multi-Parameter Grid Search:** Run 2D parameter matrices (e.g., varying arrival volume on the X-axis and turning fraction on the Y-axis simultaneously).
2. **Dynamic Headway Distribution Models:** Complement Poisson arrivals with Cowan M3 or shifted negative binomial arrival distributions for bunched platoon arrivals.
3. **Database Migration Tooling:** Integrate Alembic for formal, versioned SQLite schema migrations as database tables evolve.
4. **Dark / Light Theme Toggle:** Implement high-contrast light theme support with accessible color palettes for academic classroom projection.
5. **Interactive Replay Scrubbing Bar:** Allow scrubbing backward and forward in time across buffered snapshot histories in the canvas visualizer.
6. **Server-Side PDF Report Generation:** Direct export of publication-styled PDF documents using Weasyprint or headless Chrome.

---

## 8. V2 — Advanced Simulation Engine & Geometry

> **Important Architecture Boundary:** The features below represent major evolutions of the microscopic physics engine and geometric modeling. They are **strictly reserved for Version 2.0+** to prevent destabilizing the verified V1/V1.1 baseline.

### Why These Belong in V2
The current V1 engine uses a 1-dimensional longitudinal car-following model (IDM) mapped onto fixed path geometries with point-based yield checks. Introducing multi-lane ring circulation, lane changing, or dynamic gap acceptance changes the core physics loop. Attempting these changes during V1.1 would invalidate existing benchmark tests and delay the delivery of the experimentation platform.

```
                  CURRENT V1/V1.1 ENGINE (Fixed-Geometry IDM)
                      ┌─────────────────────────────────┐
                      │   Approach Lane (Single/Scalar) │
                      └────────────────┬────────────────┘
                                       │ Yield Line Time Gap
                                       ▼
                      ┌─────────────────────────────────┐
                      │    Single Ring Trajectory Arc   │
                      └─────────────────────────────────┘

                  FUTURE V2 ENGINE (Spatial-Temporal Multi-Lane)
       ┌───────────────────────────────┬───────────────────────────────┐
       │   Multi-Lane Approach (Indep) │   Asymmetric Inflow Geometry  │
       └───────────────┬───────────────┴───────────────┬───────────────┘
                       │ Predictive Conflict Mesh      │ Dynamic Lane Weaving
                       ▼                               ▼
       ┌───────────────────────────────────────────────────────────────┐
       │     Multi-Lane Spiral Ring with Predictive Gap Acceptance     │
       └───────────────────────────────────────────────────────────────┘
```

### Candidate V2 Feature Breakdown

1. **Predictive Roundabout Conflict Architecture:** Move beyond simple yield-line time headways to continuous spatial-temporal conflict zone prediction, projecting potential intersection trajectories seconds into the future.
2. **Proper Multi-Lane Roundabout Modeling:** Implement multi-lane circulating rings where vehicles select inner vs. outer lanes based on their planned destination exit.
3. **Independent Circulating Lane Geometry (`circulatingLanes`):** Decouple circulating ring lane counts from approach lane counts (activating the reserved `circulatingLanes` configuration field).
4. **Asymmetric Approach Geometry:** Allow independent lane configurations per leg (e.g., North approach has 3 lanes, East approach has 1 lane).
5. **Dynamic Lane Changing & Weaving:** Implement lane-changing logic (e.g., MOBIL model) enabling vehicles to change lanes to avoid queues or prepare for turns.
6. **Heterogeneous Vehicle Fleets:** Support distinct vehicle classes (passenger sedans, heavy goods trucks, city buses, motorcycles) with distinct physical dimensions, maximum accelerations, and turning radii.
7. **Advanced Conflict Severity Metrics:** Replace basic bounding-box collision audits with standard surrogate safety measures: Post-Encroachment Time (PET) and Time-to-Collision (TTC).
8. **Actuated & Demand-Responsive Signal Controllers:** Introduce virtual inductive loop detectors and gap-out/max-out logic to adjust green times dynamically based on real-time vehicle arrivals.
9. **Adaptive Signal Optimization:** Implement Webster's method for real-time cycle length optimization and Reinforcement Learning (RL) signal agents.
10. **Multi-Intersection Corridor Simulation:** Connect multiple intersections along an arterial corridor to model coordinated green waves and multi-roundabout networks.

---

## 9. Long-Term Vision (V3+)

Looking further into the future, the platform can evolve into a full-scale smart mobility testbed:

- **Connected & Autonomous Vehicles (CAV):** Model Cooperative Adaptive Cruise Control (CACC) and vehicle-to-infrastructure (V2I) communication.
- **Zero-Signal Autonomous Intersections:** Model reservation-based autonomous intersection control where self-driving vehicles cross through conflict zones without stopping by reserving precise spatio-temporal tiles.
- **Environmental & Emissions Modeling:** Integrate recognized vehicular emission models (e.g., VT-Micro, COPERT) to quantify CO₂, NOₓ, and fuel consumption differences between signals and roundabouts.
- **Open Data & GIS Integration:** Import real-world road networks from OpenStreetMap (OSM) and calibrate arrival volumes using real-world inductive loop traffic counts.

---

## 10. Deferred / Explicitly Not Now Log

A per-item audit of what is actually known to be wrong or limited in the
shipped V1 build, with each item classified and re-measured, lives in
[V1 Known Limitations](reports/v1-known-limitations.md). Read that alongside
this table: this table records *features* that were postponed, that one
records *defects and scope limits* that were measured and triaged.

This section records features that have been deliberately evaluated and postponed. 

**Rule:** Do not implement or re-plan any item in this table without an explicit decision confirming that its activation conditions have been met.

| Proposed Feature | Reason Deferred | Target Version | Condition Required to Implement |
| :--- | :--- | :--- | :--- |
| **Actuated / Smart Traffic Signals** | Destabilizes the fixed-time comparative baseline; requires virtual detector infrastructure. | V2.0 | Completion of V1.1 baseline and formal detector contract specification. |
| **Reinforcement Learning Signal Control** | High computational overhead; experimental; diverges from practical baseline traffic engineering. | V2.1+ | Working actuated signal baseline and standardized Gym/PettingZoo environment. |
| **Predictive Roundabout Conflict Mesh** | Requires deep rewrite of vehicle physics loop and coordinate projection math. | V2.0 | Dedicated simulation engine architecture phase. |
| **Multi-Lane Circulating Roundabout** | Current single-ring geometry cannot model spiral lane assignments or weaving conflicts. | V2.0 | Full geometric rewrite supporting independent ring coordinates. |
| **Asymmetric Per-Approach Lane Counts** | Requires decoupling approach lane counts from ring lane counts across both controllers. | V2.0 | Implementation of independent approach-to-intersection routing matrix. |
| **Heterogeneous Multi-Class Vehicles** | Complex rendering and acceleration tuning; passenger cars provide $90\%$ of comparative value. | V2.0 | Stable single-vehicle class comparison framework in V1.1. |
| **Corridor Coordination / Green Waves** | Requires multi-intersection network graph, routing trees, and upstream-to-downstream vehicle handover. | V2.2+ | Single-intersection simulation proven completely stable and hardened. |
| **Structured 422 Error Envelope** | FastAPI default 422 validation shape is relied upon by existing test fixtures; modifying breaks clients. | V1.2+ | Scheduled major API contract version migration. |
| **Client-Side Metric Computation** | Violates ADR-005; leads to floating-point drift between browser and headless runs. | **Rejected** | None. Metrics must remain strictly backend-authoritative. |
| **Zero-Signal Autonomous Swarm** | Theoretical future concept; irrelevant to current real-world municipal infrastructure comparisons. | V3.0+ | Fully autonomous vehicle penetration modeling requirements. |

---

## 11. Completed Work & Release History

### Version 1.0.0 — Stable Baseline
*Release Date:* 2026-09-11  
*Status:* Released & Audited

#### Key Deliverables & Architecture
- **Core Engine:** Discrete-time physics engine ($10\,\text{Hz}$) with Intelligent Driver Model (IDM) acceleration and Poisson vehicle spawner.
- **Controllers:** Fully operational Fixed-Time Signal and Modern Roundabout controllers adhering to `BaseController` polymorphic registry.
- **Real-Time Streaming:** High-performance WebSocket stream broadcasting 10 Hz simulation snapshots with serialized vehicle coordinates and running metrics.
- **Frontend Dashboard:** Interactive Vite + React 18 TypeScript application featuring dual Canvas visualizers, real-time metric charts, playback controls, and volume analysis tools.
- **Metric System:** Comprehensive `MetricCollector` calculating 10 standardized metrics with startup warmup period exclusion.
- **Scientific Validation Engine:** Mass conservation checks, kinematic boundary invariant audits, and multi-seed Monte Carlo statistical validation.
- **Persistence Layer:** SQLite database (WAL mode) tracking simulation runs, metric time-series, volume sweep sessions, and user replays.
- **Platform Hardening:** Thread-safe `SnapshotBuffer`, CORS origin allowlists, optional API key authentication, uniform error handling, and Docker containerization.

---

### Version 1.1.0 — Reproducible Traffic-Analysis Platform
*Target Release Date:* 2026-10-15  
*Status:* Planned (Ready for Implementation)

#### Scope of Work
- Implementation of the 10 core feature areas detailed in Section 4.
- Deterministic experiment reproduction with bitwise state verification.
- Advanced experiment history workspace with search, filtering, and tag management.
- Standardized scenario presets and human-friendly configuration validation.
- Multi-seed volume sweep analysis with statistical confidence bands.
- Automated multi-metric comparative intelligence and plain-language trade-off summaries.
- Production concurrency throttling and orphan session lifecycle management.
- Self-contained Experiment Summary Package exports.

---

## 12. Architectural Decision Log

This section documents foundational architectural decisions. These decisions are binding; future contributors must not alter them without an explicit ADR update.

### Decision 1: Scalar Public `lanesPerApproach` Contract
- **Decision:** The public configuration schema accepts a single integer (`roads.lanesPerApproach`, 1–4) applied symmetrically to all four approaches.
- **Context:** While internal legacy forms allow per-direction dictionaries, the versioned API enforces symmetry.
- **Rationale:** Roundabout circular geometry currently derives its circulating path count directly from approach lanes. Allowing asymmetric lanes on one approach without independent ring geometry causes physical lane-count contradictions.
- **Reference:** `docs/architecture/06-scenario-configuration-contract.md` §2.4.

### Decision 2: `circulatingLanes` Reserved Schema Property
- **Decision:** The field `controller.circulatingLanes` is accepted and schema-validated, but is currently non-functional at runtime.
- **Context:** In V1/V1.1, the roundabout's circulating lane count is derived entirely from `roads.lanesPerApproach`.
- **Rationale:** Preserves forward schema compatibility for V2 multi-lane roundabouts without premature, half-implemented ring-lane routing logic.
- **Reference:** Commit `3fde76e`; `docs/architecture/06-scenario-configuration-contract.md` §2.6.2.

### Decision 3: Post-Hoc SAT Collision Audit Safety Net
- **Decision:** The system tracks vehicle overlaps using a post-hoc Separating Axis Theorem (SAT) debounced audit rather than an active predictive collision-avoidance system.
- **Context:** If IDM car-following or roundabout yielding gaps fail under extreme saturation, vehicles may overlap.
- **Rationale:** A reactive audit provides an honest, deterministic count of safety failure events without adding massive computational overhead to the physics loop. Active collision-mesh avoidance is deferred to V2.
- **Reference:** `docs/architecture/07-metric-contract.md` §2.10.

### Decision 4: Actuated Signal Controllers Strictly Deferred
- **Decision:** Fixed-time control is the only signal controller supported in V1 and V1.1.
- **Context:** Demands frequently arise to model "smart" or actuated signals.
- **Rationale:** Comparing a dynamic roundabout against a static signal is the foundational benchmark in traffic engineering. Introducing actuated control prematurely adds dozens of uncalibrated detector variables that obscure core geometric performance differences.
- **Reference:** `ADR-012: Future Controller Extensibility`.

### Decision 5: FastAPI Default 422 Validation Error Preserved
- **Decision:** Schema validation failures triggered by FastAPI's Pydantic parser return FastAPI's default 422 error shape rather than being rewritten into the application's `{"error": {...}}` envelope.
- **Context:** HTTPExceptions return a uniform envelope, but 422s do not.
- **Rationale:** Existing integration test suites and frontend error interceptors depend on the standard Pydantic error array. Unifying 422s without a coordinated migration breaks client compatibility.
- **Reference:** `docs/architecture/08-communication-contract.md` §6.1.

### Decision 6: In-Memory Live Streaming vs. Persisted Studies Policy
- **Decision:** Interactive live canvas runs (`/ws/simulation/live`) stream ephemeral state in-memory and are not auto-persisted to SQLite unless explicitly saved via the Replay API. Programmatic runs and volume sweeps (`/api/v1/study/sweeps/run`) are automatically persisted to SQLite.
- **Context:** High-frequency 10 Hz canvas manipulation can generate thousands of transient ticks.
- **Rationale:** Prevents unbounded SQLite database file bloat during casual interactive experimentation while guaranteeing permanent storage for formal analytical studies.
- **Reference:** `docs/operations.md` §Replays and Database.

### Decision 7: Backend as the Single Source of Metric Authority
- **Decision:** All mathematical calculations, statistical averages, and metric aggregations are executed exclusively in the backend `MetricCollector`. The frontend is strictly a presentation layer.
- **Context:** Displaying running metrics could theoretically be calculated in the browser from vehicle coordinate streams.
- **Rationale:** Guarantees that live dashboard views, final REST summaries, and headless batch scripts produce $100\%$ identical numbers without floating-point drift across runtimes.
- **Reference:** `ADR-005: Metric Contract Design`.

### Decision 8: Polymorphic Controller Registry Pattern
- **Decision:** The simulation engine loop contains no conditional logic for specific intersection types. Controllers register with `@register_controller` and implement the abstract `BaseController` interface.
- **Context:** Adding intersection types should never require editing `SimulationEngine.step()`.
- **Rationale:** Enforces the Open-Closed Principle and ensures that vehicle physics and arrival processes remain identical regardless of control strategy.
- **Reference:** `ADR-012: Future Controller Extensibility`.

---

## 13. How to Maintain This Roadmap

To ensure this document remains useful over months and years, all developers and AI agents must follow these 10 maintenance rules:

1. **Single Source of Truth:** This document (`docs/ROADMAP.md`) is the canonical roadmap. Do not create separate, competing roadmap files in subdirectories.
2. **Never Delete Completed Features:** When a release ships, move its features into [Completed Work & Release History](#11-completed-work--release-history). Preserve the record of what was built.
3. **Update Statuses Promptly:** Update feature statuses (`Planned` $\rightarrow$ `In Progress` $\rightarrow$ `Complete`) as implementation advances.
4. **Move Unfinished Items Forward:** If a planned V1.1 item cannot be completed in time, explicitly move it to V1.2 rather than silently removing it.
5. **Check Capabilities Before Planning:** Before proposing a "new" feature, inspect the codebase to verify whether related infrastructure already exists.
6. **Log Architectural Decisions:** Every significant design choice or intentional deferral must be documented in [Architectural Decision Log](#12-architectural-decision-log) or [Deferred Log](#10-deferred--explicitly-not-now-log).
7. **Protect the V2 Boundary:** Do not allow advanced simulation features (multi-lane roundabouts, actuated signals, lane weaving) to creep into minor V1.x releases.
8. **Keep Plain Language Primary:** Explain technical terms simply. Ensure the document is readable by engineers, researchers, and project stakeholders alike.
9. **Update After Major Milestones:** Always review and synchronize this roadmap immediately following any major release or architectural audit.
10. **Preserve Deferred Rationales:** When rejecting or deferring an idea, always document *why* it was deferred and *what condition* would justify reopening it.
