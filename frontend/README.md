# UrbanFlow Frontend — Interactive Dashboard & Network Visualizer

The presentation and analytical layer for UrbanFlow: a modern **React 19 + TypeScript 5.8** single-page application built with **Vite 8**, rendering microscopic vehicle motion on **HTML5 Canvas** at 60 FPS, multi-junction arterial grids on **MapLibre GL**, and statistical analytics with **Recharts**.

The frontend strictly enforces the architectural boundary: **it never runs physics and never computes a metric**. It renders backend snapshots (~10 Hz stream with client-side Hermite interpolation) and presents metric values computed authoritatively by the backend.

**Core Maintainer:** Khushi Kashyap (User Experience, Canvas Maps, Analytics & UI Architecture)  
**Stack:** React 19 · TypeScript 5.8 · Vite 8 · Tailwind CSS v4 · Framer Motion · MapLibre GL · Recharts · Vitest · axe-core

---

## Technical Documentation Links

| Area | Documentation Link |
| :--- | :--- |
| **Frontend Architecture & Data Flow** | [docs/architecture/03-frontend-architecture.md](../docs/architecture/03-frontend-architecture.md) |
| **Product Journey & User Narrative** | [docs/product/urbanflow-user-narrative.md](../docs/product/urbanflow-user-narrative.md) |
| **Planner Experience Guide** | [docs/product/planner-guide.md](../docs/product/planner-guide.md) |
| **Metric Presentation Rules** | [docs/research/metrics-reference.md](../docs/research/metrics-reference.md) |
| **Frontend Testing & Accessibility** | [docs/testing/README.md](../docs/testing/README.md) |
| **Nginx Reverse Proxy & Static Host** | [docs/deployment/README.md](../docs/deployment/README.md) |

---

## Workspace Layout & Component Architecture

