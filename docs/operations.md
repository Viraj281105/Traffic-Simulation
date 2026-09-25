# Operations Guide

This guide describes the behavior implemented by `backend/src/main.py` and the current frontend services. The interactive dashboard uses the legacy live routes; the versioned routes are intended for programmatic runs and study analysis.

## Start a Versioned Simulation

The request body is a scenario object. A minimal valid example is:

```json
{
  "simulation": { "duration": 30, "timeStep": 0.1, "randomSeed": 42 },
  "geometry": { "intersectionType": "fixed_time_signal" },
  "traffic": { "arrivalRate": 0.3, "arrivalDistribution": "poisson" },
  "roads": {
    "approachLength": 200,
    "laneWidth": 3.5,
    "lanesPerApproach": 2
  }
}
```

`roads.lanesPerApproach` on the versioned routes is a single integer applied to all four approaches (see `shared/schemas/config.schema.json`). Per-direction lane counts (`{"north": 2, "south": 2, ...}`) are not yet accepted by `POST /api/v1/configs/validate` or `POST /api/v1/simulations` — that object form is currently only produced internally by the legacy live dashboard routes (see [06-scenario-configuration-contract.md](architecture/06-scenario-configuration-contract.md#24-roads--road-configuration)).

Validate it with `POST /api/v1/configs/validate`, then create it with `POST /api/v1/simulations`. The response contains `simulationId`, `configId`, and `status`. Use the returned ID with:

```text
POST /api/v1/simulations/{id}/control       {"action":"start|pause|resume|stop"}
GET  /api/v1/simulations/{id}
GET  /api/v1/simulations/{id}/metrics
GET  /api/v1/simulations/{id}/history
GET  /api/v1/simulations/{id}/history/{tick}
GET  /api/v1/simulations/{id}/report?format=json
GET  /api/v1/simulations/{id}/report?format=csv
```

The status response has `simulationId`, `status`, `elapsed`, and `tick`. The history endpoint returns buffered snapshots (up to 1,000 frames). The report endpoint returns final metrics as JSON or a CSV download. Versioned simulations are held in memory and return 404 after a backend restart.

## WebSockets

The versioned stream is:

```text
ws://localhost:8000/ws/v1/stream?simulationId=<id>
```

It sends a JSON snapshot approximately every 100 ms until the snapshot status is `completed` or `error`. The server does not accept control messages on this socket; use the REST control endpoint. A missing simulation closes with WebSocket code `1008`.

The dashboard-compatible sockets are:

```text
ws://localhost:8000/ws/simulation/live
ws://localhost:8000/ws/simulation/dual
```

They also send JSON snapshots at approximately 10 Hz. The live and dual engines advance only after their play/start actions are called.

## Dashboard Workflow

The dashboard sends a compact form payload to `POST /api/simulation/config`:

```json
{
  "intersectionType": "fixed_time_signal",
  "intersectionSize": 15,
  "laneWidth": 3.5,
  "lanesNorth": 2,
  "lanesSouth": 2,
  "lanesEast": 2,
  "lanesWest": 2,
  "arrivalRate": 0.5,
  "duration": 300,
  "randomSeed": 42
}
```

The server expands it into the internal camelCase scenario configuration. Use `POST /api/simulation/play`, `/pause`, or `/stop`; use `/api/simulation/dual/play`, `/pause`, or `/reset` for the side-by-side signal/roundabout comparison. `GET /api/simulation/dual/status` reports the dual run clock. The compatibility endpoints `/api/simulation/start`, `/stop`, `/reset`, `/status`, and `/single-vehicle` support the polling/demo view; `/single-vehicle` advances its simple state by 0.1 seconds when running.

## Study and Analysis

Run and persist a comparative volume sweep:

```http
POST /api/v1/study/sweeps/run
```

Optional JSON fields are `arrivalRates` (array of vehicles per second), `duration`, `randomSeed`, `name`, and `customConfig`. Without `arrivalRates`, the implementation uses `0.1` through `0.8` vehicles/second. Each rate runs signal and roundabout engines with the same seed and stores both runs plus a sweep session in SQLite.

Retrieve saved sweeps with `GET /api/v1/study/sweeps` and `GET /api/v1/study/sweeps/{sweepId}`. Retrieve historical runs with `GET /api/v1/study/history/runs`; optional query parameters are `limit`, `offset`, `intersection_type`, `seed`, and `batch_id`. A run detail includes `run` metadata and a `metricsTimeline`. Compare two saved runs with:

```json
POST /api/v1/study/history/runs/compare
{"runIdA":"...", "runIdB":"..."}
```

`POST /api/v1/study/history/runs/{runId}/reproduce` re-runs a stored run headlessly from its stored configuration and seed and compares average delay (±0.05 s) and vehicles served (±0.1). It never modifies the stored run. Runs with recorded provenance are re-run to their recorded `elapsed` time (so a run saved part-way through is compared at the same instant) using their recorded time step and duration; older runs keep the full-duration behaviour. Signal-vs-roundabout comparison runs are re-run through the same lockstep orchestrator the live comparison uses and both sides are compared. The response reports `mode`, `reproducedElapsed`, `comparedMetrics`, `discrepancies` and `limitations` (e.g. legacy runs, dashboard-summary configurations, a different or unknown code version); `isDeterministic` is `null` when the stored run had nothing to compare against.

`GET /api/v1/study/history/runs/{runId}/reproducibility` returns the stored run record: `runId`, `name`, `notes`, `tags`, `batchId`, `createdAt`, `status`, `intersectionType`, `runMode` (`single`/`dual`), `seed`, `gitCommitHash`, `pythonVersion`, `configSource` (`engine`: the exact config the engine ran with; `client`: the dashboard's summary, used only when no engine was available), `exactConfig`, `configAvailable`, `timing` (`timeStep`, `duration`, `warmupTime`, `elapsed`), the stored `config` with `simulation.randomSeed` pinned to the recorded seed, `summaryMetrics`, and `savedReplay` (whether its dashboard settings can be restored). Run IDs must match `[A-Za-z0-9_-]{1,128}` (otherwise `400`); unknown IDs return `404`. Runs saved before this record existed return `null` for anything they did not record; `gitCommitHash` is `"unknown"` when the backend could not read its git state (e.g. the Docker image, which excludes `.git`).

`PATCH /api/v1/study/history/runs/{runId}` sets a run's user labels only — `{"name": "...", "notes": "...", "tags": ["..."]}`, each optional (name 1–120 characters, notes up to 4000, at most 20 tags of up to 32 characters, trimmed and de-duplicated). Omitted fields are unchanged; `null`/`[]` clears notes/tags. It never changes the configuration, seed, provenance or metrics, and a rename also updates the History entry.

`GET /api/v1/study/history/runs/{runId}/export?format=json|csv` downloads the run record. JSON contains `exportVersion`, `exportedAt`, `exportedBy` (the exporting server's commit and Python version, distinct from the run's own recorded provenance), `run` (the record above) and `metricsTimeline`. CSV has `section,key,value` rows for the run identity, reproducibility fields, timing, every configuration value (dotted paths; lists as JSON) and every stored metric (raw backend keys; comparison runs as `signal.*` / `roundabout.*`). Values a run did not record are `null` in JSON and empty in CSV — never 0. For catalog labels and units, use the saved-run page's metrics table export.

Validation endpoints are:

```text
POST /api/v1/study/validate/repeatability  {"duration":20,"randomSeed":12345}
POST /api/v1/study/validate/monte-carlo    {"numSeeds":5,"duration":30,"customConfig":{...}}
POST /api/v1/study/validate/monte-carlo    {"numSeeds":5,"scenario":{...}}
GET  /api/v1/study/export?format=json|csv
```

The repeatability check verifies, on **both** the signal and the roundabout engine, vehicle conservation and non-negative speeds every tick, that the signal never shows conflicting greens, and that a same-seed re-run reproduces delay and throughput; the result reports each geometry separately (`geometries`) and lists what was checked (`checked`). It checks internal consistency, not agreement with the real world.

Monte Carlo validation generates random seeds (recorded in the result, not settable) and returns, for delay, throughput (a count) and average queue: means, sample standard deviations, **Student-t** confidence intervals (`ci` at the requested `confidenceLevel` of 0.90, 0.95 (default) or 0.99, and `ci95`), an unpaired **Welch** t-test (`pValue`, `degreesOfFreedom`), Cohen's *d* (positive = signal higher) and `significant` at `alpha = 1 − confidenceLevel`. The three metrics are tested separately with no multiple-comparison correction. The result also carries `method`, `calibration` (the default scenario is the calibrated one-lane comparison; more lanes are reported as exploratory) and `vehicleLimitReachedSeeds` (seeds whose demand was cut off by the per-run vehicle limit; the limit is sized to the scenario unless `traffic.totalVehicles` is set). A non-significant result means the study cannot distinguish the controls, not that they are equal.

`scenario` takes the dashboard's own scenario body (the same body as `POST /api/simulation/config`) and repeats exactly that scenario — geometry, demand, signal timings, gap acceptance, the live warm-up and the scenario's own duration — over fresh seeds. The comparison results page uses it for its "How reliable is this?" check. `scenario` and `customConfig` are mutually exclusive (422); a scenario the live dashboard would reject is rejected here too (400).

The command-line equivalent is:

```powershell
python scripts/run_full_study.py --help
python scripts/run_full_study.py
```

Use `--output` and the other options shown by `--help` to control output paths and run sizes. The script is separate from the API and writes reports locally.

## Replays and Database

Save a completed result with `POST /api/v1/replays`:

```json
{
  "name": "baseline",
  "config": { "simulation": { "duration": 30 }, "geometry": { "intersectionType": "roundabout" } },
  "metrics": { "throughput": 12.0 }
}
```

List with `GET /api/v1/replays`, delete with `DELETE /api/v1/replays/{replayId}`. Saving a replay also creates a completed historical run with batch ID `replay` and the same ID (returned as `runId`). An optional `"mode": "single" | "dual"` marks a comparison; without it, metrics shaped `{signal, roundabout}` imply `dual`. When the request carries the caller's live-session cookie and that session's engine ran with the saved seed, the run stores the engine's exact configuration, seed, elapsed time and timing; otherwise it stores the request's `config`. Every save records the git commit and Python version. Replay responses include a compact `reproducibility` summary (`null` for saves with no run record). When the engine was read, the stored metrics are also the engine's own at the recorded elapsed time (the same collector call that produces every snapshot), not the last snapshot the client happened to receive. Deleting a replay also deletes its run record (same ID).

Volume-sweep runs store each engine's exact configuration (including the controller settings the comparison orchestrator injects) with provenance, so each sweep point can be reproduced on its own.

The SQLite path is controlled by `DB_PATH`. `backend/src/database/db.py` creates these tables on startup:

- `configurations`: JSON configuration records.
- `simulation_runs`: status, elapsed/duration, controller type, seed, arrival rate, batch ID, configuration JSON, summary metrics, timestamp, and (nullable, added in place on older databases) `git_commit` and `provenance_json` — the reproducibility record described above — plus user labels `name`, `notes` and `tags_json`.
- `run_metrics`: one JSON metrics record per run and tick.
- `sweep_sessions`: sweep configuration and complete results JSON.
- `saved_replays`: named configuration and metrics JSON.

SQLite uses WAL mode, a five-second busy timeout, and foreign keys. Docker stores the database in the `traffic_data` named volume; deleting that volume deletes persisted studies and replays.

Saved runs record the git commit of the code that produced them. The Docker build context excludes `.git`, so pass the commit at build time or runs built into the image record `"unknown"`: `GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build` (`start.ps1 -Docker` sets it automatically). The value is used only when `.git` is not readable, and must be a 7–40 character hex hash.

## Access Control

Two independent controls, answering two different questions.

### `API_KEY` — what may talk to the backend

When `API_KEY` is set, the backend requires `Authorization: Bearer <API_KEY>` on
its mutating and compute-heavy routes. When it is unset or empty the check is
disabled, which is the local-development default.

The browser app never carries this key. Anything shipped in a JavaScript bundle
is public, so a key embedded there would protect nothing. Instead nginx attaches
the header to proxied `/api/` and `/ws/` requests on the server side, from its
own `BACKEND_API_KEY` environment variable (see
`frontend/templates/default.conf.template`). The production Compose file wires
both from a single `API_KEY` value:

```bash
API_KEY="$(openssl rand -hex 32)" docker compose up -d
```

The dashboard keeps working unchanged, and the key never reaches a client.
Earlier this was not the case: enabling `API_KEY` protected the backend but
broke the browser demo, so the two were mutually exclusive.

In the production topology the backend publishes no ports, so it is only
reachable through nginx. `API_KEY` is defence in depth for anything that reaches
it another way (a shared Docker network, a port published for debugging,
a direct `docker exec`).

### The access gate — who may use the demo

`API_KEY` does not restrict *who* can drive the demo, because nginx adds the key
for every visitor it proxies. A publicly reachable deployment is therefore open
to anyone who has the URL: they can create simulations, run sweeps and write to
the database.

To restrict that, mount an auth config and its password file into the frontend
container's `/etc/nginx/auth-gate/`:

```bash
htpasswd -c ./demo.htpasswd demo        # creates the password file
```

```yaml
# docker-compose.override.yml
services:
  frontend:
    volumes:
      - ./demo.htpasswd:/etc/nginx/auth-gate/demo.htpasswd:ro
      - ./auth.conf:/etc/nginx/auth-gate/auth.conf:ro
```

```nginx
# auth.conf
auth_basic "Traffic Simulation demo";
auth_basic_user_file /etc/nginx/auth-gate/demo.htpasswd;
```

The server block includes `/etc/nginx/auth-gate/*.conf`, a glob that matches
nothing by default — so the demo stays open unless a deployment opts in. The
browser sends the credentials automatically, so no frontend change is needed.

For a public EC2 demo, prefer restricting access at the security group as well,
and treat the gate as the application-level backstop.

## Contracts and Metrics

`shared/schemas/config.schema.json` is the validation schema for versioned configuration payloads. `snapshot.schema.json` and `vehicle_state.json` describe shared snapshot and vehicle shapes, although runtime route validation is currently centered on configuration validation. The authoritative metric names and formulas are implemented under `backend/src/metrics/definitions/` and aggregated by `MetricCollector`; the API exposes the resulting dictionary rather than a separate metric envelope.

## Troubleshooting

- If the dashboard cannot reach the backend in native mode, confirm port `8000` is listening and use the Vite proxy or set `VITE_API_URL` and `VITE_WS_URL` explicitly.
- If Docker's frontend health check fails, inspect `docker compose logs frontend backend`; the Nginx image proxies `/api`, `/ws`, and `/health` to the backend service.
- If old study data is unexpected, inspect `DB_PATH` and the active Compose volume before removing anything.
