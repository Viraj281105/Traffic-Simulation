# UrbanFlow Backend — Simulation Engine, Network Models & Decision API

A high-performance Python 3.11 **FastAPI** application containing UrbanFlow's microscopic simulation engine (Intelligent Driver Model car-following, MOBIL lane-changing, signal and roundabout controllers, network graph execution), statistical evaluation engines, machine learning environments, persistence layers, REST endpoints, and WebSocket streaming servers.

It is headless: it computes all physics and metrics, serving as the **single source of truth** for all visualizers and decision reports.

**Core Maintainer:** Viraj Jadhao (Simulation Physics, Data & Platform Architecture)  
**Runtime:** Python 3.11 (`>=3.11` in `pyproject.toml`) · FastAPI · Uvicorn · Pydantic v2 · SQLite WAL · DuckDB · PyTorch / Gymnasium · OpenTelemetry

---

## Technical Documentation Links

| Area | Documentation Link |
| :--- | :--- |
| **Backend Layering Architecture** | [docs/architecture/02-backend-architecture.md](../docs/architecture/02-backend-architecture.md) |
| **Microscopic Simulation Methodology** | [docs/simulation/methodology.md](../docs/simulation/methodology.md) |
| **Signalised Roundabout Design** | [docs/simulation/signalised-roundabout.md](../docs/simulation/signalised-roundabout.md) |
| **Complete API & WebSocket Reference** | [docs/api/README.md](../docs/api/README.md) |
| **Network Graph Model (ADR-021)** | [docs/decisions/adr-021-network-graph-model.md](../docs/decisions/adr-021-network-graph-model.md) |
| **Metrics & Physical Invariants** | [docs/research/metrics-reference.md](../docs/research/metrics-reference.md) |
| **Observability, Tracing & SLOs (ADR-022)**| [docs/decisions/adr-022-observability-and-slos.md](../docs/decisions/adr-022-observability-and-slos.md) |
| **Testing & Quality Assurance** | [docs/testing/README.md](../docs/testing/README.md) |

---

## Package Structure & Layer Map

The codebase follows a strict four-layer architecture enforced by architectural boundary tests (`tests/test_architecture.py`). Domain modules import only downwards and never import from delivery, application, or infrastructure layers:

