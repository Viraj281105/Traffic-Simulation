# V2.0 Completion Audit

> **Status:** PROPOSED — **revision 2, with revision-3 corrections of 2026-10-12** · **Branch:** `viraj-dev` @ `d62338d`, which PR #141 merged into `main` at `324cde0` (09:33 UTC, 2026-10-12) · all dates and estimates are *proposed* until the product owner approves them
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Authority:** [`docs/ROADMAP.md`](../ROADMAP.md) is the single authoritative roadmap and was **not** edited. Where this audit finds ROADMAP statements that are out of date (§7, R4.2) it records the correction as an *owner-authorised edit still to be made*.

This audit answers one question: **is everything promised through V2.0 actually finished, and exactly what must be true before V2.0 may be called released?** It judges capability available to a user, not "a module or endpoint exists".

### Revision-3 corrections (2026-10-12) — V2.0 scope is separate from V3.0 scope

* **Repository state corrected (§1).** The four local commits are no longer unpushed: PR #141 merged them into `main` (merge commit `324cde0`); Continuous Integration and Docker Container CI are green on that commit, and the **scheduled** CI run on `324cde0` (event `schedule`) ran the five `Backend Slow Simulation Regression` jobs, all green. The push/PR runs skipped the slow job. This is **context, not a gate PASS**: the gate commit is still to be declared and every gate check re-run on it (rule in §7).
* **V3.0 scope firewall (new §7.12).** The V3.0 plan now includes signalised roundabouts, a strategy registry, a driver-aggression default and two AI features. **None of it is V2.0 scope, none of it may delay or alter the V2.0 gate, and none of it may be merged before G-V2.** The V2.0 release gate rows, work packages and 7.75 ED estimate are unchanged; V2.0 closure is not compressed.
* The audit's findings (rows PASS/FAIL/NOT RUN) are **not changed** by this correction except where §1 now records a verified fact.

### What changed in revision 2

* The six-dimension **V2.0 release gate** (§7) replaces the earlier short must-fix list. Nothing is marked PASS without evidence; evidence that is stale (gathered on an earlier tree) is called out as such.
* **Repository state re-checked** (§1): the owner has since committed the pending work locally; the working tree is clean; nothing is pushed, so **no CI has run on the new commits**.
* Test evidence from the first audit is retained but labelled *"identical tree, not re-run at HEAD"*. The suites were **not** re-run for this revision (the owner asked to skip them), so the gate marks them NOT RUN until they are.
* The cause of the failed production deployments was inspected (read-only `gh run view`).
* The ≈ 7–8 engineer-day estimate is **kept as an estimate**; §7.5 breaks it into work packages.

---

## 0. Verdict (read this first)

**V2.0 is NOT release-ready.** The backend is real and works end to end; the product experience the roadmap names for V2.0 ("end-to-end planner workflow … final presentation layer") does not exist, and several security, evidence and documentation criteria are open.

| Dimension of the release gate (§7) | Rows | PASS | FAIL | NOT RUN | BLOCKED |
| --- | :-: | :-: | :-: | :-: | :-: |
| 1 Code complete and reviewed | 8 | 2 | 4 | 2 | 0 |
| 2 Automated tests and build checks | 8 | 0 | 0 | 6 | 2 |
| 3 Security and privacy | 8 | 2 | 4 | 2 | 0 |
| 4 Documentation | 5 | 0 | 4 | 1 | 0 |
| 5 Deployment pipeline (not production) | 4 | 0 | 2 | 1 | 1 |
| 6 Production deployment and smoke test (separately authorised) | 3 | 0 | 0 | 0 | 3 |

**The V2.0 release gate (G-V2) passes when dimensions 1–5 are all PASS, or each remaining item is a documented gap *accepted in writing by the product owner*.** Dimension 6 is a separate decision (G-PROD): V2.0 may be declared "released, not deployed" only if the product owner says so explicitly.

**V3.0 product-feature implementation does not start until G-V2 is passed** (see the [sprint plan](V3_WEEKLY_SPRINT_PLAN.md)).

---

## 1. Repository state — verified (re-checked after the first audit)

