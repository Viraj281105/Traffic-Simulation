# UrbanFlow: AI-Powered Microscopic Traffic Simulation Platform

A comprehensive technical and feature reference for developers, engineers, and AI agents.

---

## 1. Problem Statement & Core Objective

* **Urban Congestion & Infrastructure Decision Bottlenecks**: Civil engineers, municipal planners, and traffic researchers often lack fast, accessible, microscopic simulation tools to compare junction designs (e.g., fixed-time signals, adaptive signals, modern roundabouts, metered entries) under localized conditions (heterogeneous traffic mixes, high two-wheeler volumes, and unstructured lane filtering).
* **The UrbanFlow Solution**: A deterministic, browser-first microscopic simulation and research platform featuring synchronous dual lockstep simulations, automated statistical validation, custom junction geometry design, persistent experiment suites, AWS Cognito authentication, and an integrated AI Traffic Copilot.

---

## 2. Technology Stack & Architectural Connections

* **Backend Engine**:
  * **Framework**: Python 3.11 with FastAPI (async ASGI framework).
  * **Microscopic Simulation Core**: Discrete-time kinematics utilizing the **Intelligent Driver Model (IDM)**, MOBIL lane changing, stochastic driver behavior, and entry conflict-point resolution.
  * **Real-time Telemetry**: WebSockets (`/ws/simulation/single`, `/ws/simulation/dual`) streaming 10 Hz `LiveSnapshot` packets (vehicle speeds, delays, bounding boxes, queues, controller phase states).
  * **Persistence**: SQLite with WAL mode (`simulation.db`) via custom thread-safe DAOs for suites, runs, sweeps, and calibration data.
  * **Multiprocessing**: Dedicated worker pool for heavy Monte Carlo validation studies and volume sweeps.
* **Frontend Application**:
  * **Framework**: React 18 + TypeScript + Vite.
  * **Visual Canvas Engine**: HTML5 Canvas with sub-pixel vehicle rendering, dynamic approach paths, circulating rings, conflict zones, and signal light indicators.
  * **Analytics & Visualizations**: Recharts integration for time-series delay curves, queue length profiles, speed distribution diagnostics, and safety timelines.
  * **Design & Styling**: Custom vanilla CSS design system featuring glassmorphism tokens, dark/light themes, and responsive overlays.
* **AI & LLM Integration (UrbanFlow Copilot)**:
  * **Inference Provider**: Groq API using `openai/gpt-oss-20b` (configurable via `GROQ_MODEL`).
  * **Security**: Backend-proxied architecture. API keys are stored solely in `backend/.env` (gitignored). The client interacts only with authenticated `/api/ai/*` endpoints.
  * **Resilience**: Deterministic fallback engine (`src/ai/fallback.py`) ensures full functionality even without an API key or when offline.
* **Authentication & Access Control**:
  * **AWS Cognito**: User Pool + App Client integration for secure user sign-in, token refresh, and admin role checking via `ADMIN_EMAILS`.
  * **Dev Bypass Mode**: Local developer authentication bypass for zero-friction local development.

---

## 3. Containerization, Deployment & Networking

* **Container Architecture**:
  * Multi-stage Docker builds separating production assets from dev tools.
  * Backend container runs Python with Uvicorn and multiprocessing study workers.
  * Frontend container serves the production bundle via an unprivileged Nginx Alpine reverse proxy.
* **Nginx Reverse Proxying**:
  * Nginx listens on internal port `8080` and proxies `/api/`, `/ws/`, and `/health` requests directly to `backend:8000`.
* **Orchestration**:
  * `docker-compose.yml` (Production): Single entry point mapped to Host `80` and `3000`.
  * `docker-compose.dev.yml` (Development): Volume bind-mounts for frontend Vite hot-reload (`5173`) and backend Uvicorn reload (`8000`).
* **PowerShell Orchestrator (`start.ps1`)**:
  * Automates environment variable validation, port collision detection, container lifecycle management, healthcheck polling, smoke testing, and persistent database volume preservation.

---

## 4. Complete Feature Catalog (What Has Been Implemented)

### A. Dual Lockstep Comparative Simulation (`/app/comparative`)
* **Synchronous Side-by-Side Execution**: Fixed-time signal and roundabout run in parallel on identical random seeds, vehicle generation streams, and driver profiles.
* **Interactive Playback**: Play, pause, reset, and variable speeds (1x, 2x, 4x) with real-time synchronized telemetry.
* **Full Comparison Dialog**:
  * **Visual Analytics Tab**: Vehicles in network/waiting distribution, speed profiles, capacity/demand visualizer, and distribution spread diagnostics.
  * **Data Table Tab**: Detailed side-by-side metric tables and differential deltas.
  * **AI Insights & Q&A Tab**: Automated executive summary and interactive conversational Q&A comparing both designs.
  * **User-Weighted Scoring**: Customizable weights across Delay, Queue Length, Throughput, and Directional Fairness producing normalized comparison scores.
  * **CSV Export**: One-click download of all comparative metrics.