```
backend/src/
├── main.py                  # Composition root: middleware, DB init, exception handlers, router mounting
├── access.py                # Single ownership rule: user resource access and tenant isolation
├── csv_safety.py            # Spreadsheet formula injection sanitization for data exports
│
├── api/                     # Shared Delivery Plumbing Layer
│   ├── auth.py              # Cognito JWT verification (JWKS), dev auth bypass, identity extractors
│   ├── security.py          # API key verification (X-API-Key, Bearer parsing)
│   ├── errors.py            # Standardized JSON error envelope {"error": {code, message, details}}
│   ├── origins.py           # CORS and WebSocket origin verification helpers
│   ├── request_limits.py    # Request body size caps (1 MiB on compute) and compute slot locks
│   ├── tokens_router.py     # Personal Access Token (PAT) management (/api/v3/tokens)
│   └── meta.py              # System metadata endpoints: /health, /api/version, /api/me
│
├── core/                    # Leaf Domain Kernel
│   ├── clock.py             # Simulation clock and discrete-time advancement (Δt)
│   ├── config_models.py     # Pydantic scenario configuration models and versioned driver profiles
│   ├── enums.py             # Domain enumerations (vehicle types, control strategies, statuses)
│   ├── limits.py            # Simulation parameter bounds (duration, rates, lanes, timeStep)
│   ├── provenance.py        # Run provenance stamps (git commit, runtime, timestamp)
│   └── run_manifest.py      # Reproducibility run manifest with SHA-256 config & code hashes
│
├── roads/                   # Spatial Geometry & Road Networks
│   ├── approaches.py        # Compass approach definitions, skew angles, stop-line positions
│   ├── lanes.py             # Explicit lane models, allowed turn arrows, lane widths
│   └── road_network.py      # Spatial graph of approach arms, internal conflict paths, exit lanes
│
├── vehicles/                # Vehicle Physics & Microscopic Dynamics
│   ├── idm.py               # Intelligent Driver Model car-following physics
│   ├── lane_change.py       # MOBIL lane-changing model with shadow-lane occupancy
│   ├── vehicle.py           # Vehicle state representation (position, speed, acceleration, type)
│   ├── vehicle_types.py     # 5 distinct vehicle classes (car, SUV, bus, truck, motorcycle)
│   ├── spawner.py           # Seeded Poisson / uniform vehicle insertion with safety gaps
│   └── router.py            # Turn intent routing, leader assignment, and virtual obstacles
│
├── intersection/            # Conflict Resolution
│   ├── conflict_manager.py  # Critical conflict zone reservations for signals and roundabouts
│   └── predictive_resolver.py # Trajectory conflict detection and deceleration enforcement
│
├── controllers/             # Traffic Control Strategies
│   ├── base.py              # BaseController abstract interface
│   ├── fixed_time_signal.py # Paired-stage fixed-time signal controller with configurable splits
│   ├── adaptive_signal.py   # Actuated adaptive signal controller with stop-line gap-out
│   ├── roundabout.py        # Multi-lane roundabout controller with critical gap acceptance
│   ├── signalised_roundabout.py # Metered-entry signalised roundabout controller (gated entries)
│   ├── signal_detection.py  # Stop-line loop detectors and approach presence sensors
│   └── factory.py           # Strategy instantiation factory and signals state derivation
│
├── strategies/              # Composable Strategy Registry (ADR-014)
│   ├── registry.py          # Strategy descriptor catalog and compatibility validation
│   └── descriptors.py       # Layered strategy schema definitions
│
├── engine/                  # Discrete-Time Simulation Execution
│   ├── simulation_engine.py # Core tick loop, lifecycle transitions, engine thread locks
│   ├── vehicle_pool.py      # Microscopic vehicle collection, spatial stepping, SAT collision audit
│   ├── deadlock_detector.py # Stationary gridlock detection
│   ├── tick_callback.py     # Engine tick observer feeding MetricCollector
│   └── readout.py           # Thread-safe metric extraction under engine lock
│
├── snapshot/                # Telemetry Serialization & Lockstep Orchestration
│   ├── builder.py           # Converts engine state to snapshot contract payload
│   ├── buffer.py            # Circular memory buffer of recent telemetry snapshots
│   └── dual_orchestrator.py # DualSimulationOrchestrator: steps signal & roundabout in lockstep
│
├── metrics/                 # Measurement & Scientific Accounting
│   ├── collector.py         # MetricCollector with warmup exclusion (default 30 s)
│   ├── definitions/         # Delay (mean, median, p95), throughput, queue lengths, stops, fairness
│   ├── emissions.py         # Akçelik instantaneous fuel consumption and CO2 emissions
│   └── safety.py            # Time-to-Collision (TTC) and Post-Encroachment Time (PET)
│
├── scenario/                # Scenario Documents & Cross-Field Validation
│   ├── documents.py         # V1.4 scenario document parser, validator, and compiler
│   └── lane_validation.py   # Cross-field rules (lane arrow consistency, turn constraints)
│
├── live/                    # Live Interactive Dashboard Application Layer
│   ├── sessions.py          # Per-client LiveSession registry (cookie / Cognito subject scoping)
│   ├── dashboard_config.py  # Live settings compilation to engine configuration
│   └── router.py            # Interactive routes (/api/simulation/*) & WebSockets (/ws/simulation/*)
│
├── simulations/             # Versioned Simulation API Layer
│   ├── registry.py          # Managed in-memory simulation registry (up to 50 concurrent)
│   └── router.py            # Lifecycle management (/api/v1/simulations) & stream (/ws/v1/stream)
│
├── study/                   # Single-Junction Batch Studies & Worker Pool
│   ├── runner.py            # Multiprocessing worker pool execution for volume sweeps
│   ├── volume_sweep.py      # Demand ladder sweeps with delay crossover detection
│   ├── validation.py        # Multi-seed Monte Carlo statistical validation
│   └── router.py            # Study endpoints (/api/v1/study/*)
│
├── planning/                # V2.0 Decision-Support Planning Studies
│   ├── service.py           # Multi-alternative study orchestration and background jobs
│   ├── store.py             # Planning study database storage
│   └── router.py            # Endpoints at /api/v2/planning
│
├── experiments/             # V3.0 Robustness Lab & Uncertainty Ensembles
│   ├── service.py           # Parameter uncertainty execution service
│   ├── package.py           # Self-contained .ufpkg portable experiment package import/export
│   ├── store.py             # SQLite / Parquet experiment persistence
│   └── router.py            # Endpoints at /api/v3/experiments
│
├── uncertainty/             # Parameter Uncertainty Sampling & Statistics
│   ├── spec.py              # Multi-factor uncertainty specification
│   ├── sampler.py           # Quasi-random Sobol and Latin Hypercube sampling
│   └── analysis.py          # Wilson score intervals, Welch's t-test, bootstrap paired differences
│
├── copilot/                 # AI Experiment Copilot (V3.0 W5)
│   ├── llm.py               # LLM integration client (Groq / OpenAI API with fallback)
│   ├── proposer.py          # Proposal generator converting natural language to experiment schemas
│   ├── grounded_summary.py  # Evidence-grounded summary validator checking numbers against JSON
│   ├── eval_harness.py      # Question-set evaluation harness with LLM judge
│   └── router.py            # Endpoints at /api/v3/copilot
│
├── discovery/               # AI Strategy Discovery Lab (V3.0 W6)
│   ├── nsga2.py             # Non-dominated Sorting Genetic Algorithm II multi-objective optimizer
│   ├── search.py            # Evolutionary search runner over signal splits, cycles, and offsets
│   └── router.py            # Endpoints at /api/v3/discovery
│
├── stress/                  # Strategy Breakpoint & Traffic Chaos Explorer (V3.0 W8)
│   ├── engine.py            # Stationary and non-stationary demand surge stress runner
│   └── router.py            # Endpoints at /api/v3/stress
│
├── networks/                # Multi-Junction Network Models (V3.9–V4.6 Phase 5)
│   ├── graph.py             # Node-edge directed network graph model (ADR-021)
│   ├── corridor.py          # Two-junction arterial corridor with offset coordination
│   ├── grid.py              # 3x3 (9-junction) and 12-junction arterial grid topologies
│   ├── handoff.py           # Link-to-junction vehicle conservation and handoff logic
│   ├── osm.py               # OpenStreetMap Overpass XML/JSON network importer
│   ├── sumo.py              # SUMO .net.xml network importer and exporter
│   ├── gtfs.py              # General Transit Feed Specification transit line importer
│   └── synchro.py           # Synchro CSV traffic network importer
│
├── netmetrics/              # Network-Wide Metrics & Congestion Analysis
│   ├── metrics.py           # Network delay, throughput, space-mean speed, spillback
│   ├── congestion.py        # Topological link congestion spread analysis
│   └── mapdata.py           # GeoJSON network map data exporter
│
├── calibration/             # Network Count Calibration & Recalibration (V4.1)
│   ├── network_counts.py    # Observed traffic count CSV loader (15-min turning volumes)
│   ├── network_metrics.py   # GEH statistic, RMSE, and MAPE error metrics
│   ├── network_fit.py       # Nelder-Mead optimization fitting demand and speed multipliers
│   ├── network_recalibration.py # Continuous recalibration pipeline with warm-start
│   └── router.py            # Endpoints at /api/v2/calibration
│
├── rl/                      # Multi-Junction Reinforcement Learning (V4.1–V4.4)
│   ├── network_env.py       # Gymnasium environment for multi-junction signal control
│   ├── network_baselines.py # Fixed-time and Max-Pressure baseline policies
│   ├── network_train.py     # PPO and DQN training loop with PyTorch
│   ├── network_eval.py      # Paired-seed evaluation with confidence intervals
│   └── registry.py          # Local model registry for trained policy weights
│
├── observability/           # Distributed Tracing, Metrics & SLOs (ADR-022)
│   ├── tracer.py            # OpenTelemetry distributed tracing integration
│   ├── prom.py              # Prometheus metric collectors (counters, histograms, gauges)
│   ├── slo.py               # SLO definitions, evaluator, and compliance verifier
│   └── prom_router.py       # Metrics exposition endpoint at GET /metrics/prom
│
├── twin/                    # Digital Twin Core (V4.2–V4.5)
│   ├── replay.py            # Telemetry replay adapter over recorded simulation runs
│   ├── compare.py           # Real-time prediction-vs-observation comparison engine
│   └── router.py            # Endpoints at /api/v2/twin
│
├── incidents/               # Incidents, Disruptions & Weather (V4.7–V4.9 Phase 6)
│   ├── engine.py            # Incident execution engine, dynamic closures, Dijkstra rerouting
│   ├── model.py             # Incident specification models (crashes, lane blocks, durations)
│   ├── weather.py           # Weather parameters: rain, dense fog, snow, ice (friction, visibility)
│   ├── resilience.py        # Recovery time calculation and comparative resilience scoring (R)
│   └── router.py            # Endpoints at /api/v2/incidents
│
├── priority/                # Emergency & Transit Priority Control (V5.0–V5.2 Phase 6)
│   ├── controller.py        # Emergency signal pre-emption controller with siren detection
│   ├── phases.py            # Immediate green extensions, yellow/red truncations, clearance
│   ├── yielding.py          # Civilian vehicle yielding and corridor clearance logic
│   ├── comparison.py        # With-vs-without priority comparative performance evaluator
│   ├── audit.py             # Response-time metric tracking and preemption audit logger
│   └── router.py            # Endpoints at /api/v2/priority
│
├── v2x/                     # Connected Vehicles & V2X Messaging (V4.8–V5.2 Phase 6)
│   ├── channel.py           # V2X messaging channel with stochastic latency and packet loss
│   ├── bus.py               # In-process asynchronous publish/subscribe event bus
│   ├── mqtt_bus.py          # External MQTT broker adapter (paho-mqtt)
│   ├── behaviour.py         # Cooperative car-following and multi-vehicle lane changes
│   ├── experiment.py        # Cooperative vs. non-cooperative simulation experiment runner
│   └── router.py            # Endpoints at /api/v2/v2x
│
├── tenancy/                 # Multi-Tenant Platform & Security (V5.0–V5.3 Phase 6)
│   ├── oidc.py              # OIDC JWT token verification and claims extractor
│   ├── roles.py             # Role-Based Access Control (viewer, planner, engineer, admin)
│   ├── scoping.py           # Tenant-scoped database queries and resource isolation
│   ├── limits.py            # Tenant quotas, rate limiting, and token budgets
│   └── router.py            # Endpoints at /api/v2/tenancy
│
├── jobs/                    # Asynchronous Job Queue & Workers (V4.8–V5.5 Phase 6)
│   ├── queue.py             # Abstract job queue interface and in-memory queue
│   ├── sqs.py               # AWS SQS queue adapter with dead-letter queue (DLQ) support
│   ├── worker.py            # Background job worker daemon executing async simulations
│   ├── cost_tags.py         # Cost allocation tagging for background jobs
│   └── router.py            # Endpoints at /api/v2/jobs
│
├── runstore/                # Columnar Parquet Results Lakehouse (Phase 4)
│   ├── store.py             # Parquet storage engine for multi-seed telemetry on disk and S3
│   └── duckdb_queries.py    # Analytical SQL queries over historical runs using DuckDB
│
└── database/                # Persistence & Storage
    ├── db.py                # SQLite connection, WAL mode, foreign keys, additive schema migrations
    ├── dao.py               # Data Access Objects for runs, sweeps, suites, and users
    └── replay_dao.py        # Data Access Object for recorded live session replays
```

