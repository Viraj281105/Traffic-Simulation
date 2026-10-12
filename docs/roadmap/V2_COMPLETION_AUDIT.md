# V2.0 Completion Audit

> **Status:** PROPOSED — planning document, pending review · **Audit date:** 2026-10-12 (Monday) · **Branch:** `viraj-dev` @ `8f6e80f` (+ uncommitted work, see §1)
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Convention note:** [`docs/ROADMAP.md`](../ROADMAP.md) declares itself the *single* roadmap and forbids competing roadmap lists (its §7). These four documents are **proposals** written to the paths requested for this task. Until they are approved, `ROADMAP.md` stays authoritative; on approval its §7 requires a recorded decision there (a V3.0 section) rather than a second roadmap. `ROADMAP.md` was **not** edited by this task.

This audit answers one question: **is everything promised through V2.0 actually finished?** It judges *capability available to a user*, not "a module or endpoint exists". Nothing in the application code, tests or configuration was changed to produce it.

---

## 0. Verdict (read this first)

**V2.0 is NOT release-ready as a "Decision-Support Platform".** The backend half is real, tested and works end to end. The *product* half — the "end-to-end planner workflow … final presentation layer" that the roadmap names as V2.0's experience scope — does not exist: there is **no frontend for V1.8, V1.9 or V2.0** (verified: zero references to `/api/v2` anywhere under `frontend/src`).

| Dimension | Verdict |
| --- | --- |
| Backend capability (calibration comparison, network model, planning studies, reproduction, export) | **Working.** 21-second live run of `scripts/v2_demo.py` passed all six steps, including `reproduced=True`. |
| End-user capability (planner UI) | **MISSING.** Reachable only through Swagger / scripts. |
| Real-world calibration | **Not achieved and not claimable.** The framework compares simulation with observations; nothing is tuned and no real count data has ever been run. |
| Multi-junction simulation | **Not present.** Networks are validated/compiled/fingerprinted; execution is one junction only (documented honestly by the code). |
| Access control on the new API | **Inconsistent; two data-isolation gaps** (§5, M2 and M3). |
| Production deployment | **Unverified.** Both recorded production deploy runs (9 Oct) failed; the pipeline fix is on `main` but not on the `deployment` branch. |
| Documentation | **Contradicts the code** in several places (§6). |

**Six must-fix items** (≈ 7–8 engineer-days with coding agents; detail in §7): **M1** planner UI · **M2** `/api/v2` access control and calibration-run ownership · **M3** private scenario suites · **M4** review and commit the pending hardening work · **M5** documentation and roadmap status sync · **M6** redeploy path for production (user-authorised, not done here).