| Item | State | How verified |
| --- | --- | --- |
| Branch / HEAD | `viraj-dev` @ `d62338d`, **pushed** (`origin/viraj-dev` = `d62338d`); PR #141 **merged** into `main` at `324cde0` (2026-10-12 09:33 UTC). Local HEAD is 0 ahead / 1 behind `origin/main` (the merge commit). *Superseded statement from the earlier revision: "ahead … by 4 commits; none pushed"* | `git rev-list --left-right --count HEAD...origin/main`, `gh pr view 141` |
| The 4 local commits | `a554614` backend batch/engine/stream/DB hardening (+ tests, API doc edit) · `dd3d36b` untestable-comparison statistics (+ frontend, CLI, report generator) · `7b69815` frontend test timeout · `d62338d` the four roadmap documents | `git log`, `git show --stat` |
| Working tree | At the time of the revision-3 correction the four `docs/roadmap/*.md` files carry **uncommitted edits** (planning documents only; no application code) | `git status --short` |
| `.claude/launch.json` | Tracked (since `6e89ccd`) and unmodified; never touched by this work | `git ls-files`, `git status` |
| Concurrent modification during the first audit | `scripts/run_full_study.py` was edited by someone other than the auditor at 12:51 IST while the first backend run (12:27) failed on it (`cohensD` null → `TypeError`). That edit is now part of `dd3d36b`. **Process consequence:** one integration owner per shared file (sprint plan §1.3); every consumer of a changed result contract needs a null-feeding test | First-audit log; `git show dd3d36b` |
| CI on the new commits | **Green** on `main` @ `324cde0`: Continuous Integration (push, run 38230656807) and Docker Container CI succeeded; the push run **skipped** `Backend Slow Simulation Regression`. A **scheduled** CI run on the same commit (run 38231088419) executed the slow regression jobs (signal-capacity, calibrated-capacity, roundabout-lockup, signal-lockup, roundabout-conflicts) — all `success` | `gh run list`, `gh run view` |
| Slow suite vs the new code | **Ran green on the merged code** (scheduled run on `324cde0`, which includes `a554614`). It has **not** run on a declared gate commit, which will differ (planner UI, auth changes); R2.2 stays NOT RUN until it does | `gh run view 38231088419` |
| Deployment branch | `origin/deployment` @ `6977d20`; the pipeline fix `8f6e80f` is on `main` but **not** on `deployment` | `git log origin/deployment` |
| Deployment runs | Two runs of "Production EC2 Deployment" (9 Oct): both `failure`. The second was examined: the job ended with **"Process completed with exit code 255" about five minutes into the remote deploy step**, consistent with the SSH-session drop that `8f6e80f` redesigns. The first run was not examined. The fix has never been exercised | `gh run view --log-failed` |
| Frontend `/api/v2` usage | **None** (`grep -r "api/v2" frontend/src` → no match). A `frontend/dist/` from 2026-10-12 11:31 exists but is a stale build artefact, not evidence | grep, `ls` |
| `docs/api/README.md` `/api/v2` coverage | 0 matches | grep |

### Test and check evidence (be exact about its age)

| Check | Result | Age and tree |
| --- | --- | --- |
| Backend `pytest -m "not slow"` (1,099 tests), coverage | exit 0, 94.13 % (floor 85 %) | 2026-10-12 ≈ 13:00 on the working tree whose content was committed as `a554614`/`dd3d36b`; **not re-run at `d62338d`** |
| Backend `ruff check`, `ruff format --check`, `mypy src` | clean | same tree, same age |
| Frontend `vitest run` ×3 (383 tests, 34 files), `tsc --noEmit`, `eslint .`, `prettier --check .` | clean | same tree, same age |
| `scripts/v2_demo.py` against a live backend on a scratch database | six steps OK in 21 s, `reproduced=True` | same tree; run against `DEV_AUTH_BYPASS=1`, `API_KEY` unset |
| Engine speed (`simulate_geometry`, 1 lane, 500 veh/h/arm, 150 s) | 233 steps/s fixed-time, 405 steps/s adaptive uncontended; 39–48 steps/s at saturation under contention | this developer machine only; **not** the presentation machine |
| Backend `slow` suite (190 tests) | **not run** | — |
| Frontend `vite build`, Docker build, axe/Lighthouse | **not run** | — |

---
## 2. How to read the status column

| Status | Meaning here |
| --- | --- |
| **COMPLETE** | Implemented, covered by tests, and observed working in this audit or by CI. Documented limits are intentional and honest. |
| **PARTIAL** | Something real exists but a named part of the promise is absent, unvalidated, or reachable only through a developer interface. |
| **MISSING** | Promised; nothing a user can use exists. |
| **BLOCKED** | Cannot progress without an external decision or action. |
| **UNVERIFIED** | Evidence is absent or could not be gathered without a prohibited action (e.g. deploying). |

Effort is in **engineer-days (ED)** for one engineer, review time included; coding agents are not counted as planned throughput. "Blocks V3" means V3 implementation (Phase B) depends on it; in practice that is governed by the release gate in §7, not by this column.

---

## 3. Requirement-level audit

### 3.1 V0.1 – V1.0 foundation