---

## Simulation Physics & Numerical Model

### 1. Intelligent Driver Model (IDM) Car-Following
Each vehicle's longitudinal acceleration $\frac{dv}{dt}$ is computed as:
$$\frac{dv}{dt} = a \left[ 1 - \left(\frac{v}{v_0}\right)^\delta - \left(\frac{s^*(v, \Delta v)}{s}\right)^2 \right]$$
where the dynamic desired gap $s^*(v, \Delta v)$ is:
$$s^*(v, \Delta v) = s_0 + \max\left(0, v T + \frac{v \Delta v}{2 \sqrt{a b}}\right)$$

### 2. Vehicle Class Parameters
UrbanFlow models 5 distinct vehicle classes, each with calibrated IDM parameters:
- **Passenger Car:** $a = 2.0\text{ m/s}^2, b = 3.0\text{ m/s}^2, T = 1.2\text{ s}, s_0 = 2.0\text{ m}, L = 4.5\text{ m}$
- **SUV:** $a = 1.8\text{ m/s}^2, b = 2.8\text{ m/s}^2, T = 1.4\text{ s}, s_0 = 2.5\text{ m}, L = 5.0\text{ m}$
- **Transit Bus:** $a = 1.2\text{ m/s}^2, b = 2.0\text{ m/s}^2, T = 1.8\text{ s}, s_0 = 3.5\text{ m}, L = 12.0\text{ m}$
- **Heavy Truck:** $a = 0.8\text{ m/s}^2, b = 1.6\text{ m/s}^2, T = 2.2\text{ s}, s_0 = 4.0\text{ m}, L = 16.0\text{ m}$
- **Motorcycle:** $a = 3.2\text{ m/s}^2, b = 4.0\text{ m/s}^2, T = 0.9\text{ s}, s_0 = 1.2\text{ m}, L = 2.2\text{ m}$

