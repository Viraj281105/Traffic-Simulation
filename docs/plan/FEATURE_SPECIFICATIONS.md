# Feature Specifications (F1 – F20)

Detailed specifications for all 20 features comprising the UrbanFlow V3.1 – V6.1 master plan. Schedule mapping is maintained in [WEEKLY_PLAN.md](WEEKLY_PLAN.md).

**Conventions & Status Tags:**
- **`VERIFIED`**: Implemented, tested, and actively passing in the codebase.
- **`WRITTEN`**: Code, configuration, or infrastructure manifests authored and verified syntactically, waiting for external cluster/cloud execution.
- **`NEEDS-INPUT`**: Architecturally complete, pending owner dataset selection or third-party cloud credential assignment.
- **`PLANNED`**: Approved design scheduled in Phase 7 (W55 – W60).

---

### F1 – Go Telemetry Services
**Origin:** Director Brief · **Phase:** Phase 4 (W36, W37) · **Owner:** Viraj · **Depends on:** F3  
**Status:** `WRITTEN` (Protobuf contract, Go ingest service, and Go streaming consumer authored)

**Goal:** Provide a high-throughput, low-latency telemetry ingestion pipeline in Go to handle high-frequency simulation vehicle frames without Python GIL bottlenecks.

**Deliverables:**
- Protobuf schema: [`proto/ingest.proto`](../../proto/ingest.proto)
- Go Telemetry Ingest Microservice: [`services/ingest-go/`](../../services/ingest-go/)
- Go Streaming Consumer: [`services/consumer-go/`](../../services/consumer-go/)
- Benchmark runner: `services/ingest-go/cmd/ingest-bench/`

**Acceptance:**
- [x] Protobuf contract defined with backward compatibility.
- [x] Go ingest server supports gRPC and HTTP/JSON endpoints.
- [x] Go Redpanda / Kafka streaming consumer written.
- [ ] Live benchmark comparison against Python REST baseline executed in production cluster.

---

### F2 – AWS-Native Staging Deployment
**Origin:** Director Brief · **Phase:** Phase 6 (W47, W48, W49, W54) · **Owner:** Viraj · **Depends on:** F3, F7  
**Status:** `WRITTEN` (Terraform modules authored in `infra/terraform/`, CI workflow in `.github/workflows/aws-staging.yml`)

**Goal:** Establish reproducible Infrastructure as Code (IaC) on AWS, moving beyond single-instance EC2 deployments.

**Deliverables:**
- Terraform Staging Stack: [`infra/terraform/`](../../infra/terraform/) (modules: `network`, `storage`, `database`, `eks`, `sqs`, `iam`, `secrets`, `tagging`, `budgets`)
- GitHub Actions AWS Staging Workflow: [`.github/workflows/aws-staging.yml`](../../.github/workflows/aws-staging.yml)
- Deployment Runbook: [`infra/terraform/README.md`](../../infra/terraform/README.md)

**Acceptance:**
- [x] Terraform manifests modularized with strict cost tagging.
- [x] Private EKS cluster, RDS PostgreSQL, encrypted S3 buckets, and SQS queues defined.
- [x] Least-privilege IAM OIDC roles configured for GitHub Actions CI/CD.
- [ ] Staging apply executed against a live corporate AWS account (`NEEDS-INPUT` on account credentials D4).

---

### F3 – Containerization, Kubernetes & Airflow CI/CD
**Origin:** Director Brief · **Phase:** Phase 4 (W33, W34, W37) · **Owner:** Viraj  
**Status:** `VERIFIED` locally; `WRITTEN` for cluster execution

**Goal:** Automate scheduled simulation pipelines, container builds, and local/cloud Kubernetes deployments.