| ID | Requirement | Evidence | Status | Why | User-visible impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-01 | V0.1–V0.8: IDM engine, spawner, controllers, metrics, same-seed lockstep comparison, sweeps, Monte-Carlo validation | `backend/src/{vehicles,core,controllers,metrics,study}`; 1,099 non-slow tests pass; scheduled CI green 10 and 11 Oct; [comparative report](../reports/comparative_report.md) | **COMPLETE** | Tests pass, determinism tests exist (`tests/core/test_determinism.py`, `tests/study/test_runner.py`) | Core comparison works | Run the 190 `slow` tests once before V3 baselining (they guard capacity calibration) | 0.25 | No |
| A-02 | V0.9 Containerisation | Multi-stage `backend/Dockerfile`, compose files, nginx template; Docker CI green on `main` 9 Oct | **COMPLETE** | CI builds the images; not rebuilt locally in this audit | Reproducible local/containerised run | None | 0 | No |
| A-03 | V1.0 AWS EC2 deployment | `deploy.yml`, `docs/deployment/*`. `gh run list --workflow deploy.yml`: **2 runs, both `failure`** (9 Oct 09:55 and 12:49 UTC). Fix `8f6e80f` is on `main`; `origin/deployment` is at `6977d20`, *before* the fix | **UNVERIFIED** | No successful deployment is visible in the run history; production state, `API_KEY` and Cognito settings cannot be checked without touching production | Unknown whether the public site runs current code | Gate rows R5.1–R5.4 and R6.1–R6.3; a redeploy needs explicit PO authorisation (G-PROD) | 0.5 | No — G-PROD is a separate decision |
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
| A-18 | V1.7 Scenario engine, batch experiments, scenario workflow, comparison UI, reporting | `study/batch.py`, `/api/suites*` (6 routes), suite comparison in `ComparativeDashboard.tsx`, `test_suite_batch.py` (new, uncommitted) | **PARTIAL** | Batch = **arrival-rate sweep of one config, seeds starting at 42**. The real "what-if alternatives" capability is the V2.0 planning API, which has no UI. Two overlapping mechanisms exist | A planner cannot build a what-if study in the UI | Close via the planner UI (W1); freeze suites to their current scope, document overlap | (in W1) | Yes — through W1 |
| A-19 | Suite ownership (prior-audit open question) | `main.py` `create_suite` accepts `user_id` but never stores it; `list_suites` returns every suite; `get_suite` loads each run by id with no owner check | **PARTIAL** (defect) | Any signed-in user can list suites and read other users' run records | Cross-user data exposure | **Decision: private to creator** (W4) | 1 | No, but must-fix |

### 3.4 V1.8 Calibration

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| A-20 | Observation schema, validation, simulated-vs-observed comparison, GEH/percent-error ratings, `fieldCalibration` status | `calibration/{models,compare,rating,runner,simulate}.py`; 30 tests; [`docs/research/calibration.md`](../research/calibration.md); live demo step 2 | **COMPLETE** (as a comparison framework) | Observed working. Rating of the demo was `POOR` by design (50-second window) — the system reported honestly | API users can test a scenario against counts | None | 0 | No |
| A-21 | Parameter calibration (search / `options.tune`) | The contract ([v18-v20-contracts §3.1](../engineering/v18-v20-contracts.md)) promised `options.tune`; `docs/engineering/v20-integration.md` states "no `tune` search" | **MISSING** | Nothing fits driver parameters. "Demand fit" is *input assimilation*: it writes observed flows into the scenario, and the result flags fitted rows `inputWasFitted` | UrbanFlow cannot be called "calibrated" in any V3 material | Decide explicitly: out of V3 (recommended). State it in V3 limitations | 0 | No (claims constraint) |
| A-22 | Real-world traffic inputs | Only hand-written `urbanflow-observations` JSON. **No real dataset or case study exists in the repo.** No CSV import | **MISSING** | Zero evidence that the framework has met real data | The headline V1.8 promise is untested in the field | Add CSV turning-count import (V3 Sprint 5) and run one real or realistic public dataset if the user can supply one | 2 | No |
| A-23 | End-user access to calibration | No frontend | **MISSING** | `/api/v2/calibration` reachable only by API | Planners cannot use it | Optional planner step; proposed accepted gap (§7.8) | (in W1) | Yes — via W1 |

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
| A-43 | **End-to-end planner workflow, UX, presentation layer** | `grep -r "api/v2" frontend/src` → **no matches**; `docs/engineering/v20-integration.md` ("No frontend UI exists for V1.8–V2.0") | **MISSING** | This is the named V2.0 experience scope. Backend only | A municipal planner cannot use V2.0 | **W1 / R1.1** — planner UI | 3–4 | **Yes** |
| A-44 | Research validation of the integrated platform | [`docs/research/validation.md`](../research/validation.md) still describes V1.5 and lists V1.6–V2.0 as future; no V1.8–V2.0 validation write-up or case study | **PARTIAL** | Tests prove behaviour, not scientific adequacy | No evidence page for planners/researchers | Write a V2.0 validation addendum (what was checked, what was not) | 1 | No |
| A-45 | Performance | `/run` is synchronous; global cap of 2 planning jobs; ≤240 simulations/study; saturated 600 s run ≈ 6,000 steps at 40–400 steps/s | **PARTIAL** | Fine for demos; an uncertainty ensemble of hundreds of runs will need budgeting and parallelism | Long studies take minutes–hours | Plan compute budgets (V3 Sprint 1/5) | — | Shapes V3 scope |
| A-46 | Persistence | Completed studies persisted to `uf_planning_studies` (best effort); calibration runs in `uf_calibration_runs`; in-flight jobs and failures are in memory only; tables created lazily with `CREATE TABLE IF NOT EXISTS`; no migration framework (inline `ALTER TABLE`) | **PARTIAL** | Adequate for V2.0; adding columns for ownership needs the existing inline-migration pattern | A restart loses running jobs | Use the existing pattern for W3 and W4; add a tiny numbered-migration helper in V3 Sprint 0 | 0.5 | No |

