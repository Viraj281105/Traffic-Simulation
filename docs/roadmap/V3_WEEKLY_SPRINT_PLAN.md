# V3.0 Weekly Sprint Plan — 12 October to 26 November 2026

> **Status:** PROPOSED — pending review · **Written:** 2026-10-12 (Monday) · **Depends on:** [audit](V2_COMPLETION_AUDIT.md) (must-fix M1–M6) and [strategy](V3_PRODUCT_STRATEGY.md) (initiatives I-1, I-2, I-3; integration spine)
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)

---

## 0. Plan at a glance

**Fixed points:** preview **Thursday 29 October** · full presentation **Thursday 26 November**. Both are dates, not targets.

| Sprint | Dates | Theme | Cap. ED | Plan ED | Load | What a reviewer can use at the end | Gate |
| --- | --- | --- | :-: | :-: | :-: | --- | --- |
| **S0** | Mon 12 – Sun 18 Oct | V2.0 closure (security, first planner screen) + architecture decisions | 4.5 | 4.25 | 94 % | Run a 3-alternative study **from the browser**; a second user cannot see the first user's calibration runs or suites | **G0** Tue 13: owner approves scope and commits the pending work |
| **S1** | Mon 19 – Sun 25 Oct | **Preview slice:** Robustness Lab + SDK + package | 5.5 | 5.2 | 95 % | Submit an uncertainty experiment **from Python**, watch it in the UI, read probability-of-better / regret / flip points, export a package | **G1** Fri 23: preview feature freeze |
| **S2** | Mon 26 – Wed 28 Oct | Stabilise, rehearse, fallback assets | 3.0 | 2.75 | 92 % | Cancel/resume long runs; verify and import a package offline; two timed rehearsals | **G2** Wed 28 17:00 go/no-go |
| — | **Thu 29 Oct** | **PREVIEW PRESENTATION** | | | | | |
| **S3** | Fri 30 Oct – Thu 5 Nov | **Control Lab:** signal-control environment, baselines, learned policy, evaluation | 5.5 | 4.75 | 86 % | Evaluate five controllers (incl. one learned, labelled EXPERIMENTAL) on held-out seeds in three regimes | **G3** Thu 5 Nov: policy shell safety proof |
| **S4** | Fri 6 – Thu 12 Nov | **Platform + Emergency pre-emption v1** | 5.5 | 4.75 | 86 % | Tokens, quotas, `/api/v3` for three experiment kinds; ambulance pre-emption at a signal with response-time and collateral metrics | **G4** Thu 12 Nov: emergency go/no-go |
| **S5** | Fri 13 – Thu 19 Nov | Integration, data in/out, quantitative evaluation | 5.5 | 4.75 | 86 % | CSV counts in, GeoJSON out; learned/emergency alternatives inside the robustness view; three evaluation studies with recorded numbers | **G5** Thu 19: feature freeze for RC |
| **S6** | Fri 20 – Wed 25 Nov | Release candidate: hardening, reproducibility, docs, rehearsal | 4.4 | 3.75 | 85 % | One-command reproduction of every published number; clean-checkout demo; docs | **G6** Wed 25 17:00 go/no-go |
| — | **Thu 26 Nov** | **FULL V3.0 PRESENTATION** | | | | | |

Totals: capacity ≈ 33.9 ED, planned ≈ 30.2 ED (89 %). **S0–S1 are deliberately loaded to 94–95 %** because the preview date is fixed and V2.0 closure cannot wait; they carry an explicit cut-line (§1.3). After the preview, loads are ≤ 86 %.

### 0.1 Capacity assumptions (restated, unconfirmed)

One primary engineer + coding agents. **ED** = one reviewed, tested, merged engineer-day. Weekends are *buffer*, never plan. Monday 12 Oct is spent on this audit and owner review, so S0's capacity is 4.5 ED. Calendar facts: S3 and S4 and S5 each contain five working days (Fri + Mon–Thu); S6 has four (Fri, Mon–Wed). If the actual number of contributors or hours differs, scale the plan by the cut-line order in §1.3 and §9, not by squeezing quality.

### 0.2 Safe parallel lanes

Three agents can work at once **only if they own disjoint files**. `main.py` (3,380 lines) is the collision point: every new router is mounted by **one line** by a single owner.

| Lane | Owns | Does not touch |
| --- | --- | --- |
| **B — backend / simulation** | `backend/src/{uncertainty,experiments,rl,emergency}/`, `controllers/{policy_shell,registry}.py`, `backend/tests/*` for those | `engine.py`, `vehicles/idm.py`, physics constants |
| **F — frontend** | `frontend/src/{services/v2,services/v3,features/*}`, routes (with the mirrored nginx/Vite hooks) | existing dashboards other than adding links |
| **P — platform & docs** | `sdk/python/`, `shared/schemas/v3/`, `docs/`, migrations, CI | application logic |

### 0.3 Rules for every sprint

