# UrbanFlow: Complete Architectural & Feature Specification Document

---

## 1. Executive Summary & Problem Statement

Urban traffic intersections are the primary bottlenecks in modern transportation networks, responsible for over 40% of urban delays, excess fuel consumption, and vehicle-to-vehicle conflicts. Traffic engineers and municipal planners continually struggle with a critical trade-off: **Fixed-Time or Adaptive Traffic Signals vs. Modern Roundabouts**.

Traditional commercial traffic simulators (e.g., VISSIM, Aimsun, Synchro) present severe limitations:
- **High Licensing Costs**: Often exceed $5,000–$15,000 per seat annually.
- **Steep Learning Curves**: Require weeks of specialized training.
- **Rigid Assumptions**: Calibrated primarily for Western, lane-disciplined, homogeneous car traffic, failing to model heterogeneous vehicle mixes (auto-rickshaws, high-density two-wheelers, buses) and unstructured filtering common in developing cities (e.g., Pune, Mumbai, Bangalore).
- **Lack of Rapid Comparative Prototyping**: Running identical matched-seed comparisons across different junction designs requires complex multi-file setups.

**UrbanFlow** addresses this by providing an open-access, browser-native microscopic traffic simulation, statistical validation, and AI-assisted design platform. It enables engineers to prototype, simulate in lockstep dual view, perform Monte Carlo uncertainty validation, conduct automated traffic volume sweeps, and interact with an integrated **AI Traffic Copilot**.

---

## 2. Hardware & Software Requirements & Cost/Pricing Breakdown

### 2.1 Hardware Requirements

#### A. Development & Local Host Workstation
| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **CPU** | 4-Core x86_64 / ARM64 (e.g. Intel Core i5 8th Gen, Ryzen 5, Apple M1) | 8-Core+ (e.g. Intel Core i7/i9, Ryzen 7/9, Apple M2/M3) for parallel Monte Carlo sweeps |
| **RAM** | 8 GB DDR4 | 16 GB – 32 GB DDR4/DDR5 |
| **Storage** | 10 GB available SSD space | 25 GB+ NVMe SSD (fast Docker caching and SQLite I/O) |
| **GPU** | Integrated Graphics (Intel UHD 620 / Radeon Vega) | Discrete GPU or modern integrated GPU with WebGL2 / 60 Hz Canvas support |
| **OS** | Windows 10/11 (WSL2), macOS 12+, Ubuntu 20.04+ | Windows 11 with WSL2 (Docker Desktop) or Ubuntu 22.04 LTS |

#### B. Cloud Production Deployment Server (Single VM / Container Host)
| Tier | Cloud Provider Specs | Target Load |
|---|---|---|
| **Minimal / Proof of Concept** | AWS EC2 `t3.medium` (2 vCPU, 4 GB RAM) | 5–10 concurrent simulation streams |
| **Production Scale** | AWS EC2 `c6i.xlarge` (4 vCPU, 8 GB RAM, Compute Optimized) | 50+ concurrent simulation streams with background study workers |

---

### 2.2 Software Stack & Services Pricing Breakdown

| Layer / Technology | Component | License / Pricing Tier | Estimated Monthly Cost |
|---|---|---|---|
| **Simulation & Backend** | Python 3.11, FastAPI, Uvicorn, SQLite (WAL) | Open Source (MIT / Apache 2.0) | **$0.00** |
| **Frontend Platform** | React 18, TypeScript, Vite, HTML5 Canvas, Recharts | Open Source (MIT) | **$0.00** |
| **Containerization & Web Server** | Docker Engine, Docker Compose, Nginx Alpine | Open Source (GPL / BSD) | **$0.00** |
| **AI Inference Engine** | Groq Cloud API (`openai/gpt-oss-20b`) | **Free Tier**: 30 RPM, ~200k tokens/day.<br>**Paid Tier** (optional): ~$0.075 / 1M input tokens, ~$0.30 / 1M output tokens | **$0.00** (Free tier)<br>*(~$5–$15/month for heavy commercial scale)* |
| **Authentication & IAM** | AWS Cognito User Pool | **Free Tier**: Up to 50,000 MAUs (Monthly Active Users).<br>Beyond 50k: $0.0055 per MAU | **$0.00** (Within free tier) |
| **Cloud Hosting (Optional)** | AWS EC2 `t3.medium` + EBS 30 GB SSD | On-Demand: ~$0.0416/hr | **~$30.00 – $35.00 / month** |
| **Local Deployment** | Self-hosted via Docker Engine | Local Workstation Execution | **$0.00 / month** |