### 3.7 Cross-cutting

| ID | Requirement | Evidence | Status | Why | Impact | Remediation | ED | Blocks V3? |
| --- | --- | --- | :-: | --- | --- | --- | :-: | :-: |
| X-01 | Scenario validation | `/api/v1/scenarios/validate`, `/compile`, planning `validate`, networks `validate`; invalid-input tests across modules | **COMPLETE** | Strict `extra="forbid"` documents; explains every rejection | Good errors | None | 0 | No |
| X-02 | **API protection consistency** | Code reading plus probes (below) | **PARTIAL** (defects) | See §5. The nginx proxy attaches the API key to **every** browser request, so a route protected *only* by the API key is effectively public; V2 routers use it as their only guard | Calibration data exposure; anonymous compute | **W3 / R1.2–R1.3** | 1–1.5 | Yes |
| X-03 | API/contract documentation | `docs/api/README.md` (331 lines) has **no `/api/v2` section** (0 matches); contracts live only in `docs/engineering` | **PARTIAL** | An integrator reading the API reference will not find the planning, calibration or network routes | Integration is guesswork | **W5** | 1 | Yes (for V3 API work) |
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
| Q1 | Are scenario suites private or shared? | **Private to the creator** (admins may list all). Consistent with replays and planning studies. Legacy rows with no owner become admin-visible only. Add `user_id` via the existing inline `ALTER TABLE` pattern; scope `list`, `get`, `batch`, `export`. Sharing between users is a later, explicit feature | Defect in A-19; `tests/api/test_replay_ownership.py` is the pattern to copy | **Do (W4)** |
| Q2 | Two zero-variance groups with different means | **Resolved and committed locally (`dd3d36b`, not pushed).** Both groups' spread ≤ 1e-9 × data scale → `_untestable("no_variation")`; null p and d; `significant: false`; a single zero-variance group is still tested (Welch df comes from the other group). The old behaviour returned p = 1.0 for exact floats but p ≈ 0 and d ≈ 1e15 for `[0.1]*3` vs `[0.2]*3` | `git diff backend/src/study/validation.py`; frontend `ReliabilityCheck`, `ValidationDashboard`, `plainLanguage` updated to show "not measurable". **The CLI `scripts/run_full_study.py` also crashed on the new `None`; it was fixed concurrently during the first audit and is part of `dd3d36b` (§1)** | Closed once pushed and CI-verified (R1.6, R2.6). Keep a test that feeds `None` through every consumer |
| Q3 | Flaky frontend test | **Not reproduced.** 383/383 in three consecutive runs (46.7 s each) | `npx vitest run` ×3 | **No.** Re-run ×3 before 29 Oct and 26 Nov; quarantine only if it recurs |
| Q4 | Is `ensure_db_initialized()` correct under concurrency, file recreation and in-memory DBs? | **Acceptable.** Process-wide lock with a re-check under the lock; a recreated file is detected (`os.path.exists`); two new tests cover it. Two non-issues to record: `:memory:` never "exists", so it re-initialises each call (harmless — every in-memory connection is a fresh database anyway); and the lock is per-process, so it would not protect multiple uvicorn *worker processes* (production runs one) | `backend/src/database/db.py`, `tests/database/test_ensure_db_initialized.py` | **No.** Add a two-process test only if `--workers` is ever enabled |

---

## 7. V2.0 release gate (G-V2)

**Owners.** *Engineer* = the primary engineer (also the integration owner for shared schemas, migrations, router mounting and frontend/backend contracts). *Product owner (PO)* = the person who approves scope, accepts gaps, authorises edits to `ROADMAP.md` and any deployment. Individual names are not recorded in the repository and are **not assumed** here; D-V2-0 asks the PO to name them.

