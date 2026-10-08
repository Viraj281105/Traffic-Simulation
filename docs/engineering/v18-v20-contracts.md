# V1.8 – V2.0 Engineering Handoff: Contracts, Ownership, Order of Work

> **Status:** Design handoff · written against `viraj-dev` @ `9d593a4` (V1.5 foundation) · 2026-10-08
> **Audience:** Viraj's Claude / Antigravity sessions implementing V1.8, V1.9, V2.0.
> **Not in scope here:** V1.6 (safety/environmental) and V1.7 (scenario/what-if) belong to **Khushi**. Nothing below requires, waits for, or edits that work.

## 0. The one rule

**V1.8–V2.0 are additive, read-only consumers of the V1.5 core.** They live in *new* packages, use *new* schemas, *new* DB tables and a *new* API namespace (`/api/v2/…`), and call existing code only through its public functions. If a task seems to need an edit to a file in §5.4 (OFF-LIMITS), stop and write an adapter instead.

---

## 1. Existing contracts (as found in the repo)

| # | Contract | Where it lives | What it is |
|---|---|---|---|
| 1 | **Scenario** | `backend/src/core/scenario.py` | `ScenarioDocument` (Pydantic, `extra="forbid"`, `format="urbanflow-scenario"`, `version=1`). Junction-and-traffic description, control-independent. `approaches.{north,south,east,west}` each `ApproachSpec` or `null` (3-arm), with `lanes`, `length`, `laneUse`, `vehiclesPerHour`, `turning{left,straight,right,uturn?}`, `vehicleMix?`, `bearing?`, `laneWidth?`. Plus `roads`, `vehicles`, `signal`, `roundabout`, `simulation{duration,warmup,seed,…}`, and `advanced` (free-form engine-section merge — the sanctioned research hook). `scenario_fingerprint(doc)` = 16-hex SHA-256 over canonical JSON excluding name/description/preset. |
| 2 | **Compile (scenario → engine config)** | `compile_scenario(doc, strategy)` , strategies `fixed_time \| adaptive \| roundabout` | Engine config conforming to `shared/schemas/config.schema.json`. Same doc ⇒ same geometry/lanes/demand/seed; only `controller` differs. |
| 3 | **Validation** | `validate_scenario(payload, strategies)`; `core/config_validation.py` (`semantic_config_errors`), `core/lane_validation.py`; `POST /api/v1/scenarios/validate`, `/compile`, `/api/v1/configs/validate` | Returns `{valid, errors[], warnings[], byStrategy, design, fingerprint, scenario}`. Errors shared by all strategies listed once; strategy-specific prefixed. |
| 4 | **Run** | `snapshot/dual_orchestrator.DualSimulationOrchestrator(config)` → `engine_signal/engine_roundabout`, `collector_*`, `clock_*`; headless helper `study/runner.simulate_geometry(config, geometry, duration)` and `run_simulation_tasks(tasks, progress)` (process pool, `STUDY_WORKERS`; `0` = inline, used by tests). Engine is `core/engine.SimulationEngine`, fixed Δt (0.1 s), per-engine seeded RNG. **One junction per engine.** | Deterministic: same config + seed ⇒ bit-identical metrics (`tests/study/test_runner.py`). |
| 5 | **Result (one run)** | `simulate_geometry` return: `{metrics, elapsed, steps, config, timeStep, engineDuration, warmupTime}` | `metrics` = `MetricCollector.get_metrics(...)` dict (camelCase). Exited vehicles stay in `engine.pool.exited_vehicles` (never evicted) with `turn_intent`, `route[0].approach` (origin), `spawn_time`, `exit_time`. |
| 6 | **Metrics** | `metrics/collector.py` + `metrics/definitions/*`; docs `docs/architecture/07-metric-contract.md`, `docs/research/metrics-reference.md` | Keys incl. `averageDelay`, `medianDelay`, `throughput`, `throughputRate`, `averageQueueLength`, `maxQueueLength`, `averageStopsPerVehicle`, `speedVarianceIndex`, `travelTimeReliability`, `directionalFairnessIndex`, `collisionCount`, exploratory `minTTC/ttcEventCount/minPET/petEventCount`, `vehicleLimit/vehicleLimitReached`, `vehicleTypeBreakdown`, `approachBreakdown{dir:{exited,averageDelay,active,averageQueueLength,maxQueueLength}}`, `signalTiming{phaseChanges,averageGreenDuration,unusedGreenSeconds,greenUtilisation}`. Warm-up excluded. **Gap:** no per-*movement* (origin→turn) counts and no per-OD travel time. |
| 7 | **Comparison** | `study/control_comparison.run_scenario_comparison(doc, strategies, num_seeds, base_seed, demand_scales, confidence_level, progress)` ; `POST /api/v1/study/control-comparison/{run,jobs}`; `study/validation._calculate_stats` (Student-t CI), `study/tolerances.delays_are_tied`; `DualSimulationOrchestrator` (lockstep signal-vs-roundabout) | Result: `{study:"scenario-comparison", scenario, fingerprint, controls, demandScales, seeds, duration, warmupTime, confidenceLevel, calibration, tieTolerance, collisionCount, compiledConfigs, method, results[{demandScale, demandVph, vehicleLimitReached, controls{strategy:{metric:stats}}, delayComparisons{a_vs_b:…}}], perSeed[]}`. Reusable as-is. |
| 8 | **"Calibration" (existing meaning)** | `study/calibration.py` `calibration_status(config)` | **Capacity calibration against UrbanFlow's own measured curve, not field data.** `{calibrated, lanesPerApproach, mixedTraffic, note}`; `calibrated` only for 1 lane + cars. V1.8 must **not** overload this name — see §2. |
| 9 | **Persistence** | `database/db.py` (SQLite, WAL, `DB_PATH`), tables `configurations, simulation_runs (config_json, summary_metrics_json, provenance_json, git_commit, random_seed…), run_metrics, sweep_sessions, saved_replays`; DAOs in `database/dao.py`, `replay_dao.py`; migrations are inline `ALTER TABLE` in `init_db()` | `get_db_connection()` is the only thing V1.8+ may import from here. |
| 10 | **Provenance / reproducibility** | `core/provenance.py` (`GIT_COMMIT_HASH`, `PYTHON_VERSION`, `build_run_provenance`), `database/dao.describe_reproducibility`, `POST /api/v1/study/history/runs/{id}/reproduce`, `docs/research/reproducibility.md` | Reusable: commit, python, timing, seed, fingerprint. |
| 11 | **API boundary** | `backend/src/main.py` (3083 lines, one FastAPI app): `/api/v1/scenarios/*`, `/api/v1/study/*` (sweeps, history, compare, validate, control-comparison, export), `/api/v1/replays`, `/api/v1/simulations/*`, WS `/ws/v1/stream`, `/ws/simulation/{live,dual}`; auth `src/auth.py` (`require_api_key`, `get_current_user_id`); background jobs `study/jobs.JobRegistry` (`POST …/jobs` → 202 `{jobId}`, `GET /api/v1/study/jobs/{id}`) | Frontend talks via `frontend/src/services/{api,scenarioApi,studyJobs,…}.ts`; routes in `frontend/src/routing.ts` (mirrored by `frontend/templates/default.conf.template` and `vite.config.ts`). |
| 12 | **Shared schemas** | `shared/schemas/{config,snapshot,vehicle_state}.schema.json`; `scripts/validate_schemas.py` globs `shared/schemas/*.json` **top level only** | Joint-owned (CODEOWNERS). A `shared/schemas/v2/` subfolder is invisible to that validator and to existing loaders. |

