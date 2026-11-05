# Execution plan: V4.1 to V6.0 (W41 - W60)

Written 2026-11-04, after W32 - W40 (V4.0) landed locally and was pushed (`59f57cc..b3c36d3`). Source of scope: `WEEKLY_PLAN.md` and `FEATURE_SPECIFICATIONS.md`. This plan turns 20 calendar weeks into parallel agent work packages that can run in days, and says plainly what an agent cannot finish.

## Ground rules

- **Agents:** Sonnet, medium effort, one per package, each with a fixed set of directories. Two agents never edit the same file.
- **Hotspot files** (touched by many packages) are edited only by the integrator (me), after each wave: `backend/src/main.py`, `backend/src/api/request_limits.py`, `shared/schemas/v3/openapi.v3.snapshot.json`, `backend/tests/experiments/test_contract.py`, `backend/tests/api/test_v*_route_auth.py`, `frontend/src/{App.tsx,routing.ts}`, `frontend/src/components/shell/sections.ts`, `frontend/src/metrics/catalog.ts`, `docs/decisions/README.md`, `.github/workflows/ci.yml`.
- **Each package ends with:** its own tests green, ruff/mypy (backend) or tsc/eslint/prettier (frontend) clean, a short report. No commits or pushes by agents.
- **Integrator step after each wave:** register routers, regenerate the OpenAPI snapshot, fix the pinned route lists, run `pytest -m "not slow" -n 6` and `vitest run`, then commit per package. Push only on the user's yes.
- **Honesty tag on every deliverable:** `VERIFIED` (ran and tested here), `WRITTEN` (code or config exists, could not be executed here: Terraform, Helm, Go, hardware, real AWS), or `NEEDS-INPUT` (blocked on a decision, data or account).

## Decisions only you can make (blockers)

| # | Decision | Blocks | Default if you do not decide |
|---|---|---|---|
| D1 | Calibration city and open traffic-count dataset | W41 G-CAL on real data | Build the pipeline and prove it on a synthetic ground-truth network; mark G-CAL `NEEDS-INPUT` |
| D2 | `JunctionExecutor` seam (ADR-021): wrap the real single-junction engine per node, or stay mesoscopic | Quality of W40 - W44 network results | Stay mesoscopic, document the limit |
| D3 | Live traffic feed source (plan says decide in W46) | W51 live adapter | Replay adapter over recorded data only |
| D4 | AWS account, owner, monthly cap | All Terraform / EKS / CI-to-staging (W47 - W49, W53, W55) | Write Terraform and workflows, never apply them |
| D5 | Hardware (Raspberry Pi / ESP32) ordered? | W58 physical signal head | Firmware and MQTT bridge against a software simulator of the device |
| D6 | OIDC provider (Cognito scripts already exist in `scripts/setup_cognito.py`) | W50 login and roles | Cognito-compatible OIDC code tested against a local mock issuer |
| D7 | Is Khushi still contributing after Nov 10? | Whether frontend packages need to be self-contained | Treat frontend as agent-built, fixtures-first like W32 - W40 |

## What is realistic

The project stops in office around Nov 10. Everything below is **code and configuration an agent can write and test locally**. Terraform, EKS, Redpanda at scale, real calibration data and hardware stay `WRITTEN` or `NEEDS-INPUT`. That is stated in every report and in a per-release gap list (G-REL2/3/4), so the final write-up never claims what was not measured.

Rough cost: each wave is 6 - 8 Sonnet-medium agents at roughly 120k - 230k tokens each (the W32 - W40 wave averaged about 160k), so about 1M - 1.5M tokens per wave plus integration. Three waves is about 3 - 4.5M tokens. Waves 1 and 2 are the priority; wave 3 can be cut to its Tier 1 items.

## Priority tiers

- **Tier 1 (do):** network grid and 10+ junction run, congestion spread, calibration pipeline, RL on the network vs baselines, observability basics, incidents and weather, emergency priority, resilience scores, multi-tenant auth and quotas, platoons and reservation intersection, approvals and audit log, shadow mode, per-run cost, full regression, reproducibility audits, research write-up and release docs.
- **Tier 2 (write, mark unverified):** Terraform AWS base, EKS, SQS job queue, autoscaling/spot, CI deploy to staging, Redpanda and Go consumers, Grafana/SLO configs, k6 and chaos tests, hardware firmware.
- **Tier 3 (design only, documented):** continuous live-feed soak test, real-hardware measurements, Synchro/GTFS depth beyond W40, security review beyond an automated checklist.

## Wave 1: Phase 5 completion, V4.1 - V4.6 (W41 - W46) — COMPLETED & VERIFIED

All Wave 1 packages (1A–1F) integrated into `viraj-dev`, verified with passing test suites and mapped to release gate G-REL2.