### 3. MOBIL Lateral Dynamics
Lane changes are governed by the MOBIL incentive and safety criteria:
$$\tilde{a}_c - a_c + p \left( \sum (\tilde{a}_n - a_n) \right) > \Delta a_{\text{th}}$$
where $p$ is the politeness factor ($p = 0.3$) and $\Delta a_{\text{th}}$ is the switching threshold ($0.2\text{ m/s}^2$). The maneuver is strictly prohibited if the braking of the prospective follower exceeds $b_{\text{safe}} = 4.0\text{ m/s}^2$.

### 4. Common Random Numbers (CRN)
Comparative runs receive identical random seeds. Arrival times, approach lanes, vehicle types, turn destinations, and driver speed multipliers are deterministic across strategies, guaranteeing that differences in performance reflect control effectiveness rather than stochastic arrival variation.

---

## Persistence Architecture

UrbanFlow uses a dual persistence strategy:
1. **SQLite (Transactional Metadata & State):** Located at `DB_PATH` (`backend/simulation.db` locally, `/app/data/simulation.db` in Docker). WAL mode, foreign keys, 5-second busy timeout.
2. **Columnar Parquet Lakehouse (Telemetry & Metrics):** Located at `RUN_STORE_PATH` or AWS S3 (`s3://<bucket>/runs/`). Stores high-frequency vehicle telemetry and per-tick metrics for instant querying via DuckDB without database bloat.

