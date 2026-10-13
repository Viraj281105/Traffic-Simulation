# V2.0 Completion Audit

> **Status:** **revision 7 (2026-10-13): V2.0 release gate PASSED** — approved by the product owner on gate commit `6b609ce` (`viraj-dev`) with CI green on that commit; production deployment is left to the product owner (manual) and is **not verified by this audit** · earlier revisions kept below for history
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Authority:** [`docs/ROADMAP.md`](../ROADMAP.md) is the single authoritative roadmap and was **not** edited. Where this audit finds ROADMAP statements that are out of date (§7, R4.2) it records the correction as an *owner-authorised edit still to be made*.

This audit answers one question: **is everything promised through V2.0 actually finished, and exactly what must be true before V2.0 may be called released?** It judges capability available to a user, not "a module or endpoint exists".

### Revision-3 corrections (2026-10-12) — V2.0 scope is separate from V3.0 scope

* **Repository state corrected (§1).** The four local commits are no longer unpushed: PR #141 merged them into `main` (merge commit `324cde0`); Continuous Integration and Docker Container CI are green on that commit, and the **scheduled** CI run on `324cde0` (event `schedule`) ran the five `Backend Slow Simulation Regression` jobs, all green. The push/PR runs skipped the slow job. This is **context, not a gate PASS**: the gate commit is still to be declared and every gate check re-run on it (rule in §7).
* **V3.0 scope firewall (new §7.12).** The V3.0 plan now includes signalised roundabouts, a strategy registry, a driver-aggression default and two AI features. **None of it is V2.0 scope, none of it may delay or alter the V2.0 gate, and none of it may be merged before G-V2.** The V2.0 release gate rows, work packages and 7.75 ED estimate are unchanged; V2.0 closure is not compressed.
* The audit's findings (rows PASS/FAIL/NOT RUN) are **not changed** by this correction except where §1 now records a verified fact.

### Revision 4 (2026-10-12) — release-gate verification run

The gate's work packages W1, W3, W4, W5 and W6 (part A) were carried out and the gate checks were run **locally**. Everything below is evidence from the **working tree `4b40cc9` + uncommitted gate changes** (no commit, push, PR or deployment was authorised), except the slow suite, which ran on an unmodified export of `4b40cc9`. **No gate commit exists, so no row is PASS "on the gate commit"; §7.0 shows each row's status and its local evidence.**

* **Gate verdict: NOT PASSED.** Code, security and documentation rows now pass locally; the gate is held by (1) the slow suite (**2 of 190 fail**, a known model limit with a stale test expectation — owner decision), (2) no gate commit / review / CI (not authorised in this run), (3) product-owner decisions D-V2-0…D-V2-6, (4) `ROADMAP.md` (not editable without authorisation), (5) accessibility tooling (axe) not run, (6) the deployment rows (G-PROD).
* **New findings:** 155 of the 190 slow tests are in **no** CI job (the nightly slow run covers 35), so earlier "slow suite green in CI" statements covered 18 % of it; the documented "suites are deliberately shared" design (API reference §7.1) is reversed by the D-V2-3 proposal implemented here and needs explicit PO confirmation; V1 run history (`/api/v1/study/history/runs`) is unauthenticated, so suite privacy hides suite metadata but not run metrics; a planning study could previously attach (and read the fitted scenario of) another user's calibration run — fixed; the planning API's 422 reasons were flattened into a Python repr in the error envelope — now a list in `error.details.errors`.
* **Both failed deployments diagnosed (R5.1):** run 37914357365 (`4956570`) failed in `npm run build` on the EC2 host (TypeScript syntax errors in `SafetyTimelineVisualizer.tsx`, since fixed in `b707e3e`/`26e5577`; the script aborted and left the old containers running); run 37932609196 (`6977d20`) lost its SSH session (`client_loop: send disconnect: Broken pipe`, exit 255) about five minutes into the remote `npm run build` — the failure mode `8f6e80f` redesigns (detached run). Whether the second run's remote build finished is unknown.

### Revision 7 (2026-10-13) — release gate decision: **G-V2 PASSED**

**Gate commit:** `6b609ce` on `viraj-dev` (pushed 2026-10-13; `4b40cc9..6b609ce`: `614566a` security and data integrity, `554e767` simulation evidence and CI coverage, `548b56e` frontend, `6b609ce` documentation).

