# UrbanFlow - Final Release Plan

**Window:** Mon 2 Nov 2026 to Fri 28 May 2027 = **30 weeks**, then the final demo on **Mon 31 May**, with 1-2 June as buffer before the 2 June deadline.
**Scope:** all 20 features at full depth. Nothing is cut. Feature numbers (#1-#20) refer to `NEXT_GEN_IDEAS_FOR_DISCUSSION.md`.
**Cadence:** a public release every ~2 months (R1 ~21 Dec, R2 ~19 Feb, R3 ~16 Apr, R4 ~28 May), plus a demo every last Monday of the month.

## How the plan works

### Three parallel tracks
Full scope is about 57 build-weeks of AI-accelerated effort. One person on one stream cannot do that in 30 weeks, so the work runs in three streams:

| Track | Owns | Typical work |
|---|---|---|
| **A - Simulation core** | Sim engine, network, scenarios | Stats, metrics, network engine, disruptions, platooning |
| **B - Platform and quality** | CI/CD, infra, APIs, tests | pytest and evals, K8s, Airflow, Go, AWS, observability, auth, governance |
| **C - Research and data** | Data, ML, advanced experiments | Run store and lakehouse, RL, digital twin, V2X, autonomous intersections |

Tracks own separate directories so they can all commit to `viraj-dev` without feature branches and without colliding. Each track is run by AI agents; **you review and validate.** Review bandwidth, not typing, is the real constraint.

### Demo Mondays (reserved)
The last Monday of every month is used **only** for testing the system and preparing the demo. No feature work.

| Demo | Date | Falls in | What it shows |
|---|---|---|---|
| D1 | Mon 30 Nov | R1 wk 5 | Confidence-interval comparisons, test and CI gates, run store, Kubernetes on a local cluster |
| D2 | Mon 28 Dec | R2 wk 9 | **R1 release**: reports, reproducibility, Airflow, Go service, early RL results |
| D3 | Mon 25 Jan | R2 wk 13 | Corridor and grid network, OSM import, calibration, RL policies, live twin replay start |
| D4 | Mon 22 Feb | R3 wk 17 | **R2 release**: 10+ junction network, observability dashboards, RL on the network |
| D5 | Mon 29 Mar | R3 wk 22 | Incidents and weather, emergency priority, AWS deployment, V2X |
| D6 | Mon 26 Apr | R4 wk 26 | **R3 release**: multi-tenant on AWS, resilience scores, twin, connected vehicles |
| D7 | Mon 31 May | after R4 | **Final demo** of the full system |

**Demo-Monday protocol:**
1. End of the previous Friday: tag a demo build (`demo-YYYY-MM`) and stop merging.
2. Monday morning: deploy the tag to a clean environment and run the full smoke test.
3. Monday midday: write the demo script around what actually works. Record failures in a list instead of fixing them, except blockers.
4. Monday afternoon: rehearse end to end, and record a backup video.
5. Tuesday: back to the plan.

Weeks that contain a demo Monday have 4 working days. The week tables mark them with a diamond.

### Load check
Three tracks over the build weeks give roughly 74 build-weeks of capacity (after the demo Mondays). Full scope needs about 57. That is **~77% load**, which leaves a small buffer. Slack weeks are deliberately placed (wk 15 in B, wk 23 in A, wk 29) for rework, and **if a release runs behind, scope moves inside the release but the date does not.**

---

## Overview

| Release | Weeks | Ships | Theme | Headline |
|---|---|---|---|---|
| **R1** | 1-8 (2 Nov - 25 Dec) | #4, 6, 7, 8, 9, 3, 1 | Trustworthy Results | Defensible A-vs-B answers with confidence intervals, reproducible runs, PDF reports; CI/CD, Kubernetes, Airflow, Go |
| **R2** | 9-16 (28 Dec - 19 Feb) | #5, 11, 15, 18 | Beyond One Junction | A calibrated real network of 10+ junctions from OpenStreetMap, learned RL controllers, observability |
| **R3** | 17-24 (22 Feb - 16 Apr) | #13, 12, 2, 16, 14 | Resilience and Cloud | Incident and weather resilience scores, emergency pre-emption, multi-tenant on AWS, digital twin on live-style feeds |
| **R4** | 25-30 (19 Apr - 28 May) | #19, 20, 17, 10 | Cooperation and Governance | Connected vehicles with hardware demo, platooning and signal-free intersections, cost control, approvals |

#19 starts in R3 (software V2X) and completes in R4 (hardware-in-the-loop). RL (#18) starts in R1 on a single junction and finishes in R2 on the network. AWS is touched from R1 (the run store on S3) so it is not a late surprise for the Director.

---

## R1 - Trustworthy Results (weeks 1-8)

| Wk (start) | Track A: simulation | Track B: platform and quality | Track C: research and data |
|---|---|---|---|
| 1 (2 Nov) | Stochastic driver and demand models; multi-seed runner (#6) | pytest layout, coverage gate, golden-seed tests, CI on every push (#4) | Run manifest: seed, config hash, version (#7) |
| 2 (9 Nov) | Confidence intervals, paired significance tests (#6) | Hypothesis invariants; Copilot eval dataset v1 (#4) | Parquet run store on S3 (#7) |
| 3 (16 Nov) | Sensitivity analysis (#6); metrics v2: delay, travel time (#9) | Dockerise everything; Helm charts; local kind cluster (#3) | DuckDB queries, diff-two-runs (#7) |
| 4 (23 Nov) | Fuel and CO2, time-to-collision (#9) | CI builds and deploys to cluster; Airflow with nightly regression DAG (#3) | Gymnasium environment, reward design, baselines (#18) |
| 5 (30 Nov) ◆ **D1** | Report generator skeleton, HTML to PDF (#8) | Copilot eval harness, LLM judge, CI gate (#4) | DQN training pipeline, MLflow tracking (#18) |
| 6 (7 Dec) | Report charts with confidence intervals (#8) | Go: protobuf contract and ingest service (#1) | dbt models over run store (#7); DQN tuning (#18) |
| 7 (14 Dec) | Grounded LLM summary, hallucinated-number eval (#8) | Go: gRPC client, benchmark, load test (#1); Airflow batch-experiment DAG (#3) | Single-junction RL vs fixed-time and adaptive with CIs (#18) |
| 8 (21 Dec) | **Release week** | **Release week** | **Release week** |

**Exit:** N seeds give a CI and p-value; manifest re-run is identical; one-click PDF; eval and coverage gates enforced in CI; deploys to K8s through CI; Go service is in the data path.
Week 8 is Christmas week; availability will probably be reduced.

## R2 - Beyond One Junction (weeks 9-16)

| Wk (start) | Track A: simulation | Track B: platform and quality | Track C: research and data |
|---|---|---|---|
| 9 (28 Dec) ◆ **D2** | Network graph model and ADR; corridor spike (#5) | OSM import via OSMnx (#11) | PPO training; multi-agent design for networks (#18) |
| 10 (4 Jan) | Link-to-junction handoff, routing (#5) | SUMO import/export; GTFS and Synchro import (#11) | PPO tuning and evaluation with CIs (#18) |
| 11 (11 Jan) | 3x3 grid, network-level metrics (#5) | Calibration against open traffic counts, error report (#11) | Model registry; Airflow retraining DAG (#18) |
| 12 (18 Jan) | Congestion propagation analysis (#5) | OpenTelemetry tracing and Prometheus metrics (#15) | Redpanda and event schema; Go consumers on replayed data (#14) |
| 13 (25 Jan) ◆ **D3** | Profiling, vectorisation, partitioning (#5) | Grafana dashboards and SLOs (#15) | Continuous recalibration loop (#14) |
| 14 (1 Feb) | Scale to 10+ junctions; optimisation (#5) | k6 load tests and chaos tests (#15) | RL on the network: multi-junction training and evaluation (#18) |
| 15 (8 Feb) | Multi-junction map viewer (#5) | Slack: platform hardening, test debt, docs | Prediction-vs-observation dashboard (#14) |
| 16 (15 Feb) | **Release week** | **Release week** | **Release week** |

**Exit:** a real imported network of 10+ junctions runs end to end; calibration error is reported; RL policies compared with baselines on the network; dashboards and SLOs live.

## R3 - Resilience and Cloud (weeks 17-24)

| Wk (start) | Track A: simulation | Track B: platform and quality | Track C: research and data |
|---|---|---|---|
| 17 (22 Feb) ◆ **D4** | Incident generator: crashes, blocked lanes (#13) | Terraform: VPC, S3, RDS, IAM, Secrets Manager (#2) | Twin scenario analysis on the live model (#14) |
| 18 (1 Mar) | Closures, rerouting; weather: friction, visibility, reaction (#13) | EKS and SQS workers via Terraform (#2) | V2X message system over MQTT (#19) |
| 19 (8 Mar) | Event surges, recovery-time and resilience scores, Stress Lab extension (#13) | CI deploys to AWS staging (#2) | Latency and packet-loss modelling (#19) |
| 20 (15 Mar) | Emergency vehicle model, signal pre-emption (#12) | OIDC login and roles (#16) | Cooperative-behaviour metrics (#19) |
| 21 (22 Mar) | Yield/clearance, response-time metrics, with/without comparison (#12) | Quotas, Redis rate limiting, OpenAPI spec (#16) | Live-feed adapter for the twin; source decided by then (#14) |
| 22 (29 Mar) ◆ **D5** | Bus and transit priority (#12) | SDK generation, tenant-isolation tests (#16) | Cooperative vs non-cooperative experiments (#19) |
| 23 (5 Apr) | Slack: regression and resilience reports | Security review (#16); KEDA and Karpenter spot nodes begin (#17) | Twin live-mode soak test (#14) |
| 24 (12 Apr) | **Release week** | **Release week** | **Release week** |

**Exit:** every strategy has a resilience score; emergency pre-emption cuts response time; platform runs on AWS via Terraform, multi-tenant and tested; the twin runs from replayed and live-style feeds.
**Action needed in this release:** order the Raspberry Pi or ESP32 hardware by week 16 so it arrives before R4.

## R4 - Cooperation and Governance (weeks 25-30)

| Wk (start) | Track A: simulation | Track B: platform and quality | Track C: research and data |
|---|---|---|---|
| 25 (19 Apr) | Leader-follower platoon controller (#20A) | KEDA, Karpenter, cost tags, per-run cost (#17) | Reservation-based intersection manager (#20B) |
| 26 (26 Apr) ◆ **D6** | Platoon formation, merging, splitting (#20A) | Governance state machine and audit log (#10) | Conflict-resolution algorithm (#20B) |
| 27 (3 May) | Platoon stability and throughput analysis (#20A) | Shadow mode; approval UI wired to reports (#10) | Trajectory coordination, safety validation (#20B) |
| 28 (10 May) | Platoon plus V2X integration; fuel and CO2 benefit (#20A, #19) | Hardware-in-the-loop signal head over MQTT/IoT Core (#19) | AIM vs signals performance comparison (#20B) |
| 29 (17 May) | Full-system regression across all 20 features | HIL polish; final security and cost review | AIM stress tests; research write-up |
| 30 (24 May) | **Release week:** final hardening, docs, rehearsal | **Release week** | **Release week** |
| - (31 May) ◆ **D7** | **Final demo** | | |
| - (1-2 Jun) | Buffer: fixes only | | |

**Exit:** connected-vehicle experiments show a measured effect and run on a physical signal head; platoons show a throughput effect; signal-free intersections are compared with signals; recommendations pass review and sign-off with an audit trail; costs visible per run.

---

## Risks and mitigations

| Risk | Affects | Mitigation |
|---|---|---|
| Review bandwidth: three tracks produce more than one person can validate | All | Tests and eval gates from R1; short ADRs; slack weeks; demo Mondays double as full-system checks |
| Tracks collide on shared files | All | Separate directories per track; daily merge to `viraj-dev` |
| Open traffic-count data hard to find | R2, R3 | Choose the city and shortlist datasets during R1 |
| No live traffic feed source | R3 (#14) | Decide by week 16; replay-based mode remains the fallback inside the same feature |
| No AWS account or budget approved | R1 S3, R3 | Confirm account, owner and monthly cap before week 5; LocalStack until then |
| Hardware lead time | R4 (#19 HIL) | Order by week 16 |
| Autonomous intersections (#20B) are the riskiest algorithmically | R4 | Starts in week 25 on its own track; weeks 28-29 absorb overrun without touching other work |
| Exams and leave not yet in the plan | Calendar | Add them and shift or reshuffle slack |

## Decisions needed

1. AWS account, owner, and monthly budget cap (by week 5).
2. Calibration city and open datasets (by end of R1).
3. Live feed source for the digital twin (by week 16).
4. Your exam and leave weeks.