**Deliverables:**
- Umbrella Helm Chart: [`deploy/helm/urbanflow/`](../../deploy/helm/urbanflow/)
- Local Kind Cluster Configuration: [`deploy/kind/kind-config.yaml`](../../deploy/kind/kind-config.yaml)
- Apache Airflow DAGs:
  - Nightly regression suite: [`airflow/dags/nightly_regression.py`](../../airflow/dags/nightly_regression.py)
  - Multi-seed batch experiments: [`airflow/dags/batch_experiments.py`](../../airflow/dags/batch_experiments.py)
  - RL retraining pipeline: [`airflow/dags/rl_retrain.py`](../../airflow/dags/rl_retrain.py)
  - Nightly run history archiver: [`airflow/dags/nightly_history.py`](../../airflow/dags/nightly_history.py)

**Acceptance:**
- [x] Helm chart deploys backend, frontend, and ingest microservices.
- [x] Airflow DAGs import cleanly and execute without syntax errors.
- [x] GitHub Actions runs nightly regression workflows.

---

### F4 – AI Evaluation Harness & Invariant Property Testing
**Origin:** Director Brief · **Phase:** Phase 4 (W31, W32, W35) · **Owner:** Viraj (Harness) / Khushi (Questions & UI)  
**Status:** `VERIFIED`

**Goal:** Eliminate silent algorithmic regressions via property-based physical invariant tests and enforce factual correctness on LLM outputs.

**Deliverables:**
- Hypothesis Property-Based Invariant Tests: [`backend/tests/core/test_properties.py`](../../backend/tests/core/test_properties.py)
- Copilot Evaluation Gate: [`backend/evals/gate.py`](../../backend/evals/gate.py)
- Versioned Gold Question Dataset: [`backend/evals/copilot_questions_v1.json`](../../backend/evals/copilot_questions_v1.json)
- Pytest Coverage Floor ($\ge 85\%$): [`backend/pyproject.toml`](../../backend/pyproject.toml)

**Acceptance:**
- [x] Invariants verified: vehicle conservation ($\text{spawned} = \text{active} + \text{completed}$), strictly non-negative queue lengths, zero overlapping vehicle footprints at calibrated demand.
- [x] CI build fails automatically if Copilot evaluation accuracy score drops below threshold.
- [x] Backend test suite maintains $>85\%$ branch and statement coverage.

---

### F5 – Large-Scale Network Engine & Congestion Spread
**Origin:** Confluence (FS-9) / Director · **Phase:** Phase 5 (W39 – W45) · **Owner:** Viraj · **Depends on:** V1.8/V1.9  
**Status:** `VERIFIED`

**Goal:** Scale the microscopic simulation core from isolated junctions to multi-junction arterial corridors and grids with conserved vehicle handoffs and congestion propagation heatmaps.

**Deliverables:**
- Network Graph Model (ADR-021): [`backend/src/networks/graph.py`](../../backend/src/networks/graph.py)
- Two-Junction Corridor & Grid Topologies: [`backend/src/networks/grid.py`](../../backend/src/networks/grid.py) (3x3 grid [9 junctions], 12-junction arterial grid)
- Link-to-Junction Vehicle Handoff: [`backend/src/networks/handoff.py`](../../backend/src/networks/handoff.py)
- Topological Congestion Spread Engine: [`backend/src/netmetrics/congestion.py`](../../backend/src/netmetrics/congestion.py)
- MapLibre GL Spatial Visualizer: [`frontend/src/mapview/`](../../frontend/src/mapview/), [`frontend/src/congestion/`](../../frontend/src/congestion/)

**Acceptance:**
- [x] 12-junction network executes end-to-end with vehicle conservation across link boundaries.
- [x] Shockwaves and bottleneck spillback are calculated and displayed on link heatmaps.
- [x] Interactive MapLibre GL viewer renders arterial networks with offline vector tiles.

---

### F6 – Parameter Uncertainty & Statistical Trust
**Origin:** Future Scope (FS-6) · **Phase:** Phase 3/4 (V3.0 W1, W31, W32) · **Owner:** Viraj  
**Status:** `VERIFIED`