```
frontend/src/
├── main.tsx · App.tsx          # Application entry point, layout shell, view routing router
├── routing.ts                  # Single source of truth for URL paths (mirrored by Nginx & Vite)
├── config.ts                   # Runtime backend URL resolution (VITE_API_URL / VITE_WS_URL)
│
├── landing/                    # Product Landing Page (index.html)
│   ├── App.tsx                 # Hero presentation, interactive canvas teaser, value propositions
│   └── Reveal.tsx              # Scroll-driven reveal animations
│
├── components/                 # UI Component Hierarchy
│   ├── shell/                  # App chrome: Navigation, NavigationHeader, UserMenu, LoginDialog
│   ├── guided/                 # 3-Step Guided Comparison Planner:
│   │   ├── ScenarioSetup.tsx   # Step 1: Geometry, approach lanes, traffic demand, fleet mix
│   │   ├── LiveGuide.tsx       # Step 2: Synchronized dual Canvas maps with playback controls
│   │   ├── ResultsReport.tsx   # Step 3: Comparative findings, delay grades, "Why" explanations
│   │   └── ReliabilityCheck.tsx# Multi-seed consistency verifier (Monte Carlo check)
│   │
│   ├── canvas/ & maps/         # Canvas Visualization Engine:
│   │   ├── IntersectionMap.tsx # Signalized junction renderer (phases, stop lines, vehicles)
│   │   ├── RoundaboutMap.tsx   # Multi-lane roundabout renderer (ring lanes, give-way lines)
│   │   └── snapshotInterpolator.ts # Hermite spline interpolation for smooth 60 FPS motion
│   │
│   ├── scenario/               # Scenario Builder Components:
│   │   ├── LaneArrowEditor.tsx # Approach lane count and allowed turning arrow editor
│   │   ├── ApproachTrafficCard.tsx # Approach demand and turning split configuration
│   │   └── MixEditor.tsx       # Fleet composition distribution sliders (car, SUV, bus, etc.)
│   │
│   ├── analytics/              # Deep-Dive Specialist Charting:
│   │   ├── DelayDistributionChart.tsx # Travel time and delay histogram
│   │   ├── QueueOverTimeChart.tsx     # Queue build-up and dissipation curves
│   │   └── WeightedScoringPanel.tsx   # Multi-criteria stakeholder decision matrix
│   │
│   └── ui/                     # Primitives: buttons, drawers, modals, tooltips, loaders
│
├── netpage/                    # Network Experience Hub (/app/network)
│   ├── NetworkDashboard.tsx    # Multi-junction network control center
│   ├── NetworkToolbar.tsx      # Network preset switcher (Corridor, 3x3 Grid, 12-Junction)
│   └── NetworkKpiRibbon.tsx    # Network-wide KPIs (average network delay, throughput, spillback)
│
├── mapview/                    # MapLibre GL Multi-Junction Spatial Visualizer
│   ├── NetworkMapView.tsx      # Interactive vector map with node-edge junction representations
│   └── offlineTiles.ts         # Bundled offline vector tile fixtures for air-gapped runs
│
├── congestion/                 # Topological Congestion Heatmap
│   ├── CongestionHeatmap.tsx   # Visualizes link spillback, shockwaves, and bottleneck propagation
│   └── CongestionTimeline.tsx  # Interactive scrubbing over network congestion history
│
├── calibration/                # Network Calibration & Agreement View
│   ├── CalibrationReportView.tsx # GEH statistic histograms, scatter plots, RMSE/MAPE summaries
│   └── GehThresholdCard.tsx    # UK DMRB / FHWA calibration compliance status badges
│
├── netrl/                      # Multi-Junction Reinforcement Learning Dashboard
│   ├── RlComparisonDashboard.tsx # Trained PPO/DQN policies vs. Fixed-Time and Max-Pressure
│   └── TrainingConvergenceView.tsx # Reward curves and policy evaluation intervals
│
├── twinview/                   # Digital Twin Dashboard
│   ├── TwinReplayView.tsx      # Synchronized replay of recorded telemetry runs
│   └── WhatIfBranchEditor.tsx  # Interactive branch point selector for hypothetical interventions
│
├── loadtest/                   # Observability & Load-Test Viewer
│   ├── LoadTestDashboard.tsx   # Latest k6 performance reports (p95 latencies, error rates)
│   └── SloComplianceCard.tsx   # Service Level Objective (SLO) status checks
│
├── incidents/ & rescommon/     # Incidents, Disruptions & Weather View
│   ├── IncidentSetupModal.tsx  # Crash injection, lane blockage, and road closure configuration
│   ├── WeatherSelector.tsx     # Rain, snow, dense fog, and icy pavement condition controls
│   └── ResilienceScoreView.tsx # Comparative recovery time and system resilience curves
│
├── services/                   # Typed API & WebSocket Communication Clients
│   ├── api.ts                  # Core REST client (JSON envelopes, error interceptors)
│   ├── websocket.ts            # WebSocket stream client with exponential backoff reconnect
│   ├── liveSession.ts          # Live interactive session handshake and command dispatcher
│   ├── studyJobs.ts            # Async study job polling client
│   ├── v2/planning.ts          # Decision-support planning study API client
│   ├── v3/experiments.ts       # Robustness Lab experiment client
│   └── v3/insights.ts          # Network, RL, and load-test insights client
│
├── metrics/                    # Presentation Catalog & Narrative Rules
│   ├── catalog.ts              # Canonical metric registry (units, precision, groups, tooltips)
│   └── plainLanguage.ts        # HCM Level-of-Service grades, balance bands, causal explanations
│
└── test/                       # Comprehensive Vitest Test Suites
    ├── routing.test.ts         # Enforces exact sync between routing.ts, Nginx, and Vite fallbacks
    ├── components/             # React component unit and integration tests
    └── a11y/                   # axe-core automated accessibility audit tests
```

---

## Dashboard Routing & Navigation Map

Client-side routes are declared in `src/routing.ts` and mirrored by `templates/default.conf.template` (Nginx SPA fallback) and `vite.config.ts`. All views support deep-linking, refresh, and browser history navigation:

| URL Path | View Component | Description |
| :--- | :--- | :--- |
| `/` | Landing Page | Public product narrative, interactive canvas hero, methodology overview. |
| `/app/comparative` | Guided Comparison | 3-step comparison wizard (Scenario $\to$ Lockstep Simulation $\to$ Decision Report). |
| `/app/network` | Network Visualizer | Multi-junction MapLibre GL map, congestion heatmaps, calibration, RL, twin. |
| `/app/planner` | Decision Support | Multi-alternative planning studies and downloadable reports. |
| `/app/experiments/:id`| Robustness Lab | Parameter uncertainty ensemble viewer with bootstrap paired difference intervals. |
| `/app/copilot` | AI Copilot | Natural language experiment builder with schema validation gate. |
| `/app/discovery` | Strategy Discovery | NSGA-II multi-objective strategy search and Pareto frontier exploration. |
| `/app/stress` | Breakpoint Explorer | High-load traffic chaos and operational breakpoint explorer. |
| `/app/history` | Run History | Stored simulation catalog, tags, labels, and bit-identical seed reproduction. |
| `/app/runs/:id` | Run Detail Page | Detailed inspection of individual simulation runs and metrics. |
| `/app/compare` | Multi-Run Compare | Side-by-side comparison of up to 6 historical simulation runs. |
| `/app/research` | Research Lab Hub | Traffic volume sweeps, delay crossover explorer, Monte Carlo validation. |
| `/app/volume` | Volume Sweep | Demand ladder analysis across varying saturation percentages. |
| `/app/validation` | Monte Carlo Studio | Multi-seed statistical significance testing (Welch's t-test, Cohen's d). |
| `/app/three-way` | Control Comparison | Three-way study: Fixed-Time vs. Adaptive Signal vs. Roundabout. |
| `/app/tokens` | Access Tokens | Personal Access Token (PAT) generation and scope management. |
| `/app/admin` | System Admin | User directory and administrative system monitoring. |

---

## Motion Interpolation & Visual Rendering

### 1. Dual Canvas Motion Interpolation
The backend streams vehicle positions at ~10 Hz over WebSockets (`/ws/simulation/dual`). To achieve smooth 60 FPS rendering in the browser, `snapshotInterpolator.ts` maintains a circular buffer of recent frames and computes cubic Hermite spline interpolation:
- Smooth velocity-based vehicle orientation and position transitions.
- Visual state overlays: brake lights, turn indicators, vehicle class color-coding.
- Traffic signal state rendering: animated green/yellow/red signal heads and pedestrian clearance.
- Roundabout give-way line markers and circulating conflict zone indicators.

### 2. MapLibre GL Spatial Network Mapping
The network view integrates MapLibre GL with pre-bundled offline vector tiles, allowing multi-junction corridors and grids (such as the 12-junction arterial network) to be explored interactively:
- Node-edge spatial layout representing junctions and arterial connecting links.
- Real-time link color coding reflecting space-mean speeds and volume-to-capacity ($V/C$) ratios.
- Link congestion propagation animations showing upstream spillback evolution.

---

## Local Development Workflow

### Prerequisites
- Node.js 24 or newer (Node 26 LTS recommended)
- npm package manager

### Getting Started
```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

The application will be accessible at `http://localhost:5173`. In development mode, Vite proxies `/api` and `/ws` requests to `http://localhost:8000` automatically.

### Environment Flags (`.env.local`)
- `VITE_API_URL`: Override base backend REST API URL (defaults to current origin).
- `VITE_WS_URL`: Override base WebSocket streaming URL (defaults to current origin).
- `VITE_DEV_AUTH_BYPASS`: Set to `true` (default in dev) to bypass Cognito and sign in automatically as "Local Developer".

---

## Quality Gates & Verification Suite

The frontend implements comprehensive automated testing across unit logic, React components, and accessibility compliance:

```bash
# 1. Run Vitest Unit and Component Test Suites
npm run test

# 2. Strict TypeScript Static Type Checking
npm run type-check

# 3. ESLint Code Analysis
npm run lint

# 4. Prettier Code Formatting Verification
npm run format

# 5. Production Bundle Build & Asset Budget Verification
npm run build
```

---

## Production Containerization

The frontend Dockerfile compiles assets using a multi-stage build and serves them via `nginx-unprivileged` on container port 8080:
- **SPA Fallback:** Known routes in `src/routing.ts` fall back to `/app.html` without flickering; unknown paths render a 404 page.
- **Reverse Proxy:** Proxies `/api/*`, `/ws/*`, and `/health` to the backend service.
- **API Key Injection:** Injects the server-side `BACKEND_API_KEY` header for internal requests.
- **Security Headers:** Strict Content Security Policy (CSP), anti-clickjacking (`X-Frame-Options: SAMEORIGIN`), and MIME-type protection.