---

## 2. Architecture map

```
                 ┌──────────────────────────── EXISTING V1.5 CORE (read-only to us) ───────────────────────────┐
                 │ core/scenario.py ─ compile_scenario / validate_scenario / scenario_fingerprint                │
                 │ snapshot/dual_orchestrator.py · study/runner.py (simulate_geometry, run_simulation_tasks)     │
                 │ study/control_comparison.run_scenario_comparison · study/validation._calculate_stats          │
                 │ metrics/collector (output dict) · core/provenance · database/db.get_db_connection · auth      │
                 └───────────────▲───────────────────────▲──────────────────────────▲──────────────────────────┘
                                 │ import (public fns)   │                          │
   ┌─────────────────────────────┴───┐   ┌───────────────┴──────────────┐   ┌───────┴───────────────────────────┐
   │ V1.8  backend/src/calibration/   │   │ V1.9  backend/src/networks/  │   │ V2.0  backend/src/planning/       │
   │  models.py   (observations,      │   │  models.py (Network, Node,   │   │  models.py (Study, Alternative…)  │
   │               result, status)    │   │   Edge, Route, Demand, Result)│   │  runner.py (wraps comparison)     │
   │  movements.py (read-only pool    │   │  validate.py (graph checks)  │   │  indicators.py (registry; V1.6    │
   │               tally, adapter)    │   │  engine.py  (one-way coupled │   │               keys optional)      │
   │  fit.py   (GEH/RMSE/MAPE, grid)  │   │               junction runs) │   │  findings.py (rule-based)         │
   │  runner.py                       │   │  metrics.py (node/edge/net)  │   │  report.py (json/md/csv)          │
   └───────────────┬─────────────────┘   └───────────────┬──────────────┘   └───────────────┬───────────────────┘
                   │  calibrated ScenarioDocument ──────────┘ (node.scenario)                 │ may embed V1.8
                   │  + calibration summary ─────────────────────────────────────────────────►│ status; may run on
                   │                                                                          │ V1.9 network (later)
   ┌───────────────▼──────────────────────────────────────────────────────────────────────────▼───────────────┐
   │ backend/src/api_ext/   router.py (one APIRouter, prefix /api/v2) · jobs.py · store.py (own tables, CREATE   │
   │ IF NOT EXISTS, lazily) ──mounted by ONE line in main.py──►  /api/v2/calibration|networks|planning/…        │
   └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
   shared/schemas/v2/*.schema.json (generated from Pydantic, additive)      frontend/src/features/{calibration,network,planning}/ (new dirs)
```

**Naming guard:** the word *calibrated* already means "inside UrbanFlow's own capacity calibration" (`calibration_status`). V1.8 output uses a distinct field, `fieldCalibration`, and never touches `calibration_status()` or its `calibration` key in study outputs.