**Goal:** Replace single-run deterministic comparisons with robust statistical ensembles quantifying uncertainty across demand, fleet mix, and driver headway distributions.

**Deliverables:**
- Robustness Lab Parameter Uncertainty Spec: [`backend/src/uncertainty/spec.py`](../../backend/src/uncertainty/spec.py)
- Quasi-Random Sampler (Sobol & Latin Hypercube): [`backend/src/uncertainty/sampler.py`](../../backend/src/uncertainty/sampler.py)
- Statistical Inference Engine: [`backend/src/uncertainty/analysis.py`](../../backend/src/uncertainty/analysis.py) (Welch's t-test, Cohen's d, Wilson score intervals, bootstrap paired differences)
- Parameter Sensitivity Engine: [`backend/src/insights/sensitivity.py`](../../backend/src/insights/sensitivity.py)

**Acceptance:**
- [x] Paired Common Random Numbers (CRN) enforced across all comparative uncertainty ensembles.
- [x] 95% confidence intervals and p-values computed backend-side and displayed in decision reports.
- [x] Sensitivity analysis identifies which input factors exert the strongest influence on delay.

---

### F7 – Results Lakehouse & Reproducibility Audit Trail
**Origin:** Director Brief · **Phase:** Phase 4 (W31, W32, W33, W38) · **Owner:** Viraj  
**Status:** `VERIFIED`

**Goal:** High-throughput, scalable columnar storage for simulation telemetry and verifiable bit-identical run reproducibility.

**Deliverables:**
- Parquet Results Lakehouse: [`backend/src/runstore/store.py`](../../backend/src/runstore/store.py) (local disk and S3 adapters)
- DuckDB Analytical Queries: [`backend/src/runstore/duckdb_queries.py`](../../backend/src/runstore/duckdb_queries.py)
- Reproducibility Run Manifest: [`backend/src/core/run_manifest.py`](../../backend/src/core/run_manifest.py)
- Master Reproducibility Audit Script: [`scripts/reproducibility_audit.py`](../../scripts/reproducibility_audit.py)

**Acceptance:**
- [x] High-frequency per-tick telemetry written to Parquet without locking transactional SQLite tables.
- [x] DuckDB executes complex analytical queries over millions of stored simulation ticks in milliseconds.
- [x] Re-running a scenario with the same manifest hash yields bit-identical outputs.

---

### F8 – Decision-Support Reports & Grounded AI Summaries
**Origin:** Product Roadmap · **Phase:** Phase 4 (W35, W36, W37) · **Owner:** Khushi (Frontend) / Viraj (Backend)  
**Status:** `VERIFIED`

**Goal:** Transform raw simulation metrics into structured, plain-language decision reports guarded against hallucination.

**Deliverables:**
- Multi-format Report Generator: Markdown, JSON, and CSV export engines
- Grounded Summary Assertion Verifier: [`backend/src/copilot/grounded_summary.py`](../../backend/src/copilot/grounded_summary.py)
- Plain-Language Presentation Catalog: [`frontend/src/metrics/plainLanguage.ts`](../../frontend/src/metrics/plainLanguage.ts)

**Acceptance:**
- [x] Reports clearly state HCM Level-of-Service grades, balance bands, and causal explanations.
- [x] Grounded summary validator parses generated AI text and asserts every cited numerical value against the underlying JSON results, raising validation errors on invented numbers.

---

### F9 – Rich Environmental, Safety & Operational Metrics
**Origin:** Product Roadmap · **Phase:** Phase 4 (W33, W34) · **Owner:** Viraj  
**Status:** `VERIFIED`

**Goal:** Expand operational accounting beyond mean delay to include travel-time distributions, fuel consumption, emissions, and safety conflict proxies.

