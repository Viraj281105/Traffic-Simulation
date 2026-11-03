# V3.1 W31 — Statistics and test foundation: implementation plan

> **Status:** Proposed — planning only, nothing implemented · written 2026-11-03 (Mon of W31)
> **Source of truth for scope:** [`docs/plan/WEEKLY_PLAN.md`](../plan/WEEKLY_PLAN.md) row W31 and [`docs/plan/FEATURE_SPECIFICATIONS.md`](../plan/FEATURE_SPECIFICATIONS.md) F4, F6, F7. Nothing is added to that scope here.
> **Audience:** the Antigravity implementation session (Viraj's column) and the Claude hardening session that follows it.
> **Convention:** every statement is tagged **[V]** verified in the repository on 2026-11-03 (file named), **[A]** assumption / interpretation, or **[D]** decision needed. Section 8 lists all [D] items.

---

## 1. Executive overview

**Roadmap goal (verbatim from WEEKLY_PLAN W31):** "Multi-seed runs available · Every push runs the tests · Every run leaves a record."

| Roadmap deliverable (Viraj column) | Feature | Plain meaning |
| --- | --- | --- |
| Random driver and demand models, multi-seed runner | #6 (F6) | Traffic that varies in a controlled, seeded way, and one runner that repeats a scenario over many seeds |
| pytest layout, coverage gate, fixed-seed regression tests, CI on every push | #4 (F4) | Tests that fail the build when a result drifts |
| Run manifest: seed, config hash, code version | #7 (F7) | Each run records exactly what is needed to re-run it |

| Roadmap deliverable (Khushi's column) | Feature |
| --- | --- |
| Frontend test setup hooked into CI | #4 |
| Plain-words glossary of every metric | (no F-number given) |

**Why it matters.** Phase 4 is "Trustworthy Results". W32 adds confidence intervals, paired tests, property-based tests and an S3 run store; all of them need a seedable multi-run primitive, a trusted regression net and a stable run identity first. W31 is that base. Gate G-REL1 (W38) requires "re-run from a manifest identical" and "coverage gates enforced"; W31 supplies the manifest and the ratcheted gate it is later audited against.

### The headline finding

**Most of what W31 names already exists in a first form.** The week is mostly *closing specific gaps and making existing pieces reproducible and general*, not building from scratch. The roadmap was written as if the foundation were absent; the repository disagrees (section 2.3). The plan below therefore extends the existing code and does not duplicate it.

---

## 2. Existing architecture assessment

### 2.1 What exists and is reusable

| Area | What is there | Evidence |
| --- | --- | --- |
| Per-run determinism | Each engine owns a private `random.Random(seed)`; the global `random` module is not used during a run; reset re-seeds in place; a missing seed is generated, logged and written back into the config | **[V]** `backend/src/vehicles/spawner.py:51-78`, `:223-231`; `docs/research/reproducibility.md` §2 |
| Demand model | Poisson (exponential gaps) or uniform arrivals, per-direction split; `burst` raises `NotImplementedError` | **[V]** `spawner.py:_generate_next_arrival_time`; `core/config_models.py:60-61` |
| Driver model | Per-vehicle random length/width/desired speed; per-class IDM; `StochasticIDM` under `unstructuredTraffic`; ADR-016 driver-aggression profiles (`standard`/`moderate`/`high`) | **[V]** `spawner.py:646-654`, `vehicles/stochastic_idm.py`, `vehicles/driver_aggression.py`, `docs/decisions/adr-016-*` |
| Multi-seed runner (1) | `run_statistical_validation`: N seeds × signal and roundabout, Student-t CI, Welch p, Cohen's d, in-house t-distribution maths; endpoints `POST /api/v1/study/validation/...` (repeatability, monte-carlo, job variant) | **[V]** `study/validation.py:276-440`, `study/router.py:80-105` |
| Multi-seed runner (2) | `batch_tasks`: arrival-rate sweep × `num_seeds` consecutive seeds from 42, persisted to the run DB | **[V]** `study/batch.py:25-50` |
| Multi-seed runner (3) | Robustness Lab: paired common-random-number ensembles, `derive_seed(spec.seed, i, k)` (SHA-256, 31-bit), bootstrap, regret, eligibility labels | **[V]** `uncertainty/sampler.py:41`, `uncertainty/runner.py`, `uncertainty/stats.py` |
| Parallel execution | Process pool, deterministic result order, progress and cancellation | **[V]** `study/runner.py` (`SimTask`, `run_simulation_tasks`, `_WorkerPool`) |
| Provenance | `build_run_provenance` (schema v1): git commit, Python version, config source, run mode, timing; stored in `provenance_json`; `random_seed` and `git_commit` columns; `/reproducibility` and `/reproduce` endpoints | **[V]** `core/provenance.py:106-142`, `database/dao.py:48-141,310-358`, `history/router.py:297`, `history/reproduce.py` |
| Fingerprints | Scenario fingerprint (16-hex SHA-256), uncertainty-spec fingerprint, aggression parameter hash, `.ufpkg` experiment manifest v1 (sha256 sidecars) | **[V]** `scenario/documents.py:281`, `uncertainty/spec.py:fingerprint`, `experiments/manifest.py` |
| pytest layout | 193 test files mirroring `src/`; markers `slow/unit/integration/architecture` registered; `testpaths`, `pythonpath`; `-n auto --dist loadfile` | **[V]** `backend/pyproject.toml`, `backend/tests/` |
| Coverage gate | `--cov-fail-under=85` in `addopts`; measured **94.0 %** (17 692 / 18 819 statements) | **[V]** `pyproject.toml`; `backend/coverage.json` (generated 2026-10-30) |
| Golden tests | Roundabout golden fingerprints (fast cases in the PR job, full corpus nightly) | **[V]** `tests/fixtures/roundabout_golden_fingerprints.json`, `tests/controllers/test_roundabout_golden_fingerprints.py` |
| Invariant tests | Randomised-scenario conservation / no-collision / bit-identical second run; slow variant nightly | **[V]** `tests/integration/test_randomized_invariants.py` |
| CI | `ci.yml`: schema validation, ruff + format + mypy --strict, SDK, backend fast suite + Copilot eval gate, nightly slow matrix (guarded by `tests/test_ci_slow_matrix.py`), frontend lint/type/prettier/**vitest**/build + bundle budgets | **[V]** `.github/workflows/ci.yml` |
| Frontend tests | Vitest 3 + jsdom + Testing Library + axe; 56 test files; `@vitest/coverage-v8` installed, `test:coverage` script exists | **[V]** `frontend/package.json`, `frontend/vite.config.ts:121-141` |
| Metric descriptions | 42 `MetricDef` entries with label, unit, `description`; plain-language module; `docs/research/metrics-reference.md` | **[V]** `frontend/src/metrics/catalog.ts`, `plainLanguage.ts`, `docs/research/metrics-reference.md` |

### 2.2 Limitations and technical debt that affect W31

| ID | Finding | Evidence | Effect on W31 |
| --- | --- | --- | --- |
| L1 | **The Monte Carlo runner is not reproducible.** Seeds are `random.randint(1000, 999999)` from the *global* `random` module, "recorded in the result, not user-settable". The same request gives different numbers each time. | **[V]** `study/validation.py:319-320`, `study/router.py` request model has no seed field | Direct blocker for "multi-seed runs available" and G-REL1. Primary W31 fix. |
| L2 | **Three separate seed-derivation schemes** (random.randint; consecutive `42+i`; SHA-256 `derive_seed`). No shared primitive. | **[V]** as above | Argues for one small seed module, not a fourth scheme. |
| L3 | **Comparison statistics are unpaired** (Welch) although both controls run on identical seeds; stated openly in code. | **[V]** `study/validation.py:197-214` | Out of W31 scope (paired tests are W32 #6). Record it; do not fix it. |
| L4 | **The "random driver" model is per-tick noise, not per-driver heterogeneity.** `StochasticIDM` draws a fresh aggression factor from `U(0.5, 1.5)` on every acceleration call, so driver character averages out and results depend on the number of ticks. It is only reachable via `unstructuredTraffic`, and has no effect when a vehicle mix is set (F-38 stage 1 fixed, stage 2 design open). Its RNG falls back to the *global* `random` if none is passed. | **[V]** `vehicles/stochastic_idm.py:13-48`; `docs/engineering/REFACTOR_FINDINGS.md` F-38 | The roadmap's "random driver model" is ambiguous (see D1). Whatever is built must not change any existing result. |
| L5 | **Demand is stationary.** Constant arrival rate; `burst` unimplemented; no time-varying or random-rate demand. | **[V]** `spawner.py` `_generate_next_arrival_time` | The roadmap's "random demand model" has no existing counterpart beyond Poisson (see D1). |
| L6 | **Provenance has no config hash, no input/schema version, no dirty-tree flag, no dependency versions.** The config itself is stored, so a hash is derivable, but it is not recorded or verified. Only some paths write provenance (API runs, batch, volume sweep, replays); Monte Carlo and the Robustness Lab produce their own result documents. | **[V]** `core/provenance.py:106-142`; `grep build_run_provenance` hits: `replays/router.py`, `simulations/registry.py`, `study/batch.py`, `study/volume_sweep.py` | Primary W31 gap for #7. |
| L7 | **Commit recorded without a dirty marker.** `get_git_commit_hash` reads `.git/HEAD`; uncommitted edits are invisible, so a manifest can claim a commit that did not produce the result. `start.ps1` handles this only for Docker. | **[V]** `provenance.py:33-62`; `docs/research/reproducibility.md` Docker note | Manifest must carry an explicit `dirty` / `unknown` state. |
| L8 | **CI branch filter is not "every push".** `push.branches` is `main, develop, backend, backend*, feature/*, viraj-dev`. A branch named otherwise (e.g. `frontend-vj`, `khushi-*`, an Antigravity-generated name) gets no CI until a PR to `main/develop/backend*` is opened. | **[V]** `.github/workflows/ci.yml:3-8`; `git branch -a` shows `frontend-vj` | Roadmap says "CI on every push". See D3. |
| L9 | **Local interpreter differs from CI/Docker** (partly mitigated: `roundabout_golden.py` already measured Windows/3.14 vs Linux/3.11 and pins portably at 1 µm / 12 digits, which T5 reuses). Local Python is 3.14.7 (test caches are `cpython-314`); CI and the image use 3.11.x. Fixed-seed regression pins written locally might not hold on 3.11. | **[V]** `python --version`; `__pycache__` names; `ci.yml`; `backend/Dockerfile:2` | Golden values must be generated and verified under 3.11 (or proven stable across both). |
| L10 | **Coverage gate is far below measured coverage** (85 vs 94.0). `pyproject.toml` itself says "ratchet this up". | **[V]** `pyproject.toml` comment | Ratchet is cheap; see D4 for the number. |
| L11 | **Golden fixed-seed pins exist only for the roundabout.** The signal junction (fixed-time and adaptive) has capacity-curve pins but no whole-run metric fingerprint corpus equivalent. | **[V]** only `roundabout_golden_fingerprints.json` under `tests/fixtures/` | Gap for "fixed-seed regression tests". |
| L12 | **Frontend coverage is not gated.** CI runs `npm run test`, but coverage runs only on demand, includes only `components/` and `services/` (not `metrics/`, `hooks/`, `utils/`), and has no threshold. | **[V]** `ci.yml` frontend job; `vite.config.ts:135-138` | "Frontend test setup hooked into CI" is largely already true; the real gap is coverage reporting. |
| L13 | **Frontend test runner has open advisories** (Vitest 3, fix is Vitest 5). Deferred major upgrade. | **[V]** `REFACTOR_FINDINGS.md` F-31 | Do not bundle a test-runner major upgrade into W31 (D5). |
| L14 | **No metric glossary exists.** Descriptions are scattered across `catalog.ts`, `plainLanguage.ts`, `metrics-reference.md` and `docs/product/urbanflow-evaluation-metrics.md`; no single user-facing page, and no test that every backend metric key has an entry. | **[V]** grep for "glossary" finds only the entry-model glossary (`frontend/src/metrics/entryModel.ts`) | Khushi's second W31 item. |
| L15 | **Hypothesis is not installed** and SciPy/NumPy are not dependencies ("NumPy is not approved" per `uncertainty/stats.py` header). | **[V]** `requirements*.txt` | Property tests are W32 (F4/F6). Nothing in W31 needs a new dependency. |
| L16 | `.coverage`, `coverage.json`, `backend/simulation.db` and a stray `backend/Z:no-such-drive` entry exist in the working tree. | **[V]** `ls backend` | Check they are ignored before CI changes touch artifacts (hardening item). |
| L17 | A pre-existing uncommitted change: `.claude/launch.json`. Not W31 related. | **[V]** `git status` | Leave alone. |

### 2.3 Roadmap vs repository — discrepancies to record (not silently resolved)

| # | Roadmap says | Repository says | Treatment in this plan |
| --- | --- | --- | --- |
| X1 | "Multi-seed runner" is new work | Three multi-seed runners already exist (L2) | Plan **generalises and de-randomises** the existing one; it does not add a fourth. |
| X2 | "pytest layout, coverage gate … CI on every push" are new | Layout, a 85 % gate and CI exist | Plan **ratchets and completes** them (golden corpus for signals, branch coverage of CI, markers applied). |
| X3 | "Frontend test setup hooked into CI" | `npm run test` already runs in the `frontend-lint-test` job | Plan reduces this to **coverage reporting/gating** and confirming the job. |
| X4 | "Run manifest: seed, config hash, code version" | Seed and commit are recorded; config hash is not; a different "manifest" (`urbanflow-experiment-manifest`) already means the `.ufpkg` package manifest | Plan **names the new record a "run manifest" distinct from the experiment manifest** and reuses its hashing helpers. See D2. |
| X5 | F4 "Closes D-AI1 (provider evaluation on `copilot-eval-v1`)" | `src/copilot/eval_gate.py` already gates CI (deterministic, no network) | Not a W31 item (W32/W35). The scope line shows only for context. |
| X6 | Roadmap lists SciPy/statsmodels/SALib as F6 tech | Not installed; project policy so far is stdlib-only statistics | Not needed in W31. Decide at W32 (D6). |
| X7 | Plan tracked as GitHub weekly issue | Not verifiable from the repo | Out of scope; mention only. |

---

## 3. Scope boundary

**In scope (taken from the roadmap):** the five bullets in section 1.
**Explicitly out of scope** (belongs to later weeks per WEEKLY_PLAN): confidence intervals and paired tests (W32 #6); Hypothesis property tests (W32 #4); Parquet/S3 run store (W32 #7); Copilot eval question set v1 (W32 #4); sensitivity analysis (W33); DuckDB / dbt; Dockerise/Helm/kind (W33 #3); Go (W36 #1); Airflow (W34/W37).

**Technology diversification verdict for W31 (as requested).** None of Go, AWS, Kubernetes, Airflow or an LLM judge is justified this week:

| Technology | In W31? | Reason |
| --- | --- | --- |
| Go | No | First Go service is W36 (#1). No Go-shaped boundary exists yet. |
| AWS / S3 | No | Run store on S3 is W32; AWS owner/cap decision is due W35 (B0 decision 1). A manifest is a local JSON/DB record. |
| Docker / Kubernetes / Helm | No | W33 (#3). Only touch Docker to keep `GIT_COMMIT` flowing so manifests do not read `unknown`. |
| Airflow | No | Nightly regression DAG is W34. GitHub Actions `schedule` already runs the nightly slow suite. |
| AI evaluation | No new work | Copilot eval gate already runs per push; extension is W32/W35. |
| CI/CD and DevOps practice | **Yes — this is W31's DevOps content** | Branch filter fix, coverage ratchet, artifact upload, concurrency, required-check naming. |

---

## 4. Task breakdown (recommended order)

Notation: **B** backend, **F** frontend, **CI** workflow, **D** docs. Complexity: S ≈ ≤ 0.5 day, M ≈ 1 day, L ≈ 2 days. Total ≈ 7–8 working days for Viraj's column at one pair of hands; the roadmap allots five. **See risk R1: recommended cuts are listed in section 9.**

### Dependency summary

```
T0 ─┬─► T1 ─► T2 ─┬─► T3 ─► T4
    │             │
    ├─► T5 ───────┘            T6 ─► T7 ─► T8     (CI/test lane, parallel to T1–T4)
    └─► T9 ─► T10                                   (Khushi lane, independent)
T11 (docs + handoff) last
```

---

### T0 — Baseline and decisions freeze (Viraj) — S

- **Objective.** Fix the facts the rest of the week depends on before any code.
- **Description.** (a) Run the fast suite and the full-coverage figure under **Python 3.11** (L9), record test count, wall time, coverage %. (b) Resolve D1–D4 (section 8) or adopt the recommended defaults in writing. (c) Create nothing in `src/`.
- **Files.** `docs/planning/` (append a "Baseline" table to this file's section 11).
- **Backend / Frontend.** None.
- **Dependencies.** None. **Blocks** T1, T3, T5, T7.
- **Testing.** n/a.
- **Acceptance.** Baseline numbers (tests, seconds, coverage under 3.11) recorded; D1–D4 answered or defaulted.

### T1 — Seed primitive and de-randomised multi-seed runner core (Viraj) — M

- **Objective.** One seed-derivation rule and one seedable multi-seed entry point; fix L1/L2.
- **Description.**
  1. New small module `backend/src/study/seeds.py` exposing `derive_run_seeds(base_seed, n)` using the same SHA-256 construction as `uncertainty/sampler.derive_seed` (reuse that function's approach; do **not** change `derive_seed` — its outputs are pinned by existing tests and package fingerprints).
  2. Add optional `seed: int | None` (0 … 2³¹−1) to `MonteCarloValidationRequest` (`study/router.py`) and `run_statistical_validation(... base_seed=None)`. When omitted, behaviour is unchanged **except** that the generated base seed is recorded in the result as `baseSeed` so the run can be repeated (an omitted seed is generated from an OS-seeded instance, never the global `random`).
  3. Result gains `baseSeed` and `seedScheme` fields additively; `seeds`, `seedRuns`, `individualRuns` keep their shapes (frontend reads them).
- **Files.** `backend/src/study/validation.py`, `backend/src/study/router.py`, new `backend/src/study/seeds.py`; schemas in `shared/schemas/` only if a result schema covers this payload (**check first**, then update both sides together).
- **Backend.** As above; validation errors reuse the router's pydantic style.
- **Frontend.** None required (additive fields). T10 may display `baseSeed`.
- **Dependencies.** T0.
- **Complexity.** M.
- **Testing.** Unit: same `seed` ⇒ identical `seeds` list and identical per-seed metrics; different `seed` ⇒ different list; seeds are distinct, in range; no use of global `random` *during runs*; the single base-seed draw when `seed` is omitted deliberately uses the module generator so callers that seed it stay repeatable (existing `tests/study/test_runner.py` relies on this). Integration: two API calls with the same seed return equal `signal`/`roundabout`/`comparison` documents; legacy request (no seed) still returns the old shape plus `baseSeed`. Regression: existing `tests/` for validation unchanged and green.
- **Acceptance.** Identical request ⇒ byte-identical statistics; legacy clients unaffected; no global-`random` use in the study path; mypy --strict clean.

### T2 — Generalise the runner to any scenario and N seeds (Viraj) — M

- **Objective.** "Multi-seed runs available" for a single scenario/strategy, not only the dual signal-vs-roundabout validation.
- **Description.** Add a thin `run_multi_seed(config, geometry, n_seeds, base_seed, ...)` over the existing `SimTask` / `run_simulation_tasks` pool, returning per-seed metrics plus a descriptive summary (n, mean, sample SD, min, max — **no CI or p-values; those are W32**). `run_statistical_validation` and `batch_tasks` are re-expressed on top of it only where this is behaviour-preserving (golden-verified); otherwise left alone.
- **Files.** `backend/src/study/runner.py` or new `study/multiseed.py`; optionally new route `POST /api/v1/study/multi-seed` (+ job variant mirroring Monte Carlo) in `study/router.py`; `docs/v3-api-reference.md`.
- **Backend.** Same limits mechanism as `study/limits.py` (max seeds, duration, time-step bounds). Respect worker caps (`study_workers`, `MAX_AUTO_WORKERS`).
- **Frontend.** None in W31 (results page integration is W32 Khushi).
- **Dependencies.** T1.
- **Complexity.** M.
- **Testing.** Result order independent of worker completion (run with 1 and 4 workers, compare); per-seed result equals the same seed run alone through `simulate_geometry`; cancellation and progress behave as for existing jobs; limits reject abuse (n_seeds, duration).
- **Acceptance.** Parallel and sequential execution give identical output; unit test proves the seed→result mapping; request limits enforced; endpoint documented in the API reference.

### T3 — Opt-in stochastic driver and demand models (Viraj) — L — **D1 decided; needs ADR-020 first**

- **Objective.** Meet "Random driver and demand models" without changing any existing result.
- **Description [A].** Read as: (i) **per-driver heterogeneity** — at spawn, draw a persistent multiplier per vehicle for IDM parameters (time headway, max acceleration, comfortable deceleration, desired speed) from declared bounded distributions; (ii) **demand variability** — a seeded random multiplier on the arrival rate (per run, and optionally per interval, e.g. 5-minute blocks), with Poisson arrivals retained within each block. Both driven only by the engine's existing private `rng` (or a *separate* derived stream so enabling one model cannot shift draws used by another).
  Default is **off**; with it off, the RNG draw sequence must be bit-identical to today (the golden corpus in T5 enforces this).
  Write **ADR-020 first** (project rule: ADR before structural change): what is random, parameter bounds and their basis (`assumed` by default, same honesty as ADR-015), how the draws are isolated, which existing flag it relates to (`unstructuredTraffic`, F-38), and the claims-register wording.
- **Files.** New `docs/decisions/adr-020-*.md`; `backend/src/core/config_models.py` (new optional block, e.g. under `traffic`); `backend/src/scenario/config_validation.py`; `backend/src/scenario/documents.py` (new fields **must not** alter `scenario_fingerprint` when absent — see the existing `_V15_OPTIONAL_APPROACH_FIELDS` pattern); `backend/src/vehicles/spawner.py`; `backend/src/vehicles/vehicle.py` / `idm.py` (per-vehicle parameters); `shared/schemas/config.schema.json`; `scripts/validate_schemas.py` run.
- **Backend.** Strict validation (finite, ordered bounds, caps like ADR-015's scale limits); fingerprints include the new block only when present.
- **Frontend.** None in W31. If exposed, UI is Khushi's later work; the schema/TS types in `frontend/src/types/` must stay compatible (additive optional).
- **Dependencies.** T0, **D1**, ADR-020 accepted. Independent of T1/T2 technically but shares `config_models.py`.
- **Complexity.** L (highest-risk item this week).
- **Testing.** Off ⇒ golden fingerprints unchanged (roundabout corpus + new signal corpus from T5). On ⇒ same seed gives identical run; different seeds differ; draws for demand do not change when driver model toggles (stream isolation test); distribution tests (sample means/bounds over many draws); validation rejects bad bounds; schema validator passes; metrics stay finite; safety audit (no overlap) still passes across the T5 corpus with models on.
- **Acceptance.** ADR-020 accepted; models off by default and provably bit-identical; models on are deterministic under a seed; claims register row added (assumed distributions, not calibrated).

### T4 — Wire models into the multi-seed runner and demo (Viraj) — S

- **Objective.** Show the point of the week: spread across seeds when models are on.
- **Description.** Multi-seed runs accept the T3 block through the normal scenario/config path; add an example to `docs/research/` and, if cheap, to `scripts/v3_demo.py`.
- **Files.** `docs/research/reproducibility.md` (new §), `docs/v3-api-reference.md`.
- **Dependencies.** T2, T3.
- **Testing.** One integration test: 8 seeds with models on ⇒ non-zero SD of `averageDelay`; same base seed ⇒ identical summary.
- **Acceptance.** Documented example reproduces exactly from its stated `baseSeed`.

### T5 — Fixed-seed golden regression corpus for signals (Viraj) — M

- **Objective.** Regression safety for the signal junction comparable to the existing roundabout corpus (L11); prerequisite for T3 safety.
- **Description.** Reuse the structure of `tests/controllers/roundabout_golden.py` and its JSON fixture: a small, fast set (fixed-time, adaptive; 1 and 2 lanes; low/medium demand; a few seeds; short duration) fingerprinting the **complete metrics document**; fast cases in the PR job, a larger corpus under `@pytest.mark.slow` and added to the nightly matrix **and** `tests/test_ci_slow_matrix.py`'s expectations. Generated under **Python 3.11**; include a documented regeneration command and a rule that a changed fingerprint needs a stated reason (copy the roundabout convention).
- **Files.** New `backend/tests/controllers/signal_golden.py`, `test_signal_golden_fingerprints.py`, `backend/tests/fixtures/signal_golden_fingerprints.json`; `.github/workflows/ci.yml` (matrix entry for the slow file).
- **Dependencies.** T0 (3.11 baseline). No dependency on T1–T4, but run before T3 merges.
- **Complexity.** M.
- **Testing.** Corpus passes on 3.11 in CI; deliberately perturbing a default (e.g. one IDM constant) in a scratch check fails it (record in the PR description, do not commit the perturbation).
- **Acceptance.** ≥ 12 fast fixed-seed cases fingerprinted; slow corpus wired into the nightly matrix; `test_ci_slow_matrix` green; regeneration documented.

### T6 — CI triggers and coverage ratchet (Viraj; `.github/` announced to both) — S

- **Objective.** "Every push runs the tests" and a gate that tracks reality (L8, L10).
- **Description.** (a) Change `push` to run on all branches (`branches: ["**"]`) **or** the narrower agreed alternative (D3); keep the existing `concurrency` cancel-in-progress to avoid cost. Keep `pull_request` targets. (b) Raise `--cov-fail-under` to the D4 value. (c) Upload coverage XML/JSON and the Copilot eval report as workflow artifacts (`actions/upload-artifact`, pinned like the other actions); no third-party coverage service. (d) Confirm `build-and-test` remains the single aggregate check and add the golden/slow test file entries from T5.
- **Files.** `.github/workflows/ci.yml`, `backend/pyproject.toml` (the one-number change; this is the **only** config edit and it is explicitly part of the roadmap's "coverage gate").
- **Dependencies.** T0 (baseline), T5 for matrix entry.
- **Complexity.** S.
- **Testing.** Verify on a throwaway-named branch that CI starts; verify the gate fails when lowered coverage is simulated locally (`--cov-fail-under` above measured).
- **Acceptance.** A push to any branch starts the pipeline; the gate equals the D4 number and the build is green with margin; artifacts downloadable.

### T7 — pytest hygiene (Viraj) — S/M

- **Objective.** A layout that is actually consistent ("pytest layout").
- **Description.** Markers `unit` and `integration` are registered but used in only 2 occurrences across 193 files **[V]**. Do not mass-edit. Add a `conftest.py` collection hook that auto-applies `integration` to tests under `tests/integration/`, `tests/api/`, `tests/v2_integration/` and `unit` elsewhere (path-based, no per-file edits), plus `--strict-markers`. Add a short `tests/README` section (or extend `docs/testing/README.md`) describing layout, markers, fixtures, golden regeneration and seed helpers. Add a shared `tests/seeds.py` constants (`GOLDEN_SEEDS`) only if T5/T1 need it.
- **Files.** `backend/tests/conftest.py`, `backend/pyproject.toml` (`--strict-markers` only if D-list agrees — otherwise skip), `docs/testing/README.md`.
- **Dependencies.** T5 (so the new files follow the layout).
- **Testing.** `pytest --collect-only -m unit` and `-m integration` partition the suite with no overlaps/gaps; full count unchanged vs T0 baseline; architecture tests still pass.
- **Acceptance.** Every test carries exactly one of `unit` / `integration` / `architecture` (or slow in addition); collected test count equals baseline.

### T8 — Run manifest: record and verify (Viraj) — M/L

- **Objective.** Every run leaves a record sufficient to re-run it (L6, L7).
- **Description.**
  1. New module `backend/src/core/run_manifest.py` with `build_run_manifest(...)` and `config_hash(config)` (canonical JSON, SHA-256, full 64-hex; reuse `uncertainty/spec.canonical_json` semantics — the config **excluding** only truly non-semantic keys, listed explicitly; document the list).
  2. Fields: `format: "urbanflow-run-manifest"`, `version: 1`, `seed`, `configHash`, `gitCommit`, `gitDirty` (`true/false/"unknown"`), `pythonVersion`, `engineVersion` (project version string, read from one place), `scenarioFingerprint` when a scenario document exists, `timing`, `runMode`, `baseSeed` + `seedScheme` for multi-seed runs, `createdAt`. **Never** secrets or user identifiers.
  3. Persist by extending `provenance_json` additively (provenance `schemaVersion` 2) — **no new table, no DB migration**; old rows (v1 or `null`) must still read. Expose through the existing `/reproducibility` payload (`database/dao.py:310-358`) and include in multi-seed results (T1/T2) and Monte Carlo results.
  4. `gitDirty`: best effort without a subprocess dependency (compare the `.git/index` mtime to tracked files is unreliable) — if not cheaply and reliably computable, record `"unknown"` and rely on the `GIT_COMMIT` build arg path; do not claim certainty (consistent with `provenance.py`'s "degrade to unknown" rule).
  5. A `verify_manifest(manifest, config)` helper: recompute `configHash`, compare; used by `/reproduce` to report *why* a re-run differs (config changed vs code changed vs environment).
- **Files.** New `backend/src/core/run_manifest.py`; `core/provenance.py` (schema bump + call), `database/dao.py`, `history/reproduce.py`, `history/router.py`, `simulations/registry.py`, `study/batch.py`, `study/volume_sweep.py`, `replays/router.py` (all existing `build_run_provenance` callers); `shared/schemas/` for the manifest; `sdk/python` models if they mirror the run payload (**check**); `docs/research/reproducibility.md` §3.
- **Backend.** Additive only; `Z:`-style Windows paths irrelevant. Security: manifest holds no PII/credentials (test it).
- **Frontend.** None required; `frontend/src/services/api.ts` run types gain optional fields (optional, backward compatible). The run page may show the config hash — Khushi's later work.
- **Dependencies.** T0; benefits from T1/T2 (multi-seed fields) but can be built in parallel.
- **Complexity.** M/L (touches many callers, but each is one line).
- **Testing.** Unit: `config_hash` stable under key order, changes on any semantic edit, ignores only the declared non-semantic keys; manifest round-trips through JSON; schema validates. Integration: run → save → read back manifest; v1/legacy rows still load (fixture row without manifest); `/reproduce` of a fresh run matches **and** reports `configHash` verified; tampered config reports mismatch. Determinism: two runs with the same config+seed give identical `configHash` and identical results.
- **Acceptance.** All persisted runs carry the manifest; legacy rows unaffected; hash verified on reproduce; no new tables; mypy --strict and ruff clean.

### T9 — Frontend coverage in CI (Khushi) — S

- **Objective.** Resolve X3/L12.
- **Description.** Verify the existing CI test step; extend coverage `include` to `src/metrics/**`, `src/hooks/**`, `src/utils/**`, `src/services/**`, `src/components/**`; add `test:ci` script (`vitest run --coverage`) used by the CI job; set a **non-regressive threshold** equal to the measured figure minus ~2 points (measure first, record it); upload `lcov`. **Do not** upgrade Vitest (D5) and do not add dependencies (`@vitest/coverage-v8` is already present).
- **Files.** `frontend/vite.config.ts` (coverage block), `frontend/package.json` (script only), `.github/workflows/ci.yml` (one step).
- **Dependencies.** T6 (shared workflow file — coordinate).
- **Testing.** CI frontend job green with thresholds; temporarily raising the threshold above measured fails the job (local check).
- **Acceptance.** Coverage report produced on every PR; threshold recorded in `docs/testing/README.md`; Prettier/ESLint/tsc still pass.

### T10 — Plain-words metric glossary (Khushi) — M

- **Objective.** A single plain-language glossary of every metric (L14).
- **Description.** Source of truth is `frontend/src/metrics/catalog.ts` (42 `MetricDef`s) — add a `plain` (everyday-words) field only where `description` is too technical, then render a Glossary view (page or panel reachable from the metrics tables) and publish the same content as `docs/product/metric-glossary.md` **generated or checked** from the catalog so they cannot drift. Add a test that every numeric key exposed by `MetricCollector.get_metrics()` (backend) has a catalog entry **or** is on an explicit documented exclusion list. Plain wording follows the claims discipline (no overstating; carry the warm-up and "no data yet" caveats already encoded in `metricState`).
- **Files.** `frontend/src/metrics/catalog.ts`, `frontend/src/metrics/plainLanguage.ts` (read only), new `frontend/src/components/.../MetricGlossary.tsx` (+ test, axe-clean), route/link in the app shell, `docs/product/metric-glossary.md`.
- **Backend.** None, except a read-only test that lists metric keys (a small fixture `shared/` file or the test reads a backend run output committed as a fixture) — preserving the `backend/`↔`frontend/` import boundary (PR template rule).
- **Dependencies.** None (independent lane).
- **Complexity.** M.
- **Testing.** Component test (renders all 42, search/filter works, empty and long-text states); axe; catalog↔backend key parity test; Prettier/ESLint/tsc.
- **Acceptance.** Every shown metric has a plain-words entry; parity test fails when a new metric is added without one; accessible; docs page matches the UI.

### T11 — Documentation and hardening handoff (Viraj) — S

- **Objective.** Leave the repo and the Claude hardening session ready.
- **Description.** Update `docs/research/reproducibility.md`, `docs/testing/README.md`, `docs/v3-api-reference.md`, `docs/v3-release-candidate.md` (claims-register rows for the stochastic models and the manifest), `docs/plan/WEEKLY_PLAN.md` status; ADR-020 Accepted. Fill section 10 evidence.
- **Acceptance.** Section 10 checklist has evidence for every line.

---

## 5. Technical architecture plan

```
                 ┌───────────────────────────────────────┐
 request(seed?) ─►  study/router.py  (Monte Carlo, multi-seed, job variants)
                 └───────────────┬───────────────────────┘
                                 │ base_seed
                 ┌───────────────▼───────────────┐
                 │ study/seeds.py  derive_run_seeds │  (new, tiny; SHA-256 scheme)
                 └───────────────┬───────────────┘
                                 │ N seeds
                 ┌───────────────▼───────────────┐      existing, reused as is
                 │ study/runner.py SimTask pool   │─────► engine (private random.Random per run)
                 └───────────────┬───────────────┘
                                 │ per-seed metrics
                 ┌───────────────▼───────────────┐
                 │ summary (n, mean, SD, min/max) │  (CI / p-values arrive in W32)
                 └───────────────┬───────────────┘
                                 │
        core/run_manifest.py  ◄──┴── every result and every persisted run
              │ additive (provenance schemaVersion 2)
              ▼
   database/dao.py provenance_json  ─►  history /reproducibility, /reproduce (verifies configHash)
```

- **Reused unchanged:** engine, spawner RNG discipline, process pool, `derive_seed` (Robustness Lab), `provenance.py` commit/Python lookup, `.ufpkg` manifest, scenario fingerprints, Copilot eval gate, bundle budgets.
- **New modules (small):** `study/seeds.py`, `study/multiseed.py` (or an addition to `runner.py`), `core/run_manifest.py`, `tests/controllers/signal_golden*.py`, `frontend/.../MetricGlossary.tsx`.
- **Not created:** no new DB table, no queue, no service, no dependency.
- **Backward compatibility.** Additive JSON fields only; request seed optional; old provenance rows readable; scenario/config fingerprints unchanged when new blocks are absent; the Robustness Lab and `.ufpkg` fingerprints must not change (a package-fingerprint test already exists in `tests/experiments/`; keep it green).
- **Performance.** Multi-seed cost is `n_seeds × sim time`; reuse the pool and the existing limits; the manifest hash is O(config size). Budget: the fast backend suite must stay within the T0 baseline + 10 % (full suite is ~6.5 min on four workers per the CI comment); new golden fast cases ≤ 60 s total on CI.
- **Security.** Seed is a bounded int; request limits on seeds/duration; manifest excludes secrets and user data (explicit test); CI workflow keeps `permissions: contents: read` (artifact upload needs no extra permission); no new third-party Action beyond pinned `actions/upload-artifact`.
- **Data integrity.** Hashes over canonical JSON with documented exclusions; manifest verify detects config drift; `unknown` is recorded rather than guessed.
- **Observability.** Log base seed, hash prefix and commit at run start/finish (existing logger); no new infrastructure.

---

## 6. Dependency map and blockers

| Task | Needs | Blocks | Could be blocked by |
| --- | --- | --- | --- |
| T0 | — | T1, T3, T5, T6 | Python 3.11 not available locally (install one; do not pin results to 3.14) |
| T1 | T0 | T2, T4, T8 (partly) | Result schema in `shared/` needing dual review |
| T2 | T1 | T4 | Worker-pool behaviour on Windows vs Linux |
| T3 | T0, **D1**, ADR-020 | T4 | Product-owner answer on what "random driver/demand" means; F-38 stage-2 design is still open |
| T4 | T2, T3 | — | — |
| T5 | T0 | T3 safety, T6, T7 | 3.11 vs 3.14 numerical drift (L9) |
| T6 | T0, T5 | T9 | `.github` is shared: must be announced to Khushi |
| T7 | T5 | — | — |
| T8 | T0 | T11 | Many callers; `sdk/python` mirror; legacy rows |
| T9 | T6 (workflow file) | — | Coverage figure unknown until measured |
| T10 | — | — | Wording sign-off |
| T11 | all | handoff | — |

Critical path: T0 → T5 → T3 (needs D1) → T4. T3 is the schedule risk; if D1 slips, ship T1, T2, T5, T6, T7, T8 and defer T3/T4 inside the release (scope cut, not date cut — plan README §7).

---

## 7. Testing strategy

| Deliverable | Unit | Integration | Regression | Edge cases | Performance |
| --- | --- | --- | --- | --- | --- |
| T1 seeds | same seed ⇒ same list; range; distinct; no global `random` | API twice, equal output | existing validation tests | seed 0, 2³¹−1, `numSeeds` = 1, max | negligible |
| T2 multi-seed | per-seed result == solo run; order independence | job progress/cancel; limits | pool behaviour unchanged | 1 seed; seed with vehicle cap hit; failed run recorded not dropped silently | wall-time vs `n_seeds` (record) |
| T3 models | distributions in bounds; stream isolation; validation errors | models-on run deterministic | **golden corpora unchanged with models off** | zero-width bounds, extreme multipliers, fingerprint absence/presence | models-on overhead ≤ 5 % per tick (measure) |
| T5 golden | fingerprint function | fast corpus in PR job | whole-metrics pin | Python 3.11 only | fast set ≤ 60 s |
| T6 CI | — | branch push triggers; gate fails when expected | `test_ci_slow_matrix` | forks/Dependabot branches | job time ≤ baseline + 10 % |
| T7 layout | marker partition | collect-only | count == baseline | files with several markers | collection time |
| T8 manifest | hash stability/sensitivity, schema | save→read, reproduce, tamper | legacy rows, `.ufpkg` fingerprints | missing `.git`, `GIT_COMMIT` env, dirty unknown | hash cost trivial |
| T9 FE coverage | — | CI step | existing 56 test files | threshold edge | CI time delta |
| T10 glossary | catalog entries complete | axe, render, parity with backend keys | existing metric tests | long text, no-data states | bundle budgets (`check_bundle_budgets.mjs`) must still pass |

Standing gates that must stay green: ruff, `ruff format --check`, `mypy --strict`, `scripts/validate_schemas.py`, backend fast suite, Copilot eval gate, frontend lint/tsc/prettier/vitest/build + bundle budgets, SDK checks, nightly slow matrix.

---

## 8. Decisions needed (flagged, not assumed)

| ID | Decision | Recommended default | Needed by | Blocks |
| --- | --- | --- | --- | --- |
| D1 | **DECIDED 2026-11-03 (Viraj): opt-in heterogeneity.** "Random driver and demand models" = per-driver heterogeneity (persistent per-vehicle IDM multipliers drawn at spawn) + seeded demand-rate variability, **off by default**, specified in ADR-020 before code. The smaller "make existing `StochasticIDM`/Poisson seedable only" reading is rejected. T3 stays L. | ADR-020 | — | T3, T4 (unblocked) |
| D2 | Name of the new record: "run manifest" collides with the `urbanflow-experiment-manifest` term. | `urbanflow-run-manifest`, documented as distinct | Tue | T8 |
| D3 | "CI on every push": all branches vs the current pattern list. | `["**"]` with the existing cancel-in-progress concurrency; Dependabot already uses PRs | Tue | T6 |
| D4 | New coverage floor. Measured 94.0 % (2026-10-30; re-measure on 3.11 in T0). | measured − 2 points ≈ **92** (leaves room for the new code to be covered first) | after T0 | T6 |
| D5 | Vitest 5 upgrade (F-31) inside W31? | No; separate change | now | — |
| D6 | SciPy/statsmodels/SALib: adopt for W32+ or keep stdlib-only (current policy, in-house t-distribution)? | Decide at W32 start; W31 needs neither | W32 | — |
| D7 | Is `gitDirty` worth implementing without a subprocess? | Record `"unknown"` unless computed reliably; do not guess | T8 | T8 detail |
| D8 | B0 decisions 3 (exam/leave dates) and 1 (AWS owner/cap) remain **Open** in `B0_SETUP.md`; neither blocks W31, but leave dates affect whether a 5-day week is real. | — | now | planning |

---

## 9. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R1 | **Scope exceeds five days** (≈ 7–8 days est.). | High | High | Cut order: T4 → T7 → T2 (keep T1) → T3. Roadmap rule: scope moves, date does not. Tasks T5, T6, T8, T1 are the non-negotiables (they map to the three sprint-goal bullets). |
| R2 | Stochastic model changes existing results. | Medium | High | Off by default; stream isolation; golden corpora are the gate; ADR first. |
| R3 | Golden pins differ between Python 3.11 and 3.14 (L9). | Medium | Medium | Generate and run on 3.11; add a CI-only note; if drift found, document and pin to the CI interpreter. |
| R4 | D1 ambiguity wastes the week. | Medium | High | Resolve Tuesday; fallback reading is cheap. |
| R5 | Provenance change breaks readers (frontend, SDK, saved runs). | Low–Med | High | Additive-only; legacy-row tests; `sdk/python` check; `.ufpkg` fingerprint tests stay green. |
| R6 | CI cost/noise from "all branches". | Low | Low | Existing concurrency cancel; artifact retention short. |
| R7 | Flaky timing-dependent tests. | Low | Medium | Fixed seeds; no wall-clock assertions except coarse budgets. |
| R8 | Unrelated work collides in the tree (previous sessions noted another actor editing files). | Medium | Medium | Check `git status` at start; keep changes per task; viraj-dev only, no feature branches (project work-style). |
| R9 | Metric glossary wording overclaims. | Low | Medium | Follow claims discipline; reviewer checks warm-up/no-data caveats. |
| R10 | Coverage threshold set from a stale figure. | Low | Low | Re-measure in T0/T9; record the number. |

---

## 10. Definition of done and Claude hardening handoff

### 10.1 Definition of done (objective)

| Dimension | Measurable condition |
| --- | --- |
| Feature completion | T1, T2, T5, T6, T8, T9, T10 merged (T3/T4/T7 per risk cuts, with the cut recorded); the three sprint-goal bullets demonstrably true: (1) same `seed` ⇒ identical multi-seed output; (2) a push to a non-listed branch name starts CI; (3) a saved run exposes seed, `configHash`, commit |
| Integration | Fast backend suite, Copilot eval gate, frontend CI, schema validation and SDK jobs green on `viraj-dev`; `build-and-test` aggregate green |
| Test coverage | Backend ≥ D4 floor and not lower than T0 baseline; new modules (`seeds`, `run_manifest`, multi-seed) ≥ 95 % line coverage; frontend threshold per T9; golden fast cases ≥ 12 |
| Regression safety | Roundabout golden corpus and new signal corpus unchanged with models off; `.ufpkg` package fingerprints unchanged; legacy provenance rows load; no existing test edited to make it pass (any edit justified in the commit) |
| Performance | Fast suite wall time ≤ T0 + 10 %; frontend bundle budgets pass; models-on overhead measured and recorded |
| Documentation | `reproducibility.md`, `testing/README.md`, `v3-api-reference.md`, claims register, ADR-020 (if T3), glossary page, WEEKLY_PLAN status updated; this file's section 11 filled |

### 10.2 What Claude's weekly hardening pass must verify (each item is independent)

1. **Code review** of T1–T3, T8 diffs: no global `random`; no behavioural change when features are off; additive JSON only.
2. **Integration verification**: run the full local suite under Python 3.11 and the nightly slow files touched by T3/T5; confirm CI on a fresh branch name.
3. **Determinism audit**: repeat each golden and multi-seed call twice across processes and worker counts (1 vs 4); compare byte-for-byte.
4. **Security review**: seed and limits handling (abuse bounds), manifest contains no secrets/PII, workflow permissions unchanged, no new Action unpinned.
5. **Test expansion**: edge cases listed in section 7 not yet covered; mutation-style spot checks (perturb a constant, expect golden failure).
6. **Performance**: fast-suite time vs baseline; models-on overhead; multi-seed scaling with workers.
7. **Backward compatibility**: legacy runs in `simulation.db` fixtures; frontend `api.ts` types; SDK models; Robustness Lab and `.ufpkg` fingerprints.
8. **Documentation verification**: every claim in the new docs matches code behaviour; claims-register wording.
9. **Refactoring**: consolidate the three seed schemes only if behaviour-preserving (golden-proven); otherwise record as debt.
10. **Final regression**: complete `pytest` (including slow where affected), frontend `npm run test` with coverage, bundle budgets, schema validation.

---

## 11. Evidence log (to be filled during implementation)

| Item | Result | Date |
| --- | --- | --- |
| T0 baseline (Python 3.11): tests / wall time / coverage % | **Not obtainable locally** (only 3.14.7 installed); take it from the first CI run on 3.11. | 2026-11-03 |
| T1 seeded Monte Carlo (`study/seeds.py`, `seed`/`baseSeed`) | Implemented; 138 tests in the study/api/metrics subset pass on 3.14; ruff, ruff format, mypy clean | 2026-11-03 |
| T2 multi-seed runner and routes | Done: `study/multiseed.py`, `POST /api/v1/study/multi-seed` (+ jobs); parallel = sequential, each seed equals the solo run | 2026-11-03 |
| D1–D4 answers | D1 opt-in heterogeneity (user). D2 `urbanflow-run-manifest`, D3 `["**"]`, D5 no Vitest upgrade, D6 deps at W32, D7 `gitDirty` always `"unknown"`: taken at the plan's recommended defaults. D4 (backend floor): **open**, needs a 3.11 CI number. | 2026-11-03 |
| Golden fast case count and regeneration command | T5 done: 13 fast + 6 slow signal cases (`tests/controllers/signal_golden.py`); fast file 38 s, slow shard 12 tests pass locally; regenerate with `python -m tests.controllers.signal_golden --record --force`. Mutation check: +0.1 % IDM free acceleration fails 26/45. Recorded on Windows/3.14.7 only; portable pins unverified on Linux/3.11 until the first CI run. | 2026-11-03 |
| Coverage floor set to | Unchanged at 85. Measured 94.0 % on Windows/3.14; raise to about 92 from the `backend-coverage` artifact of the first green 3.11 CI run (T6). | 2026-11-03 |
| Frontend coverage threshold set to | Measured 76.18 % statements/lines, 79.69 % branches, 62.03 % functions over metrics/hooks/utils/services/components; thresholds 74 / 77 / 60 (about 2 below). `npm run test:ci` (30 s test timeout: one 5 s test timed out under instrumentation). 586 tests pass. | 2026-11-03 |
| T6 CI trigger + artifacts | `push` on `"**"`; `backend-coverage`, `copilot-eval-report`, `frontend-coverage` artifacts. **Not run on GitHub yet**; first push gives the run URL and the 3.11 baseline | 2026-11-03 |
| T7 markers | Path-based hook + `--strict-markers`; 3172 collected = 1983 unit + 1184 integration + 5 architecture, none unmarked | 2026-11-03 |
| T8 run manifest | `core/run_manifest.py`, provenance schema 2, exposed by `/reproducibility`, checked by `/reproduce` (`manifestCheck`), in multi-seed and Monte Carlo results; `shared/schemas/run-manifest.schema.json`. SDK does not mirror the run payload (no match for provenance/reproducibility in `sdk/python`). Frontend `api.ts` types not extended (optional) | 2026-11-03 |
| T3/T4 models | `vehicles/variability.py`, ADR-020; off ⇒ whole fast suite and both golden corpora unchanged; 24 unit/engine tests + 2 multi-seed tests. Example in `reproducibility.md` §5.3a: spread across 8 seeds is similar with models on (delay SD 3.13 vs 3.41); stated as descriptive, not an effect. Not exposed in scenario documents (cut, ADR-020) | 2026-11-03 |
| T10 glossary | `plain` text on 28 catalog metrics, `metrics/glossary.ts`, `MetricGlossary` in the Research lab, `docs/product/metric-glossary.md` (test-checked), parity with the collector via `shared/metrics/collector-metric-keys.json` (backend and frontend tests) | 2026-11-03 |
| ADR-020 status | Accepted 2026-11-03 (D1 taken by the project owner; opt-in, off by default) | 2026-11-03 |

---

## 12. Verified facts vs assumptions (summary)

- **Verified in this investigation:** every [V]-tagged row above; roadmap text for W31, F4, F6, F7; CI contents; existing multi-seed, provenance and golden-test implementations; local Python 3.14.7 vs CI/Docker 3.11.
- **Assumptions:** D1's interpretation of "random driver and demand models"; effort estimates; that the 94.0 % coverage figure still holds on 3.11; that no result schema in `shared/` covers the Monte Carlo payload (T1 says to check); that Khushi owns T9/T10 as the roadmap's column assigns.
- **Not investigated (out of scope for planning):** the GitHub weekly issue state, Antigravity tooling specifics, and the contents of every one of the 193 test files.