Nothing here is silently moved into V3.0: M1 is scheduled as **V2.0 closure work** in Sprint 0 and has its own exit gate (see the [sprint plan](V3_WEEKLY_SPRINT_PLAN.md#1-sprint-0--monday-12--sunday-18-october)).

---

## 1. Repository state — brief versus what was verified

The brief said its figures were historical. Here is what is true now.

| Brief said | Verified 2026-10-12 | Note |
| --- | --- | --- |
| Branch `viraj-dev`, three commits ahead of origin | ✅ `viraj-dev`, **ahead 3**, behind 0 | `origin/main` also at `8f6e80f` |
| 11 modified files + 3 new test files, uncommitted | ⚠️ **22 modified + 3 untracked at session start; 23 modified + 3 untracked now** | Backend 8 src + 5 tests, 2 docs, 7 frontend files. One more file, `scripts/run_full_study.py`, was modified **by someone else during this audit** (12:51 IST) — see §8 |
| `.claude/launch.json` intentionally modified/unstaged | ⚠️ **Not modified.** It is tracked (committed in `6e89ccd`) and `git status` shows it clean | Left completely untouched. It contains a `backend-v2-demo` entry on port 8765 |
| 1,081 backend tests passed (not slow), 91.65 % coverage | ✅ **1,099 non-slow tests collected; the full run exited 0; coverage 94.13 %** (floor 85 %) | 190 `slow` tests exist and were **not** run here |
| 379 frontend tests, typecheck, lint, format, build | ✅ **383 tests passed in 3 consecutive runs** (34 files); `tsc --noEmit`, `eslint .`, `prettier --check .` clean | Production `vite build` not run (writes `dist/`); not re-verified |
| Backend ruff / mypy clean | ✅ `ruff check`, `ruff format --check` (199 files), `mypy src` (97 files, strict) clean | |
| Changes not committed or pushed | ✅ true | 26 working-tree entries; this audit committed nothing |

### Checks run in this audit

| Check | Result |
| --- | --- |
| `pytest tests -m "not slow"` with coverage | Pass, exit 0, 94.13 % |
| Same, first attempt (earlier in the audit) | **1 failure**, then not reproducible — explained in §8 |
| `vitest run` ×3, `tsc`, `eslint`, `prettier --check` | Clean |
| Live backend on scratch DB (`DB_PATH` in scratchpad, port 8791, `DEV_AUTH_BYPASS=1`), `scripts/v2_demo.py` | All six steps OK in 21 s |
| Unauthenticated probes against that server | See §5 (run with `API_KEY` unset = dev mode; production behaviour is from reading the code) |
| Headless engine speed (`simulate_geometry`, 1 lane, 500 veh/h/arm, 150 s) | 233 steps/s fixed-time, 405 steps/s adaptive uncontended; **39–48 steps/s** at saturation while a test suite and server ran concurrently |
| `gh run list` (read-only) | CI green on `main` incl. scheduled runs 10–11 Oct; **both production-deploy runs failed** (§4) |
| Not done (by instruction or scope) | No deployment, no docker build, no commit/push, no `slow` suite, no production-side probing, no accessibility tooling run |

---

## 2. How to read the status column

| Status | Meaning here |
| --- | --- |
| **COMPLETE** | Implemented, covered by tests, and observed working in this audit or by CI. Documented limits are intentional and honest. |
| **PARTIAL** | Something real exists but a named part of the promise is absent, unvalidated, or reachable only through a developer interface. |
| **MISSING** | Promised; nothing a user can use exists. |
| **BLOCKED** | Cannot progress without an external decision or action. |
| **UNVERIFIED** | Evidence is absent or could not be gathered without a prohibited action (e.g. deploying). |

Effort is in **engineer-days (ED)** for one engineer working with coding agents, review time included. "Blocks V3" means the V3 plan depends on it being closed first.

---

## 3. Requirement-level audit

### 3.1 V0.1 – V1.0 foundation

| ID | Requirement | Evidence | Status | Why | User-visible impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-01 | V0.1–V0.8: IDM engine, spawner, controllers, metrics, same-seed lockstep comparison, sweeps, Monte-Carlo validation | `backend/src/{vehicles,core,controllers,metrics,study}`; 1,099 non-slow tests pass; scheduled CI green 10 and 11 Oct; [comparative report](../reports/comparative_report.md) | **COMPLETE** | Tests pass, determinism tests exist (`tests/core/test_determinism.py`, `tests/study/test_runner.py`) | Core comparison works | Run the 190 `slow` tests once before V3 baselining (they guard capacity calibration) | 0.25 | No |
| A-02 | V0.9 Containerisation | Multi-stage `backend/Dockerfile`, compose files, nginx template; Docker CI green on `main` 9 Oct | **COMPLETE** | CI builds the images; not rebuilt locally in this audit | Reproducible local/containerised run | None | 0 | No |
| A-03 | V1.0 AWS EC2 deployment | `deploy.yml`, `docs/deployment/*`. `gh run list --workflow deploy.yml`: **2 runs, both `failure`** (9 Oct 09:55 and 12:49 UTC). Fix `8f6e80f` is on `main`; `origin/deployment` is at `6977d20`, *before* the fix | **UNVERIFIED** | No successful deployment is visible in the run history; production state, `API_KEY` and Cognito settings cannot be checked without touching production | Unknown whether the public site runs current code | After M4, a **user-authorised** redeploy of `deployment`, then smoke-test `/health` and `/api/version` commit | 0.5 | Gate by 6 Nov (local demos do not need it) |
| A-04 | V1.0 Browser sign-in (Cognito) + API key + dev bypass | `backend/src/auth.py`; `test_dev_auth_bypass.py`, `test_api_key_*`; dev bypass is opt-in per request | **COMPLETE** (browser users) | Works for the shipped UI. It offers **no credential model for programmatic clients** — see X-02 | Browser users fine | Addressed by V3 platform track | — | No |
| A-05 | V1.0 Reproducibility: provenance per run, reproduce endpoint, JSON/CSV export | `core/provenance.py`, `database/dao.describe_reproducibility`; `test_provenance.py`, `test_run_reproducibility.py`; v2 demo `reproduced=True` | **COMPLETE** | Observed live | Saved runs can be re-run and compared | None | 0 | No |
| A-06 | V1.0 guided product (Compare → Results → reliability → Saved → Research Lab) | 34 frontend test files / 383 tests; routes in `frontend/src/routing.ts` | **COMPLETE** | Tests pass 3×. Automated accessibility (axe/Lighthouse) was **not** run, so accessibility is unverified | Primary UI works | Add an axe pass to CI before V3 UI work | 0.5 | No |

### 3.2 V1.1 – V1.5 capability expansion

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-11 | V1.1 Five vehicle classes, per-class IDM, mix, UI | `vehicles/vehicle_types.py`; `tests/integration/test_vehicle_types_and_lanes.py`, `tests/metrics/test_vehicle_type_breakdown.py` | **COMPLETE** | Class parameters are literature-ordered inputs, not calibrated (documented K4) — mixed results stay "exploratory" | Mixed-traffic runs work, labelled exploratory | None | 0 | No |
| A-12 | V1.2 Multi-lane + MOBIL lane changing | `vehicles/lane_change.py` (444 lines); lane tests | **COMPLETE** | Tested and documented | Lane configuration works | None | 0 | No |
| A-13 | V1.3 Adaptive signal control | `controllers/adaptive_signal.py`; `tests/controllers/test_adaptive_signal.py`, `tests/integration/test_adaptive_signal_runs.py`, API tests; subclass of `FixedTimeSignalController` | **COMPLETE** | Documented limits K17 (perfect detectors, isolated) | Fixed vs adaptive vs roundabout study | None | 0 | No |
| A-14 | V1.4 Advanced roundabouts + full scenario configuration | `core/scenario.py`, `core/lane_validation.py`, `controllers/roundabout.py` (1,250 lines); multi-lane tests | **PARTIAL** (minor) | One- and two-lane rings supported; **three-lane rings are rejected as not validated** by design. The roadmap scope also lists "spiral behaviour" and "weaving", which I could not tie to separate evidence | Scenario builder fully works; large rings unavailable | Record the ≤2-lane limit as the V1.4 final scope in `ROADMAP.md` | 0.25 | No |
| A-15 | V1.5 Real-world junction geometry (3–4 arms, bearings, U-turns) | `roads/junction_geometry.py`; `tests/roads/test_junction_geometry.py`, `tests/integration/test_real_world_junctions_v15.py` | **PARTIAL** | [Validation §4.3](../research/validation.md) states the **60-run slow safety matrix and the full slow regression were not run for V1.5**. Implemented, inadequately validated | Builder works; safety evidence thin | Run `pytest -m slow` (CI job exists; ~hours) and record the result | 0.5 | No — but must be green before any V3 safety claim |

### 3.3 V1.6 – V1.7

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-16 | V1.6 Safety proxies (collisions, near-miss/TTC/PET), safety dashboard | `metrics/definitions/safety_conflicts.py`, `tests/metrics/test_near_miss_tracker.py`, `test_safety_conflicts*.py`; `SafetyTimelineVisualizer` | **PARTIAL** | Real and tested as *implementation*, but the roadmap scope says **validated** proxies and "validation". Docs call them exploratory and say crash risk is not modelled | Safety shown, correctly caveated | Add a validation note (what was checked, what was not); keep "exploratory" labels | 1 | No (but reused by emergency work) |
| A-17 | V1.6 Fuel/CO₂ "where scientifically supportable" | `metrics/definitions/environmental_estimates.py`; `tests/metrics/test_environmental_estimates.py` (200 lines) | **PARTIAL** | A three-term linear fuel model, explicitly "ESTIMATES … NOT calibrated"; same petrol-car constants for every class; `environmentalMetricsAreEstimates` always true | Indicative figures, labelled | Keep the labels; do **not** quote absolute emissions anywhere in V3 | 0 | No |
| A-18 | V1.7 Scenario engine, batch experiments, scenario workflow, comparison UI, reporting | `study/batch.py`, `/api/suites*` (6 routes), suite comparison in `ComparativeDashboard.tsx`, `test_suite_batch.py` (new, uncommitted) | **PARTIAL** | Batch = **arrival-rate sweep of one config, seeds starting at 42**. The real "what-if alternatives" capability is the V2.0 planning API, which has no UI. Two overlapping mechanisms exist | A planner cannot build a what-if study in the UI | Close via the planner UI (M1); freeze suites to their current scope, document overlap | (in M1) | Yes — through M1 |
| A-19 | Suite ownership (prior-audit open question) | `main.py` `create_suite` accepts `user_id` but never stores it; `list_suites` returns every suite; `get_suite` loads each run by id with no owner check | **PARTIAL** (defect) | Any signed-in user can list suites and read other users' run records | Cross-user data exposure | **Decision: private to creator** (M3) | 1 | No, but must-fix |

### 3.4 V1.8 Calibration

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-20 | Observation schema, validation, simulated-vs-observed comparison, GEH/percent-error ratings, `fieldCalibration` status | `calibration/{models,compare,rating,runner,simulate}.py`; 30 tests; [`docs/research/calibration.md`](../research/calibration.md); live demo step 2 | **COMPLETE** (as a comparison framework) | Observed working. Rating of the demo was `POOR` by design (50-second window) — the system reported honestly | API users can test a scenario against counts | None | 0 | No |
| A-21 | Parameter calibration (search / `options.tune`) | The contract ([v18-v20-contracts §3.1](../engineering/v18-v20-contracts.md)) promised `options.tune`; `docs/engineering/v20-integration.md` states "no `tune` search" | **MISSING** | Nothing fits driver parameters. "Demand fit" is *input assimilation*: it writes observed flows into the scenario, and the result flags fitted rows `inputWasFitted` | UrbanFlow cannot be called "calibrated" in any V3 material | Decide explicitly: out of V3 (recommended). State it in V3 limitations | 0 | No (claims constraint) |
| A-22 | Real-world traffic inputs | Only hand-written `urbanflow-observations` JSON. **No real dataset or case study exists in the repo.** No CSV import | **MISSING** | Zero evidence that the framework has met real data | The headline V1.8 promise is untested in the field | Add CSV turning-count import (V3 Sprint 5) and run one real or realistic public dataset if the user can supply one | 2 | No |
| A-23 | End-user access to calibration | No frontend | **MISSING** | `/api/v2/calibration` reachable only by API | Planners cannot use it | Surface inside the planner UI (M1 step "Field data") | (in M1) | Yes — via M1 |

### 3.5 V1.9 Network foundations

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-30 | Network representation, validation, compile, fingerprint, result structure | `networks/{models,validate,compile}.py`; 13 tests; routes under `/api/v2/networks`; live demo step 1 (`nodes=9 routes=12`) | **COMPLETE** (as a foundation) | Pure, stateless, deterministic fingerprints | API users can describe and validate networks | None | 0 | No |
| A-31 | Multi-junction network *simulation* | `networks/execution.py` exists; `v20-integration.md`: "validated, compiled and fingerprinted but **not simulated**"; `subject.network` with >1 junction is refused. The contract's "one-way coupled sequential" execution model was **not delivered** | **PARTIAL** | A foundation, not a capability. Must not be described as network simulation | None today | Keep out of V3 (FS-9 stays Future Scope). Fix wording in README/ROADMAP | 0.25 | No |
| A-32 | Network/scenario visualisation | No frontend | **MISSING** | The roadmap scope names it | None | Out of V3; list as deferred | 0 | No |

### 3.6 V2.0 Decision-support platform

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-40 | Planning API: validate / run / async jobs / fetch / report (json, md, csv) / reproduce | `planning/*`; 27 planning tests + 8 pipeline tests; live demo steps 3–6 (9 simulations, `reproduced=True`, 93 kB JSON / 8 kB md / 4.5 kB csv) | **COMPLETE** | Observed end to end | Works for API users | None | 0 | No |
| A-41 | Evidence-only reporting (no ranking, `unavailable` ≠ 0, tie handling, caveats) | `planning/{findings,indicators,comparison}.py`; demo findings read "inconclusive … 3 seeds could not separate them"; `tests/planning/test_boundary_and_schema.py` | **COMPLETE** | Honest wording observed. Unit tests pin the no-ranking boundary | Matches "evidence, not a verdict" | None | 0 | No |
| A-42 | Integration seams: calibration → planning, network → planning, fingerprint chain | `planning/links.py`; `tests/v2_integration/test_v2_pipeline.py`; JSON Schemas in `shared/schemas/v2/` generated and checked by a test | **COMPLETE** | Fingerprints equal across calibration, study, network (demo step 5) | Traceable results | None | 0 | No |
| A-43 | **End-to-end planner workflow, UX, presentation layer** | `grep -r "api/v2" frontend/src` → **no matches**; `docs/engineering/v20-integration.md` ("No frontend UI exists for V1.8–V2.0") | **MISSING** | This is the named V2.0 experience scope. Backend only | A municipal planner cannot use V2.0 | **M1** — planner UI | 3–4 | **Yes** |
| A-44 | Research validation of the integrated platform | [`docs/research/validation.md`](../research/validation.md) still describes V1.5 and lists V1.6–V2.0 as future; no V1.8–V2.0 validation write-up or case study | **PARTIAL** | Tests prove behaviour, not scientific adequacy | No evidence page for planners/researchers | Write a V2.0 validation addendum (what was checked, what was not) | 1 | No |
| A-45 | Performance | `/run` is synchronous; global cap of 2 planning jobs; ≤240 simulations/study; saturated 600 s run ≈ 6,000 steps at 40–400 steps/s | **PARTIAL** | Fine for demos; an uncertainty ensemble of hundreds of runs will need budgeting and parallelism | Long studies take minutes–hours | Plan compute budgets (V3 Sprint 1/5) | — | Shapes V3 scope |
| A-46 | Persistence | Completed studies persisted to `uf_planning_studies` (best effort); calibration runs in `uf_calibration_runs`; in-flight jobs and failures are in memory only; tables created lazily with `CREATE TABLE IF NOT EXISTS`; no migration framework (inline `ALTER TABLE`) | **PARTIAL** | Adequate for V2.0; adding columns for ownership needs the existing inline-migration pattern | A restart loses running jobs | Use the existing pattern for M2/M3; add a tiny numbered-migration helper in V3 Sprint 0 | 0.5 | No |

### 3.7 Cross-cutting

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| X-01 | Scenario validation | `/api/v1/scenarios/validate`, `/compile`, planning `validate`, networks `validate`; invalid-input tests across modules | **COMPLETE** | Strict `extra="forbid"` documents; explains every rejection | Good errors | None | 0 | No |
| X-02 | **API protection consistency** | Code reading plus probes (below) | **PARTIAL** (defects) | See §5. The nginx proxy attaches the API key to **every** browser request, so a route protected *only* by the API key is effectively public; V2 routers use it as their only guard | Calibration data exposure; anonymous compute | **M2** | 1–1.5 | Yes |
| X-03 | API/contract documentation | `docs/api/README.md` (331 lines) has **no `/api/v2` section** (0 matches); contracts live only in `docs/engineering` | **PARTIAL** | An integrator reading the API reference will not find the planning, calibration or network routes | Integration is guesswork | **M5** | 1 | Yes (for V3 API work) |
| X-04 | Shared-schema validation | `scripts/validate_schemas.py` globs top-level only; `shared/schemas/v2/` is generated and test-checked but invisible to that script | **PARTIAL** | Works, but two mechanisms | None | Fold into CI in V3 Sprint 0 | 0.25 | No |
| X-05 | Runtime consistency | Local venv is **Python 3.14.7**; CI and `Dockerfile` use **3.11**; open Dependabot PR #134 proposes a 3.14.8 image | **PARTIAL** | Results could in principle differ across versions; nothing shows they do | Possible environment drift | Decide one supported version; pin in CI, Docker and the dev docs | 0.5 | Decide in Sprint 0 |

---

## 4. Integration checks (not just unit tests)

| Workflow | How checked | Result |
| --- | --- | --- |
| Scenario → network → calibration (fit demand) → 3-alternative planning study → findings → fingerprints → `reproduce` → three exports | `scripts/v2_demo.py` against a live uvicorn on a scratch database | ✅ All steps OK, 21 s. `reproduced=True`; scenario, calibration and network fingerprints chain; exports 93,571 / 7,996 / 4,501 bytes |
| Finding wording on a tiny study | Demo step 4 | ✅ "inconclusive … 3 seeds could not separate them"; no ranking |
| Calibration rating on a 50-second window | Demo step 2 | ✅ reported `POOR` honestly |
| Statistical edge case (two zero-variance groups, different means) | Reading `study/validation.py` diff + updated tests | ✅ Now returns `cohensD: null`, `pValue: null`, `significant: false`, `untestableReason` — see §6 Q2 |
| Planning study ownership | `tests/planning/test_planning.py` (another user's id → 404 on get and report) | ✅ per-user for planning; ❌ not for calibration or suites |
| Production deployment | `gh run list` only | ❌ both runs failed; fix not yet on `deployment` (A-03) |
| Frontend accessibility of V1.8–V2.0 | — | n/a — no UI exists |

---

## 5. Access-control findings (X-02 detail)

Probes ran against a dev-mode server (`API_KEY` unset, so the key check is a no-op by design); the production conclusions below come from reading the code and the nginx template and are **not black-box proven**.

| Route | Guard | Consequence in production |
| --- | --- | --- |
| `POST /api/v2/planning/validate` | API key only (no user) | Anyone reaching the public host can call it (probe: 200 without any token in dev mode). It compiles scenarios — cheap, but unthrottled |
| `POST /api/v2/planning/run`, `/jobs`, `GET /{id}` … | API key **and** user | Correct; ownership enforced; another user's id is a 404 |
| `/api/v2/calibration/*` (incl. `POST /runs`, `GET /runs`, `GET /runs/{id}`) | API key only | Runs simulations for anonymous visitors, and **lists every stored calibration run** (which holds the observations a municipality typed in). Runs have no owner column |
| `/api/v2/networks/*` | **None** (`include_router(networks_router)` with no dependency) | Public; stateless and pure, but no body-size limit |
| `GET /api/v1/study/sweeps` | None (probe: 200) | Pre-existing V1 behaviour; public list |
| `/api/suites*` | User dependency injected but unused | Any signed-in user reads any suite and its runs (A-19) |

Why "API key only" is not protection: the nginx template adds `X-API-Key` to **every** proxied `/api/` and `/ws/` request, by design, so the browser app can work. The key therefore authenticates *the proxy*, not the person. Routes that need to be private must also depend on `get_current_user_id`.

---

## 6. The prior audit's open questions — decisions

| # | Question | Decision | Evidence | Reopen? |
| --- | --- | --- | --- | --- |
| Q1 | Are scenario suites private or shared? | **Private to the creator** (admins may list all). Consistent with replays and planning studies. Legacy rows with no owner become admin-visible only. Add `user_id` via the existing inline `ALTER TABLE` pattern; scope `list`, `get`, `batch`, `export`. Sharing between users is a later, explicit feature | Defect in A-19; `tests/api/test_replay_ownership.py` is the pattern to copy | **Do (M3)** |
| Q2 | Two zero-variance groups with different means | **Resolved in the working tree (uncommitted).** Both groups' spread ≤ 1e-9 × data scale → `_untestable("no_variation")`; null p and d; `significant: false`; a single zero-variance group is still tested (Welch df comes from the other group). The old behaviour returned p = 1.0 for exact floats but p ≈ 0 and d ≈ 1e15 for `[0.1]*3` vs `[0.2]*3` | `git diff backend/src/study/validation.py`; frontend `ReliabilityCheck`, `ValidationDashboard`, `plainLanguage` updated to show "not measurable". **The CLI `scripts/run_full_study.py` also crashed on the new `None`; it was fixed concurrently during this audit (§8)** | Closed once committed. Keep a test that feeds `None` through every consumer |
| Q3 | Flaky frontend test | **Not reproduced.** 383/383 in three consecutive runs (46.7 s each) | `npx vitest run` ×3 | **No.** Re-run ×3 before 29 Oct and 26 Nov; quarantine only if it recurs |
| Q4 | Is `ensure_db_initialized()` correct under concurrency, file recreation and in-memory DBs? | **Acceptable.** Process-wide lock with a re-check under the lock; a recreated file is detected (`os.path.exists`); two new tests cover it. Two non-issues to record: `:memory:` never "exists", so it re-initialises each call (harmless — every in-memory connection is a fresh database anyway); and the lock is per-process, so it would not protect multiple uvicorn *worker processes* (production runs one) | `backend/src/database/db.py`, `tests/database/test_ensure_db_initialized.py` | **No.** Add a two-process test only if `--workers` is ever enabled |

---

## 7. V2.0 release-readiness verdict and must-fix list

**Verdict: backend GO; product NO-GO.** V2.0 can be called complete when M1–M5 are done and M6 has been authorised and executed (or explicitly waived for local-only demos).

| # | Must-fix | Why it matters | Smallest remediation | ED | Owner decision needed |
| --- | --- | --- | --- | :-: | --- |
| **M1** | Planner UI for V1.8–V2.0 (`/app/planning`: scenario → field data (optional) → alternatives → run with progress → results with findings and validity → export/reproduce) | The only missing *capability*; the roadmap names the planner workflow as V2.0's experience; V3's uncertainty view builds on it | Typed client in `frontend/src/services/v2/` + one routed page reusing the scenario builder; render `unavailable` as "not available", never 0; register the route with `routing.ts`, nginx template and `vite.config.ts` together (a test mirrors them). Follows steps 1–4 of `v20-integration.md`. Reusing the scenario builder and result components, it is delivered in three parts: core flow (S0–S1), field-data step (S5) | 3–4 | Confirm scope |
| **M2** | Consistent protection of `/api/v2` | Anonymous compute and cross-user exposure of calibration observations | User dependency on calibration and `planning/validate`; give `networks` the same dependencies; add `user_id` to `uf_calibration_runs` and scope reads; request-size cap; tests per route | 1–1.5 | None |
| **M3** | Private suites | Cross-user read of run records | Decision Q1; `user_id` column; scope all `/api/suites*`; ownership tests | 0.75–1 | Approve Q1 |
| **M4** | Review, run once more, and **commit** the pending hardening | 26 uncommitted entries include correct fixes; any further work builds on them. One of them needed a concurrent follow-up edit | **You** review and commit; re-run the full backend and frontend suites after the final edit | 0.25 | Yes — commit/push is yours |
| **M5** | Documentation and roadmap status sync | Docs say V1.6 is "upcoming", V1.8/V1.9/V2.0 "planned", validation K7/K8 say no safety/emissions/calibration; API reference omits `/api/v2` | Update `ROADMAP.md`, `README.md`, `docs/api/README.md` (new §8 for `/api/v2`), `docs/research/validation.md` limitations table | 1 | Approve editing `ROADMAP.md` |
| **M6** | Production redeploy path | Last two deploys failed; the fix is not on `deployment` | After M4: user-authorised merge `main → deployment`, watch the run, smoke-test `/health` and `/api/version` | 0.5 | Yes — explicit authorisation |

**Not must-fix (documented, deferred):** parameter calibration (A-21), real-data case study (A-22), multi-junction simulation (A-31), network visualisation (A-32), V1.5 slow-suite run (A-15) — except that the slow suite must pass before any V3 safety statement.

---

## 8. Concurrent change to the working tree during this audit

At 12:27 IST the first backend run **failed**:
`tests/study/test_run_full_study_cli.py::test_cli_reports_whole_junction_volume_and_measured_verdict` → `TypeError: unsupported format string passed to NoneType.__format__` at `scripts/run_full_study.py:301`. Cause: the uncommitted zero-variance change makes `cohensD` `None` for untestable comparisons, and the CLI formatted it with `:8.3f`. A real latent regression in the uncommitted batch.

By 12:51 IST `scripts/run_full_study.py` had been edited by someone else (not this task) to print `N/A` and the label "No test applies" for untestable rows. After that edit the same test passed alone (×4) and in the full run. This audit did not edit it; the edit is **uncommitted** and belongs in M4. Lesson recorded for the plan: every consumer of a changed statistical contract needs a test that feeds it the new null value.

---

## 9. What this audit did not do

No deployment, commit, push, merge or branch change · no edits to `.claude/launch.json`, application code, tests or `ROADMAP.md` · no `slow` test run · no Docker build · no production or network probing beyond read-only `gh` queries · no automated accessibility run · no line-by-line review of the codebase — statuses rest on tests, docs, runtime observation and targeted code reading, and say so where that is thin.