**Deliverables:**
- Environmental Fuel & $\text{CO}_2$ Models: [`backend/src/metrics/emissions.py`](../../backend/src/metrics/emissions.py) (Akçelik instantaneous polynomial formulation)
- Safety Conflict Proxies: [`backend/src/metrics/safety.py`](../../backend/src/metrics/safety.py) (Time-to-Collision [TTC] and Post-Encroachment Time [PET])
- Travel-Time Distributions: Percentiles (p50, p95), stop counts, and Jain's direction fairness index

**Acceptance:**
- [x] Fuel consumption (L/100km) and $\text{CO}_2$ emissions (g/km) computed on every simulation run.
- [x] Safety conflict counters track near-miss events without adding prohibitive overhead to the physics loop.

---

### F10 – Advisory-Only Governance & Tamper-Evident Audit Ledger
**Origin:** Governance Requirements · **Phase:** Phase 7 (W56, W57) · **Owner:** Viraj  
**Status:** `PLANNED`

**Goal:** Provide an enterprise governance workflow with cryptographic audit logging for municipal planning interventions.

**Planned Deliverables:**
- Governance Approval Workflow Engine: `backend/src/governance/workflow.py` (`draft` $\to$ `submitted` $\to$ `approved` $\to$ `archived`)
- Cryptographic Hash-Chained Audit Ledger: `backend/src/governance/audit_ledger.py` (SHA-256 blocks with parent pointers, timestamps, and reviewer signatures)
- Shadow Mode Evaluation Engine: `backend/src/governance/shadow.py`
- Frontend Approval Dashboard: `frontend/src/governance/`

**Acceptance Criteria for Phase 7:**
- [ ] Two-stage approval workflow enforced for publishing scenario recommendations.
- [ ] Audit ledger prevents unauthorized tampering (tampered blocks detected on chain verification).
- [ ] Shadow mode runs simulate hypothetical recommendations against historical baseline telemetry.

---

### F11 – Real Road Networks, Traffic Count Calibration & Interoperability
**Origin:** Confluence (FS-9, FS-10) · **Phase:** Phase 5 (W39, W40, W41, W43) · **Owner:** Viraj  
**Status:** `VERIFIED` (Synthetic calibration verified; `NEEDS-INPUT` on city dataset D1)

**Goal:** Ingest open geographic and transit data, and calibrate simulated vehicle counts against observed turning counts.

**Deliverables:**
- Importers: OpenStreetMap Overpass (`osm.py`), SUMO (`sumo.py`), GTFS (`gtfs.py`), Synchro (`synchro.py`)
- Traffic Count Loader: [`backend/src/calibration/network_counts.py`](../../backend/src/calibration/network_counts.py)
- Error Metrics & Compliance: [`backend/src/calibration/network_metrics.py`](../../backend/src/calibration/network_metrics.py) (GEH statistic, RMSE, MAPE)
- Continuous Recalibration Optimizer: [`backend/src/calibration/network_fit.py`](../../backend/src/calibration/network_fit.py)

**Acceptance:**
- [x] Real OSM and SUMO networks compile into valid simulation graphs.
- [x] Calibration optimizer adjusts demand and speed multipliers to minimize GEH error.
- [x] Calibration report confirms GEH < 5.0 on $\ge 85\%$ of links for synthetic ground truth.

---

### F12 – Emergency Signal Preemption & Transit Priority
**Origin:** Future Scope (FS-1) · **Phase:** Phase 6 (W50, W51, W52) · **Owner:** Viraj  
**Status:** `VERIFIED`

**Goal:** Model emergency vehicles with siren detection, signal preemption, civilian yielding, and public transit priority.

**Deliverables:**
- Emergency Preemption Controller: [`backend/src/priority/controller.py`](../../backend/src/priority/controller.py)
- Preemption Phase Logic: [`backend/src/priority/phases.py`](../../backend/src/priority/phases.py) (green extension, red truncation, minimum clearance)
- Civilian Yielding Dynamics: [`backend/src/priority/yielding.py`](../../backend/src/priority/yielding.py)
- Transit Signal Priority (TSP): [`backend/src/priority/comparison.py`](../../backend/src/priority/comparison.py)
- Response-Time Audit Logger: [`backend/src/priority/audit.py`](../../backend/src/priority/audit.py)

