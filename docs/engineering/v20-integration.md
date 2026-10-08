# V1.8 + V1.9 + V2.0 integration

> Status: integrated in one working tree on `viraj-dev` (uncommitted). Written 2026-10-08.
> `v18-v20-conflict-audit.md` (named in the brief) does not exist in the repo; the conflict
> risks in `v18-v20-contracts.md` §6 were used instead. V1.6/V1.7 are not in this tree and
> were not touched.

## What was wired

| Seam | Mechanism |
|---|---|
| V1.8 → V2.0 | `calibration: {runId, useFittedScenario}` on a planning study. `planning/links.py` loads the stored run, checks the study scenario is the run's original or fitted scenario (otherwise a validation error), and carries the status into `validity.fieldCalibration` / `fieldCalibrationDetail`, `calibration`, `meta.calibrationRunId`, `meta.calibrationFingerprint`, caveats, limitations and the report. `GET /api/v2/calibration/runs/{id}/scenario` returns the fitted scenario. |
| V1.9 → V2.0 | Every result has `network`: the scenario as a single-junction `urbanflow-network` (`networks/from_scenario.py`, also `POST /api/v2/networks/from-scenario`), its plan, fingerprint and limitations. `subject.network` is accepted when it has exactly one inline-scenario junction (route-implied volume/turning become the scenario); more than one junction is refused. |
| Fingerprints | scenario fingerprint (calibration `scenario.fittedFingerprint` == study `meta.scenarioFingerprint` == every `meta.scenarioFingerprints[alt]` == the network junction's fingerprint), observations fingerprint, network fingerprint, input and result fingerprints. `result_fingerprint` now also covers `validity`, `calibration`, `network`, so `reproduce` checks them. |
| V1.6/V1.7 shapes | Unchanged: planning still consumes `run_scenario_comparison` output through the indicator registry (`unavailable` ≠ 0). No V1.6/V1.7 module is imported. |
| Schemas | `shared/schemas/v2/{planning-study,planning-report,calibration-observations,calibration-options,network}.schema.json`, regenerated with `python -m src.planning.export_schemas` (checked against the models by a test). |
| Auth | Whole `/api/v2/calibration` router now carries the same API-key dependency as its POST (it was POST-only). Planning is per-user (bearer token); calibration runs and networks are not user-scoped. |
| DB | No migration conflict: `uf_calibration_runs` and `uf_planning_studies` are created lazily with `CREATE TABLE IF NOT EXISTS`; `database/db.py` untouched. |

## Files changed

Existing files: `backend/src/main.py` (three router mounts), `.claude/launch.json` (port-8765 demo server).
Untracked (new): `backend/src/{calibration,networks,planning}/`, `backend/tests/{calibration,networks,planning,v2_integration}/`, `shared/schemas/v2/`, `docs/engineering/`, `docs/product/decision-support.md`, `docs/research/calibration.md`, `scripts/v2_demo.py`.
Integration edits: `calibration/{runner,api}.py`, `networks/{api,from_scenario}.py`, `planning/{links,models,runner,report,export_schemas}.py`, `tests/planning/*` (allow-list; "subject required" assertion), `tests/v2_integration/test_v2_pipeline.py`.

## API (all under `/api/v2`)

| Method / path | Purpose |
|---|---|
| `GET calibration/thresholds` · `POST calibration/validate` | thresholds; check observations vs scenario (no sim) |
| `POST calibration/runs` (201) · `GET calibration/runs` · `GET calibration/runs/{id}` | run + store; list; fetch |
| `GET calibration/runs/{id}/scenario` | fitted scenario + fingerprints (use as planning subject) |
| `POST networks/validate · compile · fingerprint · scenario · result-structure` | stateless network operations |
| `POST networks/from-scenario` | scenario → single-junction network |
| `POST planning/validate` · `POST planning/run` (sync) · `POST planning/jobs` (202) | validate; run; async job |
| `GET planning/{id}` · `GET planning/{id}/report?format=json\|md\|csv` · `POST planning/{id}/reproduce` | result; export; re-run and compare |

Naming differences from the contracts doc (kept, documented rather than renamed): calibration uses `/runs` (synchronous) instead of `/jobs`; networks are stateless (no stored `{id}`); planning has both `/run` and `/jobs`.

## Demo flow (≈1 min)

```
cd backend && DEV_AUTH_BYPASS=1 .venv/Scripts/python.exe -m uvicorn src.main:app --port 8765
.venv/Scripts/python.exe ../scripts/v2_demo.py http://localhost:8765
```
Steps shown: scenario → network model → calibration (fit observed demand) → planning study on the fitted scenario with fixed-time / adaptive / roundabout → performance, safety (exploratory), environmental (proxy) indicators → findings with evidence → fingerprints and `reproduce` → json/md/csv export. Swagger: `http://localhost:8765/docs` (use bearer `urbanflow-local-dev`).

## Verify

```
cd backend
.venv/Scripts/python.exe -m pytest tests/v2_integration tests/calibration tests/networks tests/planning -q --no-cov
.venv/Scripts/python.exe -m ruff check src tests && .venv/Scripts/python.exe -m mypy src
.venv/Scripts/python.exe -m pytest tests -m "not slow" -q --no-cov     # V1.x regression
```

## Known limitations

* Multi-junction networks are validated, compiled and fingerprinted but **not simulated**; `subject.network` runs one junction only. `network.status` says `representation_only` / `single_junction_run`.
* Safety: collision count plus exploratory proxies; environmental: stop-and-go proxies only (no emissions model). V1.6 keys appear via the indicator registry once Khushi's work is merged.
* Calibration "demand" fit is input assimilation (documented in its caveats); a status is only about the compared quantities. A short window (the demo's 50 s) gives a noisy / `POOR` rating by design.
* Calibration runs are synchronous and not user-scoped; no `tune` search.
* No frontend UI exists for V1.8–V2.0 (no `frontend/` files changed, so no typecheck/build was needed or run).

## Frontend integration (when someone builds it)

1. Add a `frontend/src/services/v2/` client (not the existing `services/*.ts`) with the endpoints above; reuse the existing bearer token.
2. One route, e.g. `/app/planning`, with tabs *Scenario → Calibration → Alternatives → Results → Export*; register it through the existing `routing.ts`/`App.tsx`/nginx/Vite hooks together (a test mirrors them) after coordinating with Khushi, who owns `/frontend/`.
3. Drive it from `POST planning/validate` (errors/warnings/fingerprints), `POST planning/jobs` + polling `GET planning/{id}`, and render `results[].performance|safety|environmental|reliability`, `comparison.vsBaseline`, `findings` (cite `evidence[].path`), `validity`, `network`, and `meta`. Offer the three report exports as download links.
4. Never show `status: unavailable` indicators as zero.
