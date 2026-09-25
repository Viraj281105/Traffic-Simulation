# Stitch-Ready Design Specification: Traffic-Simulation Live Comparison & Live Metrics Experience

> **Note (2026-09-25):** this is the original design brief. Where it differs from the implementation it is superseded by `docs/product/urbanflow-evaluation-metrics.md` §15: the fixed-weight composite is no longer shown side by side across geometries, the delay whisker box is median → 95th percentile (not an IQR), and "served" figures use a single window.

## 1. Executive Summary

This document specifies the complete visual design system, component architecture, data contracts, and interaction patterns for the redesigned **Live Comparison & Live Metrics experience** in UrbanFlow Traffic-Simulation.

The redesigned experience replaces static, text-heavy tables with a polished, premium, high-density traffic analytics command center. Every evaluation metric reported by the backend is paired with an appropriate visual representation (time-series line charts, cumulative area fills, 4-stage pipeline flow indicators, directional approach radars, radial arc gauges, event timelines, and distribution whisker ranges) powered by live rolling history from the WebSocket stream.

---

## 2. Design System Tokens & Aesthetics

### 2.1 Theme Colors & Palettes

| Token | CSS Variable / Value | Dark Theme | Light Theme | Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Signal Accent** | `--control-signal` | `#f59e0b` (Amber-500) | `#d97706` (Amber-600) | Signal lines, dots, indicators |
| **Signal Soft Fill** | `--control-signal-fill`| `rgba(245, 158, 11, 0.15)` | `rgba(217, 119, 6, 0.12)` | Signal area fills, badges |
| **Roundabout Accent** | `--control-roundabout` | `#06b6d4` (Cyan-500) | `#0891b2` (Cyan-600) | Roundabout lines, dots, indicators |
| **Roundabout Soft Fill**| `--control-roundabout-fill`| `rgba(6, 182, 212, 0.15)` | `rgba(8, 145, 178, 0.12)` | Roundabout area fills, badges |
| **Delta ($\Delta$) Neutral**| `--delta-neutral` | `rgba(255, 255, 255, 0.05)` | `rgba(0, 0, 0, 0.05)` | Difference badge backgrounds |
| **Critical Cutoff** | `--color-critical` | `#ef4444` (Red-500) | `#dc2626` (Red-600) | TTC/PET thresholds, collisions |
| **Ideal Benchmark** | `--color-benchmark` | `#10b981` (Emerald-500) | `#059669` (Emerald-600) | Ideal PTI (1.00), zero collisions |
| **Warm-up Amber** | `--color-warmup` | `#f59e0b` | `#d97706` | Warm-up notice banners & pulses |

### 2.2 Typography & Formatting