**Acceptance:**
- [x] Approaching emergency vehicles trigger acoustic preemption, truncating conflicting green stages safely.
- [x] Civilian vehicles pull aside or decelerate to create an open emergency corridor.
- [x] Transit signal priority extends green intervals for scheduled buses.
- [x] Preemption compliance and response-time improvements are quantified in comparison reports.

---

### F13 – Incidents, Dynamic Closures, Weather & System Resilience
**Origin:** Future Scope (FS-7, FS-8) · **Phase:** Phase 6 (W47, W48, W49) · **Owner:** Viraj  
**Status:** `VERIFIED`

**Goal:** Simulate realistic physical disruptions, adverse weather conditions, demand surges, and quantify strategy resilience.

**Deliverables:**
- Incident Simulation Engine: [`backend/src/incidents/engine.py`](../../backend/src/incidents/engine.py)
- Dynamic Road Closures & Dijkstra Rerouting: [`backend/src/incidents/engine.py`](../../backend/src/incidents/engine.py)
- Weather Physics Modifiers: [`backend/src/incidents/weather.py`](../../backend/src/incidents/weather.py) (friction, visibility, reaction times)
- Comparative Resilience Scoring ($R$): [`backend/src/incidents/resilience.py`](../../backend/src/incidents/resilience.py)

**Acceptance:**
- [x] Lane-blocking crashes and link closures force dynamic vehicle rerouting without deadlock.
- [x] Rain, dense fog, snow, and ice adjust car-following acceleration and headway parameters.
- [x] Resilience score ($R$) quantifies post-incident recovery rate across competing strategies.

---

### F14 – Digital Twin Core with Telemetry Replay
**Origin:** Future Scope (FS-10) · **Phase:** Phase 5 (W42, W45) / Phase 6 · **Owner:** Viraj  
**Status:** `VERIFIED` (Replay engine verified; live feeds `NEEDS-INPUT` on source D3)

**Goal:** Maintain a digital replica of network traffic supporting telemetry replay, prediction-vs-observation comparisons, and what-if scenario branching.

**Deliverables:**
- Telemetry Replay Adapter: [`backend/src/twin/replay.py`](../../backend/src/twin/replay.py)
- Prediction-vs-Observation Comparison API: [`backend/src/twin/compare.py`](../../backend/src/twin/compare.py)
- Digital Twin Frontend Dashboard: [`frontend/src/twinview/`](../../frontend/src/twinview/)

**Acceptance:**
- [x] Recorded telemetry streams replay synchronously against simulation state.
- [x] Prediction-vs-observation differences are tracked in real time.
- [x] What-if branching allows users to fork historical sessions into alternative control strategies.

---

### F15 – Distributed Observability, Prometheus Metrics & SLOs
**Origin:** Director Brief · **Phase:** Phase 5 (W42, W43, W44) · **Owner:** Viraj  
**Status:** `VERIFIED` (Tracing, metrics, and evaluator verified; Grafana/k6 `WRITTEN`)

**Goal:** Provide production-grade distributed tracing, telemetry metrics exposition, and automated Service Level Objective (SLO) compliance verification.

**Deliverables:**
- OpenTelemetry Distributed Tracing: [`backend/src/observability/tracer.py`](../../backend/src/observability/tracer.py)
- Prometheus Exposition Endpoint: `GET /metrics/prom` ([`backend/src/observability/prom_router.py`](../../backend/src/observability/prom_router.py))
- SLO Definitions & Evaluator: [`deploy/observability/slo.json`](../../deploy/observability/slo.json), [`backend/src/observability/slo.py`](../../backend/src/observability/slo.py)
- Performance Load Testing: [`deploy/k6/`](../../deploy/k6/), [`deploy/chaos/`](../../deploy/chaos/)

