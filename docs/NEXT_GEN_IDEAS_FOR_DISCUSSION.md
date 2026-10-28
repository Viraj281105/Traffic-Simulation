# UrbanFlow - Next-Gen Ideas (for discussion)

Draft for a decision conversation with Khushi. Twenty ideas, merged from the Director's asks, the Confluence future scope and our own brainstorm. Sizes are rough and assume one developer.

## Who is this for?

| User | What they do with UrbanFlow | Priority |
|---|---|---|
| Traffic engineer (city or consultancy) | Tests signal timing changes before touching real signals | **Primary** |
| Urban planner | Asks what-if questions (new school, new mall, event day) | Secondary |
| Researcher / student | Benchmarks controllers (RL, adaptive, fixed) reproducibly | Secondary |
| Decision-maker | Reads a read-only summary and approves or rejects | Consumer |

UrbanFlow is **advisory only**. It recommends; it never controls live signals.

Tags: **[D]** Director's ask, **[C]** Confluence item, **[N]** new from brainstorm.

---

## A. Director's asks (new stack)

### 1. Go services [D] - ~1 month
**What:** Move a performance- or I/O-heavy piece out of Python into Go, such as the telemetry ingest service or the simulation job runner.
**How:** Pick one boundary that already has a clear contract (for example, the service that receives run events and writes them to storage). Define it in protobuf, expose it over gRPC, and build the Go service with its own tests and a Dockerfile. Python keeps calling it through a generated client. Benchmark old vs new so the gain is measurable, not assumed.

### 2. AWS-native deployment [D] - 1-2 months
**What:** Run UrbanFlow on AWS instead of only Docker on a laptop.
**How:** Describe everything in Terraform: S3 for run artifacts, SQS for the job queue, RDS Postgres for metadata, ECS or EKS for compute, Lambda for small event handlers, and Secrets Manager plus IAM roles for access. Start with one environment (dev), then add staging. Keep cost low with small instances and auto-shutdown.

### 3. Kubernetes, Airflow and CI/CD [D] - 1-2 months
**What:** Containerised, scheduled, automatically tested and deployed.
**How:** Package services as Helm charts and deploy to a local kind cluster first, then EKS. Use Airflow to schedule batch experiments, nightly regression runs and report generation. GitHub Actions builds images, runs the test suite and deploys on merge, with a staged promotion (dev, staging).

### 4. AI evals and hardcore pytest [D] - ongoing
**What:** Make quality provable, especially for the Experiment Copilot and the simulation core.
**How:** Add property-based tests (Hypothesis) for invariants such as vehicle conservation and no negative queues. Add golden-file regression tests with fixed seeds. Build an eval harness for the Copilot: a versioned set of questions with expected structured outputs, scored by exact-match checks plus an LLM judge, tracked per prompt or model version. Gate CI on coverage and eval score so regressions fail the build.

---

## B. Product credibility

### 5. Large-scale network engine [C9 + multi-junction] - 3-6 months
**What:** Go beyond one junction: corridors, grids and congestion that spreads between intersections.
**How:** Represent the network as a graph (nodes are junctions, edges are links with length, lanes and speed). Add routing (shortest path with congestion-aware weights) and link-to-junction handoff of vehicles. Start with a 2-junction corridor, then a 3x3 grid, then profile and optimise (vectorised updates, spatial partitioning). Measure congestion propagation with network-level metrics.

### 6. Uncertainty and statistical trust [C6 + stats] - 2-3 months
**What:** Replace "one run, one answer" with confidence.
**How:** Randomise driver behaviour, reaction time and demand from distributions, run many seeds per scenario, and report means with confidence intervals. Add paired significance tests for "is strategy A really better than B?" and a sensitivity analysis (SALib) showing which input matters most. This is the backbone for the evals and the reports.

### 7. Reproducibility, audit trail and results lakehouse - 1-2 months
**What:** Every result can be re-run and compared; all runs are queryable together.
**How:** Store seed, config hash, code version and input data version with every run. Write run outputs as Parquet to S3 (or local disk), then query across runs with DuckDB or Athena and model them with dbt. Add a "diff two runs" view. Use DVC or content-addressed storage for large inputs.

### 8. Auto-generated decision reports - 1 month
**What:** A one-click report a council or manager can read.
**How:** Template the report (Jinja to HTML to PDF), fill it with before/after charts, key metrics with confidence intervals and a plain-language summary. Draft the summary with an LLM but ground it strictly in the computed numbers, and eval it for hallucinated figures.

### 9. Richer metrics - 1 month
**What:** Measures planners and councils actually decide on.
**How:** Add delay per vehicle, travel time, fuel and CO2 (a standard emissions model keyed on speed and acceleration), and safety surrogates such as time-to-collision. Compute them inside the metrics layer so every scenario gets them for free.