**Coupling guard (V1.9):** the engine models one junction. The network layer therefore **composes** junction runs (one-way coupled, §3.2); it does not teach the engine about networks.

**Sibling-work guard (V1.6/V1.7):** V2.0 reads indicators through a *registry of metric-key paths* with `unavailable` as a first-class status. V1.6 keys appearing later light up with a one-line registry edit; V1.7's scenario sets plug in through an `AlternativeSource` adapter. No import of V1.6/V1.7 modules, ever.

---

## 3. Contract definitions

All documents follow the `urbanflow-scenario` convention: `format` string, integer `version`, Pydantic `extra="forbid"`, camelCase, never normalised (a mix summing to 95 % is reported, not rescaled). Every result carries a `meta` block (§3.4). Pydantic models are the source; JSON Schemas are generated into `shared/schemas/v2/` (do not hand-write both).

### 3.1 V1.8 — Real-world input + calibration

**Package:** `backend/src/calibration/` · **API:** `POST /api/v2/calibration/validate`, `POST /api/v2/calibration/jobs`, `GET /api/v2/calibration/{id}`

**Input — `urbanflow-observations` v1**
```jsonc
{
  "format": "urbanflow-observations", "version": 1,
  "name": "Baner Rd / Pashan Rd, weekday AM peak",
  "period": {"label": "08:00–09:00", "durationSeconds": 3600, "source": "manual count 2026-09-18"},
  "approachFlows": [                       // required (≥1)
    {"approach": "north", "vehiclesPerHour": 640}            // or "count" + "durationSeconds"
  ],
  "turningMovements": [                    // optional; movement ∈ left|straight|right|uturn
    {"approach": "north", "movement": "left", "count": 120}  // or "share" (0–1) or "vehiclesPerHour"
  ],
  "vehicleMix": {"car": 0.62, "motorcycle": 0.25, "truck": 0.05, "bus": 0.03, "suv": 0.05},   // junction-wide
  "approachVehicleMix": {"north": {"car": 0.7}},                                                // optional per-arm
  "signal": {                              // optional, only when junction is a signal
    "cycleLengthSeconds": 90, "greensSeconds": {"ns": 40, "ew": 36}, "source": "timing sheet"
  },
  "queues":      [{"approach": "north", "meanVehicles": 8.5, "maxVehicles": 17}],               // optional
  "travelTimes": [{"from": "north", "to": "south", "meanSeconds": 62, "samples": 40}],           // optional
  "quality": {"countMethod": "manual|video|sensor", "notes": ""}
}
```
Request wrapper:
```jsonc
{ "scenario": <ScenarioDocument>,              // junction geometry + control to calibrate
  "observations": <urbanflow-observations>,
  "options": { "strategy": "fixed_time|adaptive|roundabout",   // default: scenario.junction.type
               "seeds": 5, "baseSeed": 1,
               "fit": ["demand","turning","mix"],               // what to set FROM observations (direct, no search)
               "tune": [],                                      // optional bounded search: ["desiredSpeedFactor","tau"] → written to scenario.advanced
               "tolerances": {"gehMax": 5.0, "flowMapePct": 15, "queueMapePct": 30, "travelTimeMapePct": 20},
               "minGehPassShare": 0.85 } }
```

**How V1.8 stays out of the physics:** observed *demand, turning shares and mix* are written into a **copy** of the `ScenarioDocument` (`approaches.*.vehiclesPerHour`, `turning`, `vehicleMix`) — these are existing input fields. Optional behavioural tuning is expressed only through the existing `advanced` merge. Simulated quantities are read from `metrics` plus a **read-only tally of `engine.pool.exited_vehicles`** (origin via `metrics.definitions.approach_breakdown.origin_of`, movement via `vehicle.turn_intent`) to get the per-movement counts the collector lacks (`calibration/movements.py`). Run via `DualSimulationOrchestrator` / `run_simulation_tasks`; no engine edits.

**Output — `urbanflow-calibration-result` v1**
```jsonc
{
  "format": "urbanflow-calibration-result", "version": 1,
  "calibratedScenario": <ScenarioDocument>,     // the fitted copy; original untouched; fingerprint recomputed
  "comparison": {                               // simulated-vs-observed, mean ± CI over seeds
    "approachFlows":    [{"approach","observed","simulated","ci95":[lo,hi],"error":-12.0,"errorPct":-1.9,"geh":0.5,"pass":true}],
    "turningMovements": [{"approach","movement","observed","simulated","error","errorPct","geh","pass"}],
    "vehicleMix":       [{"class","observed","simulated","error"}],
    "signal":           {"greenUtilisation": {...}, "averageGreenDuration": {...}} | null,
    "queues":           [{"approach","observedMean","simulatedMean","error","errorPct","pass"}] | [],
    "travelTimes":      [{"from","to","observed","simulated","error","errorPct","pass"}] | []
  },
  "errors": { "flow": {"rmse","mape","gehPassShare"}, "turning": {...}, "queue": {...}|null, "travelTime": {...}|null },
  "fieldCalibration": {                         // NOT calibration_status()
    "status": "calibrated | partially_calibrated | not_calibrated | insufficient_data",
    "criteria": [{"name":"flow GEH<5 on ≥85% of approaches","met":true}],
    "dataCoverage": {"flow":true,"turning":true,"mix":true,"signal":false,"queue":false,"travelTime":false},
    "caveats": ["No queue observations: queue behaviour unvalidated", "…"],
    "engineCapacityCalibration": <study.calibration.calibration_status(config)>   // embedded verbatim, read-only
  },
  "tuning": {"parameters":[{"name","value","range"}], "evaluations": 0},         // empty unless options.tune used
  "meta": <§3.4>
}
```
`status` rule (documented, deterministic): `insufficient_data` if no `approachFlows`; `calibrated` if flow GEH pass-share ≥ `minGehPassShare` **and** every provided optional series meets its MAPE tolerance **and** no `vehicleLimitReached`; `partially_calibrated` if flow passes but ≥1 optional series fails or only flow+nothing else is provided; else `not_calibrated`. The demand-driven fit is *input assimilation* — the result must say so in `caveats`; GEH on flow that was itself an input is trivially met, so the judging series are turning, queue, travel time, signal.