**Acceptance:**
- [x] `GET /metrics/prom` exports simulation run rates, queue depths, and endpoint latencies.
- [x] SLO evaluator verifies latency and error rate budgets.
- [x] Distributed traces propagate request IDs across HTTP and worker boundaries.

---

### F16 – Enterprise Multi-Tenancy & Security
**Origin:** Security & Compliance · **Phase:** Phase 6 (W50, W51, W52, W53) · **Owner:** Viraj  
**Status:** `VERIFIED`

**Goal:** Ensure secure multi-tenant isolation, role-based authorization, quota enforcement, and automated client SDK generation.

**Deliverables:**
- OIDC JWT Authentication & Claims Verifier: [`backend/src/tenancy/oidc.py`](../../backend/src/tenancy/oidc.py)
- Role-Based Access Control (RBAC): [`backend/src/tenancy/roles.py`](../../backend/src/tenancy/roles.py) (`viewer`, `planner`, `engineer`, `admin`)
- Tenant-Scoped Isolation: [`backend/src/tenancy/scoping.py`](../../backend/src/tenancy/scoping.py)
- Tenant Quotas & Rate Limits: [`backend/src/tenancy/limits.py`](../../backend/src/tenancy/limits.py)
- TypeScript SDK Generator: [`scripts/generate_ts_client.py`](../../scripts/generate_ts_client.py)
- Python Client SDK: [`sdk/python/`](../../sdk/python/)

**Acceptance:**
- [x] Tenant data is strictly isolated; users cannot read or modify other tenants' runs or studies (HTTP 404).
- [x] RBAC policies prevent unauthorized users from launching compute-intensive studies.
- [x] TypeScript and Python SDKs are generated directly from OpenAPI v3 contracts.

---

### F17 – Asynchronous Job Queue & Cloud Cost Control
**Origin:** Operations Architecture · **Phase:** Phase 6 (W53, W54) / Phase 7 (W55) · **Owner:** Viraj  
**Status:** `VERIFIED` for Queue/Worker; `PLANNED` for Phase 7 Cost Accounting Engine

**Goal:** Decouple heavy multi-seed simulation execution from API servers using an asynchronous job queue with AWS SQS adapters and cost estimation.

**Deliverables:**
- Asynchronous Job Queue Interface: [`backend/src/jobs/queue.py`](../../backend/src/jobs/queue.py)
- AWS SQS Queue Adapter: [`backend/src/jobs/sqs.py`](../../backend/src/jobs/sqs.py)
- Background Worker Runner: [`backend/src/jobs/worker.py`](../../backend/src/jobs/worker.py)
- Compute Cost Tags: [`backend/src/jobs/cost_tags.py`](../../backend/src/jobs/cost_tags.py)
- **Phase 7 Planned:** Per-Run AWS Compute Cost Calculator: `backend/src/costing/`

**Acceptance:**
- [x] Long-running studies process asynchronously in worker daemons without HTTP timeouts.
- [x] SQS queue handles job dispatch, retry backoff, and dead-letter queue (DLQ) routing.
- [ ] Phase 7: Compute cost accounting estimates dollar cost per simulation run from CPU/GPU duration.

---

### F18 – Reinforcement Learning Signal Control & MLOps
**Origin:** Future Scope (FS-2) / Director · **Phase:** Phase 4 (W34–W37) / Phase 5 (W39–W44) · **Owner:** Khushi (ML) / Viraj (Env)  
**Status:** `VERIFIED`

**Goal:** Provide standardized Gymnasium simulation environments, train deep RL policies (PPO/DQN), and benchmark against classical traffic control baselines.