* Existing strategies are baselines and are **never edited to be beaten**. A new controller is a new strategy.
* No change to simulation physics or scientific parameters without a recorded reason; the pre-existing determinism tests (`tests/core/test_determinism.py`, `tests/study/test_runner.py`, V1.4/V1.5 reproduction pins) must stay green and unmodified.
* Schema changes use the existing inline-migration pattern, are tested on a **copy** of `simulation.db`, and are additive.
* Every consumer of a changed result contract gets a test that feeds it the new value (lesson from the `cohensD: null` CLI crash, audit §8).
* The UI shows a capability only when `GET /api/v3/capabilities` (from S1) says the backend has it.

---

## 1. Sprint 0 — Monday 12 – Sunday 18 October

### 1.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Mon 12 – Sun 18 Oct. Working days Tue 13 – Fri 16; Mon 12 = audit + owner review; weekend = buffer |
| 2 | **Main objective** | Close the data-isolation defects, put the first V2.0 planner screen in front of a user, commit the hardening work, and fix the V3 architecture so S1 can start on Monday without debate |
| 3 | **Major features delivered** | (a) Owner-scoped, consistently protected `/api/v2` and `/api/suites*` (M2, M3). (b) **Planner UI v0** at `/app/planning`: scenario → alternatives → run with progress → summary results (M1, first half). (c) Three ADRs and a measured compute budget |
| 4 | **Backend / simulation** | **M2:** user dependency on `calibration` router and `planning/validate`; `networks` router gets the API-key dependency plus a user dependency; request-body cap (1 MB) on `/api/v2` and `/api/v3`; `user_id` column on `uf_calibration_runs` via the existing inline `ALTER TABLE` pattern; legacy rows owner-less (admin-visible only). **M3:** `user_id` on scenario suites, scoped `list/get/batch/export`, legacy rows admin-only. **Spikes (≤ 0.25 ED):** re-measure steps/s on the demo machine at 3 loads; confirm NumPy installs on the chosen Python; time a 20-sample Latin-hypercube prototype over the existing comparison path |
| 5 | **Frontend / product** | Typed client `frontend/src/services/v2/`; page `/app/planning` registered **together** in `routing.ts`, the nginx template and `vite.config.ts` (the existing mirror test enforces this). Step 1 *Scenario* reuses the scenario builder and presets. Step 2 *Alternatives*: fixed-time / adaptive / roundabout toggles, seeds and demand scales within server limits, with **simulation count and estimated time from `/planning/validate`** shown before submit. Step 3 *Run*: job progress by polling, then summary table, validity banner ("no field calibration"), caveats. `unavailable` indicators render as "not available", never 0 |
| 6 | **Integration work** | **M4:** owner reviews and commits the 26 pending entries on `viraj-dev`, pushes, PR to `main`, CI green. Save an OpenAPI snapshot as the baseline for contract tests. Settle the supported Python version (D5) |
| 7 | **Scientific validation and testing** | Ownership tests per route (mirror `tests/api/test_replay_ownership.py`): A cannot list/get/export B's calibration runs or suites (404), anonymous gets 401 when `API_KEY` is set, dev bypass still works. Negative-input tests. Vitest tests for the planner with a mocked API. **Null-contract test:** every consumer of `cohensD`/`pValue` (frontend, CLI, report generator, planning findings) is fed `null` |
| 8 | **Documentation and demo assets** | ADR-013 *integration contract and versioning* (`/api/v3`, additive-only v1/v2, document envelope); ADR-014 *signal-policy seam and registry* (completes ADR-012); ADR-015 *uncertainty design* (factors, sampling, CRN, guardrails). Decision log for D1–D8. Compute-budget table re-measured |
| 9 | **Dependencies and risks** | Owner review/commit on Tue 13 (blocks everything). Migration touching production data — rehearse on a copy of `simulation.db`. Planner scope creep → cut export/reproduce/findings to S1. Spike may show the machine is slower than assumed → shrink presets in S1 (do not shrink the guardrails) |
| 10 | **Acceptance criteria** | **AC-0.1** `pytest -m "not slow"` green with ≥ 90 % coverage after the commit. **AC-0.2** New ownership tests pass; removing the `user_id` filter makes them fail (mutation check done once by hand). **AC-0.3** A user can complete scenario → 3 alternatives → results in the browser against a local server with `DEV_AUTH_BYPASS=1`; verified by a vitest flow test and one manual run. **AC-0.4** `grep -r "api/v2" frontend/src` is non-empty and the routing mirror test passes. **AC-0.5** Three ADRs merged; D1–D8 each marked decided/deferred. **AC-0.6** Measured steps/s recorded in the compute table |
| 11 | **User-visible difference** | The V2.0 backend finally has a front door. A planner can compare three controls from the browser. Other users' calibration data and suites are no longer readable |
| 12 | **Explicitly deferred** | Findings/evidence panel, export, reproduce button → S1. Field-data (calibration) step → S5. Tokens/quotas → S4. Roadmap/README status sync beyond API docs → S1 (API) and S6 (roadmap) |

**ED budget (4.25 of 4.5):** M2 1.25 · M3 0.75 · M4 0.25 · planner v0 1.5 · ADRs + spikes 0.5.

### 1.2 Day plan (guide, not contract)