**CI on the gate commit (all green):**
* Continuous Integration, push — [38374615193](https://github.com/Viraj281105/Traffic-Simulation/actions/runs/38374615193): Schema Validation, Backend Lint & Types (ruff, ruff format, mypy), Backend CI (`pytest -m "not slow"` + 85 % coverage gate, Python 3.11), Frontend CI (ESLint, tsc, Prettier, Vitest), build-and-test.
* Continuous Integration, manual dispatch with the slow suite — [38374630279](https://github.com/Viraj281105/Traffic-Simulation/actions/runs/38374630279): the same jobs plus **all 12 slow shards** (the first CI run of the full slow suite; previously 5 shards covered 35 of 190 tests).
* Docker Container CI, push — [38374615230](https://github.com/Viraj281105/Traffic-Simulation/actions/runs/38374615230): compose validation, backend and frontend image builds, full-stack compose smoke test.
* Static check of the deployment scripts: `shellcheck -S warning` (v0.10.0) on the committed `scripts/deploy-ec2.sh`, `scripts/run-remote-deploy.sh`, `scripts/validate-schemas.sh` — clean.

**Product-owner decisions (2026-10-13), recorded in the accepted-gap register (§7.8):**

| Item | Decision | Status in this audit |
| --- | --- | --- |
| R1.7 Independent review of the gate commit | **Waived** by the product owner | Accepted gap — no second-engineer review took place |
| R2.8 Keyboard-only and screen-reader review | **Done**, per the product owner | Owner-attested; this audit verified the automated part (axe in Vitest, browser contrast check) only |
| R5.2–R5.4, R6.1–R6.3 Production deployment (G-PROD) | **Left to the product owner, done manually** | Not verified by this audit (no access to production); the pipeline root causes (R5.1) and script checks are recorded |
| D-V2-2, D-V2-3, D-V2-7, D-V2-8, npm deferral | Approved / accepted (revision 6) | Evidence in revision 6 and §7.0b–7.0c |

**Gate verdict.** Dimensions 1–5 are PASS on the gate commit or an accepted gap above; dimension 6 (production) is left to the product owner's manual deployment. **G-V2 is passed and V2.0 is complete.** Issues #142–#149 are closed with this evidence. **V3.0 still needs its own design-approval gate (G-D, #150) before implementation starts** (§7.12).

**Known limitations that ship with V2.0 (documented, not defects):** calibration is a comparison framework — no field data has been run through it and nothing is fitted; network documents are validated but multi-junction networks are not simulated; a third approach lane on a two-lane roundabout adds no capacity (K1); safety proxies and fuel/CO₂ figures are exploratory; interrupted planning jobs are reported, not resumed; no per-IP request-rate limit (compute is bounded per client); Python 3.11 is the supported runtime (Dependabot PR #134, Python 3.14, is not part of V2.0).

### Revision 6 (2026-10-13) — product-owner decisions applied, residual risks closed, final verification

**Product-owner decisions recorded (2026-10-13):** D-V2-7 *approved* — saved (owned) runs are owner/admin-only; unowned runs keep the documented public-read policy. D-V2-3 *approved* — private scenario suites and owner-scoped batch results. D-V2-8 *conditionally accepted*, subject to independent validation (done below). npm advisories: deferral accepted *if* verified development-only (verified below). D-V2-2 *authorised* for evidence-backed factual corrections to `ROADMAP.md`, no scope changes (done below). Local commits permitted after a full diff review; **no push, merge, deployment or closure of #142**.

* **D-V2-8 independent validation — classification confirmed, test tolerance overturned.** 50 more paired seeds (new seeds 21–40; a 600 s horizon; 2,880 veh/h): every 95 % CI of the third lane's mean effect contains zero; 0 collisions in 140 runs; the largest 600 s shortfall (seed 10, −8.6 %) shows steady discharge with no stall. But seed 22 falls **11.5 %** short, falsifying the revision-5 per-seed 10 % bound and its stated justification. Replaced by a ten-seed aggregate (`tests/integration/test_roundabout_lane_capacity.py`, ratio ≥ 0.95, three standard errors; new nightly CI shard); the per-seed test keeps only the robust 1 < 2 check for the roundabout. Evidence: [validation §4.4](../research/validation.md). **D-V2-8: condition met → accepted.**
* **npm deferral — verified development-only.** `npm audit` (6: 2 critical, 2 high, 2 moderate): `tinypool`, `vitest`, `@vitest/mocker`, `@vitest/coverage-v8` (test runner); `brace-expansion` (eslint, coverage glob); `source-map-js` (`@tailwindcss/node`, `postcss`, build time only, even though `npm audit --omit=dev` lists it because Tailwind is declared in `dependencies`). The production frontend image copies only `dist/` and the nginx templates (`frontend/Dockerfile`), and none of these packages' code is in the 37 shipped bundle files. Exploitation needs attacker-controlled build inputs or test-runner options. **Deferred** (accepted); remedy: Vitest 3 → 5 major upgrade after V2.0.
* **Residual risk 1 — per-client limits.** *Fixed (app):* one client may hold at most one of the two synchronous-compute slots (client = nginx's `X-Real-IP`, which nginx overwrites). Two more synchronous simulation routes were found ungated and gated: `GET /api/v1/study/export` (ran a sweep and a Monte Carlo study on an anonymous GET) and `POST /api/v2/planning/{id}/reproduce`. *Not fixed, deliberately:* an nginx per-IP request-rate limit — the dashboard polls at up to 10 Hz per viewer and demos share one NAT, so it would block legitimate audiences while compute is already bounded; recommended at the edge (ALB/WAF) from observed traffic. *Residual (low):* one client can still fill the 4 background-job slots (each bounded by study caps and the step ceiling). Release impact: none blocking.
* **Residual risk 2 — WebSocket origin.** *Fixed:* `/ws/*` handshakes from another site's page are refused before accept (`src/ws_origin.py`): same host name as `Host` (ports not compared — nginx forwards `Host` without one, verified through the production nginx on port 18080), or `CORS_ORIGINS`, or no `Origin` (non-browser). Verified: unit and handshake tests on all three streams; live dev server (foreign 403, dev 101); the app's own stream in the browser; production images through nginx (foreign 403, same-site 101).
* **Residual risk 3 — planning jobs across restarts.** *Two defects fixed:* (1) a study queued or running when the process stopped answered 404 afterwards, indistinguishable from "deleted"; (2) failed studies were never persisted although the operations guide said they were. Every state is now stored (inline additive migration, `status`/`error` columns), and the process-wide service marks studies an earlier process left unfinished as **failed — "Interrupted by a server restart …"**, which the planner UI shows. *Not done:* resuming interrupted jobs (needs a durable job queue; documented). Mutation-checked: reverting to completed-only persistence fails 2 of the 4 new tests.
* **`ROADMAP.md` and README** — status corrections only (V1.4–V2.0 implemented and merged; V1.6–V1.9 partial, with what is missing stated; V1.5 slow matrix now run; V2.0 release gate open). Planned slot dates, scope tables and §7 (V3.0) unchanged.
* **Container privileges checked:** the backend server process runs as `appuser` (uid 999, real/effective/saved/fs), after the entrypoint's root-only volume-ownership repair; nginx as uid 101.

#### 7.0c Revision 6 — final verification of the exact working tree (2026-10-13)

| Check (command) | Environment | Result |
| --- | --- | --- |
| `pytest -m "not slow"` (coverage gate in `addopts`) | Windows, Python 3.14.7 | **1,271 passed, 0 failed, coverage 94.83 %** (floor 85 %), 239 slow deselected, 21 min |
| `pytest -m "not slow" -v` | Docker `python:3.11.16` image, tree copy incl. checkout files | **1,271 passed, 0 failed, coverage 94.86 %**, 63 min (the three checkout-dependent tests of revision 5 pass here) |
| `pytest <file> -m slow --no-cov`, every slow file, one process each | Docker Python 3.11.16 | **239 passed, 0 failed** across 12 files (incl. the new 10-seed `test_roundabout_lane_capacity.py`, 41 min; longest shard) |
| `ruff check src/ tests/` · `ruff format --check src/ tests/` · `mypy src/` (strict) | Python 3.14.7 | clean · 220 files formatted · 105 files, no issues |
| `python scripts/validate_schemas.py` | — | passed (3 files) |
| `docker compose -f docker-compose.yml config` · `-f docker-compose.dev.yml config` | Docker 29.7.2 | both valid |
| `docker build -f backend/Dockerfile .` · `docker build -f frontend/Dockerfile ./frontend` | Docker 29.7.2 | both built |
| Full-stack smoke of those images (backend + nginx, API key set to a throwaway value) | Docker network, port 18080 | `/health` 200 · `/app/planner` 200 · unknown page 404 · run list 200 · anonymous PATCH 401 · `/api/v2` without a user 401 (key injected) · WebSocket foreign origin 403, same-site 101 |
| `npx vitest run` · `tsc --noEmit` · `eslint .` · `prettier --check .` · `npm run build` | Node 24.20.0 | **35 files, 409/409**; tsc, ESLint, Prettier clean; build exit 0 (also 409/409 ×3 earlier on identical frontend code) |
| `npm audit` · `npm audit --omit=dev` · `pip-audit -r requirements.txt` | — | as in §7.0b / above; no new findings |
| Roundabout re-validation (`scripts/roundabout_lane_experiment.py`, 3 runs) | Python 3.14.7 | as above |

**Not verifiable here (still open):** external CI on a pushed gate commit (R2.6); deployment (R5.x, R6.x — production `API_KEY`, Cognito settings, running commit); review by a second engineer (R1.7); keyboard and screen-reader accessibility review.

### Revision 5 (2026-10-12/13) — hardening run

Working tree only: **no commit, push, merge, PR or deployment** (not authorised). Builds on the revision-4 gate changes, which were preserved unchanged except where listed. Every claim below has its command in §7.0b.

* **Gate verdict: still NOT PASSED** — now held only by owner/operator items: no reviewed gate commit + CI run (R1.5, R1.7, R2.6), product-owner decisions (D-V2-3, D-V2-7, D-V2-8, deferred npm advisories), `ROADMAP.md` (R4.2), and deployment (R5.x, R6.x). Every engineering row that can be run locally now passes (§7.0b).
* **Security defects found and fixed** (each with regression tests; the shared access rule was mutation-checked — disabling it fails 12 tests):
  1. **Owned runs were public** — `/api/v1/study/history/runs*` let anyone list, read, export, compare and reproduce a signed-in user's saved runs, and **anonymously rename or rewrite notes/tags on any run** (PATCH had only the proxy-injected API key). Now owner/admin only (404 to others); unowned study runs stay public to read and admin-only to relabel (403). This implements the D-V2-7 question in its deny-by-default form — **PO confirmation requested**.
  2. **Private suites leaked their results** — suite-batch runs were stored without an owner, so `?batch_id=<suite>` listed them publicly. Now owned by the suite owner.
  3. **Unbounded synchronous compute (DoS)** — seven synchronous simulation routes, reachable without sign-in, had no concurrency bound; a few dozen concurrent requests would starve every synchronous route, `/health` included. Now 2 at a time, 429 at once otherwise (`src/request_limits.py`).
  4. **Unbounded run length (DoS)** — the schema accepted any `timeStep > 0`, so a 1e-6 s step made a 3600 s run 3.6 billion steps. Now at most 72,000 steps, enforced by the shared validator and by the engine itself; reproducing a stored run with a client-supplied duration is bounded too.
  5. **Hardening:** admin requires `email_verified`; a token without `sub` is refused; tokens must be RS256 (blocks HS256-with-public-key confusion, CVE-2024-33663 / CVE-2026-85394, the latter without an upstream fix); CSV exports neutralise spreadsheet formulas (run and suite exports; the planning CSV carries no free text).
  6. **Dependencies:** `python-jose` 3.3.0 → 3.5.0, `requests` 2.31.0 → 2.33.1 (none of their advisories was exploitable as used; verified first by a new end-to-end test of the real Cognito RS256 path, which previously had none). Their transitive dependencies are now pinned.
* **Integrity:** `POST /history/runs/compare` substituted 0 for missing metrics and still named a "winner" (two comparison runs read as a 0 s "tie"); now null deltas and `winner: "unavailable"`.
* **Simulation (R2.2):** the two slow roundabout failures are a **documented model boundary, not a defect**, on 20-seed paired evidence (third merging lane on a two-lane ring: +0.3 of ~99 vehicles, 95 % CI −1.7 to +2.3; 0 collisions) — [validation §4.4](../research/validation.md). Test corrected to what the model promises; validation now warns users. **PO acknowledgement requested (D-V2-8).** New randomized-invariant test over the accepted scenario space (fast 6, slow 48).
* **CI:** the five slow files that were in no CI job (155 tests) plus the new one are in the nightly matrix; `tests/test_ci_slow_matrix.py` fails the PR job if a slow file is ever left out.
* **Accessibility (R2.8):** axe-core 4.13.0 (dev, pinned) in Vitest: app shell, planner setup and results, run page — 0 violations. Colour contrast, which jsdom cannot measure, checked with the same axe in a real browser on the dev stack: Compare, Planner and Run page, light and dark — **0 violations** (69, 43 and 136 text nodes passing; 6–23 nodes per page on gradients undeterminable; a 1 px decorative dot grid was hidden for the measurement). Not claimed: full WCAG conformance or screen-reader usability.
* **Modularisation:** run history extracted from `main.py` (3,449 → 2,873 lines) into `src/history/` (`router.py` HTTP and access, `reproduce.py` domain logic, `export.py` pure CSV); one ownership rule in `src/access.py` now serves runs, suites and calibration runs; request limits consolidated in `src/request_limits.py`. Behaviour is preserved except for the deliberate fixes above: every existing history and reproduction test passes unchanged except one that encoded anonymous relabelling, which was updated to the new contract.

### What changed in revision 2

* The six-dimension **V2.0 release gate** (§7) replaces the earlier short must-fix list. Nothing is marked PASS without evidence; evidence that is stale (gathered on an earlier tree) is called out as such.
* **Repository state re-checked** (§1): the owner has since committed the pending work locally; the working tree is clean; nothing is pushed, so **no CI has run on the new commits**.
* Test evidence from the first audit is retained but labelled *"identical tree, not re-run at HEAD"*. The suites were **not** re-run for this revision (the owner asked to skip them), so the gate marks them NOT RUN until they are.
* The cause of the failed production deployments was inspected (read-only `gh run view`).
* The ≈ 7–8 engineer-day estimate is **kept as an estimate**; §7.5 breaks it into work packages.

---

## 0. Verdict (read this first)

**V2.0 is NOT release-ready.** The backend is real and works end to end; the product experience the roadmap names for V2.0 ("end-to-end planner workflow … final presentation layer") does not exist, and several security, evidence and documentation criteria are open.

**Revision 7 — G-V2 PASSED (2026-10-13):** product-owner approval on gate commit `6b609ce` with CI green (push, full slow suite, Docker); review waived, accessibility review owner-attested, production deployment left to the product owner (manual; not verified here). V2.0 is complete.

**Revision 6 (§7.0b, §7.0c):** every engineering check that can run locally passes on the final tree (backend fast suite on Python 3.14 and 3.11, full slow suite, frontend, build, images and a full-stack smoke test); the product-owner decisions D-V2-2/3/7/8 and the npm deferral are recorded. **Still not release-ready:** no pushed gate commit with external CI, no second-engineer review, deployment unverified. Issue #142 stays open.

**Revision 4 (local verification, §7.0):** V2.0 was still **not release-ready**, but for different reasons. The planner UI, the access-control and privacy fixes and the documentation now exist and pass locally. What holds the gate: two slow tests, the absence of a reviewed gate commit with CI, product-owner decisions, `ROADMAP.md`, accessibility tooling and deployment. *Revision-2 counts are kept below the new ones for history.*

| Dimension of the release gate (§7) | Rows | PASS (local) | FAIL | NOT RUN (on a gate commit) | BLOCKED |
| --- | :-: | :-: | :-: | :-: | :-: |
| 1 Code complete and reviewed | 8 | 5 | 1 | 0 | 2 |
| 2 Automated tests and build checks | 8 | 1 | 1 | 5 | 1 |
| 3 Security and privacy | 8 | 7 | 0 | 0 | 1 |
| 4 Documentation | 5 | 4 | 0 | 0 | 1 |
| 5 Deployment pipeline (not production) | 4 | 1 | 0 | 1 | 2 |
| 6 Production deployment and smoke test (separately authorised) | 3 | 0 | 0 | 0 | 3 |

*Revision 2 (superseded):*

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

### 7.0 Revision 4 — status of every gate row (2026-10-12)

**PASS (local)** = the requirement is met and verified on the working tree (`4b40cc9` + uncommitted gate changes); it must be re-confirmed by R2.x on the gate commit. The tables in §7.2–§7.7 keep the requirement definitions; their status column is superseded by this table.

| Row | Status | Evidence (exact) | Remaining |
| --- | :-: | --- | --- |
| R1.1 Planner MVP | **PASS (local)** | `frontend/src/components/planner/*`, `frontend/src/services/v2/planning.ts`, route `/app/planner` in `routing.ts` + nginx template (`routing.test.tsx` mirror green); `src/test/planner.test.tsx` 19 tests (PL-1…PL-9 incl. `unavailable`, tie, null statistic, 429, failed job, unreachable, 404); live run in the browser against the running dev stack (below) | Review by the frontend owner (#143 is assigned to khushik8605; `v20-integration.md` asked for coordination) |
| R1.2 `/api/v2` per-user auth | **PASS (local)** | `main.py` mounts networks with key + user, calibration router takes user/admin deps, `planning/validate` takes the user; `tests/api/test_v2_route_auth.py` (every OpenAPI `/api/v2` route × no key / key-no-user / forged token / dev token without bypass → 401) | — |
| R1.3 Calibration-run ownership | **PASS (local)** | `calibration/store.py` `user_id` column (inline migration), owner-scoped get/list/delete, legacy rows admin-only; `tests/calibration/test_calibration_ownership.py` (8 tests incl. migration of an old table); mutation check: disabling the filter fails 5 tests | — |
| R1.4 Suite privacy | **PASS (local)** | `scenario_suites.user_id` (inline migration), scoped list/get/batch/export, legacy admin-only, creation refuses other users' runs; `tests/api/test_suite_privacy.py` (5 tests), `tests/database/test_suite_dao.py`; mutation check fails 3 tests | **D-V2-3 confirmation** (reverses the documented shared-suite design); V1 run history still public (new decision D-V2-7) |
| R1.5 Pending work committed | **BLOCKED** | Gate changes are uncommitted (commit not authorised in this run) | Owner commits |
| R1.6 Null `cohensD`/`pValue` consumers | **PASS** | Unchanged since `dd3d36b`; all consumer suites green (backend non-slow, frontend ×3) | Re-confirm on the gate commit |
| R1.7 Gate commit, PR, review | **BLOCKED** | No commit/push/PR authorised; reviewer not named (D-V2-0, D-V2-5) | — |
| R1.8 Clean tree at gate time | **FAIL** | 20+ files of uncommitted gate changes (by design of this run) | Commit, then re-check |
| R2.1 Backend non-slow + coverage | **NOT RUN** (gate commit) | Local, final tree: `pytest -m "not slow"` **1,204 passed, 0 failed, 190 deselected, coverage 94.52 %** (floor 85 %), 20 min 50 s. An earlier run on the same day found one failure caused by the suite-privacy change (`test_suite_dao.py::test_list_suites` relied on an unscoped list); the test was updated to the owner-scoped contract with added scoping assertions, not weakened | Gate commit |
| R2.2 Slow suite | **FAIL** | Full `pytest -m slow` on an export of `4b40cc9`, one process per file: **188/190**; failed `test_calibration_pass.py::test_capacity_rises_with_lanes[2-roundabout]` (93 < 87) and `[3-roundabout]` (103 < 102) — the documented ≤ 2-ring-lane limit (validation §4.2) vs a stale expectation. Files `test_real_world_junctions_v15` 60/60, `test_adaptive_signal_runs` 27/27, `test_roundabout_multilane_v14` 24/24, `test_vehicle_types_and_lanes` 20/20, the five CI-matrix files 35/35. **155 slow tests are in no CI job** | Owner decides test vs model (D-V2-8); add the five missing files to the CI slow matrix |
| R2.3 ruff / format / mypy | **NOT RUN** (gate commit) | Local: `ruff check .` clean, `ruff format --check .` 206 files formatted, `mypy src` 98 files no issues | Gate commit |
| R2.4 Frontend vitest ×3, tsc, eslint, prettier | **NOT RUN** (gate commit) | Local: vitest 35 files / **403 tests ×3** green; `tsc --noEmit` clean; `eslint .` and `prettier --check .` clean (after formatting the new test file) | Gate commit |
| R2.5 Production build | **NOT RUN** (gate commit) | Local `npm run build` (tsc + vite) succeeded in 14.4 s; Docker CI's `build-frontend` job builds the image on push | Gate commit + Docker CI |
| R2.6 CI green on gate commit | **BLOCKED** | No push authorised | — |
| R2.7 Planner acceptance PL-1…PL-10 | **PASS (local)** | (a) 19 mocked-API UI tests; (b) real run in the browser against the dev stack (Docker, Python 3.11, `DEV_AUTH_BYPASS`): server validation (15 → 6 simulations after setting 2 seeds), job with cumulative progress ("4 of 6"), results, exports JSON 99,740 B / MD 8,317 B / CSV 4,774 B, **reproduce: identical result fingerprint `99cdeadc710c5a59`**, re-open after reload, delete → 404 and a clear "not found" message; (c) PL-9 *after backend restart* verified by `test_deleted_study_is_removed_from_the_database` (fresh store reads the DB), **not** by restarting a live server; PL-10 by R3.1/R3.2 tests | Live restart check on the gate commit |
| R2.8 Accessibility | **NOT RUN** | No axe tooling in the repo (adding it is a dependency decision); keyboard: Tab order and visible focus checked by hand on the planner form; landmarks: no nested `<main>`, tables have captions and `scope` | Add vitest-axe or run axe once (D-V2-9) |
| R3.1 Route-level auth test | **PASS (local)** | `tests/api/test_v2_route_auth.py` (parametrised from the OpenAPI document, 20 routes) | — |
| R3.2 Planning isolation | **PASS** | `tests/planning/test_planning.py` (get, report, reproduce, delete → 404 for another user) | — |
| R3.3 Calibration isolation | **PASS (local)** | R1.3; plus a planning study cannot attach another user's run (validate/run/jobs) | — |
| R3.4 Suite isolation | **PASS (local)** | R1.4 | V1 history exposure (D-V2-7) |
| R3.5 Request-size limits | **PASS (local)** | `src/request_limits.py` (ASGI; declared and chunked bodies) 1 MiB on `/api/v2/networks/*` and `/api/v2/planning/validate` → 413 `PAYLOAD_TOO_LARGE`; `tests/api/test_request_limits.py` (incl. a realistic large network ≥ 20× under the cap) | — |
| R3.6 Dev bypass not in prod compose | **PASS** | Unchanged; `test_dev_auth_bypass.py` green | — |
| R3.7 Deletion or documented retention | **PASS (local)** | `DELETE /api/v2/calibration/runs/{id}` (owner/admin), `DELETE /api/v2/planning/{id}` (owner; 409 while running); retention table in `docs/operations.md` (suites and run history: no delete route, documented) | D-V2-6 confirmation |
| R3.8 Production `API_KEY` set | **BLOCKED** | Operator check on the host; procedure now in `docs/operations.md` | Operator |
| R4.1 `/api/v2` API reference | **PASS (local)** | `docs/api/README.md` §10 from the OpenAPI document (all 20 routes), error table (413, 422 envelope) | — |
| R4.2 README and ROADMAP status | **BLOCKED** | `ROADMAP.md` not editable without authorisation (D-V2-2); README: only the calibration sentence corrected and the planner guide linked — its status row and roadmap table still mirror `ROADMAP.md` | D-V2-2 |
| R4.3 Validation addendum, K7/K8 | **PASS (local)** | `docs/research/validation.md` §4.4 (checked / not checked), K7, K8, §4.3, §6 rows updated | — |
| R4.4 Planner guide | **PASS (local)** | `docs/product/planner-guide.md`, linked from README | Screenshots optional |
| R4.5 Operator notes | **PASS (local)** | `docs/operations.md`: `API_KEY` mandatory + host check, per-user auth and admins, data retention and deletion | — |
| R5.1 Root cause of failed runs | **PASS** | Revision-4 block above (both logs read via `gh run view --log-failed`) | — |
| R5.2 Fix on `deployment` | **BLOCKED** | Merge is a deployment trigger (G-PROD) | PO |
| R5.3 Static checks | **NOT RUN** (partial) | `bash -n` passes for `scripts/deploy-ec2.sh`, `run-remote-deploy.sh`, `validate-schemas.sh`; `shellcheck` not installed; workflow not re-reviewed line by line | shellcheck + review |
| R5.4 Successful pipeline run | **BLOCKED** | G-PROD | PO |
| R6.1–R6.3 Production | **BLOCKED** | No authorisation (G-PROD) | PO |

#### 7.0a Commands (local, Windows, backend Python 3.14.7; dev stack Python 3.11.16)

```
backend> .venv/Scripts/python.exe -m pytest -m "not slow"                       # coverage gate in addopts
backend> .venv/Scripts/python.exe -m ruff check . ; ruff format --check . ; mypy src
export of 4b40cc9> pytest <file> -m slow --no-cov -v --durations=0              # each of the 10 slow files, in parallel
frontend> npx prettier --check . ; npx eslint . ; npx tsc --noEmit ; npx vitest run (x3) ; npm run build
```

**New decisions raised by revision 4:** D-V2-7 should V1 run history (`/api/v1/study/history/runs`) become per-user? · D-V2-8 the two failing slow tests: change the expectation to the documented ≤ 2-ring-lane limit, or treat as a model defect · D-V2-9 add an axe dependency (vitest-axe) or accept a one-off manual axe run.

**Side effect to note:** the running Docker dev stack bind-mounts `backend/src`, so it hot-reloaded the gate changes and its `init_db` added the `scenario_suites.user_id` column to the dev volume's database (additive; no row changed). One planning study was created there for the walk-through and deleted afterwards through the new route.

### 7.0b Revision 5 — row changes and evidence (2026-10-13)

Rows not listed keep their §7.0 status. "PASS (local)" still needs re-confirmation on a gate commit (R1.7/R2.6).

| Row | Was | Now | Evidence (command → result, final working tree) |
| --- | :-: | :-: | --- |
| R2.1 Backend non-slow + coverage | NOT RUN | **PASS (local)** | Python 3.14.7: `pytest -m "not slow"` → **1,247 passed, 0 failed, coverage 94.81 %** (floor 85 %), 24 min. Python 3.11.16 (CI/Docker runtime, container copy without `.git`): **1,244 passed, 3 failed, coverage 94.87 %** — the 3 are the checkout-dependent tests in the environment note below, which pass on 3.11 with the checkout files present (39/39 for their files) |
| R2.2 Slow suite | FAIL | **PASS (local)**, classification pending D-V2-8 | Python 3.11.16, one process per file, final tree: **238/238 passed, 0 failed** (190 original + 48 randomized; calibration-pass 24/24, real-world junctions 60/60, adaptive 27/27, multilane 24/24, vehicle types 20/20, calibrated capacity 10/10, lock-up 10/10, conflicts 9/9, signal capacity 5/5, router 1/1; longest file 34 min). Baseline tree on 3.11 earlier: 188/190, the two roundabout cases, values identical to 3.14 |
| R2.3 ruff / format / mypy | NOT RUN | **PASS (local)** | `ruff check src tests` clean; `ruff format` clean; `mypy src` (strict) 104 files, no issues |
| R2.4 Frontend | NOT RUN | **PASS (local)** | `vitest run` ×3 → **35 files, 409/409** each; `tsc --noEmit`, `eslint .`, `prettier --check .` clean |
| R2.5 Production build | NOT RUN | **PASS (local)** | `npm run build` (tsc + vite) exit 0 |
| R2.8 Accessibility | NOT RUN | **PASS (local)**, automated checks only | axe in Vitest (4 tests, 0 violations) + browser contrast check (0 violations, both themes, 3 pages). Keyboard and screen-reader review: not done |
| R3.4 Suite isolation | PASS (local) | **PASS (local)**, gap closed | Batch runs owned by the suite owner (`test_suite_batch_runs_belong_to_the_suite_owner`) |
| R3.9 *(new)* Run-history isolation | — | **PASS (local)** | `tests/api/test_run_history_access.py` (owner / other / anonymous / admin on every route, filters, labels, compare, reproduce bound); live dev server: owner 200, anonymous 404 on read and 401 on PATCH; browser export works for the owner |
| R3.10 *(new)* Compute bounds | — | **PASS (local)** | `tests/api/test_compute_limits.py` (every synchronous route → 429 when full; thread safety; step ceiling in validator, scenario API and engine) |
| R3.11 *(new)* Token verification | — | **PASS (local)** | `tests/api/test_cognito_token_verification.py` (valid ID and access tokens; expired, wrong audience, wrong key, unknown kid, tampered, HS256 with PEM and DER public key, `alg: none`, malformed → 401) |
| R3.12 *(new)* Dependency audit | — | **PASS with accepted risk** (PO to accept) | `pip-audit -r requirements.txt`: only `ecdsa` CVE-2024-23342 (signing only; never used) and python-jose CVE-2026-85394 (no fix; blocked by the RS256 pin, tested). `npm audit --omit=dev`: `source-map-js` (build time, own sources only); dev only: `brace-expansion`, Vitest/tinypool (test runner). Fixes are patch bumps ≤ 4 weeks old or a forced Vitest major: deferred |

**Environment notes.** Three tests fail in a container copy that lacks `.git` and `frontend/Dockerfile` (`test_get_git_commit_hash_against_the_real_repo`, `test_mid_run_save_reproduces_to_the_recorded_elapsed_time`, `test_nginx_template_keeps_runtime_variables_unsubstituted`); with those checkout files copied in, the three files pass on 3.11 (39/39). CI runs from a real checkout. The dev Docker stack was used for the live checks; one test replay was created there and deleted.

**Residual risks (not fixed for V2.0).** No per-client rate limit (one client can hold both synchronous slots; each run is bounded by the step ceiling) · WebSocket streams have no Origin check (a cross-site page could read a visitor's live simulation frames; no personal data in them) · in-flight planning jobs are lost on restart (documented) · compute and job caps are per process (production runs one) · deployment unverified.

**Commands.** Backend (from `backend/`): `pytest -m "not slow"`; `pytest <file> -m slow --no-cov` per slow file; `ruff check src tests`; `ruff format --check src tests`; `mypy src`; `pip-audit -r requirements.txt`. Frontend (from `frontend/`): `npx vitest run` ×3; `npx tsc --noEmit`; `npx eslint .`; `npx prettier --check .`; `npm run build`; `npm audit [--omit=dev]`. Roundabout third-lane experiment: `python scripts/roundabout_lane_experiment.py`.

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

*Revision 4:* no commit, push, merge, PR, deployment, GitHub milestone change or `ROADMAP.md` edit; application code **was** changed (working tree only) to resolve gate rows, and every change is listed in §7.0. The paragraph below describes revision 2.


No deployment, commit, push, merge or branch change · no edits to `.claude/launch.json`, application code, tests or `ROADMAP.md` · the backend and frontend suites were **not re-run for revision 2** (owner's instruction), so every test row is NOT RUN against the gate commit · no `slow` run, no Docker or `vite` build, no accessibility tooling · no probing of production or of the EC2 host · no line-by-line review of the codebase — statuses rest on tests, docs, runtime observation of the first audit and targeted code reading, and say so where that is thin.

**Claims that could not be verified from the repository:** the production `API_KEY`/Cognito configuration; whether production currently runs any particular commit; the cause of the first failed deployment run; whether the scheduled CI "slow" job ran green on the last nightly (only the workflow's overall success was seen); actual presentation-machine performance.