### 3.2 V1.9 — Network representation / multi-junction foundation

**Package:** `backend/src/networks/` · **API:** `POST /api/v2/networks/validate`, `POST /api/v2/networks/jobs`, `GET /api/v2/networks/{id}`

**Input — `urbanflow-network` v1**
```jsonc
{
  "format": "urbanflow-network", "version": 1, "name": "Two-junction corridor",
  "nodes": [
    {"id": "J1", "kind": "junction", "scenario": <ScenarioDocument> | {"ref": "<saved-id>"}},   // junction reference
    {"id": "J2", "kind": "junction", "scenario": {...}},
    {"id": "O1", "kind": "origin"}, {"id": "D1", "kind": "destination"}                          // gates; no sim
  ],
  "edges": [
    {"id": "E1", "from": {"node": "J1", "arm": "east"}, "to": {"node": "J2", "arm": "west"},   // arm = junction slot (exit side → entry side)
     "lengthMeters": 420, "lanes": 2, "speedLimit": 13.89,                                      // lane metadata
     "laneWidth": 3.5, "direction": "oneway"},
    {"id": "E2", "from": {"node": "O1"}, "to": {"node": "J1", "arm": "west"}, "lengthMeters": 150, "lanes": 2, "speedLimit": 13.89}
  ],
  "routes": [ {"id": "R1", "origin": "O1", "destination": "D1", "path": ["E2","E1","E5"]} ],     // ordered edge ids
  "demand": [ {"routeId": "R1", "vehiclesPerHour": 600, "vehicleMix": {"car": 1.0}} ],           // OD/route demand
  "simulation": {"duration": 300, "warmup": 30, "seed": 1, "seeds": 3}
}
```
Validation (pure, no sim): unique ids; edge ports reference existing nodes and **existing arms** (a `null` arm is an error); each arm used by at most one edge per direction; routes are connected edge chains whose turns at each junction are one of left/straight/right/uturn; `lanes` of an edge ≥ lanes of the receiving arm or a warning; **graph must be acyclic in V1.9** (cycle ⇒ error "cyclic networks need iteration; not supported in V1.9"); total vehicle limit guard (`core/limits.demand_vehicle_limit`).

**Execution model (V1.9, deliberately minimal):** *sequential, one-way coupled composition.* Topologically order junctions. For each junction, per-arm inflow = external route demand entering that arm + upstream junction's measured **departure rate on the connecting arm** (from the V1.8-style movement tally of the upstream run, per seed). Edge adds free-flow travel time `length/speedLimit` (no platoon dispersion, no spillback — stated limitation). Junction runs are ordinary `compile_scenario` + orchestrator runs with `vehiclesPerHour`/`turning` rewritten on a *copy*; per-route turning shares are derived from `routes`. Same seed policy as studies ⇒ deterministic. Route-level demand → node turning shares is an aggregation step in `networks/engine.py`; it never touches `Router`/`Spawner`.

**Output — `urbanflow-network-result` v1**
```jsonc
{
  "format": "urbanflow-network-result", "version": 1,
  "network": {"fingerprint": "…", "nodeCount": 2, "edgeCount": 5, "executionModel": "one-way-coupled-sequential"},
  "network_level": {"totalThroughput","vehicleHoursDelay","meanDelayPerVehicle","meanRouteTravelTime","vehicleLimitReached"},
  "perNode": { "J1": {"metrics": <subset of §1.6 incl. approachBreakdown, signalTiming>, "inflowByArm": {...}, "fingerprint": "…",
                       "fieldCalibration": <from V1.8 if the node scenario was calibrated> | null } },
  "perEdge": { "E1": {"flowVph","freeFlowSeconds","estimatedSeconds","utilisation"} },
  "perRoute": { "R1": {"demandVph","estimatedTravelSeconds","delayShare":{"J1":…,"J2":…}} },
  "limitations": ["Edges carry flow, not vehicles: no queue spillback…", "…"],
  "meta": <§3.4>
}
```

### 3.3 V2.0 — Integrated planning / decision support

**Package:** `backend/src/planning/` · **API:** `POST /api/v2/planning/validate`, `POST /api/v2/planning/jobs`, `GET /api/v2/planning/{id}`, `GET /api/v2/planning/{id}/report?format=json|md|csv`