| Day | Lane B | Lane F | Lane P |
| --- | --- | --- | --- |
| Tue 13 | M2 (routes, tests) | Client + route registration | Owner review/commit (G0); ADR drafts |
| Wed 14 | M3 migration + tests | Scenario + alternatives steps | Spikes; Python-version decision |
| Thu 15 | Null-contract tests; OpenAPI snapshot | Run + progress + summary | ADR-013/014/015 final |
| Fri 16 | Fixes from review | Vitest flow; polish | Decision log; S1 hand-off checklist |

### 1.3 Cut-line for S0 and S1 together (cut in this order if behind)

1. Roadmap status sync (stays in S6). 2. Planner "Reproduce" button. 3. Robustness *flip chart* (keep the flip *table*). 4. Notebook polish (keep the script). 5. Package export (keep JSON result export). **Never cut:** M2, M3, M4, the robustness backend, the experiment viewer, the SDK's submit/wait/result.

---

## 2. Sprint 1 — Monday 19 – Sunday 25 October

### 2.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Mon 19 – Sun 25 Oct. Working days Mon–Fri; **feature freeze Fri 23 Oct 18:00 (G1)**; weekend = overflow only |
| 2 | **Main objective** | Build the preview's vertical slice end to end: define uncertainty → run a paired ensemble → read what it shows → do all of it from code |
| 3 | **Major features delivered** | (a) **Robustness Lab** v1 (I-1): spec, Latin-hypercube sampling, common-random-number runs, robustness analysis with guardrails. (b) `/api/v3/experiments` envelope for `kind: "robustness"`, plus `/capabilities`. (c) **Experiment viewer** `/app/experiments/:id`. (d) **Python SDK** (submit / wait / result / package / ui_url). (e) Planner v1 completion: findings, validity, export. (f) Experiment package export |
| 4 | **Backend / simulation** | New `backend/src/uncertainty/`. **`spec.py`** — `urbanflow-uncertainty-spec` v1 (`extra="forbid"`): factors `{id, kind, dist{uniform \| triangular \| truncnormal \| lognormal}, bounds, basis: assumed \| observed \| user}`; kinds: global/per-approach demand scale, turning shift, mix shift, IDM headway scale, desired-speed scale, max-acceleration scale (all via existing input fields and the `advanced` merge — **no physics edits**); `n`, `seed`, `replicates`, `alternatives`, `tieTolerance`, `confidence`. **`sampling.py`** — stratified Latin hypercube, deterministic from `random.Random(seed)`; a perturbed scenario that fails `validate_scenario` is rejected and reported, never silently repaired (mix is never rescaled). **`runner.py`** — expands to samples × alternatives × replicates tasks on the existing `run_simulation_tasks` pool; **CRN**: all alternatives share the sampled scenario and the engine seed for each (sample, replicate); runs that hit `vehicleLimitReached` or fail are excluded **and counted**. **`analysis.py`** — paired differences vs baseline; P(alternative better by more than tie tolerance) with Wilson interval; expected and worst-case regret; preferred-share; Spearman rank-correlation sensitivity; flip detection along the strongest factor (sign change of the paired difference between strata); convergence trace; guardrails (< 30 → *indicative*, ≥ 100 + converged → *robust-eligible*). **`/api/v3/experiments`** (`POST` → 202, `GET /{id}`, `GET /{id}/result`, `GET /{id}/package`, `DELETE`) and `GET /api/v3/capabilities`; the experiment kind is a registry entry from day one so S4 adds kinds without refactoring |
| 5 | **Frontend / product** | **Experiment viewer:** header (kind, status, fingerprint, N, preset, estimated vs actual time); evidence badge (*Indicative* / *Robust-eligible*) with the rule in a tooltip; tabs — **Distribution** (paired-difference plots per alternative, Recharts), **Preference** (P(better) with interval, regret, preferred-share — never "winner"), **What drives it** (rank-correlation bars, flip table), **Conditions** (factors, priors with `basis`, exclusions, failures), **Provenance**. **Launch:** "Check robustness" from planner results; preset picker (Quick / Standard / Thorough) showing runs and estimated time before submit. Planner v1: findings with evidence paths, export links (json/md/csv), validity. Responsive down to 375 px |
| 6 | **Integration work** | **SDK** `sdk/python/urbanflow_client/` — standard-library HTTP only (no new dependency), `Client(base_url, token)`, `submit_experiment`, `wait(progress=…)`, `result`, `package(path)`, `ui_url(id)`; `examples/robustness_quickstart.py` and a notebook. Packages are zip files with the extension `.ufpkg`. Mount the v3 router with one line in `main.py`. API reference for `/api/v2` (audit M5-lite) and the new `/api/v3` surface. JSON Schemas for spec/result generated into `shared/schemas/v3/` |
| 7 | **Scientific validation and testing** | Property: Latin-hypercube stratification (every factor occupies every stratum exactly once). **Determinism:** same spec + seed ⇒ identical `resultFingerprint`. **CRN:** for each sample index the compiled scenario is identical across alternatives except `controller`. **Analytic check:** inject a stub comparison function with a planted flip at demand multiplier 1.0 and verify detection within one stratum, correct P(better), regret and Wilson interval against hand-computed values. Guardrail tests (N = 29 → *indicative*; 30–99 → *indicative*; ≥ 100 unconverged → *indicative*). Exclusion/failure accounting. One real end-to-end ensemble in the fast suite (4 samples × 2 alternatives × 60 s); the Quick preset in the `slow` marker. **Known-effect check:** run the ensemble over a demand range spanning capacity and compare with the documented fixed/adaptive/roundabout behaviour in [validation §4.1](../research/validation.md) — agreement or disagreement is recorded either way |
| 8 | **Documentation and demo assets** | `docs/research/uncertainty.md` (method, assumption-driven priors, what "robust" means, what is not modelled — notably that the engine has **no explicit reaction delay**, so headway scale is a proxy, stated as such). SDK README. Demo scenario + spec + runbook draft (feeds the [presentation plan](V3_PRESENTATION_PLAN.md)) |
| 9 | **Dependencies and risks** | Needs S0's security work and `/capabilities`. Compute (Quick preset must finish in ≤ 4 min on the demo machine). Pure-Python statistics errors → verified against hand-computed values. Over-scope → cut-line §1.3. UI charting time → table-first, chart second |
| 10 | **Acceptance criteria** | **AC-1.1** Determinism and CRN tests pass. **AC-1.2** Stub-flip test recovers the planted flip and the hand-computed numbers. **AC-1.3** `python sdk/python/examples/robustness_quickstart.py` submits, waits and prints a summary against a local server. **AC-1.4** The same experiment opens in `/app/experiments/<id>` with all five tabs, badge and provenance. **AC-1.5** Quick preset (24 samples × 3 alternatives × 1 replicate, 180 s runs) finishes ≤ 4 min with 6 workers on the demo machine. **AC-1.6** `GET /api/v3/experiments/<id>/package` returns a zip whose manifest checksums verify. **AC-1.7** Planner shows findings and exports. **AC-1.8** All existing tests unchanged and green; frontend ×3 stable |
| 11 | **User-visible difference** | "Does the answer survive uncertainty?" becomes a question you can ask — in the UI or from a script — and the answer shows how often each option is better, the regret of choosing wrongly, and where the preference flips |
| 12 | **Explicitly deferred** | Replicate variance decomposition (field exists; analysis in S5), 2-D flip surfaces, Sobol indices, tokens/quotas (S4), package *import* (S2), policies and emergency alternatives (S5) |