---

## 3. High-Level Architecture & Connectivity

```
                     ┌──────────────────────────────────────────────────────────────┐
                     │                         CLIENT BROWSER                       │
                     │  ┌────────────────────────────────────────────────────────┐  │
                     │  │ React 18 + TypeScript SPA (HTML5 Canvas Engine)         │  │
                     │  │ - Comparative Lockstep Dual View  - Volume Analysis    │  │
                     │  │ - Single Signal / Roundabout View - Validation Lab     │  │
                     │  │ - Custom Junction Builder         - Scenario Planner   │  │
                     │  │ - AI Copilot Sidebar & Modal      - Saved History      │  │
                     │  └───────────────┬──────────────────────────▲─────────────┘  │
                     └──────────────────┼──────────────────────────┼────────────────┘
                                        │ HTTP / WS                │ Telemetry Snapshots
                                        ▼                          │ (10 Hz JSON Streams)
                     ┌─────────────────────────────────────────────┴────────────────┐
                     │                    NGINX REVERSE PROXY                       │
                     │               (Port 80/3000 -> Internal 8080)                │
                     │  - Serves static Vite bundle (/app, /app/comparative, etc.)  │
                     │  - Proxies /api/ and /health to Backend                     │
                     │  - Proxies /ws/ with WebSocket upgrade headers               │
                     └──────────────────┬──────────────────────────▲────────────────┘
                                        │ ASGI Proxy               │ WebSocket Frames
                                        ▼                          │
┌──────────────────────────────────────────────────────────────────┴────────────────────────────────┐
│                               FASTAPI BACKEND APPLICATION CONTAINER                               │
│                                                                                                   │
│  ┌───────────────────────────────┐     ┌───────────────────────────────────────────────────────┐  │
│  │         API ROUTERS           │     │               MICROSCOPIC SIMULATION ENGINE           │  │
│  │ - /api/simulations            │     │ - Intelligent Driver Model (IDM) & Kinematics         │  │
│  │ - /api/study (Monte Carlo)    │     │ - MOBIL Lane Changing & Lateral Creep                 │  │
│  │ - /api/ai (Copilot Proxies)   │     │ - Circular Conflict Gap Acceptance Engine             │  │
│  │ - /api/replays & history      │     │ - Actuated / Adaptive & Fixed-Time Controllers        │  │
│  └───────────────┬───────────────┘     └───────────────────────────┬───────────────────────────┘  │
│                  │                                                 │                              │
│                  ▼                                                 ▼                              │
│  ┌───────────────────────────────┐     ┌───────────────────────────────────────────────────────┐  │
│  │      AI COPILOT SERVICE       │     │               MULTICORE WORKER POOL                   │  │
│  │ - Groq Cloud API Client       │     │ - Parallel Monte Carlo Seeds                          │  │
│  │ - Rule-Based Fallback Engine  │     │ - Volume Demand Parametric Sweeps                     │  │
│  │ - Pydantic JSON Validators    │     │ - Hypothesis Testing & Paired t-tests                 │  │
│  └───────────────┬───────────────┘     └───────────────────────────┬───────────────────────────┘  │
│                  │                                                 │                              │
│                  ▼                                                 ▼                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                     SQLITE DATABASE WITH WAL MODE (simulation.db)                           │  │
│  │ - Saved Simulation Runs  - Scenario Suites  - Volume Sweeps  - User Configurations           │  │
│  └─────────────────────────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                    │ Outbound HTTPS API
                                                    ▼
                                     ┌─────────────────────────────┐
                                     │       GROQ CLOUD API        │
                                     │    (openai/gpt-oss-20b)     │
                                     └─────────────────────────────┘
```

---

## 4. Detailed Feature & Page-by-Page Specification

### 4.1 Comparative Dual Simulation (`/app/comparative`)
* **Purpose**: The primary benchmark view of the platform. Executes a fixed-time signalized junction and a modern roundabout side-by-side in exact lockstep.
* **Key Mechanics**:
  - **Identical Random Seeds**: Every vehicle arrival, headway, vehicle type, and reaction time is mirrored across both simulations to guarantee scientific fairness.
  - **Synchronized Playback**: Play, Pause, Reset, and variable speed toggles (1x, 2x, 4x) operating synchronously over dual WebSockets.
  - **Live Guide**: Explains warm-up duration (default 30 s) where statistics are excluded to prevent initial network-filling bias.