**Deliverables:**
- Single & Multi-Junction Gymnasium Environments: [`backend/src/rl/network_env.py`](../../backend/src/rl/network_env.py)
- Baseline Policies: Fixed-Time and Max-Pressure ([`backend/src/rl/network_baselines.py`](../../backend/src/rl/network_baselines.py))
- Training Pipelines: PPO and DQN with PyTorch ([`backend/src/rl/network_train.py`](../../backend/src/rl/network_train.py))
- Airflow Retraining DAG: [`airflow/dags/rl_retrain.py`](../../airflow/dags/rl_retrain.py)
- RL Model Registry & Comparison Dashboard: [`frontend/src/netrl/`](../../frontend/src/netrl/)

**Acceptance:**
- [x] Gymnasium environments comply strictly with standard observation and action spaces.
- [x] Classical Fixed-Time and Max-Pressure baselines provide rigorous benchmark controls.
- [x] Paired multi-seed statistical evaluation quantifies policy performance differences with confidence intervals.

---

### F19 – Connected Vehicles, V2X Messaging & Hardware-in-the-Loop Demo
**Origin:** Future Scope (FS-3) · **Phase:** Phase 6 (W48, W49, W52) / Phase 7 (W58) · **Owner:** Viraj  
**Status:** `VERIFIED` for V2X Bus; `PLANNED` for Phase 7 Physical Signal Head Hardware

**Goal:** Model Vehicle-to-Everything (V2X) inter-vehicle messaging and interface the simulation engine with a physical microcontroller traffic signal head over MQTT.

**Deliverables:**
- V2X Messaging Channel & Bus: [`backend/src/v2x/channel.py`](../../backend/src/v2x/channel.py), [`bus.py`](../../backend/src/v2x/bus.py)
- MQTT Broker Adapter: [`backend/src/v2x/mqtt_bus.py`](../../backend/src/v2x/mqtt_bus.py)
- Stochastic Latency and Packet Loss Models: [`backend/src/v2x/channel.py`](../../backend/src/v2x/channel.py)
- **Phase 7 Planned:** ESP32 / Raspberry Pi Pico MicroPython Firmware: `hardware/firmware/`
- **Phase 7 Planned:** Hardware MQTT Bridge Daemon: `backend/src/hardware_bridge/`

**Acceptance:**
- [x] V2X messaging bus enables simulated vehicles to share speed, intent, and braking state.
- [x] Cooperative car-following benefits are demonstrated over non-cooperative baselines.
- [ ] Phase 7: Physical 3-color LED signal head transitions in real time driven by simulation MQTT events; physical button actuation triggers simulation stage calls.

---

### F20 – Cooperative Autonomy: Platooning & Autonomous Intersection Management (AIM)
**Origin:** Future Scope (FS-4, FS-5) · **Phase:** Phase 7 (W55, W56, W57, W58) · **Owner:** Viraj  
**Status:** `PLANNED`

**Goal:** Introduce leader-follower vehicle platooning with string stability and reservation-based signal-free Autonomous Intersection Management (AIM).

**Planned Deliverables:**
- Leader-Follower Platoon Controller: `backend/src/platoon/controller.py` (constant time headway, intra-gap regulation)
- Dynamic Platoon Maneuvers: `backend/src/platoon/maneuvers.py` (join, leave, split, coordinated merge)
- Reservation-Based Autonomous Intersection Controller: `backend/src/aim/controller.py` (space-time reservation grid tiles)
- Formal G-AIM Mathematical Safety Verifier: `backend/src/aim/safety.py`
- Frontend Space-Time Reservation Visualizer: `frontend/src/aim/`

**Acceptance Criteria for Phase 7:**
- [ ] Platoons maintain string stability ($\|\Gamma(j\omega)\| < 1$) across sudden lead vehicle decelerations with zero collisions.
- [ ] Platoon join and leave maneuvers execute dynamically without disrupting adjacent traffic streams.
- [ ] Signal-free AIM manager guarantees zero overlapping space-time tile reservations under emergency deceleration bounds.
- [ ] Aerodynamic drafting fuel savings ($8\text{–}15\%$) are quantified for platoon followers.
- [ ] Signal-free intersection performance is compared fairly against optimal actuated traffic signals.