**ED budget (5.15 of 5.5):** robustness backend + API 2.4 · experiment viewer 0.9 · planner v1 (findings, export) 0.75 · M5-lite API docs 0.5 · SDK 0.35 · package export 0.25. The planner's field-data step (≈ 0.75 ED) is scheduled in S5, so M1 totals ≈ 3 ED across S0, S1 and S5.

### 2.2 Day plan (guide)

| Day | Lane B | Lane F | Lane P |
| --- | --- | --- | --- |
| Mon 19 | spec + sampling + tests | Planner findings/export | v3 router + capabilities; schemas |
| Tue 20 | runner (CRN, exclusions) | Viewer skeleton, Conditions + Provenance | SDK core |
| Wed 21 | analysis + guardrails + stub test | Distribution + Preference tabs | SDK wait/progress; quickstart |
| Thu 22 | API + package export | What-drives-it tab; launch form | API docs; uncertainty.md |
| Fri 23 | known-effect check; fixes | 375 px pass; vitest | **G1 freeze**; runbook draft |
| Sat–Sun | overflow only | | |

---

## 3. Sprint 2 — Monday 26 – Wednesday 28 October

### 3.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Mon 26 – Wed 28 Oct (three days). Preview Thu 29 Oct |
| 2 | **Main objective** | Make the preview impossible to fail badly: bounded run times, interruptible jobs, an offline fallback, and rehearsed delivery |
| 3 | **Major features delivered** | **Cancel / resume** for experiments · **time-bounded presets** · **package import + verify** (CLI and SDK) · precomputed demo packages · recorded fallback video · preview runbook |
| 4 | **Backend / simulation** | `DELETE /api/v3/experiments/{id}` cancels cleanly: completed tasks are retained, status `cancelled`. `POST …/resume` re-queues only tasks without results (tasks keyed by a task fingerprint = scenario fingerprint + alternative + seed). Worker-count setting and per-preset estimated time computed from a one-run timing probe |
| 5 | **Frontend / product** | Cancel/resume buttons and partial-results view; estimated-versus-actual time; clear error states (failed runs, server restart, over-quota placeholder). "Open package" (read-only) page for offline inspection |
| 6 | **Integration work** | `urbanflow verify <pkg>` / `urbanflow import <pkg>` (thin CLI over the SDK): integrity check (checksums, schema versions), warns on commit/Python mismatch, optional `--reproduce` that re-runs and reports `reproduced` or `differs (engine changed)` |
| 7 | **Scientific validation and testing** | **Resume equivalence:** a run cancelled at 40 % then resumed has the same final `resultFingerprint` as an uninterrupted run. Tamper test (edited result ⇒ verify fails). Soak: 20 consecutive Quick runs, no leaked processes or memory growth beyond a threshold. Frontend ×3 stable. Defect-fix reserve (0.75 ED) |
| 8 | **Documentation and demo assets** | Final demo packages (Quick live-equivalent + Standard with N ≥ 100), checksums recorded in the runbook; backup screen recording; printable one-page "claims and limits"; rehearsal notes |
| 9 | **Dependencies and risks** | Feature freeze held (only fixes after G1). Demo machine differences → rehearse on the presenting machine. Risk: late defect in analysis → fallback to precomputed packages (they are the safety net by design) |
| 10 | **Acceptance criteria** | **AC-2.1** Resume-equivalence test passes. **AC-2.2** `verify` rejects a tampered package and accepts an untouched one. **AC-2.3** Two full timed rehearsals ≤ 15 min each, one on a cold start of the presentation machine **with the network disabled**. **AC-2.4** Fallback video and packages verified by checksum. **AC-2.5** Zero console errors on the demo path. **AC-2.6** G2 checklist in the presentation plan signed |
| 11 | **User-visible difference** | A long experiment can be stopped and continued; a result can travel as a file and be checked on another machine |
| 12 | **Explicitly deferred** | Any new analysis or chart; AI work (S3); tokens (S4) |

