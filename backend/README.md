# UrbanFlow Backend — Simulation Engine & API

A Python 3.11 **FastAPI** application containing UrbanFlow's discrete-time simulation engine (Intelligent Driver Model car-following, fixed-time signal and roundabout controllers), the metric collector, the study layer (volume sweeps, Monte Carlo validation, invariant checks), SQLite persistence, REST routes and WebSocket streams. It is headless: it produces JSON and is the single source of every number the frontend shows.

**Owner:** Viraj Jadhao · **Stack:** Python 3.11, FastAPI, Uvicorn, Pydantic, jsonschema, SQLite, pytest

| Read next | |
| --- | --- |
| Package structure and dependencies | [docs/architecture/02-backend-architecture.md](../docs/architecture/02-backend-architecture.md) |
| What the simulation models | [docs/simulation/methodology.md](../docs/simulation/methodology.md) |
| Every route and stream | [docs/api/README.md](../docs/api/README.md) |
| Metrics | [docs/research/metrics-reference.md](../docs/research/metrics-reference.md) |
| Tests and quality gates | [docs/testing/README.md](../docs/testing/README.md) |

---

## Layout

```
src/
├── main.py           FastAPI app: routes, WebSockets, live sessions, errors, CORS, API key
├── auth.py           Cognito token verification and the local-development bypass
├── core/             engine, clock, configuration models and rules, limits, provenance
├── roads/            road network, lanes, approaches
├── vehicles/         vehicle, IDM, spawner, pool, router, speed profile
├── controllers/      BaseController, fixed-time signal, roundabout, virtual obstacles, factory
├── intersection/     conflict manager (signal) and predictive conflict resolver
├── metrics/          MetricCollector, composite score, definitions/
├── snapshot/         snapshot builder and buffer, dual (lockstep) orchestrator
├── study/            volume sweep, validation, worker pool, jobs, calibration, tolerances, reports
└── database/         SQLite schema and migrations, run/sweep/replay DAOs
```

## Core model in one paragraph

Each tick (Δt = 0.1 s by default) the engine spawns seeded arrivals, updates the controller, then moves every vehicle with the IDM (`a = 2.0`, `b = 3.0 m/s²`, `T = 1.5 s`, `s₀ = 2 m`, `δ = 4`) under curve speed limits, audits for overlaps, and feeds the metric collector, which ignores the first `warmupTime` seconds (30 s by default). The fixed-time signal runs the paired plan `ns_green → ns_yellow → all_red → ew_green → ew_yellow → all_red` (30/4/2 s by default, permissive lefts). The roundabout gives way to circulating traffic using a critical gap (4.0 s) and follow-up time (2.5 s). The `DualSimulationOrchestrator` steps a signal engine and a roundabout engine **in lockstep with the same seed**, so both see identical traffic. Details: [methodology](../docs/simulation/methodology.md).

## Persistence

SQLite at `DB_PATH` (default `backend/simulation.db`; `/app/data/simulation.db` in Docker), WAL mode, 5 s busy timeout, foreign keys. Tables are created and migrated in place on startup by `src/database/db.py`:

| Table | Holds |
| --- | --- |
| `simulation_runs` | One row per persisted run: status, timing, seed, arrival rate, configuration, summary metrics, provenance, name/notes/tags, owner |
| `run_metrics` | Per-tick metric dictionaries for a run |
| `sweep_sessions` | Sweep configuration and complete results |
| `saved_replays` | Saved dashboard runs (name, configuration, metrics, owner) |
| `configurations` | Configuration records |

---

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API at `http://localhost:8000`, OpenAPI docs at `http://localhost:8000/docs`. Useful environment variables: `DB_PATH`, `CORS_ORIGINS`, `API_KEY`, `STUDY_WORKERS`, `DEV_AUTH_BYPASS=1` (accept the dev-server sign-in), `COGNITO_USER_POOL_ID` / `COGNITO_CLIENT_ID` / `AWS_REGION` — see the [configuration reference](../docs/simulation/configuration.md#33-environment).

A quick scripted sweep:

```bash
curl -X POST http://localhost:8000/api/v1/study/sweeps/run \
  -H "Content-Type: application/json" \
  -d '{"arrivalRates": [0.1, 0.2, 0.3, 0.4], "duration": 120, "randomSeed": 1}'
```

The full validated study without a server: `python scripts/run_full_study.py` from the repository root.

## Test

```bash
pytest -m "not slow"     # the CI gate (coverage floor 85 %)
pytest -m slow --no-cov  # full-strength simulation regression sweeps (nightly in CI)
pytest                   # everything
ruff check src/ tests/ && ruff format --check src/ tests/ && mypy src/
```

The `slow` marker selects; it never hides — a bare `pytest` runs every test.

## Docker

`Dockerfile` has a `dev` target (Uvicorn `--reload` on bind-mounted source, used by `docker-compose.dev.yml`) and a `production` target (source copied in, non-root `appuser`, `GIT_COMMIT` build argument recorded with saved runs). The image's health check calls `/health`.