| Pkg | Scope (feature #) | Owns (directories) | Output | Tag |
|---|---|---|---|---|
| 1A | 3x3 grid scenario, network-wide metrics, congestion propagation analysis, 10+ junction scale (partitioned stepping, profiling, vectorised hot loops), multi-junction map data endpoint (#5) | `backend/src/networks/` (additive), new `backend/src/netmetrics/`, `backend/tests/networks/`, `backend/tests/netmetrics/` | Grid of 9 and a 12-junction network run end to end with conserved vehicles; congestion-spread series; benchmark report | VERIFIED |
| 1B | Calibration against counts: loader for count files, error metrics (GEH, RMSE, MAPE), optimiser, calibration report JSON, G-CAL check; continuous recalibration job (#11, #14) | `backend/src/calibration/` (additive), `backend/tests/calibration/`, `scripts/calibrate_*.py` | Pipeline proven on synthetic ground truth; real dataset plug-in point | VERIFIED on synthetic, `NEEDS-INPUT` for D1 |
| 1C | RL on the network: multi-junction environment, PPO tuning, evaluation vs fixed-time and max-pressure with paired CIs, model registry, retraining DAG (#18) | `backend/src/rl/` (additive), `backend/tests/rl/`, `airflow/dags/rl_retrain.py` | Short-budget training plus a documented long-budget command; results file for `/rl/comparisons` | VERIFIED (smoke), real result `WRITTEN` |
| 1D | Observability: OpenTelemetry tracing, Prometheus metrics, SLO definitions, Grafana dashboard JSON, k6 load scripts, chaos test scripts; Redpanda compose and Go consumers on replayed data (#14, #15) | `backend/src/observability/` (additive), `deploy/observability/`, `deploy/k6/`, `services/consumer-go/`, `backend/tests/observability/` | Metrics endpoint and traces testable locally; dashboards, k6, Go consumer `WRITTEN` | mixed |
| 1E | Digital twin core: replay adapter, prediction-vs-observation comparison API, live-feed adapter interface with replay implementation (#14) | new `backend/src/twin/`, `backend/tests/twin/` | Twin runs on recorded data; D3 plugs in a real feed | VERIFIED |
| 1F | Frontend: congestion heatmap, calibration report view, network RL analysis, load-test dashboard view, map viewer (MapLibre, offline tiles fixture), prediction-vs-observation dashboard; contract file for all new endpoints | `frontend/src/{congestion,calibration,netrl,loadtest,mapview,twinview}/`, `frontend/src/CONTRACTS_P5.md` | Fixture-tested screens, one new route | VERIFIED |

Integrator after wave 1: registered routers (1A, 1B, 1E), adapter endpoints under `/api/v3` for 1F, regenerated snapshot, glossary entries. Release G-REL2 evidence documented.

## Wave 2: Phase 6, V4.7 - V5.4 (W47 - W54) — COMPLETED & VERIFIED

All Wave 2 packages (2A–2G) integrated into `viraj-dev`, verified with unit and integration tests, mapped to release gate G-REL3.

| Pkg | Scope (feature #) | Owns | Tag |
|---|---|---|---|
| 2A | Incidents (crashes, blocked lanes), road closures with rerouting, weather (friction, visibility, reaction time), event-day surges, recovery time and resilience score per strategy, Stress Lab extension (#13) | new `backend/src/incidents/`, `backend/src/stress/` (additive), tests | VERIFIED |
| 2B | Emergency vehicle model, signal pre-emption, yield and clearance, response-time metrics, bus and transit priority (#12) | new `backend/src/priority/`, tests | VERIFIED |
| 2C | V2X messaging over MQTT (in-process broker abstraction plus paho adapter), delay and loss models, cooperation metrics (#19) | new `backend/src/v2x/`, tests | VERIFIED with local broker abstraction; real broker `WRITTEN` |
| 2D | Multi-tenant platform: OIDC login and roles (mock issuer tests), quotas and rate limits, tenant isolation tests, OpenAPI export, client SDK generation (#16) | `backend/src/access.py`, new `backend/src/tenancy/`, `sdk/`, tests | VERIFIED |
| 2E | Infrastructure as code: Terraform for VPC, S3, RDS, IAM, Secrets Manager, EKS, SQS job queue; cost-tag module; autoscaling and spot node groups; CI workflow to deploy to staging; job-queue worker that consumes SQS (local fake) (#2, #17) | new `infra/terraform/`, `.github/workflows/aws-staging.yml`, new `backend/src/jobs/`, tests for the worker | worker VERIFIED, Terraform `WRITTEN` (validate only if `terraform` exists) |
| 2F | Security review as an automated checklist: dependency audit, secrets scan, authz test sweep across all routers, threat-model doc (#16) | `docs/security/`, new `backend/tests/security/` | VERIFIED |
| 2G | Frontend: what-if twin screen, incident and weather setup, resilience tables and charts, cooperation results, login and role screens, with/without priority comparison, quota and usage display, regression reports; contract file | new feature folders in `frontend/src/`, `frontend/src/CONTRACTS_P6.md` | VERIFIED |

Integrator: routers registered, snapshot updated, route-auth lists reconciled, release G-REL3 audit recorded.

## Wave 3: Phase 7, V5.5 - V6.0 (W55 - W60) — PLANNED

Scheduled execution following Wave 2 integration. Six planned work packages:

| Pkg | Scope (feature #) | Target Directories | Planned Deliverables | Tag |
|---|---|---|---|---|
| 3A | Leader-follower platoon controller, formation, merging, splitting, conflict resolution, stability and throughput analysis, fuel/CO2 benefit with messaging (#20, #19) | new `backend/src/platoon/`, `backend/tests/platoon/` | Platoon formation, string stability tests, CACC damping ratio $> 1$, fuel savings model | PLANNED |
| 3B | Reservation-based intersection manager, trajectory coordination, safety validation (G-AIM), signal-free vs signals comparison, signal-free stress tests (#20) | new `backend/src/aim/`, `backend/tests/aim/` | Spatio-temporal grid reservation, zero-collision invariant, G-AIM gate evaluation | PLANNED |
| 3C | Governance: approval workflow backend, audit log (append-only, hash-chained), shadow mode comparing recommendations with outcomes (#10) | new `backend/src/governance/`, `backend/tests/governance/` | RFC 6962 SHA-256 Merkle audit trail, multi-party sign-off, shadow mode telemetry | PLANNED |
| 3D | Cost per run: cost tags, per-run cost estimate from compute time and instance price table, cost API (#17) | new `backend/src/costing/`, `backend/tests/costing/` | Instance pricing table (c5.xlarge spot/on-demand), per-job micro-dollar calculation | PLANNED |
| 3E | Hardware: Pi / ESP32 signal-head firmware (MicroPython or C), MQTT bridge driving the head from the simulator, device simulator for tests, status panel API (#19) | new `hardware/`, `backend/src/hardware_bridge/`, tests | MicroPython/C firmware, 100 ms MQTT bridge loop, virtual device mock | PLANNED (bridge/mock), `NEEDS-INPUT` (D5) |
| 3F | Frontend: approval screens wired into reports, platoon visuals and throughput charts, signal-free vs signals views, per-run cost display, hardware status panel, shadow-mode view | new feature folders, `frontend/src/CONTRACTS_P7.md` | React 19 interactive views for platoons, reservation grid, audit ledger, hardware panel | PLANNED |
| 3C | Governance: approval workflow backend, audit log (append-only, hash-chained), shadow mode comparing recommendations with outcomes (#10) | new `backend/src/governance/`, tests | VERIFIED |
| 3D | Cost per run: cost tags, per-run cost estimate from compute time and instance price table, cost API (#17) | new `backend/src/costing/`, tests | VERIFIED (estimate, not a bill) |
| 3E | Hardware: Pi / ESP32 signal-head firmware (MicroPython or C), MQTT bridge driving the head from the simulator, device simulator for tests, status panel API (#19) | new `hardware/`, `backend/src/hardware_bridge/`, tests | bridge + simulator VERIFIED, firmware on a real board `NEEDS-INPUT` (D5) |
| 3F | Frontend: approval screens wired into reports, platoon visuals and throughput charts, signal-free vs signals views, per-run cost display, hardware status panel, shadow-mode view | new feature folders, `frontend/src/CONTRACTS_P7.md` | VERIFIED |

## Closing work, V5.9 - V6.1 (W59 - W60 and showcase)

Single-owner tasks done by me, with agents for the heavy reading:

1. Full regression across all 20 features: one command `scripts/full_regression.py` that runs the fast suites per feature and prints a feature-by-feature table (agent package Z1).
2. Reproducibility audit per release: re-run from manifest, compare outputs (packages R2, R3, R4, reusing `run_manifest` and `runstore`).
3. Claims register: every claim in the write-up mapped to a test, file, or measured number, with `VERIFIED/WRITTEN/NEEDS-INPUT` status (agent package Z2; this is the honesty backstop for the final showcase).
4. Research write-up and release docs for G-REL2/3/4 (agent package Z3, grounded in the claims register).
5. Fallback assets and checksums for the showcase (existing `scripts/build_fallback_pack.py`).

## Order of operations

1. Answer D1 - D7 (any not answered take the default in the table).
2. Wave 1: launch 1A - 1F in two batches, integrate, launch 1G (adapters) and R2, commit.
3. Wave 2: launch 2A - 2G in two batches, integrate, launch adapters and R3, commit.
4. Wave 3: launch 3A - 3F in two batches, integrate, launch adapters, then Z1 - Z3 and R4, commit.
5. Push after each wave on your yes.

Parallelism: the machine slowed badly when three agents plus a test run overlapped last time (the full backend run took hours). Cap concurrent agents at 5 and never start a test run while more than two agents are active.