---

## 4. Sprint 3 — Friday 30 October – Thursday 5 November

### 4.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Fri 30 Oct – Thu 5 Nov (working days: Fri, Mon–Thu) |
| 2 | **Main objective** | Deliver the Control Lab (I-2): a safe environment, fair baselines, a trained policy and a held-out evaluation protocol — and report whatever the evidence shows |
| 3 | **Major features delivered** | **`SignalEnv`** · **policy shell + registry** (completes ADR-012) · baselines **Webster-tuned fixed-time** and **max-pressure** · **DQN trainer** with domain randomisation from I-1's sampler · **evaluation harness** · **Control Lab page** · production redeploy (M6, if authorised) |
| 4 | **Backend / simulation** | `controllers/policy_shell.py` — `PolicySignalController(FixedTimeSignalController)` (the way `AdaptiveSignalController` is built): the policy sees `Observation` (served / passing / calls / per-direction counts from `StopLineDetection`, current phase, time in phase) and returns one of `{hold, advance, goto(phase)}` at decision epochs; the shell enforces legal order, minimum green, yellow, all-red, maximum green; illegal requests are clamped and counted in `policyViolations`. `controllers/registry.py` — name → factory, consulted by `create_controller`; existing controllers keep their current path. `backend/src/rl/`: `env.py` (`reset(seed)`, `step(action)`, legal-action mask, reward = negative queue-weighted delay proxy, 300 s episodes after 60 s warm-up), `baselines.py` (Webster cycle from demand and saturation flow; max-pressure by queue difference), `dqn.py` (NumPy 2 × 64 MLP, replay buffer, target network, seeded), `train.py` (parallel actors on the existing pool, checkpoints with provenance), `evaluate.py` (disjoint train/test seeds, regimes: in-distribution, +20 % demand, skewed split; ≥ 30 paired seeds; statistics from the existing paired-comparison code and tie tolerance). Policy artifact: JSON (weights, normalisation, training provenance), usable as `controller.signalControl = "policy:<id>"`. **M6:** if authorised, redeploy `deployment` from `main`, smoke-test `/health` and `/api/version` |
| 5 | **Frontend / product** | Control Lab page `/app/control-lab`: pick scenario preset, pick policies, choose evaluation preset, **"Tested conditions" panel first**, then paired results; permanent **EXPERIMENTAL** badge on learned policies; policy list from `/capabilities`; link to the experiment viewer for long evaluations |
| 6 | **Integration work** | Evaluation runs as `kind: "control-evaluation"` through the same job machinery; the environment is importable (`pip install -e backend`, `from src.rl.env import SignalEnv`) for researchers and documented with a 30-line example; policy JSON round-trips through the package format |
| 7 | **Scientific validation and testing** | **Safety proof (G3):** 10,000 random actions — legal and illegal — over 10 seeds ⇒ **0 conflicting greens, 0 collisions, minimum green respected 100 %**, every clamp counted. **Shell fidelity:** a "replay the fixed plan" policy run through the shell reproduces the existing fixed-time controller's metrics exactly; the existing fixed-time and adaptive controllers are evaluated **as they are** (not re-implemented as policies), so the baselines are untouched. **Training reproducibility:** same seed ⇒ identical weights hash. **Fair comparison:** every controller sees the same scenario, seeds, duration and warm-up. **Baseline sanity:** Webster is compared with the default plan; if it is worse in the in-distribution regime, the implementation or the saturation-flow estimate is investigated before it is used as the "fair fixed baseline". Determinism suite unchanged |
| 8 | **Documentation and demo assets** | `docs/research/control-lab.md` (environment definition, reward, action space, baselines, protocol, the exact claims allowed). Training log and curve stored with the policy. One-page "how to add your own policy" |
| 9 | **Dependencies and risks** | NumPy (D2). Training wall time (see strategy §3.5) — schedule long training for nights, keep a Quick-trained fallback policy. Policy fails to beat baselines — acceptable outcome, reported. Shell/controller equivalence mismatch → block merge, do not weaken the shell. Prod redeploy depends on owner authorisation |
| 10 | **Acceptance criteria** | **AC-3.1** Safety fuzz passes with the numbers above. **AC-3.2** The replay-fixed-plan policy via the shell matches the existing fixed-time controller exactly. **AC-3.3** Evaluation report produced for 5 controllers × 3 regimes × ≥ 30 paired seeds; each table states regime, N, duration, warm-up, fingerprint. **AC-3.4** `policy:<id>` runs in the ordinary comparison API. **AC-3.5** Same-seed training reproduces the weights hash. **AC-3.6** Control Lab shows "Tested conditions" before results and the EXPERIMENTAL badge. **AC-3.7** Pre-existing determinism tests unchanged. **AC-3.8** (if authorised) production `/api/version` commit equals `main` HEAD |
| 11 | **User-visible difference** | A researcher can train, load and fairly evaluate a signal policy against strong baselines, and a planner can see — with the limits attached — whether a learned policy was competitive in named regimes |
| 12 | **Explicitly deferred** | PPO, multi-agent, roundabout/geometry transfer, reward-shaping studies, GPU/torch, remote stepping API |

