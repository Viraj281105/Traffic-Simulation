# Operations Guide

> **Status:** Current · V1.5 · detailed runtime behaviour of the backend routes (mounted by `backend/src/main.py`; `live/`, `simulations/`, `study/`, `replays/`, `suites/`, `history/`) and the frontend services.
> **Companions:** [API & WebSocket reference](api/README.md) (every route, inputs, outputs, errors) · [Deployment & operations](deployment/README.md) (architecture, verification, known issues) · [Reproducibility](research/reproducibility.md)

This guide describes the behavior implemented by the backend routes (see [backend architecture](architecture/02-backend-architecture.md) for which package owns which) and the current frontend services. The interactive dashboard (guided comparison and single-strategy views) uses the live-session routes under `/api/simulation/*`; the versioned `/api/v1/*` routes are intended for programmatic runs and study analysis.

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

`roads.lanesPerApproach` specifies the baseline lane count across approaches. Individual approaches can override lanes (`lanes`, V1.2), approach length (`length`, V1.4), lane movements (`laneUse`, V1.4), compass bearing (`bearing`, V1.5), and lane width (`laneWidth`, V1.5) via `roads.approaches[]` (see [06-scenario-configuration-contract.md](architecture/06-scenario-configuration-contract.md#24-roads--road-configuration)). Scenario documents (`format: "urbanflow-scenario"`) can also be validated across strategies using `POST /api/v1/scenarios/validate` or compiled to strategy-specific engine configurations via `POST /api/v1/scenarios/compile`.

Validate engine configurations with `POST /api/v1/configs/validate`, then create the simulation with `POST /api/v1/simulations`. The response contains `simulationId`, `configId`, and `status`. Use the returned ID with:

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

Optional JSON fields are `arrivalRates` (array of vehicles per second), `duration`, `randomSeed`, `name`, and `customConfig`. Without `arrivalRates`, the implementation uses eight tiers from 20 % to 160 % of the measured 1-lane capacity (`0.069` through `0.556` vehicles/second; `backend/src/study/calibration.py`). Each rate runs signal and roundabout engines with the same seed and stores both runs plus a sweep session in SQLite.

Retrieve saved sweeps with `GET /api/v1/study/sweeps` (summaries: `id`, `name`, `created_at`) and `GET /api/v1/study/sweeps/{sweepId}` (the full configuration and results). Retrieve historical runs with `GET /api/v1/study/history/runs`; optional query parameters are `limit`, `offset`, `intersection_type`, `seed`, and `batch_id`. A run detail includes `run` metadata and a `metricsTimeline`. Compare two saved runs with:

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

Monte Carlo validation generates random seeds (recorded in the result, not settable) and returns, for delay, throughput (a count) and average queue: means, sample standard deviations, **Student-t** confidence intervals (`ci` at the requested `confidenceLevel` of 0.90, 0.95 (default) or 0.99, and `ci95`), an unpaired **Welch** t-test (`pValue`, `degreesOfFreedom`), Cohen's *d* (positive = signal higher) and `significant` at `alpha = 1 − confidenceLevel`. The three metrics are tested separately with no multiple-comparison correction. The result also carries `method`, `calibration` (the default scenario is the calibrated one-lane comparison; more lanes are reported as exploratory) and `vehicleLimitReachedSeeds` (seeds whose demand was cut off by the per-run vehicle limit; the limit is sized to the scenario unless `traffic.totalVehicles` is set). A non-significant result means the study cannot distinguish the controls, not that they are equal. When no test statistic is defined, `pValue` and `cohensD` are `null`, `significant` is `false` and `untestableReason` says why: `insufficient_data` (fewer than two seeds), `invalid_data` (a non-finite value) or `no_variation` (every seed gave each control the same value, within a relative tolerance of 1e-9, so Welch's t is 0/0 whether or not the means differ). Earlier versions reported `pValue: 1.0` and `cohensD: 0.0` for these cases.

`scenario` takes the dashboard's own scenario body (the same body as `POST /api/simulation/config`) and repeats exactly that scenario — geometry, demand, signal timings, gap acceptance, the live warm-up and the scenario's own duration — over fresh seeds. The comparison results page uses it for its "How reliable is this?" check. `scenario` and `customConfig` are mutually exclusive (422); a scenario the live dashboard would reject is rejected here too (400).

The command-line equivalent is:

```powershell
python scripts/run_full_study.py --help
python scripts/run_full_study.py
```

Use `--output` and the other options shown by `--help` to control output paths and run sizes. The script is separate from the API and writes reports locally.

### Background study jobs and progress

The dashboards start studies as background jobs so the page gets progress while they run:

- `POST /api/v1/study/sweeps/jobs` — same body as `/sweeps/run`.
- `POST /api/v1/study/validate/monte-carlo/jobs` — same body as `/validate/monte-carlo`.

Both return `202` with `{jobId, kind, status, progress, result, error}`. Poll `GET /api/v1/study/jobs/{jobId}` (about once a second) until `status` is `completed` (then `result` is exactly what the synchronous endpoint returns) or `failed` (`error`). `progress` is the backend's own count: `phase` (`queued`, `simulating`, `saving`, `done`), `total` and `completed` simulations, `fraction` (ticks done / ticks total), the simulations `running` now (e.g. `"Tier 3/8 · Roundabout"`), `elapsedSeconds`, and `etaSeconds` (null until at least 20 % is done). At most 4 studies run at once (`429` beyond that); jobs live in server memory, so a restart drops unfinished ones, and finished jobs are kept for an hour.

Every tier/seed × geometry is an independent simulation (each engine has its own seeded random stream), so studies run them in parallel in worker processes (`backend/src/study/runner.py`) and aggregate in the original order: results are identical to running them one after another. `STUDY_WORKERS` sets the number of worker processes: unset = one per CPU up to 8 (a 2-vCPU t3.micro gets 2; each worker is ~40 MB); `N` = exactly N (1–32); `0` = run inline in the API process (the test suite uses this). Because simulations no longer run inside the API process, the API and live streams stay responsive while a study runs.

### Deterministic caches in the engine

Three caches speed up the per-tick hot path without changing any result (`tests/roads/test_lane_lookup_equivalence.py` compares whole trajectories against the original implementations):

- `Lane` precomputes per-segment vectors, lengths and headings once (lane geometry never changes after construction) and finds a distance's segment by bisection.
- `Vehicle.coords` / `heading` are memoised on `(lane, position)` — they are pure functions of those two values, and any change to either recomputes.
- Lane-id parsing in `router.py` (circulating-lane index, lower-cased id) is cached per lane id with `functools.lru_cache`.

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

Saved runs record the git commit of the code that produced them. The Docker build context excludes `.git`, so pass the commit at build time or runs built into the image record `"unknown"`: `GIT_COMMIT=$(git rev-parse HEAD) docker compose up -d --build` (`start.ps1` sets it automatically, to the last commit that changed the backend's image inputs, and leaves it empty — recording `"unknown"` — when those inputs have uncommitted changes; `GET /api/version` reports the value the running backend uses). The value is used only when `.git` is not readable, and must be a 7–40 character hex hash.

## Access Control

Two independent controls, answering two different questions.

### `API_KEY` — what may talk to the backend

When `API_KEY` is set, the backend requires the key on its mutating and
compute-heavy routes, sent as `X-API-Key: <API_KEY>` (or, for scripts,
`Authorization: Bearer <API_KEY>`). When it is unset or empty the check is
disabled, which is the local-development default.

The browser app never carries this key. Anything shipped in a JavaScript bundle
is public, so a key embedded there would protect nothing. Instead nginx attaches
`X-API-Key` to proxied `/api/` and `/ws/` requests on the server side, from its
own `BACKEND_API_KEY` environment variable (see
`frontend/templates/default.conf.template`). The production Compose file wires
both from a single `API_KEY` value:

```bash
API_KEY="$(openssl rand -hex 32)" docker compose up -d
```

The key never reaches a client, and the dashboard keeps working with it set.

The key deliberately does **not** use `Authorization`: that header carries the
signed-in user's Cognito ID token, which nginx passes through untouched so the
backend can identify the user (saved runs, per-user live sessions). A bearer
value equal to the API key is treated as "no user" by the live-session
middleware, so scripts or proxies that still send the key as a bearer token get
the anonymous cookie session rather than a 401. (Before 2026-10-05 nginx
overwrote `Authorization` with the key, which broke both the live dashboard and
sign-in whenever `API_KEY` was set; `tests/api/test_api_key_with_user_tokens.py`
pins the fix.)

In the production topology the backend publishes no ports, so it is only
reachable through nginx. `API_KEY` is defence in depth for anything that reaches
it another way (a shared Docker network, a port published for debugging,
a direct `docker exec`).

**Production: `API_KEY` is mandatory.** `docker-compose.yml` defaults it to
empty (`API_KEY=${API_KEY:-}`), which *disables* the check. Set it on the host
(`.env` or the environment) before every production start, and confirm after a
deploy that a request without the key is refused, e.g.
`curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/api/v2/networks/validate`
from the host must print `401`. Nothing in the repository can verify the
production value; it is an operator check.

### Signed-in users and ownership (`/api/v2`, suites, replays)

The key identifies the proxy, not a person, so every route that runs compute
for a user or stores user data also requires a verified Cognito ID token
(`Authorization: Bearer <token>`). That covers every `/api/v2` route
(calibration, networks, planning), scenario suites and saved replays. Records
belong to their creator; another user's record answers 404 (replays: 403).
Admins — users whose email is in `ADMIN_EMAILS` — can list every calibration
run and suite, including legacy rows stored before those tables had an owner
column; ordinary users never see legacy rows. The owner columns are added
automatically on first use (`ALTER TABLE … ADD COLUMN user_id`); no manual
migration is needed, and existing rows are kept.

**Run history** (`/api/v1/study/history/runs`) follows the same rule for
runs that have an owner: a run saved by a signed-in user (a saved replay, or a
run from their suite's batch) is visible, exportable, comparable and
reproducible only by that user or an admin. Runs without an owner — sweeps
and studies started without signing in — stay public to read, and only an
admin may change their labels. The rule lives in one place,
`backend/src/access.py`. Admin status needs a **verified** email
(`email_verified` in the ID token) listed in `ADMIN_EMAILS`, and the backend
accepts only RS256-signed user-pool tokens.

### Request and workload limits

| Limit | Value | Where |
| --- | --- | --- |
| Concurrent synchronous simulations (sync study routes, the study report export, run reproduction, calibration `POST /runs`, planning `POST /run` and `/{id}/reproduce`) | 2 in total and **1 per client**; further requests get 429 at once | `src/api/request_limits.py` `MAX_SYNC_COMPUTE_REQUESTS`, `MAX_SYNC_COMPUTE_PER_CLIENT` |
| Background study jobs / planning jobs | 4 / 2 | `src/study/jobs.py`, `src/planning/service.py` |
| Steps per run (`duration / timeStep`) | 72,000 (validator and engine) | `src/core/limits.py` `MAX_SIMULATION_TICKS` |
| Simulated duration | 3600 s | schema, `src/study/limits.py` |
| Request body | 1 MiB on `/api/v2/networks/*`, `/api/v2/planning/validate` (app); nginx's default 1 MiB on every proxied request | `src/api/request_limits.py`, nginx |

These are per backend process; the stack runs one. A *client* is the socket
peer address, unless that peer is a configured trusted proxy, in which case it
is the address the proxy reports in `X-Real-IP` (see below). Visitors behind
one NAT count as one client.

**Client identity (`TRUSTED_PROXY_IPS`).** One rule serves both the
synchronous-compute limiter and the failed-authentication limiter
(`client_key` in `src/api/request_limits.py`):

* `TRUSTED_PROXY_IPS` is a comma-separated list of IPv4/IPv6 addresses and
  CIDRs (e.g. `172.18.0.0/16,fd00::/8`). Code default: empty (compose sets it,
  below). An invalid entry
  stops the backend at startup; the error names the entry's position, not its
  text.
* `X-Real-IP` is honoured only when the socket peer is inside that list, and
  only if it is a single valid IP address. A missing or malformed value from a
  trusted proxy falls back to the proxy's own address. `X-Forwarded-For` is
  never used. From any other peer the header is ignored, so rotating it
  does not change a client's identity.
* **Fail-closed caveat:** with the list empty or wrong, every request through nginx
  has nginx's address as its peer, so all visitors share one client: one
  synchronous simulation at a time site-wide, and one shared failed-auth
  counter. Set `TRUSTED_PROXY_IPS` to the nginx container's address to restore
  per-visitor limits.
* `docker-compose.yml` defines a private `urbanflow` network
  (`172.30.77.0/24`, override with `URBANFLOW_SUBNET`) and pins the frontend
  (nginx) container to `172.30.77.10` (`URBANFLOW_FRONTEND_IP`). The backend's
  `TRUSTED_PROXY_IPS` defaults to that one address, so only nginx is trusted and
  visitors keep distinct identities. If the subnet collides with a network on
  your host, change `URBANFLOW_SUBNET` and `URBANFLOW_FRONTEND_IP` together
  (`TRUSTED_PROXY_IPS` follows the frontend address unless set explicitly).
  Trust only the proxy's address, never a range clients can originate from.
  `docker-compose.dev.yml` publishes port 8000 and sets no trusted proxy, so
  there the header is ignored. After deploying, check that two different
  visitors are not counted as one client (for example two hosts each running a
  simulation at once should both be accepted).
* nginx reports `$remote_addr` as `X-Real-IP`. If another proxy or load balancer
  sits in front of nginx, that address is the load balancer's, so all visitors
  collapse into one client again until nginx is configured with the real-IP
  module (`set_real_ip_from` / `real_ip_header`) for that hop. This is not
  configured here.
* Counters are per backend process (the stack runs one).

**Platform quotas (`/api/v3`, W7).**

| Quota | Value | Where |
| --- | --- | --- |
| Requests per personal access token | 60 per minute (429, `Retry-After`, names `perTokenRequestsPerMinute`) | `src/api/auth.py` `check_token_rate`; process-local |
| Simulated seconds per user per UTC day | 86,400, reserved at submission and resume, refunded on cancel (429, or 422 if one experiment exceeds a day) | `UsageStore` in `src/experiments/store.py`, table `uf_usage` |
| Package size | 10 MB uploaded or exported (413) | `src/experiments/limits.py`, body-size middleware |
| Package unpacked size / entries | 50 MB actually read / 50 members | `src/experiments/package.py` |

`GET /api/v3/capabilities` reports all of them.

**No per-IP request-rate limit, deliberately.** The live dashboard polls up to
10 times a second per viewer and the demo is often shown to a room behind one
NAT address, so an nginx `limit_req` sized to stop a flood would also stop a
legitimate audience. The exhaustible resource -- simulation -- is bounded
above. If the deployment is exposed to hostile traffic, add a rate limit at
the edge (ALB/AWS WAF rate-based rule) sized from observed traffic. Residual
risk: one client can fill the four background-job slots (each job bounded by
the study caps and the step ceiling); others then get 429 until they finish.

**WebSocket origin.** `/ws/*` handshakes from a page on another site are
refused (close code 1008): CORS does not cover WebSockets and the browser
would send the visitor's live-session cookie. Same-site pages (the `Host` the
browser connected to; ports are not compared because nginx forwards `Host`
without one), the origins in `CORS_ORIGINS`, and clients that send no
`Origin` (scripts) are accepted (`src/api/ws_origin.py`). Serving the app under a
second hostname needs that origin added to `CORS_ORIGINS`.

`DEV_AUTH_BYPASS=1` (only in `docker-compose.dev.yml`) accepts the local
development token as one fixed local user. Never set it in production.

### Data retention and deletion

| Data | Where | Kept | Deleted by |
| --- | --- | --- | --- |
| Calibration runs (they contain the observations a user typed in) | `uf_calibration_runs` | Until deleted | Owner or admin: `DELETE /api/v2/calibration/runs/{id}` |
| Planning studies (queued, running, finished or failed) | `uf_planning_studies` + memory | Until deleted. Every state is stored; a study a stopped process was still running is shown after restart as **failed — interrupted by a server restart** (it is not resumed; run it again) | Owner: `DELETE /api/v2/planning/{id}` (not while queued or running) |
| Saved replays | `saved_replays` | Until deleted | Owner: `DELETE /api/v1/replays/{id}` |
| Scenario suites | `scenario_suites` | Until removed by an operator | No API route |
| Simulation run history | `simulation_runs`, `run_metrics` | Until removed by an operator | A saved replay's run is deleted with the replay; otherwise no API route. Owned runs are private to their owner; unowned runs are public (see above) |

There is no automatic expiry. Deleting a calibration run does not remove the
copy of its result embedded in planning studies that used it, but those
studies can then no longer be reproduced. Back up `simulation.db` before any
manual clean-up.

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

## Python client, tokens, cancel and packages (`/api/v3`)

**Personal access tokens (PATs).** Create one in a signed-in browser session (`POST /api/v3/tokens`, shown
once, 1–90 days, at most 10 active). A PAT can never create a PAT. Scopes: `experiments:read`,
`experiments:run`, `packages:read`, `packages:write`, `tokens:read` (list your tokens), `tokens:manage` (revoke
them). A token without the scope gets 403; another user's token or experiment is a 404. Failed
authentication is counted per client and audited (`auth_failed`); the audit table is append-only.

**Client.** `sdk/python` is a standard-library package (`pip install ./sdk/python`):

```python
from urbanflow_client import Client
api = Client("https://urbanflow.example", token=os.environ["URBANFLOW_TOKEN"])
result = api.run(experiment_document)               # submit, wait, fetch the result
api.export_package(experiment_id, "run.ufpkg")      # never overwrites an existing file
print(api.verify_package("run.ufpkg")["internallyConsistent"])
```

`URBANFLOW_URL` / `URBANFLOW_TOKEN` are read from the environment; the CLI (`python -m urbanflow_client`)
reads only the environment, never a token argument. The client refuses to send credentials over plain HTTP
(except to loopback), refuses redirects, caps response sizes, and keeps tokens out of `repr`, logs and
exception text. It does not hold the shared `API_KEY`; in a locked-down deployment that key stays with nginx,
so an external SDK needs the gateway pattern still to be decided (see the W7 plan, section 6).

**Cancel and resume.** `POST /api/v3/experiments/{id}/cancel` stops a queued or running experiment: runs not
yet started are skipped, simulations already running in a worker finish (they cannot be interrupted), so the
experiment still counts as active until they do. `POST .../resume` simulates only the missing runs and yields
the result an uninterrupted run would have. The partial result of a cancelled experiment is not exportable.

**Packages (`.ufpkg`).** `GET /api/v3/experiments/{id}/package` (needs `packages:read`) downloads a completed
experiment as a ZIP: `manifest.json`, `experiment.json`, `result.json`, `SHA256SUMS` and optional
`sidecars/*.json|csv|txt`. `POST /api/v3/packages/verify` (needs `packages:write`, raw `application/octet-stream`
body, 10 MB) checks an upload in memory and returns a report; it never runs, imports or stores anything.
Verification enforces: size, entry-count and unpacked-size limits measured on bytes actually read, a
compression-ratio ceiling, no duplicate/absolute/traversing/backslash/drive/dotted/Windows-reserved names, no
links, encryption or exotic compression, no executable or archive content, exact SHA-256 of every member,
manifest/request/result cross-checks and recomputed fingerprints. **Integrity is not authenticity**: a passing
report says the package is internally consistent, not who made it. `replayClass` compares recorded
provenance with this server and is not a re-run.

## Contracts and Metrics

`shared/schemas/config.schema.json` is the validation schema for versioned configuration payloads. `snapshot.schema.json` and `vehicle_state.json` describe shared snapshot and vehicle shapes, although runtime route validation is currently centered on configuration validation. The authoritative metric names and formulas are implemented under `backend/src/metrics/definitions/` and aggregated by `MetricCollector`; the API exposes the resulting dictionary rather than a separate metric envelope.

## Troubleshooting

- If the dashboard cannot reach the backend in native mode, confirm port `8000` is listening and use the Vite proxy or set `VITE_API_URL` and `VITE_WS_URL` explicitly.
- If Docker's frontend health check fails, inspect `docker compose logs frontend backend`; the Nginx image proxies `/api`, `/ws`, and `/health` to the backend service.
- If old study data is unexpected, inspect `DB_PATH` and the active Compose volume before removing anything.