* **Full Comparison Modal (Three Integrated Views)**:
  1. **Visual Analytics**:
     - *In-Network & Pipeline Flow*: Active vehicles, waiting counts (<0.5 m/s), circulating vehicles, and completed trips.
     - *State Distribution Horizontal Bars*: Ratio of vehicles waiting vs. circulating vs. cruising.
     - *Safety Timeline Visualizer*: Records near-misses, vehicle overlaps, and critical decelerations over time.
     - *Capacity & Demand Visualizer*: Real-time inflow vs. design discharge saturation.
     - *Distribution Diagnostics*: Recharts box plots showing p50, p85, and p95 delay spreads.
  2. **Data Table**: Tabular matrix of all 18+ metrics with delta differences (Roundabout minus Signal).
  3. **AI Insights & Q&A**:
     - *Automatic Executive Takeaway*: Generates high-level synthesis automatically upon data availability.
     - *Key Highlights & Vulnerabilities*: Highlights delays, queue clearances, and directional fairness.
     - *Conversational Traffic Analyst*: Interactive Q&A bar with suggested chips to ask follow-up questions.
  4. **Multi-Criteria User-Weighted Scoring**: Allows users to configure relative importance weights (e.g. 40% Delay, 30% Queue, 20% Throughput, 10% Fairness) to compute an overall winning index.

---

### 4.2 Signal on its Own (`/app/signal`)
* **Purpose**: Focused engineering analysis of a signalized 4-leg junction.
* **Capabilities**:
  - **Controller Modes**: Switch between **Fixed-Time Signal** (preset split green times) and **Adaptive Actuated Signal** (dynamically extends greens based on detected approach queues).
  - **Phase Telemetry**: Displays current active phase (North-South vs. East-West), elapsed green countdown, yellow intervals, and all-red clearance times.
  - **Queue Tracking**: Visual approach queues on canvas with stop-line sensor indicators.
  - **Integrated AI Copilot**: Accessible via the sidebar button to summarize metrics, query behavior, or configure signal parameters.

---

### 4.3 Roundabout on its Own (`/app/roundabout`)
* **Purpose**: Detailed operational analysis of a modern single-lane or multi-lane roundabout.
* **Capabilities**:
  - **Gap Acceptance Physics**: Real-time modeling of driver critical gap ($t_c \in [2.0, 6.0]$ s) and follow-up headway ($t_f \in [1.0, 3.5]$ s).
  - **Circulating Ring Tracking**: Telemetry showing circulating vehicle count, yielding vehicle count, and entry conflict statuses.
  - **Metered Entry Control**: Optional metering signal on dominant approaches to break circulating platoons during peak asymmetry.
  - **Integrated AI Copilot**: Instant natural-language adjustment of gap acceptance, circulating diameter, or entry flows.

---

### 4.4 Your Own Junction / Custom Geometry Studio (`/app/junction`)
* **Purpose**: Allows civil engineers to break away from pre-configured 4-leg templates and build bespoke geometries.
* **Configurable Geometry Parameters**:
  - Number of approaches (3-leg T-junction, 4-leg cross, or custom arm orientations).
  - Lane count per approach arm (1 to 3 lanes).
  - Lane width adjustments (2.5 m to 4.8 m, matching IRC and AASHTO road design standards).
  - Dedicated turning lanes (exclusive left-turn slips or right-turn pockets).
  - Pedestrian crosswalk activations and stop-line setbacks.
* **Simulation Verification**: Instant execution of both signal control and roundabout rules on the custom geometry to evaluate operational feasibility.

---

### 4.5 Three-Way Study (`/app/three-way`)
* **Purpose**: Rigorous simultaneous benchmark of the three dominant junction control philosophies:
  1. Fixed-Time Signal
  2. Adaptive / Actuated Actuator Signal
  3. Modern Roundabout
* **Methodology**: Executes all three variants under matched pseudo-random arrival seeds, plotting real-time comparative curves of delay, stop frequency, and throughput saturation to evaluate which control strategy excels under identical demand.

---

### 4.6 Statistical Validation Lab (`/app/validation`)
* **Purpose**: Scientific verification that differences between junction controls are statistically valid rather than artifacts of a single lucky random seed.
* **Capabilities**:
  - **Monte Carlo Batch Execution**: Dispatches multi-seed simulation batches across background worker processes.
  - **Hypothesis Testing**: Computes paired Student's t-tests, standard deviation, variance, and p-values.
  - **Confidence Intervals**: 95% confidence intervals on mean delay and maximum queue lengths.
  - **Distribution Spread Charts**: Visual violin and box plots showing performance variance under stochastic traffic flow.