---

## 5. Sprint 4 — Friday 6 – Thursday 12 November

### 5.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Fri 6 – Thu 12 Nov (Fri, Mon–Thu) |
| 2 | **Main objective** | Make UrbanFlow genuinely usable by outside clients (tokens, quotas, one experiment API) and deliver the first working emergency pre-emption slice (I-3 phase 1) |
| 3 | **Major features delivered** | **Personal access tokens + scopes + expiry + revocation** · **per-user quotas** · **`/api/v3/experiments` for three kinds** (planning, robustness, control-evaluation) · **SDK v1** · **Emergency events + class + fixed-time pre-emption + response/collateral metrics** |
| 4 | **Backend / simulation** | *Platform:* table `uf_api_tokens` (hash only, prefix, scopes, expiry, last-used, owner) by migration; auth dependency accepts Cognito JWT or `uf_pat_…`; quotas — concurrent jobs, simulations per experiment, simulated-seconds per day, body size, per-token rate limit — enforced in-process and reported by `/capabilities`; audit log of token and submission metadata; experiment registry gains `planning` and `control-evaluation`. *Emergency (phase 1):* optional `emergency` block in the scenario document (`{departAt, from, movement, class}`); `ambulance` and `fire_engine` profiles with a `priority` flag (the engine still never branches on class names); fixed-time pre-emption state machine — detect upstream, finish current clearance, serve the emergency approach, hold until clear plus margin, defined recovery to the interrupted plan, lock-out interval, deterministic tie rule; metrics: emergency delay/travel time, paired saving versus no pre-emption, collateral delay by approach, recovery time, pre-emption count |
| 5 | **Frontend / product** | Settings → *Access tokens* (create, copy once, revoke, scopes, expiry) and *Usage* (quotas and consumption). Experiment viewer generalised to all three kinds. Scenario builder: "Emergency vehicle" section — adds events to the scenario (shown only when `/capabilities` lists `emergency`) |
| 6 | **Integration work** | SDK v1 targets `/api/v3`, reads `UF_TOKEN`; `examples/` for each kind; contract test generated from the OpenAPI snapshot; schemas for all three kinds in `shared/schemas/v3/` |
| 7 | **Scientific validation and testing** | *Platform:* token shown once, hash stored; revoked/expired ⇒ 401; user A cannot read B's experiment (404); the third concurrent job is refused with 429; oversize body refused; SDK integration test against a live server. *Emergency:* **absent block ⇒ every pre-existing determinism and reproduction test passes unmodified (bit-identical)**; safety suite — pre-emption during yellow/all-red, two simultaneous requests (tie rule), request during adaptive-style max green (shell only), cancelled request, request storm vs lock-out; 50-seed fuzz with random emergency arrivals ⇒ **0 conflicting greens, 0 collisions**; paired with/without pre-emption on the same seeds |
| 8 | **Documentation and demo assets** | `docs/api/README.md` §9 `/api/v3` (auth, quotas, kinds, errors); SDK guide; `docs/research/emergency-priority.md` (model, assumptions, what is not modelled: no yielding, no pull-over, no roundabouts) |
| 9 | **Dependencies and risks** | Token/quota work is security-sensitive — keep it small and tested. Emergency touches reproduction-critical code — it must be additive. **G4 (Thu 12 Nov) emergency go/no-go:** pass ⇒ phase 2 in S5; fail ⇒ fallback ladder below |
| 10 | **Acceptance criteria** | **AC-4.1** Token lifecycle and isolation tests pass. **AC-4.2** Quota tests pass (429, 413/422). **AC-4.3** One SDK script runs a planning, a robustness and a control-evaluation experiment with a PAT. **AC-4.4** OpenAPI contract test green. **AC-4.5** Emergency absent-block equivalence: full non-slow suite unchanged. **AC-4.6** Safety suite and 50-seed fuzz pass. **AC-4.7** Sample scenario: the ambulance is served green within the configured detection-to-green bound and the conflicting approach always receives yellow and all-red first. **AC-4.8** Paired metrics (saving, collateral delay) produced for ≥ 20 seeds |
| 11 | **User-visible difference** | An outside program, with its own revocable credential and limits, can run three kinds of experiment; an ambulance can be sent through a signalised junction and the response-time saving and the cost to others are measured |
| 12 | **Explicitly deferred** | Adaptive-signal pre-emption (S5), surrounding-traffic yielding/pull-over, roundabouts, webhooks, organisation sharing |