### Database Tables (`src/database/db.py`)
- `simulation_runs`: Run status, configuration snapshot, summary metrics, seed, provenance SHA-256 hash, owner.
- `run_metrics`: Time-series per-tick operational metric records.
- `sweep_sessions`: Multi-seed traffic volume sweep configurations and crossover points.
- `saved_replays`: Serialized canvas replay states.
- `planning_studies`: V2.0 multi-alternative decision-support studies and findings.
- `experiments`: V3.0 parameter uncertainty ensembles and quota tracking.
- `tokens`: Hashed Personal Access Tokens (PATs) and scope records.

---

## Local Setup & Development

### 1. Environment Setup
```bash
cd backend
python -m venv .venv

# Activate environment:
.venv\Scripts\activate          # Windows PowerShell / CMD
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements-dev.txt
```

### 2. Launch FastAPI Development Server
```bash
# Start backend on port 8000 with hot-reload and local auth bypass
DEV_AUTH_BYPASS=1 uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
- API Documentation (Swagger UI): `http://localhost:8000/docs`
- Prometheus Metrics: `http://localhost:8000/metrics/prom`
- Health Probe: `http://localhost:8000/health`

### 3. Key Environment Variables
| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DB_PATH` | `backend/simulation.db` | Path to SQLite database file |
| `API_KEY` | *(disabled)* | Infrastructure API key (passed via `X-API-Key`) |
| `DEV_AUTH_BYPASS` | `0` (`1` in dev) | Bypass Cognito authentication for local development |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `STUDY_WORKERS` | $\min(\text{CPUs}, 8)$ | Process pool size for heavy simulation studies |
| `RUN_STORE_BACKEND`| `local` | Storage backend for Parquet run lakehouse (`local` or `s3`) |
| `RUN_STORE_S3_BUCKET`| *(empty)* | AWS S3 bucket name when using S3 storage |
| `OIDC_ISSUER` | *(Cognito URL)* | OIDC token issuer URL for JWT verification |

---

## Testing & Quality Gates

UrbanFlow enforces an 85% test coverage floor on all non-slow backend code:

```bash
# 1. Fast PR Quality Gate (runs in ~20-30s; coverage floor >= 85%)
pytest -m "not slow"

# 2. Architectural Boundary & Marker Check
pytest tests/test_architecture.py tests/test_ci_slow_matrix.py --no-cov

# 3. Hypothesis Invariant Tests (property-based)
pytest tests/core/test_properties.py --no-cov

# 4. Copilot Question Evaluation Score Gate
python -m evals.gate

# 5. Full Simulation Regression Matrix (Slow Shards)
pytest -m slow --no-cov

# 6. Static Analysis (Linter, Formatter & Strict Types)
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/
```