- **Font Families**:
  - Primary UI: `"Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
  - Numbers & Metrics: `"JetBrains Mono", "DM Mono", monospace` (`font-variant-numeric: tabular-nums`)
- **Units Presentation**:
  - Always rendered alongside values (`s`, `veh`, `veh/min`, `m/s`, `m²`, `veh/s`, `%`, `pp`).
  - Differences ($\Delta = \text{Roundabout} - \text{Signal}$) use signed formatting with explicit units (e.g. `+1.4 s`, `−2 veh`, `+4.5 pp`).
- **Tooltips**:
  - Rich dark tooltips on hover displaying full plain-language definitions from the metric catalog and exact numerical values.

---

## 3. Architecture & Information Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Comparative View Screen                         │
├──────────────────────────────────────────┬─────────────────────────────┤
│         Simulation Canvases (Left)       │  Live Comparison Panel      │
│  ┌───────────────────┬────────────────┐  │  (Docked Sidebar, 440px)    │
│  │ 🚦 Fixed-Time     │ 🔄 Modern      │  ├─────────────────────────────┤
│  │    Signal         │    Roundabout  │  │ Category Pills Nav:         │
│  │    Intersection   │    Junction    │  │ [Flow][Perf][Queues][Safe]  │
│  │                   │                │  ├─────────────────────────────┤
│  │                   │                │  │ Vehicles Pipeline & Flow    │
│  │                   │                │  │ Key Performance Sparklines  │
│  │                   │                │  │ Collisions & Min TTC Alert  │
│  └───────────────────┴────────────────┘  ├─────────────────────────────┤
│                                          │ Actions: [Full Analytics]   │
└──────────────────────────────────────────┴─────────────────────────────┘
                                  │
                                  ▼ (Clicks "Full comparison & weighting")
┌────────────────────────────────────────────────────────────────────────┐
│        Full Comparative Analytics Command Center (Modal Dialog)        │
├────────────────────────────────────────────────────────────────────────┤
│  Header: Signal vs Roundabout — Full Comparison                        │
│  View Switcher: [📊 Visual Analytics]  |  [📋 Data Table]              │
├────────────────────────────────────────────────────────────────────────┤
│  1. Vehicles Now & Pipeline Flow (4-stage cards + proportional bar)    │
│  2. Performance & Service Dynamics (Live Recharts multi-metric charts) │
│  3. Traffic Flow & Approach Cross (4-way directional N/S/E/W queues)   │
│  4. Safety & Surrogate Conflict Measures (Collision timeline, TTC, PET)│
│  5. Capacity & Demand Balance (Offered vs Served stack, utilization)   │
│  6. Distribution Spread & Diagnostics (Delay whisker, dispersion dials)│
│  7. Multi-Criteria Evaluation (Interactive user-weighted score panel)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Metric-by-Metric Visual Specification

### 4.1 Vehicles Now

- **Underlying Data**: `LiveSnapshot.vehicleCounts` (`active`, `approaching`, `waiting`, `crossing`, `inRoundabout`, `exited`).
- **Visual Components**:
  1. **4-Stage Pipeline Grid**:
     - Stage 1: `In Network` (`active`) — Total active vehicles in network.
     - Stage 2: `Waiting` (`waiting`) — Queue count with speed $< 0.5\text{ m/s}$.
     - Stage 3: `In Junction` (Signal: `crossing`, Roundabout: `crossing + inRoundabout`).
     - Stage 4: `Exited` (`exited`) — Cumulative completed vehicle trips.
     - Each card displays Signal value, Roundabout value, and $\Delta$.
  2. **Proportional Flow Bar**:
     - Visual horizontal breakdown showing distribution of in-network vehicles:
       `Waiting` (Red) vs `In Junction` (Amber) vs `Cruising` (Green).

### 4.2 Performance Metrics

| Metric | Backend Key | Visual Type | Scale / Axis | Behavior & Thresholds |
| :--- | :--- | :--- | :--- | :--- |
| **Average Delay** | `averageDelay` | Live Line Chart | $0 - Y_{\max}$ s | Signal vs Roundabout live trends. |
| **Median Delay** | `medianDelay` | Live Line Chart | $0 - Y_{\max}$ s | Dashed trend lines alongside average delay. |
| **95th Percentile Delay** | `p95Delay` | Live Line Chart | $0 - Y_{\max}$ s | Upper tail delay envelope curve. |
| **Average Queued Time** | `averageWaitTime` | Live Line Chart | $0 - Y_{\max}$ s | Post-warmup queue duration trend. |
| **Vehicles Served** | `throughput` | Cumulative Area Chart | $0 - Y_{\max}$ veh | Dual shaded area fills showing cumulative throughput. |
| **Throughput Rate** | `throughputRate` | Live Line Chart | $0 - Y_{\max}$ veh/min | Rolling 60s exit rate. |
| **Current Mean Speed** | `averageTravelSpeed` | Live Line Chart | $0 - 15$ m/s | Instantaneous speed with $0.5\text{ m/s}$ wait reference line. |
| **Planning Time Index** | `travelTimeReliability` | KPI + Trend Chart | Ratio | Reference line at $1.00$; warning tag when $n < 20$. |

### 4.3 Traffic Flow & Queues

| Metric | Backend Key | Visual Type | Key Characteristics |
| :--- | :--- | :--- | :--- |
| **Current Queues (N, S, E, W)** | `currentQueueLengths` | 4-Way Approach Cross | Directional real-time horizontal bars for North, South, East, West approaches comparing Signal vs Roundabout. |
| **Directional Fairness Index**| `directionalFairnessIndex`| Jain's Arc Gauge | Semicircular dial calibrated from $0.25$ (extreme bias) to $1.00$ (perfect equity). |
| **Average Queue Length** | `averageQueueLength` | Paired Stat Item | Time-averaged queue per approach (veh). |
| **Maximum Queue Length** | `maxQueueLength` | Paired Stat Item | Largest queue observed on any approach (veh). |
| **Active Average Queue** | `activeAverageQueueLength` | Paired Stat Item | Mean total queue over ticks where any queue was present. |
| **Stops per Vehicle** | `averageStopsPerVehicle` | Paired Stat Item | Mean full stops per exited vehicle. |
| **Total Stops** | `totalStops` | Paired Stat Item | Total stops count for post-warmup vehicles. |
| **Time Congested** | `congestionRecoveryTime` | Duration Item | Simulated seconds with $> 5$ vehicles queued. |
| **Queue Stability Index** | `queueStabilityIndex` | Stability Badge | Queue CV ($\sigma / \mu$); lower value indicates steadier flow. |

### 4.4 Safety & Surrogate Measures

- **Collisions (`collisionCount`)**:
  - Prominent status card:
    - If count is `0`: Shield icon with green badge *"Zero collisions recorded"*.
    - If count $> 0$: Pulsing red alert card with total distinct overlap events.
  - **Discrete Event Timeline Log**:
    - Chronological log pills recording timestamp ($t$) and control (`Signal` or `Roundabout`) for each debounced event.
- **Minimum Time-to-Collision (`minTTC`)**:
  - Live Recharts line chart with horizontal reference line at `ttcThresholdSeconds` ($1.5\text{ s}$).
  - Observations $\le 1.5\text{ s}$ highlight critical leader-follower proximity.
- **Surrogate Conflict Events (`ttcEventCount`, `minPET`, `petEventCount`)**:
  - Low-TTC events count and sample count.
  - Conflict-point PET for Signal with $5.0\text{ s}$ threshold and clear *"Not applicable to Roundabout"* indicator.
- **Mandatory Disclaimer**:
  - Prominently styled research callout:
    *"Surrogate Safety Measures Notice: Surrogate safety measures (TTC, PET) are exploratory research metrics based on literature defaults. Event counts are surrogate indicators and do not constitute a validated safety ranking between geometries."*

### 4.5 Capacity & Demand

- **Demand vs. Served Balance**:
  - Dual stacked comparison bar showing:
    - Served Vehicles (`throughput`)
    - In-Network Vehicles (`activeVehicleCount`)
    - Total Offered Demand (`totalVehiclesSpawned`)
  - Demand fulfillment rate (%) displayed alongside bars.
- **Service Utilization (`intersectionUtilization`)**:
  - Dual circular SVG progress rings ($0\% - 100\%$) indicating percentage of demand ticks with moving vehicles ($> 0.5\text{ m/s}$).
- **Critical Saturation Volume (`criticalSaturationVolume`)**:
  - Comparative capacity throughput rate in veh/s.
- **Idle Green Opportunity Loss (`idleOpportunityLoss`)**:
  - Signal-only opportunity waste progress bar with tag *"Signal Only"*, showing share of ticks where red approaches were queued while green approaches were empty.
- **Junction Footprint (`spaceFootprintConsumed`)**:
  - Comparative spatial land footprint consumed in $m^2$.

### 4.6 Distribution Spread & Diagnostics

- **Delay Spread Whisker Range**:
  - Spatial horizontal box/whisker visualization displaying:
    - Minimum Delay (left bound)
    - Median Delay (start of IQR box)
    - 95th Percentile Delay (end of IQR box)
    - Maximum Delay (right bound)
    - Average Delay (mean marker dot)
- **Dispersion Parameters**:
  - `delayStdDev`, `queueStdDev`, `speedVarianceIndex`.
- **Master Composite Efficiency Score (`masterEfficiencyScore`)**:
  - Dual score dials (/100) with explanatory footnote regarding fixed backend weighting.

---

## 5. Live History Buffering & State Handling

### 5.1 Rolling Buffer Specification
- **Hook**: `useLiveComparisonHistory(snapshot: DualSnapshot | null)`
- **Buffer Depth**: Up to 200 chronological data points.
- **Sampling Frequency**: $\approx 1\text{ Hz}$ of simulated time ($0.8\text{ s} \le \Delta t$) or tick advances.
- **Reset Invariants**:
  - History buffer is flushed immediately when:
    - `snapshot` becomes `null`
    - Simulation ID changes (`simId !== prevSimId`)
    - Simulated timestamp resets to 0 or rewinds (`t < lastRecordedTime - 1.0`)
    - User clicks Stop / Reset or re-rolls the random seed

### 5.2 Warm-up Masking Invariant
- When simulated time $t < \text{warmupTime}$ (typically $30\text{ s}$):
  - Post-warmup metrics return `null` in history points.
  - Charts display continuous time on X-axis, while lines only plot where valid post-warmup numbers exist (`connectNulls`).
  - Warm-up banner displays active countdown with pulsing amber indicator.

---

## 6. Implementation Architecture & Files

| File | Purpose |
| :--- | :--- |
| `frontend/src/hooks/useLiveComparisonHistory.ts` | Rolling time-series history buffer & collision event detector |
| `frontend/src/components/analytics/VehiclesFlowVisualizer.tsx` | 4-stage pipeline & in-network flow distribution bars |
| `frontend/src/components/analytics/PerformanceCharts.tsx` | Live Recharts line and cumulative area performance charts |
| `frontend/src/components/analytics/TrafficFlowVisualizer.tsx` | 4-way approach queue cross & Jain's fairness arc dials |
| `frontend/src/components/analytics/SafetyTimelineVisualizer.tsx` | Collision counter, event timeline & live TTC threshold trend |
| `frontend/src/components/analytics/CapacityDemandVisualizer.tsx` | Demand vs served balance bar, utilization rings & idle loss |
| `frontend/src/components/analytics/DistributionDiagnosticsVisualizer.tsx`| Delay whisker spread range & composite score dials |
| `frontend/src/components/ComparativeDashboard.tsx` | Integrated scannable side panel & command-center modal |
| `frontend/src/components/ComparativeDashboard.css` | Stitch visual system styles, dark/light themes, animations |