### 10. Advisory-only governance - 1 month
**What:** A safe, auditable path from simulation result to a recommendation.
**How:** Model a state machine (draft, proposed, reviewed, approved) with role-based permissions and a full audit log. Add a "shadow mode" that compares the recommended plan against real observed data without acting on it. State clearly in the UI and API that nothing is ever pushed to live signals.

---

## C. Realism and data

### 11. Real networks, calibration and interoperability [N] - ~2 months
**What:** Real roads and real counts, and compatibility with tools engineers already use.
**How:** Import road networks from OpenStreetMap (OSMnx, GeoPandas, PostGIS) and import/export SUMO, GTFS and Synchro formats. Calibrate the simulator against open traffic count datasets by tuning parameters until simulated flows match observed ones, and report the remaining error.

### 12. Emergency and transit priority [C1] - 1-2 months
**What:** Ambulances, fire trucks and buses that get priority.
**How:** Add emergency vehicle types with dedicated behaviour, signal pre-emption (the controller switches or extends a phase when one approaches) and yield/clearance behaviour for surrounding cars. Track response-time metrics and compare strategies with and without priority.

### 13. Incidents, disruptions and weather [C7 + C8] - 2-3 months
**What:** Stress cases: crashes, blocked lanes, closures, event surges, rain, fog, snow.
**How:** Build a scenario generator that injects events at set times. Incidents reduce lane capacity and trigger rerouting. Weather scales speed, acceleration, braking and reaction time, and lowers road friction. Measure recovery time and resilience of each strategy. This extends the existing Stress Lab.

---

## D. Platform engineering

### 14. Digital twin with live data streaming [C10] - 4-6 months
**What:** Compare the simulation against real, continuously updated traffic data.
**How:** Stand up an event backbone (Kafka or Redpanda) with Go consumers that ingest live or replayed sensor feeds. Continuously recalibrate the model, then show prediction-vs-observation in a Grafana-style dashboard. Start with replayed historical data before touching any live feed.

### 15. Observability and reliability - 1 month
**What:** Know it is healthy, and prove it under stress.
**How:** Add OpenTelemetry tracing, Prometheus metrics and Grafana dashboards, and define SLOs (for example, 99% of simulation jobs start within 30 seconds). Verify them with k6 load tests and chaos tests such as killing a worker mid-run.

### 16. Multi-tenant platform - 1-2 months
**What:** Several teams can use it safely.
**How:** Add OIDC login (Cognito or Keycloak), role-based access, per-user quotas and Redis-backed rate limiting. Publish an OpenAPI spec and generate a Python or Go SDK from it.

### 17. Job queue with cost control - 1 month
**What:** Heavy simulation batches without runaway cost.
**How:** Run jobs from a queue with autoscaling workers (KEDA), spot instances (Karpenter), per-user budgets and cost tags. Surface cost per run in the UI.

---

## E. Research showpieces

### 18. RL signal control with MLOps [C2] - 2-3 months
**What:** Learned controllers vs fixed-time and adaptive ones.
**How:** Wrap the simulator as a Gymnasium environment, train DQN and PPO agents (PyTorch or RLlib) on simulated traffic, and compare them against existing controllers using the statistical machinery from idea 6. Track experiments and register models with MLflow, and schedule retraining with Airflow. Identify the conditions where learning helps and where it does not.

### 19. Connected vehicles with hardware-in-the-loop demo [C3 + N] - 2-3 months
**What:** V2V and V2I communication, plus a physical signal head driven by the sim.
**How:** Model a message system with latency, packet loss and imperfect information, and measure cooperative-behaviour effects on flow and safety. Carry messages over MQTT (IoT Core on AWS), then connect a Raspberry Pi or ESP32 "signal head" as a live demo.

### 20. Cooperative autonomy [C4 + C5] - 4-6 months
**What:** Platooning and signal-free intersections for autonomous vehicles.
**How:** Track A: leader-follower platoon controller with formation, merging and splitting, then throughput and stability analysis. Track B: a reservation-based intersection manager where vehicles request time slots, with a conflict-resolution algorithm and safety validation. Both build on idea 19's messaging.

---

## Suggested phasing

1. **Foundation:** 4, 6, 7, 9 (everything else is measured by these)
2. **Scale and realism:** 5, 11, 12, 13
3. **Platform:** 1, 2, 3, 15, 17, 16, 10, 8
4. **Research showpieces:** 18, then 14, 19, 20

Dependencies worth remembering: 14 and 19 share the event backbone; 18 needs 5, 6 and 7; 20 needs 19; the Confluence sizes alone total roughly 24-36 months, so something must be cut or deferred.

## Questions to settle with Khushi

1. Primary user: traffic engineers or researchers? It decides the order in section C vs E.
2. How much of the 20 is realistic for the time we have? What is the cut line?
3. Is there an AWS account and budget, and who owns it?
4. Which two or three ideas best demo to the Director?
5. Should the digital twin (14) use real live data, or replayed data only?
6. Any hard "no" ideas, or ideas missing from this list?