**Status values.** **PASS** — verified, evidence cited. **FAIL** — verified not met. **NOT RUN** — not yet checked, or evidence is stale/for a different commit. **BLOCKED** — cannot be run until another row passes or a decision is made.

**Rule.** All checks are re-run on **one gate commit** (the release candidate, pushed). Evidence from an earlier tree is context, not a PASS.

### 7.1 Minimum viable planner workflow (acceptance for R1.1 and R2.7)

The V2.0 planner must let a non-engineer do all of the following in the browser against the existing `/api/v2/planning` API:

| Step | Requirement | Verified by |
| --- | --- | --- |
| PL-1 | **Create a scenario** from a preset or the existing scenario builder; validation errors from `planning/validate` are shown in plain language | UI test + manual |
| PL-2 | **Choose alternatives** (fixed-time, adaptive, roundabout; baseline first), seeds and demand scales within the server's limits | UI test |
| PL-3 | **See the cost before running:** number of simulations from `validate`; any time estimate is labelled *unverified* unless it comes from a measured benchmark | UI test |
| PL-4 | **Run** as an asynchronous job with progress; a failed job shows its error; the 2-job cap (HTTP 429) is explained, not swallowed | UI test + backend test |
| PL-5 | **Compare:** indicator table per alternative with the paired difference against the baseline and its interval; `unavailable` indicators read "not available", never 0; ties read as inconclusive | UI test (fixture incl. `unavailable`, tie, null statistic) |
| PL-6 | **Read the evidence:** findings with their evidence paths, the validity banner ("not field-calibrated") and caveats/limitations | UI test |
| PL-7 | **Report:** download JSON, Markdown and CSV | UI + API test |
| PL-8 | **Reproducibility:** fingerprints, source commit and seeds are visible; a *Reproduce* action reports `reproduced` true/false from `POST /{id}/reproduce` | UI + API test |
| PL-9 | **Re-open:** the finished study is retrievable by id after a page reload and after a backend restart | scripted check |
| PL-10 | **Access:** a second user receives 404 for the first user's study; an anonymous caller is refused when `API_KEY` is set | backend tests (R3.1, R3.2) |

**Acceptance procedure:** (a) automated UI flow test with a mocked API covering PL-1…PL-8; (b) one scripted run against a real local backend (`DEV_AUTH_BYPASS=1`) whose output is saved as evidence; (c) PL-9/PL-10 checks; (d) a manual walk-through recorded in the evidence pack.

**Explicitly outside the V2.0 minimum** (each is an accepted-gap candidate, §7.8): the field-data (calibration) step, any network view, job *cancellation* (V2.0 jobs have none — `study/jobs.py` has no cancel), saving named scenarios beyond what exists, parameter tuning.

### 7.2 Dimension 1 — Code complete and reviewed

| ID | Requirement | Status | Evidence / verification method | Remaining work | Owner |
| --- | --- | :-: | --- | --- | --- |
| R1.1 | Minimum viable planner workflow (§7.1) implemented | **FAIL** | No `/api/v2` reference in `frontend/src`; `v20-integration.md` states no UI exists | W1: client `frontend/src/services/v2/`, one routed page reusing the scenario builder, route registered in `routing.ts` + nginx template + `vite.config.ts` together (a test mirrors them) | Engineer |
| R1.2 | `/api/v2` calibration routes, `planning/validate` and `networks` require per-user authentication in addition to the API key | **FAIL** | Code: calibration router `dependencies=[Depends(auth)]` with `auth = require_api_key`; `planning/validate` has no user dependency; `networks_router` is mounted with no dependency (`main.py`) | W3: add `get_current_user_id`; API-key dependency on `networks` | Engineer |
| R1.3 | Calibration runs belong to their creator; list/get/scenario are scoped | **FAIL** | `calibration/store` has no owner column; `GET /runs` lists all | W3: `user_id` column via the existing inline `ALTER TABLE` pattern; legacy rows admin-only | Engineer |
| R1.4 | Scenario suites and their run records are private to the creator | **FAIL** | `create_suite` receives `user_id` but never stores it; `scenario_suites` has no owner column; `get_suite` loads runs by id with no owner check | W4: migration + scoping of list/get/batch/export; legacy rows admin-only | Engineer (decision: PO, D-V2-3) |
| R1.5 | Pending hardening and statistics work committed | **PASS** | `git log`: `a554614`, `dd3d36b`, `7b69815`; tree clean | — | Engineer |
| R1.6 | Every consumer of the now-nullable `cohensD`/`pValue` handles null | **PASS** (inspected) | `dd3d36b` updates `report_generator`, `scripts/run_full_study.py`, `ValidationDashboard`, `ReliabilityCheck`, `plainLanguage`; no other consumers found by grep | Re-confirm at the gate commit | Engineer |
| R1.7 | Gate commit pushed, PR opened and reviewed (second reviewer, or a recorded self-review if none is available) | **NOT RUN** | The *current* work was pushed and merged via PR #141, but the **gate commit** (with the planner UI and security fixes) does not exist yet; the review record of #141 has not been inspected for this audit | W7: push, PR, review | Engineer; reviewer named by PO |
| R1.8 | Working tree clean and no uncommitted concurrent edits at gate time | **NOT RUN** (was PASS) | At the revision-3 correction the four roadmap documents carry uncommitted planning edits, so "clean" is not currently true; this is a documents-only difference and says nothing about the gate commit | Re-check at the gate commit; planning documents are committed or stashed by the owner before the freeze | Integration owner |