**Input — `urbanflow-planning-study` v1**
```jsonc
{
  "format": "urbanflow-planning-study", "version": 1, "name": "…", "objective": "reduce AM peak delay",
  "subject": {"scenario": <ScenarioDocument>} | {"network": <urbanflow-network>},   // network optional/late
  "calibration": {"resultRef": "<id>"} | null,                                      // V1.8 attach
  "alternatives": [                                                                 // first = baseline
    {"id": "base", "label": "Existing fixed-time", "strategy": "fixed_time", "patch": {}},
    {"id": "adaptive", "label": "Adaptive", "strategy": "adaptive", "patch": {"signal": {…}}},
    {"id": "rbt", "label": "Roundabout", "strategy": "roundabout", "patch": {"roundabout": {"circulatingLanes": 2}}}
  ],                                                                                // patch = JSON merge-patch over a ScenarioDocument copy, then validate_scenario
  "controls": {"signalPlan": {…} | null, "adaptive": {…} | null},                   // maps onto scenario.signal / scenario.advanced.controller
  "demand": {"scales": [0.8, 1.0, 1.2], "growthLabel": "2030 +20%"},                // × scenario demand
  "repetitions": {"seeds": 10, "baseSeed": 1, "confidenceLevel": 0.95},
  "indicators": ["performance","safety","environmental","reliability"]
}
```
`patch` is applied only to the V1.4/V1.5 document fields; unknown paths are rejected by `ScenarioDocument` strictness — that *is* the validation.

**Output — `urbanflow-planning-result` v1**
```jsonc
{
  "format": "urbanflow-planning-result", "version": 1,
  "summary": {"baseline": "base", "alternatives": 3, "scales": [..], "seeds": 10, "recommendationBasis": "…"},
  "indicators": {                                       // per alternative × demand scale, mean ± CI, from the §1.7 comparison
    "performance":   {"averageDelay","throughput","averageQueueLength","maxQueueLength","averageStopsPerVehicle"},
    "safety":        {"status":"exploratory|available|unavailable","collisionCount","minTTC","ttcEventCount","…V1.6 keys when present…"},
    "environmental": {"status":"unavailable|available","source":"v1.6 | null","values":{…},"note":"No emissions model in this build"},
    "reliability":   {"travelTimeReliability","delayAcrossSeedsCI","planningTimeIndex"}
  },
  "comparison": {"vsBaseline": [{"alt","scale","metric","delta","deltaPct","ci95":[..],"verdict":"better|worse|tie|inconclusive"}], "tieTolerance": {…}},
  "findings": [                                         // rule-based, every claim cites evidence
    {"id":"F1","statement":"Adaptive reduces mean delay by 18% (CI 11–25%) at ×1.2 demand","confidence":"high|moderate|low",
     "evidence":[{"path":"indicators.performance.averageDelay","alt":"adaptive","scale":1.2}],
     "caveats":["Exploratory: >1 lane (not capacity-calibrated)"]}
  ],
  "validity": {"fieldCalibration": <V1.8 status | "not_provided">, "engineCapacityCalibration": {…}, "vehicleLimitReached": false, "exploratory": true},
  "report": {                                           // exportable structure (rendered by planning/report.py)
    "title","generatedFor","sections":[{"id":"exec-summary","title","blocks":[{"type":"text|table|chart","…":"…"}]}, …],
    "exports": ["json","md","csv"]
  },
  "meta": <§3.4>
}
```
**Indicator registry (`planning/indicators.py`)** maps each indicator to metric-key paths and a `status` rule, e.g. `safety.collisionCount → metrics.collisionCount`, `environmental.* → []` (→ `unavailable`). V1.6 key names are *unknown today*: the registry is the single place to wire them; `findings.py` must treat `unavailable` as "no claim", never as zero.

**Alternatives adapter:** `planning/alternatives.py` defines `AlternativeSource` (Protocol: `list_alternatives() -> list[AlternativeSpec]`). V2.0 ships `InlineAlternatives`. When V1.7 lands, an additional adapter (written *after* it merges) maps its scenario sets in. Do not import V1.7.

**Execution:** per (alternative, scale): compile and call `run_scenario_comparison` with one strategy per call or group alternatives sharing a document patch; reuse paired-delay machinery against the baseline. Jobs run via `api_ext/jobs.py` (own `JobRegistry`, same class).

### 3.4 Common `meta` block (reproducibility)
```jsonc
"meta": {
  "schemaVersion": 1, "format": "…", "createdAt": "ISO-8601",
  "gitCommit": core.provenance.GIT_COMMIT_HASH, "pythonVersion": core.provenance.PYTHON_VERSION,
  "scenarioFingerprints": {"<alt|node>": "scenario_fingerprint(...)"},
  "inputFingerprint": "sha256-16 of canonical request (observations / network / study)",
  "seeds": [1,2,3], "baseSeed": 1, "timeStep": 0.1, "duration": 300, "warmupTime": 30,
  "compiledConfigs": {"<id>": <compile_scenario output, first seed>},
  "engineModel": "UrbanFlow V1.5 core", "executionModel": "…",
  "reproduce": {"endpoint": "/api/v2/<kind>/{id}/reproduce", "deterministic": true}
}
```
Re-running the stored request with the same commit must reproduce `comparison/indicators` exactly (add an `…/{id}/reproduce` that re-executes and diffs, modelled on the existing `reproduce_run_endpoint`).