### B. Single Intersection Simulators (`Signal on its own` & `Roundabout on its own`)
* **Signal Simulation**: Models fixed-time and adaptive actuated controllers, per-approach queue lengths, and green-time allocation.
* **Roundabout Simulation**: Models circular circulating capacity, critical gap acceptance (2.0–6.0 s), follow-up times (1.0–3.5 s), and metered entry options.
* **Live Metrics Sidebar**: Real-time breakdown of vehicle states, queue bars, stop-line telemetry, and connection status.

### C. UrbanFlow AI Copilot (Implemented in Single & Comparative Views)
* **Single-Run Copilot (`AICopilotPanel`)**:
  * Accessible from the Metrics Sidebar header via a clean `AI Copilot` button.
  * **Summary**: Structured analysis covering average delay, throughput, queue accumulation, and fairness.
  * **Ask (Conversational Q&A)**: Grounded multi-turn chat answering questions using active simulation metrics.
  * **Natural Language Config Patching**: Translates plain English instructions (e.g., *"simulate heavy Pune peak-hour traffic with aggressive drivers"*) into validated configuration diffs, displays before/after parameter previews, and requires explicit user confirmation before applying.
* **Comparative AI Analytics (`ComparativeAIInsights`)**:
  * Integrated as **AI Insights & Q&A** in the **Signal vs Roundabout Full Comparison** dialog.
  * **Automatic Synthesis**: Generates comparison summaries and takeaways as soon as simulation metrics are collected.
  * **Delta Telemetry Analysis**: Compares throughput, delay, queue bottlenecks, and safety trade-offs between both junctions.
  * **Interactive Q&A Analyst**: Pre-configured query chips and interactive chat bar for deep-dive comparative engineering questions.

### D. "Your Own Junction" Builder & Custom Geometry (`JunctionStudyPage`)
* **Interactive Intersection Designer**: Build custom intersections by configuring approach arm counts, lane counts per direction (North, South, East, West), lane widths (2.5–4.8 m), turn lanes, and crosswalks.
* **Comparative Geometry Evaluation**: Test custom layouts against signals and roundabouts with matched traffic demand.

### E. Research Lab & Scientific Studies (`ResearchHub`)
* **Three-Way Study (`ThreeWayStudyPage`)**: Comprehensive side-by-side evaluation of Fixed-Time Signal, Adaptive Actuated Signal, and Modern Roundabout under matched demand seeds.
* **Statistical Validation Suite (`ValidationDashboard`)**:
  * Monte Carlo batch simulation framework running multiple random seeds per demand level.
  * Formal statistical tests (paired t-tests, confidence intervals, p-values, box-plots) to verify whether observed performance differences are statistically significant.
* **Traffic-Level Volume Sweep (`VolumeAnalysisDashboard`)**:
  * Automated parametric sweeps across demand volumes (e.g., from 0.1 to 1.2 veh/s).
  * Generates capacity curves, delay thresholds, and identifies exact tipping points where roundabouts outperform signals and vice versa.

### F. Scenario Planning & Experiment Suites (`PlannerPage` / `ExperimentPage`)
* **Scenario Matrix Designer**: Build multi-scenario test suites varying vehicle mix, arrival rates, and signal timing parameters.
* **Batch Execution**: Run suites in the background and view aggregate comparative matrices.
* **Experiment Loading & Replay**: Re-open past saved suites and experiments directly from SQLite without re-running simulations.

### G. Saved Runs, History & Auditability (`HistoryDashboard` / `RunPage`)
* **Saved Run Repository**: Persistent storage of simulation runs with full configuration snapshots, random seeds, and Git commit hashes for 100% reproducibility.
* **Replay Engine**: Reload and inspect past simulation runs and metric curves with zero divergence.
* **Tagging & Filtering**: Organize saved runs by junction geometry, date, scenario name, and tags.

### H. Authentication, User Profiles & Admin Management
* **AWS Cognito Authentication**: User registration, sign-in, token validation, and secure session management.
* **User Profile Chip**: Header display with avatar, user name, email, and logout.
* **Admin Panel (`AdminPanel`)**: Restricted dashboard for authorized administrators (configured via `ADMIN_EMAILS`) to manage system configurations, monitor activity, and inspect database volumes.

### I. Multi-Junction Arterial Networks & Map Viewer (`/app/network`)
* **Arterial Grid Engine (`networks/network_sim.py`)**: Mesoscopic vehicle handoff with link storage caps, speed limits, and queue spillback propagation across 9, 12, 36, and 100+ junction topologies.
* **MapLibre GL & Canvas Network Map**: Interactive multi-junction network visualizer rendering nodes, directed links, lane configurations, and real-time link occupancy.
* **Congestion Heatmap & Bottleneck Tracing**: Step-by-link space-time heatmaps identifying congestion onset points, propagation velocity, and spillback chains.
* **Network Format Ingestion**: Direct parsers for OpenStreetMap XML/Overpass JSON and SUMO `.net.xml` network topologies.