**Emergency fallback ladder (decided at G4):** (1) *pass* → phase 2 in S5; (2) *partial* (pre-emption works but safety suite incomplete) → ship **class + events + metrics without pre-emption** and label the study "no priority"; (3) *fail* → remove the UI section, keep the code behind a disabled capability, and spend S5's emergency allotment on replicate variance decomposition and condition presets inside I-1 ("G-lite"). The V3.0 story is complete in all three cases.

---

## 6. Sprint 5 — Friday 13 – Thursday 19 November

### 6.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Fri 13 – Thu 19 Nov (Fri, Mon–Thu). **G5 feature freeze Thu 19 Nov 18:00** |
| 2 | **Main objective** | Join the three initiatives into one coherent workflow, connect UrbanFlow to the data planners actually have, and produce the quantitative evidence the full presentation will stand on |
| 3 | **Major features delivered** | **Learned and baseline policies as alternatives inside robustness ensembles** · **Emergency phase 2** (adaptive pre-emption, full safety suite, UI results panel, paired study) · **CSV turning-count import → observations** · **GeoJSON result export** (and arms → draft scenario if time) · **Field-data (calibration) step in the planner** (closes audit A-23) · **three recorded evaluation studies** |
| 4 | **Backend / simulation** | Robustness alternatives may reference `policy:<id>` (registry) and emergency scenarios. Replicate variance decomposition (between-sample vs within-sample) in `analysis.py`. Emergency pre-emption extended to the adaptive signal and checked by the same safety suite. Importers: `integrations/counts_csv.py` (documented column format: approach, movement, count, interval start/end, vehicle class optional) → `urbanflow-observations` with explicit validation messages; `integrations/geojson.py`: result → GeoJSON `Feature` (junction point + indicator properties + fingerprints); arms `LineString`s → draft scenario via the existing `assign_slots` (warnings listed, never silent fixes) |
| 5 | **Frontend / product** | Planner step *Field data*: upload counts CSV, see validation, compare with simulation using the existing calibration comparison, show the rating and the caveat that demand fitting is input assimilation. Planner alternatives list shows registered policies (EXPERIMENTAL badge). Emergency results panel (saving vs collateral, by approach). Download buttons: GeoJSON, package |
| 6 | **Integration work** | One end-to-end story across kinds: planner → robustness over {fixed, adaptive, Webster, max-pressure, learned} → package → SDK reproduce. `/capabilities` lists importers/exporters |
| 7 | **Scientific validation and testing** | **Evaluation studies (Standard preset, recorded with fingerprints and N):** (E1) robustness of the signal-vs-adaptive-vs-roundabout choice over uncertain demand and headway, ≥ 100 samples; (E2) Control Lab: 5 controllers × 3 regimes × ≥ 30 paired seeds; (E3) emergency: ≥ 5 demand levels × ≥ 20 paired seeds. Each is stored as a package and summarised in `docs/research/v3-evaluation.md` **with limitations and null results included**. CSV importer: round trip and malformed-input suite; GeoJSON output validated against the GeoJSON schema |
| 8 | **Documentation and demo assets** | Evaluation report; importer format guide; final demo scenario selection; draft claims register (claim → package → N → limitation) |
| 9 | **Dependencies and risks** | Compute for E1–E3 (~ 2–3 machine-hours with 6 workers; start by Fri 13 evening so results exist by Tue 17). Messy CSV real data (mitigation: strict format, clear errors, sample files). If G4 failed: emergency allotment (1.75 ED) is re-spent as in the fallback ladder. First cut if behind: arms-GeoJSON import, then field-data UI step (stays on the record as an open A-23, not silently dropped) |
| 10 | **Acceptance criteria** | **AC-5.1** A robustness experiment with five alternatives (incl. a learned policy) completes and renders. **AC-5.2** CSV sample imports to valid observations; bad CSV gives line-numbered errors. **AC-5.3** GeoJSON export validates. **AC-5.4** E1–E3 packages exist, verify, and their numbers appear in `v3-evaluation.md` with N, regime and limitations. **AC-5.5** Emergency safety suite passes for adaptive pre-emption (if G4 passed). **AC-5.6** Replicate variance decomposition tested against a hand case. **AC-5.7** Planner field-data step runs on the sample CSV |
| 11 | **User-visible difference** | The pieces become one product: bring your counts, compare controls including a learned one, check robustness, send an ambulance through, and take the evidence away as a package or a map layer |
| 12 | **Explicitly deferred** | SUMO/OpenStreetMap importers, live data feeds, calibration search, webhooks |

---

## 7. Sprint 6 — Friday 20 – Wednesday 25 November

### 7.1 Specification