### 3.5 Persistence (new tables only, `api_ext/store.py`)
`uf_observation_sets`, `uf_calibrations`, `uf_networks`, `uf_network_runs`, `uf_planning_studies` — each `id TEXT PK, user_id, name, schema_version INT, request_json, result_json, fingerprint, created_at`. Created with `CREATE TABLE IF NOT EXISTS` on first use via `get_db_connection()`. **Do not edit `database/db.py::init_db()` or the existing DAOs** (V1.7 will add saved-scenario tables there).

---

## 4. Which existing files V1.6 / V1.7 will likely touch

| Work | Likely-touched files |
|---|---|
| **V1.6** safety & environmental | `metrics/collector.py`, `metrics/definitions/safety_conflicts.py`, new `metrics/definitions/*` (emissions), `intersection/predictive_conflicts.py`, `vehicles/vehicle.py`, `vehicles/idm.py` (accel/speed history), `snapshot/builder.py`, `core/config_models.py` + `shared/schemas/config.schema.json` (metrics options), `shared/schemas/snapshot.schema.json`, `study/validation.py`, `study/report_generator.py`, `study/control_comparison.py` (new measures), `docs/research/metrics-reference.md`, `docs/architecture/07-metric-contract.md`, frontend `metrics/catalog.ts`, `metrics/plainLanguage.ts`, `components/{MetricSections,TierMetrics,MetricsSidebar}.tsx`, `components/analytics/SafetyTimelineVisualizer.tsx`, `components/guided/ResultsReport.tsx` |
| **V1.7** scenario / what-if | `core/scenario.py`, `study/control_comparison.py`, `study/jobs.py`, `main.py` (new `/api/v1/…` endpoints, request models), `database/db.py` + `dao.py` (saved scenarios / batches), `frontend/src/scenario/*`, `components/scenario/*`, `components/guided/*`, `components/{ComparePage,ResearchHub,HistoryDashboard}.tsx`, `runs/savedRun.ts`, `services/{api,scenarioApi,studyJobs}.ts`, `routing.ts`, `App.tsx`, `templates/default.conf.template`, `vite.config.ts` |

---

## 5. File ownership boundaries

### 5.1 SAFE FOR V1.8 (Viraj, exclusive)
`backend/src/calibration/**` · `backend/tests/calibration/**` · `shared/schemas/v2/calibration-*.schema.json` · `frontend/src/features/calibration/**` · `docs/engineering/v18-*.md` · `docs/research/calibration.md` (new)

### 5.2 SAFE FOR V1.9 (Viraj, exclusive)
`backend/src/networks/**` · `backend/tests/networks/**` · `shared/schemas/v2/network-*.schema.json` · `frontend/src/features/network/**` · `docs/engineering/v19-*.md` · `docs/simulation/networks.md` (new)

### 5.3 SAFE FOR V2.0 (Viraj, exclusive)
`backend/src/planning/**` · `backend/tests/planning/**` · `shared/schemas/v2/planning-*.schema.json` · `frontend/src/features/planning/**` · `docs/engineering/v20-*.md` · `docs/product/decision-support.md` (new)

### 5.3a Safe for the whole V1.8–V2.0 stream (create once, in the scaffold commit)
`backend/src/api_ext/**` (router, jobs, store) · `backend/tests/api_ext/**` · `shared/schemas/v2/**` · `frontend/src/features/index.ts` (feature registry) · `frontend/src/services/v2/**` (new API client dir — **not** the existing `services/*.ts`) · `backend/tests/test_import_boundary.py`

### 5.4 OFF-LIMITS (read/import public functions only; never edit)
**Simulation physics & engine:** `backend/src/vehicles/**`, `controllers/**`, `intersection/**`, `roads/**`, `core/engine.py`, `core/clock.py`, `core/enums.py`, `snapshot/**`
**Metrics (V1.6 is rewriting):** `backend/src/metrics/**`
**Scenario / config / validation (V1.7 + schemas):** `core/scenario.py`, `core/config_models.py`, `core/config_validation.py`, `core/lane_validation.py`, `core/limits.py`, `core/schema.py`, `shared/schemas/*.json` (top level)
**Studies (V1.6/V1.7 extend):** `backend/src/study/**` (incl. `control_comparison.py`, `jobs.py`, `report_generator.py`, `validation.py`)
**Persistence core:** `database/db.py`, `database/dao.py`, `database/replay_dao.py`
**Existing frontend:** everything under `frontend/src/` outside `features/` and `services/v2/`
**Existing tests:** `backend/tests/**` outside the new subfolders (do not edit shared `conftest.py` — add a local `conftest.py` in each new test folder)