### 7.3 Dimension 2 — Automated tests and build checks (on the gate commit)

| ID | Requirement | Status | Evidence / verification method | Remaining work | Owner |
| --- | --- | :-: | --- | --- | --- |
| R2.1 | Backend `pytest -m "not slow"` green, coverage ≥ the 85 % floor | **NOT RUN** | Prior pass (1,099 tests, 94.13 %) on an identical earlier tree only | Run on the gate commit | Engineer |
| R2.2 | Backend **slow suite (190 tests)** green | **NOT RUN** | Never run locally; scheduled CI ran it on `main` before `a554614` changed `core/engine.py`, `main.py`, `db.py`, `batch.py` | `workflow_dispatch` with `run_slow_suite=true` on the pushed gate commit, or `pytest -m slow` locally (hours) | Engineer |
| R2.3 | `ruff check`, `ruff format --check`, `mypy src` clean | **NOT RUN** | Prior pass, earlier tree | Run on the gate commit | Engineer |
| R2.4 | Frontend `vitest run` ×3 stable, `tsc --noEmit`, `eslint .`, `prettier --check .` | **NOT RUN** | Prior 3× pass (383 tests), earlier tree | Run on the gate commit (includes the new planner tests) | Engineer |
| R2.5 | Frontend **production build** (`npm run build`) succeeds | **NOT RUN** | Never run; `ci.yml` has no build step; a stale `dist/` exists | Run; confirm Docker CI builds the frontend image | Engineer |
| R2.6 | CI green on the pushed gate commit (CI + Docker CI) | **NOT RUN** | CI is green on `324cde0` (context only); the gate commit is not declared | W7 | Engineer |
| R2.7 | Planner end-to-end acceptance (§7.1 PL-1…PL-10) passes | **BLOCKED** | Needs R1.1 | Run the acceptance procedure; save evidence | Engineer |
| R2.8 | Accessibility: axe 0 serious/critical and a keyboard-only path on the planner | **BLOCKED** | Needs R1.1; no accessibility tooling has been run on any page | Add an axe check (vitest-axe or a one-off browser run); record results | Engineer |

### 7.4 Dimension 3 — Security and privacy

