# Feature specifications (F1 – F20)

Detailed scope for every feature in the V3.1 – V6.1 plan. The week-by-week schedule is in [WEEKLY_PLAN.md](WEEKLY_PLAN.md); this page says what each feature is, what "done" means, and what it depends on.

**Conventions**

- **Origin:** `Director` (the Director's brief: Go, AWS, cloud/DevOps, Kubernetes, Airflow, AI evals, harder pytest, beyond a single junction), `Confluence` (the future-scope list), `New` (added during planning).
- **Owner split:** Viraj = simulation / data / backend / infrastructure; Khushi = frontend / analytics.
- **Done** means every acceptance item is ticked, the evidence (commands, CI run, fingerprints) is recorded on the GitHub issue, and the claim is added to the claims register only if it is allowed there.
- Existing delivered work (V1.0 – V3.0) is **extended, not rebuilt**. Where a feature overlaps something that already exists, the overlap is named.
- The product stays **advisory-only**: nothing in this plan controls live signals.

---

### F1 – Go services

**Origin:** Director · **Weeks:** W36, W37 · **Owner:** Viraj · **Depends on:** F3

**Goal.** Move one performance- or I/O-heavy boundary out of Python into Go, with a measured result.

**Scope**
- Telemetry/run-event ingest service in Go behind a protobuf contract and gRPC.
- Generated Python client so the existing backend calls it without changes to callers.
- Dockerfile, Helm chart, CI build and tests.

**Deliverables:** protobuf contract, Go service, Python client, benchmark report (Go vs Python path).

**Acceptance**
- [ ] The Go service is in the real data path, not a side demo.
- [ ] Contract tests pass from both languages.
- [ ] Benchmark reports throughput and latency for both paths; if Go is not faster, that is reported.
- [ ] Existing backend and SDK tests still pass.

**Tech:** Go, protobuf, gRPC. **Risk:** porting for its own sake — mitigated by the benchmark gate.

### F2 – AWS-native deployment

**Origin:** Director · **Weeks:** W47, W48, W49 · **Owner:** Viraj · **Depends on:** F3, F7

**Goal.** Run UrbanFlow on AWS with infrastructure defined as code, moving beyond the single EC2 host.

**Scope**
- Terraform for VPC, S3, RDS, IAM, Secrets Manager.
- Kubernetes on AWS (EKS) and an SQS job queue with workers.
- CI deploys to an AWS staging environment.

**Deliverables:** Terraform modules, staging environment, runbook, teardown procedure.

**Acceptance**
- [ ] A clean AWS account can be brought to a working staging environment from the repository alone.
- [ ] CI deploys to staging on merge; no secrets in the repository.
- [ ] Budget alarm configured and teardown tested.
- [ ] Existing EC2 deployment documentation updated or retired.

**Tech:** AWS, Terraform, EKS, SQS, RDS. **Risk:** account ownership and cost — see decisions in the plan README.

### F3 – Kubernetes, Airflow and CI/CD

**Origin:** Director · **Weeks:** W33, W34, W37 · **Owner:** Viraj

**Goal.** Containerised services, scheduled batch work and an automated path to a cluster.

**Scope**
- Helm charts and a local kind cluster.
- CI builds images and deploys to the cluster.
- Airflow with a nightly regression run and a batch-experiment DAG.

**Deliverables:** Helm charts, Airflow DAGs, CI pipeline changes, operations notes.

**Acceptance**
- [ ] `helm install` brings up the full stack on kind.
- [ ] The nightly regression DAG runs and reports pass/fail.
- [ ] A batch-experiment DAG runs a multi-seed study end to end.
- [ ] CI deploys to the cluster on merge.

**Tech:** Docker, Helm, kind, Airflow, GitHub Actions. **Extends:** existing Docker Compose and `ci.yml`/`deploy.yml`.

### F4 – AI evals and hardcore pytest

**Origin:** Director · **Weeks:** W31, W32, W35 · **Owner:** Viraj (harness) / Khushi (question sets, UI tests)

**Goal.** Make quality provable and make regressions fail the build.

**Scope**
- Coverage gate and fixed-seed golden tests.
- Property-based tests (Hypothesis) for invariants: vehicle conservation, no negative queues, no overlapping vehicles, determinism under a seed.
- Copilot eval harness: versioned question sets, structured-output checks, LLM judge, score gate in CI.
- Frontend test setup connected to CI.

**Deliverables:** test harness, invariant catalogue, eval datasets (v1 plus an independently written set), CI gates.

**Acceptance**
- [ ] The invariant catalogue is written down and each invariant has a property test.
- [ ] A drop in eval score below the recorded threshold fails CI.
- [ ] Eval datasets are versioned and the independent set is written by someone other than the author of the prompts.
- [ ] Closes the open D-AI1 item (provider evaluation on `copilot-eval-v1`) or records why it stays open.

**Tech:** pytest, Hypothesis, Vitest. **Extends:** existing backend suite, 500+ frontend tests, `copilot-eval-v1`.

### F5 – Large-scale network engine

**Origin:** Director + Confluence · **Weeks:** W39 – W45 · **Owner:** Viraj (engine) / Khushi (viewer, network metrics)

**Goal.** Go beyond one junction: corridors and grids with vehicles travelling between junctions.

**Scope**
- Network graph model (ADR first), link-to-junction vehicle handoff, congestion-aware routing.
- Two-junction corridor, then a 3×3 grid, then 10+ junctions.
- Network-level metrics, congestion propagation analysis, performance work (profiling, vectorisation, partitioning).
- Multi-junction map viewer.

**Deliverables:** network engine, ADR, network metrics, map viewer, performance report.

**Acceptance**
- [ ] A network of 10+ junctions runs end to end and is deterministic under a seed.
- [ ] Vehicle conservation holds across links and junctions (property test).
- [ ] A performance budget is recorded in the ADR and met.
- [ ] Congestion spread is measured and visualised.

**Tech:** graph modelling, numpy. **Extends:** V1.9 network-level foundations (delivered as partial). **Risk:** largest single item; slack week W45 absorbs overrun.

### F6 – Uncertainty and statistical trust

**Origin:** Confluence + New · **Weeks:** W31, W32, W33 · **Owner:** Viraj / Khushi (display)

**Goal.** Replace "one run, one answer" with confidence.

**Scope**
- Stochastic driver and demand models; generalised multi-seed runner.
- Confidence intervals and paired significance tests for "is A better than B?".
- Sensitivity analysis (which input matters most).

**Deliverables:** statistics module, sensitivity analysis, results-page display.

**Acceptance**
- [ ] Any comparison reports an interval and a p-value, with the method named.
- [ ] Sensitivity ranking is reproducible from the seed.
- [ ] The eligibility labels from the Robustness Lab are preserved (eligible / indicative / exploratory).

**Tech:** SciPy, statsmodels, SALib. **Extends:** the V3.0 Robustness Lab (paired ensembles, bootstrap, regret).

### F7 – Reproducibility, audit trail and results lakehouse

**Origin:** New · **Weeks:** W31, W32, W33, W36 · **Owner:** Viraj / Khushi (queries, dbt)

**Goal.** Every result can be re-run and compared, and all runs can be queried together.

**Scope**
- Run manifest: seed, config hash, code version, input version.
- Parquet run store on S3, DuckDB queries, compare-two-runs, dbt models.

**Deliverables:** manifest format, run store, query layer, compare view.

**Acceptance**
- [ ] Re-running from a manifest gives an identical result.
- [ ] Two runs can be diffed in the UI.
- [ ] Analytics queries run over all stored runs.

**Tech:** Parquet, S3, DuckDB, dbt. **Extends:** existing provenance records, reproduce endpoint and `.ufpkg` manifests.

### F8 – Decision reports

**Origin:** New · **Weeks:** W35, W36, W37 · **Owner:** Khushi (reports) / Viraj (support)

**Goal.** A one-click report a decision-maker can read.

**Scope:** HTML-to-PDF report, charts with intervals, plain-language summary grounded in the computed numbers.

**Deliverables:** report generator, template, grounding check.

**Acceptance**
- [ ] The summary contains no number that is not in the computed results (automated check).
- [ ] The report states assumptions and limitations first, matching the claims register.
- [ ] A hallucinated-number test fails the build if triggered.

**Tech:** Jinja, PDF rendering, LLM (optional, with deterministic fallback). **Extends:** existing planning reports (JSON/Markdown/CSV).

### F9 – Richer metrics

**Origin:** New · **Weeks:** W33, W34 · **Owner:** Viraj / Khushi (panels)

**Goal.** Metrics that planners and councils decide on.

**Scope:** delay, travel time, fuel and CO₂, time-to-collision.

**Deliverables:** metric definitions, tests, UI panels, glossary.

**Acceptance**
- [ ] Each metric has a documented formula, units and an assumption note.
- [ ] Emissions numbers are labelled as model estimates, not measurements.
- [ ] Safety numbers are labelled as proxies, consistent with the claims register.

**Tech:** numpy. **Extends:** V1.6 safety/environmental analysis (partial) and the metric contract.

### F10 – Advisory-only governance

**Origin:** New · **Weeks:** W56, W57 · **Owner:** Viraj (backend) / Khushi (screens)

**Goal.** A safe, auditable path from result to recommendation.

**Scope:** draft → proposed → reviewed → approved workflow with roles and audit log; shadow mode comparing a recommendation with observed outcomes without acting.

**Deliverables:** workflow API, audit log, approval screens, shadow-mode report.

**Acceptance**
- [ ] Every state change is attributed and logged.
- [ ] No code path pushes anything to a live signal controller.
- [ ] The UI and API state the advisory-only rule.

**Tech:** state machine, RBAC. **Depends on:** F16.

### F11 – Real networks, calibration and interoperability

**Origin:** New · **Weeks:** W39, W40, W41 · **Owner:** Viraj / Khushi (import UI, error report)

**Goal.** Real roads and real counts, and compatibility with tools engineers already use.

**Scope:** OpenStreetMap import, SUMO import/export, GTFS and Synchro import, CSV turning counts and GeoJSON export, calibration against open traffic counts.

**Deliverables:** importers/exporters, calibration run, error report, upload UI.

**Acceptance**
- [ ] **Gate G-CAL:** simulated flows match real counts within an agreed error, reported openly.
- [ ] Imports validate and show clear messages for unsupported input.
- [ ] Round-trip export/import preserves the network.

**Tech:** OSMnx, GeoPandas, PostGIS (optional), SUMO formats. **Extends:** V1.8 calibration framework. **Needs:** a chosen city and open datasets (decision before W39).

### F12 – Emergency and transit priority

**Origin:** Confluence · **Weeks:** W50, W51, W52 · **Owner:** Viraj / Khushi (visuals, comparison)

**Goal.** Ambulances, fire trucks and buses that get priority through junctions.

**Scope:** emergency vehicle model, signal pre-emption, yield/clearance behaviour by surrounding vehicles, response-time metrics, with/without comparison, bus priority.

**Deliverables:** vehicle model, pre-emption logic, metrics, comparison view.

**Acceptance**
- [ ] Pre-emption measurably changes response time, reported with intervals.
- [ ] No new collision or deadlock regressions in the safety matrix.
- [ ] Results are labelled as in-model only.

**Tech:** simulation core. **Extends:** the strategy registry and the safety test matrix.

### F13 – Incidents, disruptions and weather

**Origin:** Confluence · **Weeks:** W47, W48, W49 · **Owner:** Viraj / Khushi (setup screen, charts)

**Goal.** Stress cases: crashes, blocked lanes, closures, event surges and bad weather.

**Scope:** incident generator, closures and rerouting, weather (friction, visibility, reaction time), event-day surges, recovery-time and resilience scores.

**Deliverables:** scenario generators, resilience score, Stress Lab extension, UI.

**Acceptance**
- [ ] Each disruption type is reproducible from a seed.
- [ ] Every strategy gets a resilience score with an interval.
- [ ] The claims register is updated: surges and incidents move from "not modelled" to "modelled".

**Tech:** simulation core. **Extends:** V3.0 Stress Lab and Breakpoint Explorer (stationary extremes only until now).

### F14 – Digital twin with live data streaming

**Origin:** Confluence + New · **Weeks:** W42, W43, W45, W47, W51, W53 · **Owner:** Viraj (stream, calibration) / Khushi (dashboards, what-if)

**Goal.** Compare the simulation with continuously updated real traffic data.

**Scope:** event stream, Go consumers, replayed historical data first, continuous recalibration, prediction-vs-observation dashboard, what-if on the twin, a live-feed adapter, soak test.

**Deliverables:** stream pipeline, twin model, dashboard, live adapter.

**Acceptance**
- [ ] Replayed data drives the twin end to end.
- [ ] Prediction error against observation is shown and tracked over time.
- [ ] The live adapter runs for an extended soak test without data loss or drift in memory use.

**Tech:** Redpanda/Kafka, Go, Grafana. **Depends on:** F1, F5, F11. **Needs:** a live feed source (decision by W46).

### F15 – Observability and reliability

**Origin:** New · **Weeks:** W42, W43, W44 · **Owner:** Viraj / Khushi (dashboards)

**Goal.** Know it is healthy, and prove it under stress.

**Scope:** OpenTelemetry tracing, Prometheus metrics, Grafana dashboards, SLOs, k6 load tests, chaos tests.

**Deliverables:** instrumentation, dashboards, SLO definitions, load/chaos test results.

**Acceptance**
- [ ] SLOs are written down and measured on the dashboards.
- [ ] Load tests and a worker-kill chaos test run in CI or on a schedule.
- [ ] Findings are recorded and fixed or accepted explicitly.

**Tech:** OpenTelemetry, Prometheus, Grafana, k6, Chaos Mesh.

### F16 – Multi-tenant platform

**Origin:** New · **Weeks:** W50 – W53 · **Owner:** Viraj (backend) / Khushi (screens)

**Goal.** Several teams can use it safely.

**Scope:** OIDC login and roles, quotas and rate limits, OpenAPI spec, generated client SDKs, tenant-isolation tests, security review.

**Deliverables:** auth and roles, quota system, SDKs, isolation test suite, review notes.

**Acceptance**
- [ ] Two tenants cannot read or affect each other's data (automated test).
- [ ] Quotas and rate limits are enforced and visible to users.
- [ ] The OpenAPI snapshot contract test covers the new surface.

**Tech:** OIDC (Cognito/Keycloak), Redis, OpenAPI. **Extends:** existing Cognito sign-in, ownership rules, personal access tokens, quotas and Python SDK.

### F17 – Job queue with cost control

**Origin:** New · **Weeks:** W53, W55 · **Owner:** Viraj / Khushi (cost display)

**Goal.** Heavy simulation batches without runaway cost.

**Scope:** autoscaling workers, spot capacity, cost tags, per-run cost.

**Deliverables:** autoscaling config, cost allocation, cost display.

**Acceptance**
- [ ] Workers scale to zero when idle.
- [ ] Each run shows an estimated cost.
- [ ] A budget cap stops new jobs, with a clear message.

**Tech:** KEDA, Karpenter, cost tags. **Depends on:** F2.

### F18 – Reinforcement-learning signal control with MLOps

**Origin:** Confluence · **Weeks:** W34 – W37, W39 – W41, W44 · **Owner:** Viraj / Khushi (comparison charts)

**Goal.** Learned controllers compared honestly against fixed-time and adaptive ones.

**Scope:** Gymnasium environment and baselines, DQN and PPO training, MLflow tracking, model registry, scheduled retraining, evaluation with intervals first on one junction then on the network.

**Deliverables:** environment, training pipelines, registry, evaluation report.

**Acceptance**
- [ ] Policies are evaluated on held-out seeds against unchanged baselines, using the F6 statistics.
- [ ] Conditions where learning wins and where it loses are both documented.
- [ ] The claims register keeps "AI-optimised" off the table unless evidence supports it.

**Tech:** PyTorch, Gymnasium, MLflow, Airflow. **Depends on:** F5, F6, F7. **Extends:** the V3.0 Discovery Lab (bounded evolutionary search).

### F19 – Connected vehicles with hardware-in-the-loop demo

**Origin:** Confluence + New · **Weeks:** W48, W49, W50, W52, W58 · **Owner:** Viraj / Khushi (metrics views, demo panel)

**Goal.** Vehicle-to-vehicle and vehicle-to-infrastructure messaging with imperfect communication, plus a physical signal head driven by the simulator.

**Scope:** message system over MQTT, latency and loss, cooperation metrics, cooperative vs non-cooperative experiments, Raspberry Pi/ESP32 signal head.

**Deliverables:** messaging model, experiments, hardware demo, demo runbook.

**Acceptance**
- [ ] Latency and loss are parameters and are recorded in provenance.
- [ ] Cooperation effect is measured with intervals.
- [ ] The hardware demo runs from the simulator end to end and has a recorded fallback.

**Tech:** MQTT, AWS IoT Core, embedded Python. **Needs:** hardware ordered by W46.

### F20 – Cooperative autonomy

**Origin:** Confluence · **Weeks:** W55 – W59 · **Owner:** Viraj / Khushi (visuals, comparisons)

**Goal.** Platooning and signal-free (reservation-based) intersections.

**Scope:** leader-follower platoon controller, formation/merge/split, stability and throughput analysis, reservation-based intersection manager, conflict resolution, trajectory coordination, safety validation.

**Deliverables:** platoon controller, intersection manager, comparison results.

**Acceptance**
- [ ] **Gate G-AIM:** the intersection manager passes safety validation (no conflicting reservations, no collisions across the test matrix).
- [ ] Platoon stability and throughput effects are measured with intervals.
- [ ] Signal-free vs signals compared on the same scenarios.

**Tech:** control algorithms, conflict resolution. **Depends on:** F19. **Risk:** riskiest algorithm; W58 – W59 absorb overrun.