---

### 4.7 Traffic-Level Volume Sweep (`/app/volume`)
* **Purpose**: Identifies the operational breaking points and capacity thresholds of junction designs.
* **Methodology**:
  - Automatically sweeps vehicle demand from low volume (0.1 veh/s ≈ 360 veh/h) to extreme saturation (1.2 veh/s ≈ 4,320 veh/h) in incremental volume steps.
  - Generates **Volume-Delay Curves** and **Throughput-Saturation Curves**.
  - Highlights the exact **Tipping Point** (the critical volume where roundabout yield delays cross above signal cycle delays).

---

### 4.8 Scenario Planning & Experiment Suites (`/app/planner` & `/app/experiments/*`)
* **Purpose**: Large-scale civil planning test-bed for running and archiving multi-scenario studies.
* **Features**:
  - **Scenario Matrix Generation**: Configure matrices varying vehicle mix (e.g. 80% cars vs. 60% motorcycles), lane width, and signal timing across multiple permutations.
  - **Background Batch Runner**: Executes entire test suites asynchronously.
  - **SQLite Experiment Persistence**: Save completed suites with custom descriptions, inspect past results, and load stored experiments instantly without re-simulating.

---

### 4.9 Saved Runs & Reproducibility Repository (`/app/history` & `/app/runs/*`)
* **Purpose**: Complete audit trail and reproducibility archive.
* **Capabilities**:
  - Every saved run stores the exact simulation parameters, random seed, duration, metrics snapshot, and the Git commit hash of the simulation engine.
  - **Deterministic Replay Engine**: Replays any past simulation run in the browser with 100% fidelity.
  - **Run Comparison (`/app/compare`)**: Select up to 6 historical runs to display side-by-side comparative metric tables and charts.

---

### 4.10 Admin Dashboard (`/app/admin`)
* **Purpose**: System administration, infrastructure monitoring, and security management.
* **Access Control**: Strictly restricted to emails listed in the `ADMIN_EMAILS` environment configuration.
* **Capabilities**:
  - Real-time container resource telemetry (memory usage, worker health).
  - Database management: Inspect SQLite table sizes, saved run counts, and run database VACUUM / optimization tasks.
  - User activity inspection and Cognito session audit logs.

---

### 4.11 Authentication & User Management (AWS Cognito)
* **User Authentication**: Secure Sign-Up, Sign-In, and Forgot Password workflows via AWS Cognito User Pools.
* **User Session Chip**: Persistent user session displayed in the header with avatar, name, and email.
* **Saved Run Ownership**: Associate simulation runs and scenario planning experiments with individual user profiles.
* **Dev Bypass Mode**: Built-in `DEV_AUTH_BYPASS` allows offline and zero-configuration local development.

---

### 4.12 UrbanFlow AI Copilot (Complete Architecture)
* **Single-Run Copilot (`AICopilotPanel`)**:
  - Clean slide-in glassmorphism drawer replacing the right sidebar when triggered.
  - **Summary**: Concise bullet points breaking down delay, throughput, queue buildup, and fairness.
  - **Ask**: Multi-turn chat grounded in active metrics.
  - **Natural Language Config Patching**: Parses instructions like *"simulate heavy Pune peak-hour traffic with aggressive drivers"* into validated parameter diffs, presenting a before/after preview table requiring user confirmation before applying.
* **Comparative AI Analytics (`ComparativeAIInsights`)**:
  - Dedicated tab inside the Full Comparison modal.
  - Automatically triggers when comparative metrics are recorded.
  - Synthesizes differential performance (e.g. roundabout throughput advantage vs. signal queue balance) and offers an interactive analytical query interface.
* **Robust Fail-Safe**: When Groq API keys are absent or offline, an intelligent deterministic fallback engine (`src/ai/fallback.py`) handles all summaries, Q&A, and config patches seamlessly without errors.

---

## 5. Software Verification & Quality Assurance

* **Backend Unit & Integration Tests**:
  - Automated pytest suite covering all AI endpoints, schema validation, fallback logic, kinematics, and SQLite DAOs (`pytest tests/api/test_ai.py` 100% passing).
* **Frontend Strict Type Safety**:
  - TypeScript strict mode enforced across all 49+ components and views (`tsc --noEmit` clean).
  - Production Vite bundle builds with zero warnings (`vite build` exit code 0).
* **Deterministic Simulation Engine**:
  - Validated with identical random seeds producing bit-identical vehicle trajectory matrices.