| ID | Requirement | Status | Evidence / verification method | Remaining work | Owner |
| --- | --- | :-: | --- | --- | --- |
| R3.1 | For **every** `/api/v2` route: with `API_KEY` set, a request without the key is 401, and routes that take a user reject a missing or invalid user token | **NOT RUN** | No such test exists; dev-mode probes (API key unset) only show the no-op path | W3: parametrised test over the app's routes | Engineer |
| R3.2 | Cross-user isolation of planning studies | **PASS** | `tests/planning/test_planning.py` (another user's id → 404 on get and report) | Keep in the gate run | Engineer |
| R3.3 | Cross-user isolation of calibration runs | **FAIL** | R1.3 | W3 + test | Engineer |
| R3.4 | Cross-user isolation of suites and their runs | **FAIL** | R1.4 | W4 + test mirroring `tests/api/test_replay_ownership.py` | Engineer |
| R3.5 | Request-size / abuse limits on stateless compute endpoints (`networks/*`, `planning/validate`) | **FAIL** | No body-size cap found in the routers read | W3: 1 MB cap + test | Engineer |
| R3.6 | The development auth bypass cannot be switched on by the production compose file | **PASS** | `docker-compose.yml` contains no `DEV_AUTH_BYPASS`; only `docker-compose.dev.yml` defaults it to 1; `tests/api/test_dev_auth_bypass.py` | — | Engineer |
| R3.7 | Privacy: a user can delete their calibration runs, planning studies and suites, **or** the retention of observation data is documented and the PO accepts no deletion for V2.0 | **FAIL** | No delete route in the calibration or planning routers read | Decision D-V2-6; then implement or document | PO decides; Engineer |
| R3.8 | In production `API_KEY` is actually set (the compose default is empty, which **disables** the check) | **NOT RUN** | `docker-compose.yml`: `API_KEY=${API_KEY:-}`; the host `.env` cannot be inspected without touching production | Operator confirms on the host; recorded in the evidence pack | PO / operator |

### 7.5 Dimension 4 — Documentation

| ID | Requirement | Status | Evidence / verification method | Remaining work | Owner |
| --- | --- | :-: | --- | --- | --- |
| R4.1 | `/api/v2` (calibration, networks, planning) documented in the API reference | **FAIL** | `grep -c "api/v2" docs/api/README.md` → 0 | W5: new section from the live OpenAPI | Engineer |
| R4.2 | README and `ROADMAP.md` state the true V1.6–V2.0 status | **FAIL** | README status row says V1.5; ROADMAP lists V1.6 as upcoming and V1.8–V2.0 as planned | W5: **requires PO authorisation to edit `ROADMAP.md`** (it is authoritative and was not touched here) | PO authorises; Engineer edits |
| R4.3 | `docs/research/validation.md` limitations (K7, K8) corrected and a V2.0 validation addendum stating what was and was not checked | **FAIL** | K7 says no emissions/safety; K8 and the V1.8–V2.0 rows are future-tense | W5 | Engineer |
| R4.4 | Planner user guide (how to run, read and reproduce a study) | **FAIL** | None exists | W5 | Engineer |
| R4.5 | Operator notes: `API_KEY` is mandatory in production, how user auth works, data retention | **NOT RUN** | `docs/operations.md` and `docs/deployment/*` were not checked for these points | W5: check and complete | Engineer |

### 7.6 Dimension 5 — Deployment pipeline verified (no production change)

| ID | Requirement | Status | Evidence / verification method | Remaining work | Owner |
| --- | --- | :-: | --- | --- | --- |
| R5.1 | Root cause of both failed runs identified | **FAIL** | Second run: exit code 255 ≈ 5 min into the remote step; first run not examined | W6: read both logs; confirm against the `8f6e80f` redesign | Engineer |
| R5.2 | The fix `8f6e80f` is on the `deployment` branch | **FAIL** | `origin/deployment` @ `6977d20` | Merge `main` into `deployment` — **a deployment trigger; only with PO authorisation** | PO authorises |
| R5.3 | Deploy scripts statically checked (`bash -n`, `shellcheck` if available) and the workflow reviewed | **NOT RUN** | — | W6 | Engineer |
| R5.4 | Pipeline demonstrated by one successful run | **BLOCKED** | Requires the real host, secrets and R5.2 | Authorised run; see G-PROD | PO |

*Pipeline readiness (R5.1–R5.3) is a code-and-logs claim. It is **not** evidence that production works; only R6 is.*

### 7.7 Dimension 6 — Production deployment and smoke test (separately authorised)

| ID | Requirement | Status | Evidence / verification method | Remaining work | Owner |
| --- | --- | :-: | --- | --- | --- |
| R6.1 | Written PO authorisation for a production deployment of a named commit | **BLOCKED** | None given | PO decision (G-PROD) | PO |
| R6.2 | `GET /api/version` on production reports the released commit | **BLOCKED** | R6.1 | After deployment | Engineer / operator |
| R6.3 | Production smoke test: `/health`, sign-in, a planner run, reproduce, anonymous access to `/api/v2/calibration` refused | **BLOCKED** | R6.1 | After deployment | Engineer / operator |

### 7.8 Accepted-gap register (the only way a non-PASS row can be passed)

A gap is accepted only if the PO records it in writing. The following are proposed for acceptance; none is silently dropped.

| Gap | Audit ref | Why acceptable for V2.0 | Condition | If rejected |
| --- | --- | --- | --- | --- |
| Field-data (calibration) step in the planner UI | A-23 | The calibration API works; the planner MVP is complete without it | Listed as an open V1.8 item; scheduled in Phase B only if capacity allows | +0.75 ED in Phase A |
| Parameter tuning (`options.tune`) | A-21 | Never implemented; documented | V3 material never says "calibrated" | Out of reach this season |
| Real observed-data case study | A-22 | No dataset supplied | Same wording rule | Needs PO to supply data |
| Multi-junction simulation; network view | A-31, A-32 | Foundations only, honestly labelled | Docs say "representation only" | Out of scope |
| Job cancellation | — | Not a V2.0 promise | Becomes a Phase B requirement | +0.5 ED |
| Deletion routes (if the PO prefers documentation) | R3.7 | Small user base, owner-scoped | Retention documented in R4.5 | +0.75 ED |

### 7.9 Estimate (kept as an estimate)

The earlier estimate of **≈ 7–8 engineer-days** stands; repository evidence has not yet justified a revision. The only change since it was made is that the local commit step is done. Breakdown used for planning (sums to 7.75):

| Package | Content | ED |
| --- | --- | :-: |
| W1 | Planner UI (§7.1) | 3.0 |
| W2 | Evidence runs and builds (slow suite attendance, production build, axe, scripted real-backend run) | 0.75 |
| W3 | Access control, calibration ownership, request limits, route-level auth tests | 1.25 |
| W4 | Private suites | 0.75 |
| W5 | Documentation (API reference, README/ROADMAP edits once authorised, validation addendum, planner guide, operator notes) | 1.0 |
| W6 | Pipeline verification without production change | 0.5 |
| W7 | Push, PR, review, CI | 0.25 |
| W8 | Evidence pack and gate review | 0.25 |

Estimation unit: one **engineer-day = one working day ≈ 6 focused hours**, including review, tests, debugging and documentation. Coding agents are potential throughput, **not** planned throughput. Planning uses the upper end (8) as the committed duration.

### 7.10 Gate procedure and outcomes

The Engineer assembles an **evidence pack** (links to the gate commit, CI run, slow-suite run, build log, axe report, scripted run output, security test output, doc diffs). The PO decides.

| Outcome | Condition | Consequence |
| --- | --- | --- |
| **PASS** | Dimensions 1–5 all PASS | V2.0 released (not necessarily deployed); Phase B may start |
| **PASS with accepted gaps** | Every non-PASS row is in the §7.8 register with written PO acceptance | Same; the gaps are published in the release notes |
| **FAIL** | Anything else | Phase B does not start; remaining rows are worked; the preview shows V2.0 progress only |

### 7.11 Decisions needed from the product owner

| # | Decision | Owner | Schedule impact if late |
| --- | --- | --- | --- |
| D-V2-0 | Name the PO, the Engineer/integration owner and a reviewer | PO | Blocks R1.7 |
| D-V2-1 | Accept or reject each §7.8 gap | PO | Rejection adds up to ≈ 2 ED |
| D-V2-2 | Authorise edits to `ROADMAP.md` and `README.md` (R4.2) | PO | Blocks W5 completion |
| D-V2-3 | Suites private to the creator; legacy rows admin-only | PO | Blocks W4 |
| D-V2-4 | G-PROD: authorise (or decline) a production deployment, and of which commit | PO | R5.2–R6.3 stay BLOCKED |
| D-V2-5 | Is a recorded self-review acceptable if no second reviewer exists? | PO | R1.7 |
| D-V2-6 | Implement deletion routes or accept documented retention (R3.7) | PO | ± 0.75 ED |

### 7.12 V3.0 scope firewall (added in the revision-3 correction)

V3.0 planning now includes large simulation and AI features (signalised roundabouts, a strategy registry, a driver-aggression default, an AI experiment copilot, an AI strategy-discovery search). To keep V2.0 closure honest:

| Rule | Consequence for the V2.0 gate |
| --- | --- |
| No V3.0 feature code is written, merged or deployed before G-V2 passes | The gate commit contains **no** V3.0 feature code; the evidence pack's `git diff --stat` between the gate-candidate commit and G-V2 shows documentation only after the code freeze |
| V3.0 items never appear as V2.0 gate rows or accepted gaps | The gate table (§7.2–§7.7) is unchanged; no V2.0 row is satisfied by a V3.0 deliverable |
| The V3.0 **driver-aggression default** must not change any V2.0 result | Until G-V2 and the V3.0 design gate, no default changes; afterwards an absent field means today's behaviour (strategy §14.3), so V2.0 reproduction and fingerprints stay valid |
| V3.0 documents and GitHub issues describe future work only | Issues for V3.0 are labelled *planned* and *blocked by the V2.0 release gate*; the V2.0 release issue (#142) stays open until the gate is formally approved |
| Capacity | V2.0 closure keeps its eight working days (13 – 22 Oct, 7.75 ED, 97 % loaded); V3.0 preparation (ADRs, preview fallback) begins on Mon 26 Oct |

---

## 8. What this audit did not do

No deployment, commit, push, merge or branch change · no edits to `.claude/launch.json`, application code, tests or `ROADMAP.md` · the backend and frontend suites were **not re-run for revision 2** (owner's instruction), so every test row is NOT RUN against the gate commit · no `slow` run, no Docker or `vite` build, no accessibility tooling · no probing of production or of the EC2 host · no line-by-line review of the codebase — statuses rest on tests, docs, runtime observation of the first audit and targeted code reading, and say so where that is thin.

**Claims that could not be verified from the repository:** the production `API_KEY`/Cognito configuration; whether production currently runs any particular commit; the cause of the first failed deployment run; whether the scheduled CI "slow" job ran green on the last nightly (only the workflow's overall success was seen); actual presentation-machine performance.