### 5.5 SHARED / CONFLICT RISK — change only via a scaffold commit, as a one-liner, announced
| File | Why | Allowed edit |
|---|---|---|
| `backend/src/main.py` | V1.6/V1.7 add endpoints; 3083-line single file | **One** `app.include_router(api_ext_router)` + import, in scaffold commit only |
| `frontend/src/routing.ts`, `App.tsx`, `templates/default.conf.template`, `vite.config.ts` | V1.7 adds routes; nginx/Vite fallbacks must stay in step (tested by `routing.test.tsx`) | **One** registration hook per file (e.g. spread `FEATURE_ROUTES` from `features/index.ts`); coordinate with Khushi first (CODEOWNERS: `/frontend/` is hers) |
| `backend/requirements.txt`, `pyproject.toml` | Dependency drift | Avoid new deps entirely (pure Python + stdlib; stats helpers already exist in `study/validation.py`) |
| `docs/ROADMAP.md`, `docs/api/README.md`, `README.md`, `docs/README.md` | Both streams update status | Edit last, in the integration branch only, after merging Khushi's changes |
| `.github/workflows/ci.yml`, `backend/tests/conftest.py` | Shared gates | Do not edit |

---

## 6. Conflict risks and mitigations

| # | Risk | Mitigation |
|---|---|---|
| 1 | **`main.py` merge conflicts** (both streams add endpoints) | `/api/v2` router in `api_ext`; single mount line, merged first. |
| 2 | **Name collision: "calibration"** (`study/calibration.py` = engine-capacity calibration) | `fieldCalibration` key; embed existing status verbatim; package named `calibration` is fine (distinct from `study.calibration`) but never re-export. |
| 3 | **V1.6 renames/adds metric keys** | Indicator registry + defensive `.get`; `unavailable ≠ 0`; contract test that every registry path either exists in a real metrics dict or is explicitly listed `unavailable`. |
| 4 | **V1.7 duplicates "alternatives/scenarios/batch"** | V2.0 owns only `AlternativeSpec` (patch over `ScenarioDocument`); `AlternativeSource` adapter later; no shared tables. If V1.7 lands first and offers batch execution, swap the runner internals behind `planning/runner.py` — contract unchanged. |
| 5 | **V1.7 changes `ScenarioDocument` (new optional fields)** | V1.8–V2.0 treat it as opaque: only `model_dump/model_copy`, field writes limited to those listed in §3.1; round-trip through `parse_scenario`. New optional fields can't break us. If V1.7 bumps `version` to 2, `calibration/` and `planning/` read `SCENARIO_VERSION` and fail loudly with a clear error. |
| 6 | **V1.6 adds per-step state to `Vehicle`/collector (perf)** | We never hold engines past a run; tallies read `exited_vehicles` once at the end. |
| 7 | **Shared `JobRegistry` capacity** (`MAX_ACTIVE_JOBS=4`, process pool) | Own registry instance in `api_ext`; reuse `study_workers()` pool size; cap our job concurrency to 2. |
| 8 | **DB schema drift** | Own tables, lazy `CREATE IF NOT EXISTS`; never `ALTER` existing ones. |
| 9 | **`shared/schemas` joint ownership** | Additive `v2/` subfolder (`validate_schemas.py` globs top level only) — still tell Khushi. |
| 10 | **Frontend routes mirrored in nginx + Vite + a test** | Feature routes live under `/app/lab/*`-style prefix registered through one hook; do not hand-edit each file. If this can't be agreed by tomorrow noon, ship V1.8–V2.0 UI as a single route `/app/planning` with internal tabs. |
| 11 | **Accuracy of V1.9 coupling** | Label as `one-way-coupled-sequential` in every output; limitations array mandatory; no claims of spillback. |
| 12 | **Deadline** (tomorrow 16:00) | Cut lines in §8. |

---

## 7. Recommended branch structure

```
main
 └─ viraj-dev  (V1.5, 9d593a4)               ← do NOT commit V1.8+ here
     └─ viraj/v18-v20-base        scaffold: api_ext skeleton + mount line, v2 schema dir, import-boundary test
         ├─ viraj/v1.8-calibration     (calibration/…)
         ├─ viraj/v1.9-network         (networks/…)
         └─ viraj/v2.0-planning        (planning/…)
     └─ viraj/v18-v20-integration  merge of the three + docs (ROADMAP/API README) — last
Khushi: her own V1.6 / V1.7 branches off main or viraj-dev; independent.
```
- Merge `viraj/v18-v20-base` into the three feature branches (not vice-versa) so they share only the scaffold.
- Final: merge Khushi's V1.6/V1.7 into `main` first (or into integration), re-run our contract tests, then merge integration. Because ownership sets are disjoint, expected conflicts = `main.py` mount line, routing hook, docs index files.
- Worktrees/Antigravity sessions: one per feature branch; each session's prompt must include §5 for its stream.

---

## 8. Exact implementation order

**Hour 0–1 — Scaffold (single owner, one session)**
1. `api_ext/{__init__,router,jobs,store}.py` with `/api/v2/health`; mount line in `main.py`; `shared/schemas/v2/` + generator script `backend/src/api_ext/export_schemas.py`; `backend/tests/test_import_boundary.py`; `frontend/src/features/index.ts` (empty registry). Commit → `viraj/v18-v20-base`. **Tell Khushi.**

**Then three parallel streams (separate sessions):**