### J. Network-Scale Optimization & Recalibration (G-CAL Gate)
* **Sensor Count Ingestion**: CSV sensor time-series loader aggregating interval counts into vehicle-per-hour link flows.
* **Error Metrics**: Real-time computation of GEH statistics ($GEH < 5$ for $\ge 85\%$ of links), RMSE, and MAPE.
* **Continuous Recalibration**: Warm-start Nelder-Mead/Powell optimization adapting baseline demand multipliers upon detector drift.

### K. Multi-Junction Reinforcement Learning (MARL)
* **Gymnasium Signal Environment**: Multi-agent environment controlling coordinated signals with queue and delay reduction rewards.
* **Comparative Evaluation**: Automated benchmarking against Fixed-Time and Max-Pressure baselines with paired Student-$t$ confidence intervals.

### L. Digital Twin Replay & What-If Analysis
* **Observation Replay**: High-fidelity replay of recorded link sensor feeds against simulated predictions.
* **Interactive What-If Branching**: Pause replay at arbitrary timestamps, inject lane closures or signal overrides, and simulate counterfactual traffic futures.

### M. Dynamic Incidents, Road Closures, Weather & Resilience (`/app/resilience`)
* **Disruption Injection**: On-demand simulation of crashes, stalled vehicles, lane closures, and work zones.
* **Adverse Weather Modifiers**: Friction reduction (wet/ice pavement) and visibility degradation altering driver reaction times and spacing.
* **Resilience Scoring**: Automated calculation of Time-to-Recovery ($T_{\text{rec}}$) and Resilience Index ($R \in [0, 1]$).

### N. Emergency Priority Preemption & Transit Signal Priority (TSP)
* **Emergency Preemption**: Emergency vehicle siren detection triggering instantaneous green-wave signal clearance.
* **Autonomous Yielding**: Surrounding vehicles dynamically pull over to clear center emergency corridors.
* **Bus Transit Priority**: Conditional green extension and early green recall for delayed public transit buses.

### O. V2X Connected Vehicle Telematics
* **MQTT Telematics Bus**: Real-time Basic Safety Message (BSM) and SPaT broadcasting over in-process and external MQTT brokers.
* **Network Impairment Simulation**: Evaluates packet loss (0–20%) and transmission latency (10–500 ms) on cooperative maneuvers.

### P. Multi-Tenant Enterprise Platform & RBAC (`/api/v2/tenancy`)
* **OIDC & Role-Based Access Control**: Strict multi-tenant isolation supporting `admin`, `analyst`, `viewer`, and `service` roles.
* **Tenant Quotas & Rate Limits**: Dual-level token bucket rate-limiting and daily/concurrent run quotas.

### Q. Cloud Platform, Terraform Staging & Background Workers
* **Terraform AWS Staging**: Complete Infrastructure-as-Code modules for VPC, EKS, RDS PostgreSQL, S3, Secrets Manager, and SQS job queues.
* **Asynchronous SQS Worker**: Decoupled worker process consuming batch simulation jobs with automatic DLQ redrive and spot-instance auto-scaling via KEDA.

### R. Enterprise SDKs & Open Specifications
* **Python SDK (`sdk/python/`)**: Type-safe client wrapping all UrbanFlow APIs (simulation, networks, Copilot, stress, tenancy).
* **TypeScript SDK**: Auto-generated typed client from OpenAPI v3 snapshots (`scripts/generate_ts_client.py`).

---

## 5. Software Results & Performance Benchmarks

* **Telemetry Latency**: 10 Hz continuous WebSocket delivery with <15 ms frame processing overhead.
* **100% Determinism**: Complete reproducibility on identical seeds and configurations verified by property tests.
* **Network Simulation Throughput**:
  * **12-Junction Arterial Grid (900 s sim):** Runs in **0.0316 s** wall time (28,500 simulated seconds per wall second).
  * **100-Junction Grid (440 links, 900 s sim):** Runs in **0.2522 s** wall time.
* **AI Inference Speed**: 300–600 ms response times via Groq inference with 100% deterministic fallback.
* **Automated Test Coverage**:
  * 37 backend packages fully covered by pytest test suites.
  * 18 frontend views fully validated with Vitest unit tests and contract fixtures.

---

## 6. Planned Phase 7 Scope (V5.5 – V6.1 Showcase)

* **Vehicle Platooning & CACC (`backend/src/platoon/`):** Cooperative Adaptive Cruise Control with string-stable gap regulation, platoon formation, splitting, and aerodynamic fuel reduction models.
* **Autonomous Intersection Management (AIM, `backend/src/aim/`):** Spatio-temporal reservation grid for signal-free autonomous vehicle coordination with formal zero-collision guarantees (Release Gate G-AIM).
* **Enterprise Governance & Merkle Audit Trail (`backend/src/governance/`):** RFC 6962 SHA-256 hash-chained immutable audit ledger for configuration approvals and shadow-mode validation.
* **Per-Run Cost Allocation (`backend/src/costing/`):** Automated per-study dollar cost tracking against AWS spot/on-demand pricing models.
* **Physical Signal Head Hardware Bridge (`hardware/`, `backend/src/hardware_bridge/`):** 100 ms MQTT bridge connecting simulation states to physical Raspberry Pi / ESP32 LED signal heads.