| # | Item | Content |
| --- | --- | --- |
| 1 | **Date range** | Fri 20 – Wed 25 Nov (Fri, Mon–Wed). Release candidate cut **Fri 20 Nov**; no features after that |
| 2 | **Main objective** | Turn the integrated build into a release candidate whose every published number can be reproduced and whose limits are written down |
| 3 | **Major features delivered** | **Release candidate `v3.0.0-rc1`** · reproducibility audit · documentation set · accessibility and responsive pass · deployment dry-run · two full-demo rehearsals · V2.0 validation addendum |
| 4 | **Backend / simulation** | Bug fixes only. Full suites including `slow` (closes audit A-15). Performance review of the three experiment kinds against their presets. Version bump to `3.0.0`; `/api/version` reports it |
| 5 | **Frontend / product** | Accessibility pass (axe: zero serious/critical on planner, experiment viewer, Control Lab, tokens page); keyboard path through the primary journey; 375 px check of the read-only status/results pages; copy review against the claim rules; remove or hide anything the backend only stubs |
| 6 | **Integration work** | Clean-checkout test: `docker compose` up on a fresh clone, `scripts/v3_demo.py` end to end. SDK published as an installable folder (`pip install ./sdk/python`). **Staging-style deployment dry-run locally** (compose with `API_KEY` set and nginx injecting it); a production redeploy only on explicit authorisation |
| 7 | **Scientific validation and testing** | **Reproducibility audit:** every number on every slide is traced to a package; `urbanflow verify --reproduce` on ≥ 5 packages from a clean checkout returns `reproduced` (or documents a version difference). Full test matrix: backend non-slow **and** slow, frontend ×3, `ruff`, `mypy`, `prettier`, schema validation, OpenAPI contract, coverage ≥ 90 %. Security regression: ownership and token tests. Limitations review by someone other than the author if available |
| 8 | **Documentation and demo assets** | API reference (v3), SDK guide, methods and limitations pages (robustness, control lab, emergency), `v3-evaluation.md`, V2.0 validation addendum (audit A-44), `ROADMAP.md` and `README.md` status sync (audit M5, D6), runbook, claims register, backup video, precomputed packages, printed one-pager |
| 9 | **Dependencies and risks** | Late defects (reserve built in); machine differences (rehearse on the presenting machine); documentation volume (start with the claims register, which the slides need first). If a late defect cannot be fixed safely, the affected feature is **hidden via `/capabilities` and listed under limitations**, not left half-working |
| 10 | **Acceptance criteria** | **AC-6.1** All suites green on the RC commit; coverage ≥ 90 %. **AC-6.2** Clean-checkout demo passes. **AC-6.3** ≥ 5 packages reproduce. **AC-6.4** axe: 0 serious/critical; keyboard-only primary journey passes. **AC-6.5** Claims register complete: no slide number without a package id. **AC-6.6** Two timed rehearsals ≤ 25 min, one cold-start offline. **AC-6.7** Docs reviewed; `ROADMAP.md` consistent with this plan's outcome |
| 11 | **User-visible difference** | A coherent, documented, reproducible V3.0 — and a written account of what it does not do |
| 12 | **Explicitly deferred** | Everything in the strategy's "Deferred" list; any feature not in the RC |

---

## 8. Dependency map

```
S0: M2/M3 security ──────────────┐
S0: planner UI v0 ───────────────┼─► S1: robustness (backend→viewer→SDK→package) ─► S2: cancel/resume, verify ─► PREVIEW
S0: ADR-013/014/015 ─────────────┘            │
                                              ├─► S3: SignalEnv/shell/registry ─► baselines ─► DQN ─► evaluation ─┐
                         I-1 sampler ─────────┘   (domain randomisation)                                         │
S4: tokens/quotas/v3 kinds ◄──────────────────────────────── S1 envelope ─────────────────────────────────────────┤
S4: emergency phase 1 ─► G4 ─► S5 emergency phase 2 ─────────────────────────────────────────────────────────────┤
S5: policies+emergency inside robustness · CSV/GeoJSON · evaluation studies ◄─────────────────────────────────────┘
S6: RC freeze ─► reproducibility audit ─► docs ─► rehearsals ─► FULL PRESENTATION
```

Critical path: **S0 security → S1 robustness slice → S3 shell/registry → S4 tokens/v3 kinds → S5 evaluation → S6 RC.** The emergency work (I-3) is *off* the critical path by design: its failure never delays the release.

## 9. Scope reduction ladder (if the plan slips)

Cut in this order; each step keeps a complete, honest product.

1. Emergency phase 2 and then phase 1 (I-3) → re-spend on I-1/I-2 hardening.
2. Arms-GeoJSON import; field-data UI step (kept on the open-items list).
3. Notebook polish; GeoJSON export (CSV remains).
4. Control Lab learned policy → keep environment, shell, baselines and protocol, show "no learned policy trained" honestly.
5. Standard evaluation presets → Quick presets with *indicative* labels.
6. PATs → keep per-user Cognito access and document the API as "trusted-network" (the SDK still works with the dev token).

**Never cut:** M2/M3 (data isolation), the guardrails and claim rules, reproducibility checks, the limitations page.