*V1.8 (≈4–5 h)*
1. `calibration/models.py` (observations, request, result; validators; fingerprint).
2. `calibration/movements.py` (tally of `exited_vehicles`: origin × `turn_intent`, plus per-approach mean queue/delay from `metrics`).
3. `calibration/fit.py` (apply observed demand/turning/mix to scenario copy; GEH/RMSE/MAPE; status rule).
4. `calibration/runner.py` (multi-seed run via `run_simulation_tasks`-style helper, aggregate with `_calculate_stats`).
5. Endpoints + store. 6. (If time) bounded `tune` via `scenario.advanced`.

*V2.0 backend (≈5 h, can start in parallel from models)* — highest demo value, depends only on existing comparison:
1. `planning/models.py` + `alternatives.py` (patch → validate).
2. `planning/runner.py` wrapping `run_scenario_comparison`.
3. `planning/indicators.py` registry (performance/reliability live; safety exploratory from existing keys; environmental `unavailable`).
4. `planning/findings.py` (rules over CIs/verdicts), `report.py` (json/md/csv).
5. Endpoints + store + reproduce.

*V1.9 (≈4 h)*
1. `networks/models.py` + `validate.py` (graph checks, cycle rejection) — pure, testable first.
2. `networks/engine.py` (topological order, inflow derivation using V1.8's movement tally — **import from `calibration.movements`**, the only cross-stream import allowed).
3. `networks/metrics.py` (node/edge/route/network aggregation). 4. Endpoints + store.

**Then:** thin frontend per stream in `frontend/src/features/*` (form + JSON import + results table + export button; reuse existing CSS tokens). V2.0 UI first, V1.8 second, V1.9 last. Integration branch: attach V1.8 result into V2.0 `validity`, optional V1.9 `subject.network` (stretch), docs.

**Cut lines if time runs short (in order):** V1.9 UI → V1.8 `tune` search → V2.0 network subject → V1.8 signal/queue/travel-time series (keep flow/turning/mix) → frontend polish. Never cut: schemas, meta/reproducibility block, validation endpoints, import-boundary test.

---

## 9. Minimal test strategy

Run only fast tests locally: `cd backend && pytest tests/calibration tests/networks tests/planning tests/api_ext -m "not slow"`. Simulations ≤ 60 s sim-time, ≤ 2–3 seeds; use `STUDY_WORKERS=0` (the repo's `conftest.py` autouse fixture already sets inline mode). Do **not** run the slow regression sweeps.

| Layer | Tests |
|---|---|
| **Import boundary** (`tests/test_import_boundary.py`) | AST-scan `calibration/ networks/ planning/ api_ext/`: imports from `src.*` limited to an allowlist (`core.scenario`, `core.provenance`, `core.limits`, `core.enums`, `study.runner`, `study.control_comparison`, `study.validation` (stats helpers), `study.tolerances`, `study.calibration`, `study.jobs`, `snapshot.dual_orchestrator`, `metrics.definitions.approach_breakdown.origin_of`, `database.db`, `auth`, `roads.lane_config.target_direction`). Fails if a future edit couples to V1.6/V1.7 internals. |
| **Schema/contract** | Each Pydantic model round-trips; generated `shared/schemas/v2/*.json` are valid JSON Schema with `$schema`; unknown fields rejected; fingerprints stable across key order. |
| **V1.8 unit** | GEH/RMSE/MAPE on hand-computed values; status rule truth table; observed→scenario write-back (shares sum, 3-arm `null` arms respected). |
| **V1.8 self-consistency (one tiny sim)** | Generate "observations" from a 60 s simulation at seed S, feed back → `gehPassShare == 1`, errors ≈ 0, `status` per rule; same call twice ⇒ identical result and `meta`. |
| **V1.9 unit** | Graph validation table (missing node, null arm, duplicate port, disconnected route, cycle); topological order; inflow derivation from a **fake tally** (no sim). |
| **V1.9 integration (one tiny sim)** | 2-junction chain, 60 s, 2 seeds: downstream inflow on the connecting arm == upstream departures on its exit arm (flow conservation within tolerance); deterministic across runs; `limitations` present. |
| **V2.0 unit (no sim)** | Feed a **canned `run_scenario_comparison` result** to `indicators/findings/report`: every finding cites a resolvable `evidence.path`; `unavailable` indicators never produce claims; `md`/`csv` export non-empty and contain the baseline; patch application rejects unknown fields. |
| **V2.0 integration (one tiny sim)** | 2 alternatives × 1 scale × 2 seeds, 60 s: result validates against schema; `meta.seeds` correct; re-run equals first. |
| **API** | FastAPI `TestClient` (existing `tests/api` pattern, dev-auth bypass): `validate` 200/422, `jobs` 202 → poll → `completed`, `GET` returns stored result, unauthorised user cannot read another user's study. |
| **Regression guard** | Existing suite untouched: `pytest -m "not slow"` must still pass on the integration branch; `git diff --stat main -- <§5.4 paths>` must be empty for our branches (add as a CI-free script `scripts/check_off_limits.sh` if time permits). |

---

## 10. Open handshakes with Khushi (non-blocking)

1. Metric-key names V1.6 will use for safety proxies / emissions → one-line registry update in `planning/indicators.py`.
2. Whether V1.7 changes `ScenarioDocument`/`version`, or adds batch execution → V2.0 runner internals only.
3. Agree the single frontend registration hook (routing.ts / App.tsx / nginx / Vite).
4. Agree that `shared/schemas/v2/` is ours.
