# Weekly plan: V3.1 - V6.1

Same layout as the V2.1 - V3.0 weekly plan. Version goes up by 0.1 every week (V3.1 in W1 to V6.0 in W30), and rolls over at .9 the way V2.9 became V3.0. Weeks run Mon - Fri; the planned date is the Friday.

- **[A]** Simulation core, **[B]** Platform and quality, **[C]** Research and data
- **◆** The Monday of that week is a reserved demo Monday: testing and demo prep only
- Feature numbers (#n) refer to `NEXT_GEN_IDEAS_FOR_DISCUSSION.md`
- Release weeks (W8, W16, W24, W30) tag a public release. All status values start as TO DO.

## Prep

| Week | Dates | Planned | Version and title | Details | Status |
|---|---|---|---|---|---|
| B0 | Oct 28 – Oct 30 | Oct 30, 2026 | **V3.0 Prep – Decisions and setup** | • Plan approved with Khushi<br>• Track ownership and directories agreed<br>• Confirm AWS account, owner, monthly budget cap<br>• Shortlist calibration city and open traffic datasets<br>• Add exam and leave weeks to the calendar | TO DO |

## Release 1 – Trustworthy Results (W1 – W8)

| Week | Dates | Planned | Version and title | Details | Status |
|---|---|---|---|---|---|
| W1 | Nov 2 – Nov 6 | Nov 6, 2026 | **V3.1 W1 – Statistics and test foundation** | • Every run leaves a record<br>• Every push runs the tests<br>• Multi-seed runs available<br>• [A] Random driver and demand models, multi-seed runner (#6)<br>• [B] pytest layout, coverage gate, fixed-seed regression tests, CI on every push (#4)<br>• [C] Run manifest: seed, config hash, code version (#7) | TO DO |
| W2 | Nov 9 – Nov 13 | Nov 13, 2026 | **V3.2 W2 – Confidence intervals and run store** | • "A beats B" reported with confidence interval and p-value<br>• Runs saved on S3<br>• [A] Confidence intervals, paired significance tests (#6)<br>• [B] Property-based tests (vehicle conservation, no negative queues), Copilot eval question set v1<br>• [C] Parquet run store on S3 (#7) | TO DO |
| W3 | Nov 16 – Nov 20 | Nov 20, 2026 | **V3.3 W3 – Sensitivity, metrics and containers** | • Know which input changes the answer most<br>• Services run in containers on a local cluster<br>• [A] Sensitivity analysis (#6), delay and travel-time metrics (#9)<br>• [B] Dockerise services, Helm charts, local kind cluster (#3)<br>• [C] DuckDB queries, compare two runs | TO DO |
| W4 | Nov 23 – Nov 27 | Nov 27, 2026 | **V3.4 W4 – Emissions, safety metrics and CI/CD** | • Fuel, CO2 and collision-risk numbers on every run<br>• CI deploys to the cluster<br>• [A] Fuel and CO2, time-to-collision safety metric (#9)<br>• [B] CI builds and deploys to cluster, Airflow nightly regression (#3)<br>• [C] Gymnasium RL environment, reward, baselines (#18) | TO DO |
| W5 ◆ | Nov 30 – Dec 4 | Dec 4, 2026 | **V3.5 W5 – Reports, eval gate and first RL training** | • Mon Nov 30: Demo D1 prep and testing only<br>• D1 shows: confidence intervals, tests and CI, run store, local Kubernetes<br>• Copilot quality becomes a CI gate<br>• [A] Report generator skeleton, HTML to PDF (#8)<br>• [B] Copilot eval harness, LLM judge, eval gate in CI (#4)<br>• [C] DQN training pipeline, MLflow tracking (#18) | TO DO |
| W6 | Dec 7 – Dec 11 | Dec 11, 2026 | **V3.6 W6 – Go service and report charts** | • First Go service in the data path<br>• Reports show uncertainty<br>• [A] Report charts with confidence intervals (#8)<br>• [B] Go ingest service and protobuf contract (#1)<br>• [C] dbt models over the run store (#7), RL tuning (#18) | TO DO |
| W7 | Dec 14 – Dec 18 | Dec 18, 2026 | **V3.7 W7 – Grounded summaries and Go benchmark** | • AI summaries cannot invent numbers<br>• Go speed-up measured against Python<br>• [A] LLM summary checked against real numbers (#8)<br>• [B] Go gRPC client and benchmark (#1), Airflow batch experiments (#3)<br>• [C] RL vs fixed-time on one junction with confidence intervals (#18) | TO DO |
| W8 | Dec 21 – Dec 25 | Dec 25, 2026 | **V3.8 W8 – Release week: Trustworthy Results** | • Gate G-REL1: CIs and p-values reported, manifest re-run identical, eval and coverage gates enforced, deploys to Kubernetes via CI<br>• Hardening, docs, ADRs, demo build tag<br>• Christmas week: expect reduced availability<br>• [A] Fix list, release docs<br>• [B] Platform runbook, ADRs<br>• [C] Reproducibility audit | TO DO |

## Release 2 – Beyond One Junction (W9 – W16)

| Week | Dates | Planned | Version and title | Details | Status |
|---|---|---|---|---|---|
| W9 ◆ | Dec 28 – Jan 1 | Jan 1, 2027 | **V3.9 W9 – Network model and road import** | • Mon Dec 28: Demo D2 prep and testing only<br>• D2 shows the Release 1 outcome<br>• Real roads start flowing into the simulator<br>• [A] Network graph model and ADR, two-junction corridor (#5)<br>• [B] Import roads from OpenStreetMap (#11)<br>• [C] PPO training, multi-agent design for networks (#18) | TO DO |
| W10 | Jan 4 – Jan 8 | Jan 8, 2027 | **V4.0 W10 – Vehicles between junctions** | • Fixed commitment: V3.0 showcase prep Jan 4 – Jan 6, showcase Thu Jan 7 (capacity reduced this week)<br>• Vehicles travel across a network<br>• Other tools' formats importable<br>• [A] Link-to-junction vehicle handoff, routing (#5)<br>• [B] SUMO import and export, GTFS and Synchro import (#11)<br>• [C] PPO tuning and comparison (#18) | TO DO |
| W11 | Jan 11 – Jan 15 | Jan 15, 2027 | **V4.1 W11 – Grid and calibration** | • Gate G-CAL: simulated flows match real counts within an agreed error<br>• [A] 3x3 grid, network-wide metrics (#5)<br>• [B] Calibrate against open traffic counts, error report (#11)<br>• [C] Model registry, Airflow retraining run (#18) | TO DO |
| W12 | Jan 18 – Jan 22 | Jan 22, 2027 | **V4.2 W12 – Congestion spread and observability** | • See how a jam spreads between junctions<br>• Tracing and metrics live<br>• Event stream running<br>• [A] Congestion propagation analysis (#5)<br>• [B] OpenTelemetry tracing, Prometheus metrics (#15)<br>• [C] Redpanda event stream and schema, Go consumers on replayed data (#14) | TO DO |
| W13 ◆ | Jan 25 – Jan 29 | Jan 29, 2027 | **V4.3 W13 – Speed-ups, dashboards and recalibration** | • Mon Jan 25: Demo D3 prep and testing only<br>• D3 shows: corridor and grid, OSM import, calibration, RL policies<br>• [A] Profiling, vectorisation, partitioning (#5)<br>• [B] Grafana dashboards and SLOs (#15)<br>• [C] Continuous recalibration (#14) | TO DO |
| W14 | Feb 1 – Feb 5 | Feb 5, 2027 | **V4.4 W14 – 10+ junctions and stress tests** | • Network of 10+ junctions runs end to end<br>• System survives load and failures<br>• [A] Scale to 10+ junctions (#5)<br>• [B] k6 load tests, chaos tests (#15)<br>• [C] RL trained and evaluated on the network (#18) | TO DO |
| W15 | Feb 8 – Feb 12 | Feb 12, 2027 | **V4.5 W15 – Map viewer and slack week** | • Network visible on a map<br>• Predicted vs observed traffic side by side<br>• [A] Multi-junction map viewer (#5)<br>• [B] Slack: test debt, docs, hardening<br>• [C] Prediction-vs-observation dashboard (#14) | TO DO |
| W16 | Feb 15 – Feb 19 | Feb 19, 2027 | **V4.6 W16 – Release week: Beyond One Junction** | • Gate G-REL2: real network of 10+ junctions, calibration error reported, RL compared with baselines on the network, dashboards and SLOs live<br>• Order Raspberry Pi / ESP32 hardware this week<br>• Decide live traffic feed source this week<br>• [A] Fix list, release docs<br>• [B] Platform runbook, ADRs<br>• [C] Reproducibility audit | TO DO |

## Release 3 – Resilience and Cloud (W17 – W24)

| Week | Dates | Planned | Version and title | Details | Status |
|---|---|---|---|---|---|
| W17 ◆ | Feb 22 – Feb 26 | Feb 26, 2027 | **V4.7 W17 – Incidents, AWS base and twin scenarios** | • Mon Feb 22: Demo D4 prep and testing only<br>• D4 shows the Release 2 outcome<br>• [A] Crashes and blocked lanes (#13)<br>• [B] AWS base with Terraform: VPC, S3, RDS, IAM, Secrets Manager (#2)<br>• [C] What-if scenarios on the twin (#14) | TO DO |
| W18 | Mar 1 – Mar 5 | Mar 5, 2027 | **V4.8 W18 – Closures, weather and cloud cluster** | • Rain, fog, snow change driver behaviour<br>• Cluster running on AWS<br>• Vehicles can exchange messages<br>• [A] Road closures and rerouting, weather: friction, visibility, reaction time (#13)<br>• [B] Kubernetes on AWS and job queue (SQS) (#2)<br>• [C] Vehicle-to-vehicle messages over MQTT (#19) | TO DO |
| W19 | Mar 8 – Mar 12 | Mar 12, 2027 | **V4.9 W19 – Event surges and AWS staging** | • Each strategy gets a resilience score<br>• Changes deploy to AWS staging automatically<br>• [A] Event-day surges, recovery-time and resilience scores, Stress Lab extension (#13)<br>• [B] CI deploys to AWS staging (#2)<br>• [C] Message delay and loss modelling (#19) | TO DO |
| W20 | Mar 15 – Mar 19 | Mar 19, 2027 | **V5.0 W20 – Emergency vehicles and login** | • Ambulances and fire trucks get priority<br>• Users sign in with roles<br>• [A] Emergency vehicle model, signal pre-emption (#12)<br>• [B] OIDC login and roles (#16)<br>• [C] Cooperation metrics (#19) | TO DO |
| W21 | Mar 22 – Mar 26 | Mar 26, 2027 | **V5.1 W21 – Yielding, quotas and live feed** | • Cars clear the way for emergency vehicles<br>• Per-user limits enforced<br>• Twin reads live-style data<br>• [A] Yield and clearance behaviour, response-time metrics, with/without comparison (#12)<br>• [B] Quotas, rate limits, OpenAPI spec (#16)<br>• [C] Live feed adapter for the twin (#14) | TO DO |
| W22 ◆ | Mar 29 – Apr 2 | Apr 2, 2027 | **V5.2 W22 – Bus priority and SDKs** | • Mon Mar 29: Demo D5 prep and testing only<br>• D5 shows: incidents and weather, emergency priority, AWS deployment, V2X<br>• [A] Bus and transit priority (#12)<br>• [B] Generated client SDKs, tenant-isolation tests (#16)<br>• [C] Cooperative vs non-cooperative experiments (#19) | TO DO |
| W23 | Apr 5 – Apr 9 | Apr 9, 2027 | **V5.3 W23 – Security and autoscaling** | • Two tenants cannot see each other's data<br>• Twin survives a long live run<br>• [A] Slack: regression and resilience reports<br>• [B] Security review (#16), autoscaling and spot nodes begin (#17)<br>• [C] Twin live-mode soak test (#14) | TO DO |
| W24 | Apr 12 – Apr 16 | Apr 16, 2027 | **V5.4 W24 – Release week: Resilience and Cloud** | • Gate G-REL3: resilience scores for every strategy, emergency pre-emption cuts response time, platform on AWS via Terraform and multi-tenant, twin running on live-style feeds<br>• Hardware must be in hand<br>• [A] Fix list, release docs<br>• [B] Platform runbook, ADRs<br>• [C] Reproducibility audit | TO DO |

## Release 4 – Cooperation and Governance (W25 – W30)

| Week | Dates | Planned | Version and title | Details | Status |
|---|---|---|---|---|---|
| W25 | Apr 19 – Apr 23 | Apr 23, 2027 | **V5.5 W25 – Platoon controller and cost control** | • Vehicles can follow a leader closely<br>• Cost of each run visible<br>• [A] Leader-follower platoon controller (#20)<br>• [B] Autoscaling, spot nodes, cost tags, per-run cost (#17)<br>• [C] Reservation-based intersection manager (#20) | TO DO |
| W26 ◆ | Apr 26 – Apr 30 | Apr 30, 2027 | **V5.6 W26 – Platoon changes and approvals** | • Mon Apr 26: Demo D6 prep and testing only<br>• D6 shows the Release 3 outcome<br>• [A] Platoon formation, merging, splitting (#20)<br>• [B] Approval workflow and audit log (#10)<br>• [C] Conflict resolution between vehicles (#20) | TO DO |
| W27 | May 3 – May 7 | May 7, 2027 | **V5.7 W27 – Stability, shadow mode and safety checks** | • Gate G-AIM: signal-free intersection passes safety validation<br>• Recommendations compared against real outcomes without acting<br>• [A] Platoon stability and throughput analysis (#20)<br>• [B] Shadow mode, approval screen wired into reports (#10)<br>• [C] Trajectory coordination, safety validation (#20) | TO DO |
| W28 | May 10 – May 14 | May 14, 2027 | **V5.8 W28 – Platoons with messaging and hardware demo** | • A physical signal head driven by the simulator<br>• Signal-free vs signals compared<br>• [A] Platoons with vehicle messaging, fuel and CO2 benefit (#20, #19)<br>• [B] Raspberry Pi / ESP32 signal head over MQTT / IoT Core (#19)<br>• [C] Signal-free vs signals performance comparison (#20) | TO DO |
| W29 | May 17 – May 21 | May 21, 2027 | **V5.9 W29 – Full regression and polish** | • Whole system re-checked across all 20 features<br>• Research write-up drafted<br>• [A] Full regression across all features<br>• [B] Hardware demo polish, final security and cost review<br>• [C] Signal-free stress tests, research write-up | TO DO |
| W30 | May 24 – May 28 | May 28, 2027 | **V6.0 W30 – Release week: Cooperation and Governance** | • Gate G-REL4: connected vehicles measured on hardware, platoon throughput effect shown, signal-free vs signals compared, approvals with audit trail, cost visible per run<br>• Final hardening, docs, rehearsals<br>• [A] Fix list, release docs<br>• [B] Platform runbook, ADRs<br>• [C] Reproducibility audit, claims register frozen | TO DO |

## Final showcase

| Week | Dates | Planned | Version and title | Details | Status |
|---|---|---|---|---|---|
| Showcase ◆ | May 31 – Jun 2, 2027 | Jun 2, 2027 | **V6.1 Final showcase – Mon May 31, 2027** | • Mon May 31: Demo D7 prep, testing and final demo<br>• Jun 1 – Jun 2: buffer, fixes only<br>• Fallback assets and checksums<br>• Rehearsals and fallback drills | TO DO |
