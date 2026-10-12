# V3.0 Product Strategy

> **Status:** PROPOSED — pending review · **Written:** 2026-10-12 · **Depends on:** [V2.0 completion audit](V2_COMPLETION_AUDIT.md)
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Convention note:** this is a proposal. [`docs/ROADMAP.md`](../ROADMAP.md) remains the single authoritative roadmap; on approval a V3.0 section is added *there* (its §7), and Future Scope entries FS-1, FS-2 and FS-6 move into it without duplication.

---

## 1. Product direction in one paragraph

**UrbanFlow V3.0 turns the application into a reproducible, uncertainty-aware junction-experiment platform that can be driven from the UI or from code.** A planning officer asks *"does the preferred signal or roundabout choice survive uncertain demand and driver behaviour?"* and gets evidence with its limits attached. A researcher runs the same question from a script, plugs in their own signal policy, and receives a portable package another machine can verify and re-run. Three research initiatives provide the substance; one integration spine makes it usable outside UrbanFlow's own screens.

**The principle stays: EVIDENCE, NOT A VERDICT.** V3.0 never says an intersection or controller is "best". It says what happened under named conditions, how often, with what interval, and what was not tested.

### Who it is for

| User | Needs | V3.0 gives them |
| --- | --- | --- |
| **Municipal planning officer** (not a traffic engineer) | A defensible, plain-language answer to "will this still hold if traffic is different from our count?"; something to attach to a report | A guided planner (finally with a UI — V2.0 closure), a *robustness view* that shows how often each option wins and where the answer flips, exportable reports and packages |
| **Traffic researcher / student** | Fair controller comparison, repeatable training and evaluation, citable provenance | A signal-control lab with strong baselines and held-out evaluation; a plug-in policy interface; scripted batch experiments; portable packages |
| **Integrator / developer** (another tool or workflow) | A stable contract, credentials, quotas, schemas | A versioned `/api/v3` experiment API, a Python SDK, personal access tokens, JSON schemas, CSV/GeoJSON in and out |

### Claim rules that govern every V3.0 screen and document

1. Results are **conditional**: every result states scenario fingerprint, demand range, vehicle mix, seeds/samples, duration and limitations.
2. **"Robust"** may be written only when at least 100 sampled conditions completed and a convergence check passed; below 30 the page says *indicative*.
3. **Learned controllers are labelled EXPERIMENTAL** wherever they appear, with the regimes and number of held-out seeds beside every number.
4. **Emergency response times are model outputs** for a modelled junction, never predictions for a real one.
5. **No absolute emissions, no field-calibration claims** (parameter calibration does not exist; see audit A-21).
6. A feature the backend only stubs is **not shown as available** in the UI.
7. Determinism is promised **per code commit and Python version**; a package records both and reports "differs (engine changed)" honestly.

---

## 2. Capacity assumptions

Not confirmed with the owner — these are working assumptions to be corrected.

| Assumption | Value |
| --- | --- |
| People | **One primary engineer** using coding agents. Other contributors named in the docs (e.g. the V1.6/V1.7 and `frontend/` owner in `v18-v20-contracts.md`) are **not** assumed available |
| Working time | Mon–Fri; ~6 focused hours/day of directed work; weekends are buffer, not plan |
| Agent leverage | 2–3 agents in separate git worktrees on independent modules; **review by the engineer is the bottleneck**, so a feature-day below means *reviewed and merged*, not drafted |
| Estimating unit | **engineer-day (ED)** = one reviewed, tested, merged day of output with agents |
| Weekly output | ~5–6 ED in a 5-day week. After the preview, plan ≤ 86 % of capacity. **Sprints 0–1 are loaded to 94–95 %** because the preview date is fixed and V2.0 closure cannot wait; they carry a published cut-line ([sprint plan §1.3](V3_WEEKLY_SPRINT_PLAN.md#13-cut-line-for-s0-and-s1-together-cut-in-this-order-if-behind)) |
| Compute | One developer machine (cores unknown). Measured engine speed: **233–405 steps/s** uncontended at moderate load, **39–48 steps/s** at saturation under contention; one 300 s run = 3,000 ticks ≈ 10–70 s. All compute budgets in this plan are derived from these numbers and must be re-measured in Sprint 0 on the demo machine |

---

## 3. Choosing the initiatives

### 3.1 Scoring framework

Each candidate is scored 1–5 per criterion (5 = best) against **the repository as it is today**. Weights sum to 100.

| Criterion | Weight | 5 means |
| --- | :-: | --- |
| User and research value | 15 | Answers a question planners/researchers actually ask |
| Novelty and differentiation | 10 | Not already in UrbanFlow or commodity |
| Scientific credibility achievable | 15 | Defensible method with the data/time available |
| Demonstrable by 29 Oct | 15 | A real, honest slice runs live in 17 days |
| Feasible by 26 Nov | 15 | Complete, validated increment fits ≈ 4 development weeks |
| Low dependency on unfinished work | 10 | Builds on shipped, tested code |
| Integration value | 10 | Strengthens API/SDK/plugin/package story |
| Low risk and validation burden | 10 | Small blast radius; tests are tractable |

### 3.2 Scores

| # | Candidate | Value 15 | Novelty 10 | Sci. 15 | Demo 15 | Feasible 15 | Deps 10 | Integr. 10 | Risk 10 | **Weighted /5** | Equal-weight /5 |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| **B** | **Uncertainty & robust simulation** (FS-6) | 5 | 4 | 5 | 4 | 5 | 3 | 4 | 4 | **4.35** | 4.25 |
| **A** | **AI-based signal control** (FS-2) | 4 | 5 | 3 | 3 | 4 | 4 | 5 | 3 | **3.80** | 3.88 |
| **C′** | **Emergency priority — scoped to signal pre-emption** (FS-1) | 4 | 4 | 3 | 3 | 4 | 3 | 3 | 3 | **3.40** | 3.38 |
| G | Weather & road condition (FS-7) | 3 | 2 | 2 | 4 | 4 | 4 | 3 | 3 | 3.15 | 3.13 |
| C | Emergency priority — full FS-1 (yielding/clearance) | 4 | 4 | 3 | 2 | 3 | 3 | 3 | 2 | 3.00 | 3.00 |
| H | Incident & disruption (FS-8) | 4 | 3 | 3 | 2 | 2 | 3 | 3 | 2 | 2.75 | 2.75 |
| E | Platooning & cooperative driving (FS-4) | 2 | 3 | 3 | 2 | 3 | 3 | 2 | 3 | 2.60 | 2.63 |
| J | Digital twin (FS-10) | 4 | 4 | 2 | 1 | 1 | 1 | 5 | 1 | 2.30 | 2.38 |
| I | Large-scale network simulation (FS-9) | 5 | 3 | 2 | 1 | 1 | 1 | 4 | 1 | 2.25 | 2.25 |
| D | Connected-vehicle communication (FS-3) | 2 | 4 | 2 | 1 | 2 | 2 | 3 | 2 | 2.15 | 2.25 |
| F | Autonomous intersection management (FS-5) | 3 | 5 | 2 | 1 | 1 | 2 | 2 | 1 | 2.05 | 2.13 |

Weighted score = Σ(score × weight) ÷ 100, so the maximum is 5.00. Scores are judgement. The ranking is the same under equal weights, and shifting any single weight by ±5 points does not change the top two (checked by hand: the A–C′ gap of 0.40 can move by at most 0.10).

### 3.3 Reasoning that the numbers do not carry

* **B — Robustness (lead initiative).** Highest value-for-risk. It is almost entirely *orchestration* over proven code: the scenario compiler, the seeded engine, paired comparison and the planning layer already exist. It directly operationalises the product principle, and it is the only candidate whose output (a view of *where the answer flips*) is something no single-seed study can show. **What exists today is not this:** `vehicles/stochastic_idm.py` is a fixed "unstructured traffic" noise mode (random hesitation, aggression jitter) with hard-coded constants; V1.0 repeats seeds; V1.7 sweeps arrival rate. None treats the *parameters themselves* as uncertain or reports robustness — which is exactly FS-6's stated boundary.
* **A — AI signal control.** Highest novelty and integration value (a gym-style environment is the researcher's entry point), but the highest scientific-credibility risk. It is made credible by *protocol*, not by the algorithm: strong baselines (including a tuned fixed-time plan and max-pressure — a naive fixed plan would make any learner look good), held-out seeds, out-of-distribution regimes, paired comparison, and an unconditional EXPERIMENTAL label. A feasible hook already exists: `AdaptiveSignalController` subclasses `FixedTimeSignalController` and exposes stop-line detection (`controllers/signal_detection.Observation`), so a policy shell reuses the legal phase machinery rather than touching physics. Training throughput is the binding constraint (§3.5).
* **C′ — Emergency priority, scoped.** The full FS-1 (surrounding traffic yielding, path clearance, pull-over) scores 3.00 because it touches spawning, routing, lane-change and conflict arbitration in code whose **bit-for-bit reproduction of earlier scenarios is a project invariant**. The scoped version — an emergency class that appears only when a scenario lists emergency events (so ordinary runs stay bit-identical), signal **pre-emption** on fixed-time and adaptive signals with clearance and recovery, and response-time versus collateral-delay metrics — scores 3.40 and is a recognised study in its own right (pre-emption benefit versus cost to conflicting movements). Yielding and clearance behaviour are explicitly deferred. C′ is also the **first thing cut** if time slips (go/no-go gate **G4, Thursday 12 November**, at the end of its first slice).
* **Why not Weather (G, 3.15)?** It scores well on demo/feasibility only because it is parameter scaling. But there is no calibration source in this repository for friction or visibility effects, so its credibility is the weakest of the top five; and half its value is already captured by B — "degraded driving" appears as a *labelled sensitivity factor* (headway and desired-speed scale), which does not claim to model weather. **Substitution is not recommended**; C′ beats G once scoped. If the owner prefers a pure score ranking, G-lite (condition presets inside B) replaces C′ at no schedule risk.
* **Why not the larger frontiers (D, F, I, J)?** Each depends on capabilities that do not exist: multi-junction simulation (audit A-31 — networks are *representation only*), vehicle-to-vehicle messaging, or reservation-based arbitration. They are the right post-V3 research programme, not a six-week one.

### 3.4 Overlap check against existing code

| Candidate | Already exists | Genuinely new in V3.0 |
| --- | --- | --- |
| B | Seeded repeats; Student-t CIs; Welch/Cohen's d (with the new untestable case); paired comparison; demand scales (planning); `stochastic_idm.py` (fixed noise mode); `advanced` merge as the sanctioned parameter hook | Distributions over demand/mix/turning/driver parameters; stratified sampling; common-random-number pairing across alternatives; probability-of-better, regret, preference stability; sensitivity and flip detection; sample-size and convergence guardrails |
| A | Fixed-time and adaptive controllers; stop-line detection; control-comparison study; `BaseController` + `factory.py`; no RL code or dependencies anywhere | Environment, baselines (Webster, max-pressure), policy shell with safety clamps, trainer, held-out evaluation, policy artifact format, UI |
| C′ | Vehicle-class profiles (`VehicleTypeProfile`); signal phase machinery; `ConflictManager`; safety counters. `grep` finds no emergency/priority/pre-emption code | Emergency events, class, pre-emption state machine, recovery, response/collateral metrics |

### 3.5 The binding constraint: compute

Measured engine speed puts hard limits on ensembles and on RL. These are planning numbers to be re-measured in Sprint 0.

| Workload | Calculation | Wall time (single core → 6 workers) |
| --- | --- | --- |
| Robustness: 100 samples × 3 alternatives × 2 replicates, 300 s runs | 600 runs × ~25 s typical | ~4 h → ~45 min |
| Robustness preview preset: 24 samples × 3 × 1, 180 s runs | 72 runs × ~12 s | ~15 min → ~3 min |
| RL training: 500 episodes × 300 s sim | 500 × ~20 s | ~2.8 h → ~30–45 min with parallel actors |
| RL evaluation: 5 controllers × 3 regimes × 30 seeds, 300 s | 450 runs × ~20 s | ~2.5 h → ~25 min |
| Emergency study: 5 demand levels × 20 seeds × 2 modes | 200 runs × ~20 s | ~1.1 h → ~12 min |

Consequence: every long experiment gets a **preset ladder** (Quick / Standard / Thorough) with the run count and estimated time shown *before* submission, and the preview uses Quick presets or precomputed packages.

---

## 4. The three initiatives

### 4.1 I-1 Robustness Lab (Uncertainty & robust simulation) — *lead*

**Question answered:** *"If demand and driver behaviour differ from what we assumed, does the comparison between alternatives still hold — and where does it flip?"*

**Scope (committed)**

* **Uncertainty specification** (`urbanflow-uncertainty-spec` v1): factors, each with distribution, bounds, and a mandatory `basis` (`assumed` | `observed` | `user`). Factors: global and per-approach demand multiplier; turning-share perturbation; vehicle-mix perturbation; IDM headway scale (the nearest parameter to driver reaction — the engine has no explicit reaction delay and the UI must not claim one); desired-speed scale; maximum-acceleration scale.
* **Sampling:** stratified (Latin hypercube) with deterministic seeding; optional replicate seeds per sample to separate parametric from stochastic variance.
* **Fair comparison:** every alternative runs the *same sampled scenario and the same engine seed* (common random numbers), so differences are paired.
* **Outputs:** distribution of paired differences per alternative; probability each alternative is better than the baseline by more than the tie tolerance (with interval); expected and worst-case regret; "preferred in x % of sampled conditions" (never "winner"); sensitivity (rank correlation) of the difference to each factor; flip detection along the strongest factors; convergence trace.
* **Guardrails:** N < 30 → *indicative*; N ≥ 100 plus convergence → may use "robust"; runs that hit the vehicle limit are excluded and counted; failed runs counted and shown.
* **Delivery:** async experiment job through the planner UI and the API/SDK; Quick/Standard/Thorough presets; package export/import.

**Out of scope:** weather claims; calibrated priors; correlated multi-factor copulas beyond a single demand-correlation parameter; Sobol indices (rank-correlation first).

**Success measures:** same spec + seed ⇒ identical result fingerprint; pairing test proves identical samples across alternatives; a synthetic case with a *known* flip point is recovered within one sampling stratum; guardrail tests; < 3 min Quick preset on the demo machine.

### 4.2 I-2 Control Lab (AI-based signal control) — *experimental by definition*

**Question answered:** *"Under these named demand regimes, can a learned signal policy match or beat strong non-learning controllers, and with what evidence?"*

**Scope (committed)**

* **Environment** (`SignalEnv`, Gym-style `reset(seed)` / `step(action)`) over the existing engine. Decisions at a fixed epoch (default 5 s); actions are *legal-phase selections* only.
* **Policy shell:** the learned (or any plugged-in) policy never sets lamp colours. The shell enforces legal phase order, minimum green, yellow, all-red and maximum green; illegal requests are clamped and counted (`policyViolations`). A 10,000-decision random-action fuzz test must show zero conflicting greens and zero collisions.
* **Baselines (all evaluated identically):** existing fixed-time; existing adaptive; **Webster-tuned fixed-time** (new — a fair fixed baseline); **max-pressure** (new — strong, simple, widely cited); random-legal and always-hold as sanity floors.
* **Learner:** a small DQN (2 × 64) trained with domain randomisation drawn from I-1's sampler. Chosen over PPO for sample efficiency at our ~100 – 500 steps/s. Pure-Python/NumPy so there is no deep-learning dependency in the production image (decision D2; a torch wheel for the local Python 3.14 is not assumed).
* **Evaluation protocol:** train seeds and held-out seeds are disjoint; three regimes (in-distribution, higher demand, skewed split) with ≥ 30 paired seeds each; paired differences with intervals through the existing statistics code; results state regime, N, duration, warm-up, scenario fingerprint.
* **Artifact:** policy JSON (weights, normalisation, training provenance: commit, config fingerprint, seeds, hyper-parameters, learning curve) selectable as `controller.signalControl = "policy:<id>"`.
* **UI:** Control Lab page — pick policies, run the evaluation, read "tested conditions" first, then paired results; permanent EXPERIMENTAL badge.

**Honest outcome rule:** if the learner does not beat adaptive or max-pressure, that *is* the result, reported as such. The deliverable is the environment, protocol and baselines, which stand on their own.

**Out of scope:** PPO/multi-agent, multi-junction coordination, roundabout learning, transfer to other geometries, any real-world performance claim.

### 4.3 I-3 Emergency Priority (scoped) — *gated, first to be cut*

**Question answered:** *"How much response time does signal pre-emption save an emergency vehicle at this junction, and what does it cost the other road users?"*

**Scope (committed if the 5 Nov gate passes)**

* `emergency` block in the scenario document: a list of scheduled events `{departAt, from, movement, class}`. **No block ⇒ byte-identical to today** (pinned by existing determinism tests).
* Emergency class(es) as a profile (`ambulance`, `fire_engine`) with a `priority` flag, so the engine still never branches on class names.
* **Pre-emption** on fixed-time and adaptive signals: detection upstream, finish the current clearance, serve the emergency approach, hold until the vehicle clears the stop line plus margin, then a defined recovery; lock-out between consecutive pre-emptions; a deterministic tie rule for simultaneous requests.
* **Metrics:** emergency delay and travel time; paired saving versus the same seed without pre-emption; collateral delay by approach; recovery time; pre-emption count; safety invariants (collisions, conflicting greens) must stay at zero.
* **Safety tests** are part of scope, not polish: pre-empt during yellow/all-red; two simultaneous requests; request during adaptive max-green; cancelled request; storm of requests; randomised-arrival fuzz.

**Deferred explicitly:** surrounding traffic yielding/pull-over and path clearance; roundabouts; multiple concurrent emergency vehicles beyond the tie rule; dispatch/routing; real response-time claims.

**Gate G4 (Thursday 12 November, end of Sprint 4):** class and events work and a signal crossing alters no pre-existing deterministic test; pre-emption passes the safety suite. Partial ⇒ ship "emergency class + metrics, no pre-emption"; fail ⇒ hide it and re-spend the time on I-1/I-2 (see the [sprint plan's fallback ladder](V3_WEEKLY_SPRINT_PLAN.md#5-sprint-4--friday-6--thursday-12-november)).

---

## 5. Integration platform (the spine, not a fourth project)

Integration is a **budgeted cross-cutting track (≈ 25–30 % of capacity)** delivered *through* the three initiatives: the robustness job is the first thing exposed through the new API, the Control Lab exposes the environment and policy interface, and the emergency study ships as a package. Nothing is built for its own sake.

### 5.1 The six directions compared

| Direction | Who benefits / problem solved | Minimum useful implementation | Dependencies | Effort & risk | When |
| --- | --- | --- | --- | --- | --- |
| **1. API-first platform** (versioned endpoints, contracts, auth, reproducible execution) | Integrators and researchers: today there is no stable contract or per-client credential; the API key authenticates the nginx proxy, not a person (audit §5) | `/api/v3/experiments` (one job envelope for planning / robustness / control-evaluation / emergency), published OpenAPI plus JSON Schemas, personal access tokens with scopes, per-user quotas, contract tests | M2 (consistent protection), M5 (docs) | 5–6 ED; medium — security surface | **Documented subset at preview; tokens/quotas in V3.0** |
| **2. Python SDK** | Researchers and automation: scripts instead of hand-written HTTP | `urbanflow-client`: `Client`, `validate`, `submit`, `wait`, `result`, `export_package`, `open_url`; typed result objects; one notebook | #1 | 2 ED; low | **Preview (minimal), V3.0 (complete)** |
| **3. Scenario/result import–export, portable schema** | Everyone: reproducible hand-off, offline demo, review by a third party | `urbanflow-experiment-package` v1 (zip + manifest + checksums + provenance), import with integrity check and optional re-run | Existing schemas, fingerprints, `reproduce` | 3 ED; low | **Preview** |
| **4. GIS / real-data / planning-workflow integration** | Planning officers: counts arrive as spreadsheets, sites as map layers | CSV turning-movement counts → `urbanflow-observations`; GeoJSON arms → draft scenario via existing `assign_slots`; results as GeoJSON for QGIS | V1.8 observations (exists), `roads/junction_geometry.assign_slots` (exists) | 3 ED; medium — messy real data | **V3.0 (Sprint 5), minimal** |
| **5. Mobile / PWA** | A planner in a meeting checking a long job and reading findings on a phone | Responsive, read-only status and results pages verified at 375 px | M1 planner UI | 1 ED responsive; +0.5 ED PWA manifest | **Responsive in V3.0; installable PWA stretch; native app rejected** |
| **6. Controller / experiment plugin architecture** | Researchers extending signal control without forking the engine | Registry that finally implements ADR-012; `SignalPolicy` interface + safety shell; experiment-kind registry | I-2 | 3 ED; medium | **V3.0 (Sprint 3)** |

### 5.2 Recommended minimum set

**Preview (29 Oct):** #3 packages + #2 minimal SDK + the already-existing `/api/v2` endpoints, now documented (M5), driven from a notebook; the UI shows the same experiment.
**V3.0 (26 Nov):** #1 tokens, scopes, quotas and the `/api/v3` envelope · #6 policy and experiment plugin seams · #4 CSV/GeoJSON · #5 responsive read-only views · the complete SDK.
**Later:** webhooks, SUMO/OpenStreetMap importers, embeddable result widgets, organisation-level sharing, installable PWA, native mobile.

### 5.3 API versioning and compatibility

* `/api/v1` and `/api/v2` become **frozen**: additive changes only, no removals. They stay what they are.
* New capabilities live under `/api/v3` (`experiments`, `packages`, `tokens`, `controllers`, `capabilities`). One generic job envelope: `POST /api/v3/experiments {kind, spec}` → `202 {id}`; `GET /{id}` (status, progress, partial results); `GET /{id}/result`; `GET /{id}/package`; `DELETE /{id}` (cancel/delete).
* Documents keep the `format` + integer `version` + `extra="forbid"` convention; a new major `version` never silently changes the meaning of an old one.
* `GET /api/v3/capabilities` lists experiment kinds, registered policies, limits and quotas, so the UI and SDK discover what the server can do (and never advertise a stub).
* OpenAPI published and checked by a contract test; the SDK is tested against a live local server.

### 5.4 Authentication, authorisation, quotas, privacy

| Concern | Design |
| --- | --- |
| Credentials | **Personal access tokens** (`uf_pat_…`, 256-bit random; only a SHA-256 hash stored; prefix shown in the UI; expiry default 90 days; revocable; last-used time). Cognito JWTs keep working for the browser |
| Authorisation | Scopes `read`, `run`, `admin`; every v3 resource carries an owner; **default private**; `GET` on another owner's id is a 404 (the planning-study pattern) |
| Quotas | Per user: concurrent jobs (default 2), simulations per experiment (cap by kind), simulated-seconds per day, request body ≤ 1 MB, rate limit per token. Counted server-side and reported by `/capabilities`. Limits are enforced in-process (production runs a single uvicorn process); a shared store is needed before scaling out |
| Code execution | **No uploaded code.** External users supply *data* (a policy's weights, a spec). Custom Python policies are installed server-side by an administrator through an entry-point group; remote-controlled stepping is deferred. No webhooks in V3.0 (SSRF surface) |
| Privacy | Observations may reveal municipal data: owner-scoped, deletable, never in logs; schemas carry no personal-data fields and say so; packages strip user id/e-mail; retention setting documented |
| Compatibility | Packages record UrbanFlow commit, Python version and schema versions; import warns on mismatch and `reproduce` reports `reproduced` or `differs (engine changed)` |
| Audit | Token creation, revocation and experiment submission logged (metadata only) |

### 5.5 Plugin design (summary)

* **`SignalPolicy`** — `decide(observation, legal_actions) -> action`, nothing else. A single engine-side `PolicySignalController` (a subclass of `FixedTimeSignalController`, the way `AdaptiveSignalController` is) owns lamp colours and safety. Built-in policies: fixed-time, adaptive, Webster, max-pressure, learned (weights). A registry (`controllers/registry.py`) is the missing piece of ADR-012; `factory.create_controller` consults it. Existing controllers keep their current path and stay the baselines.
* **Experiment kinds** — a small registry mapping `kind → validate / expand to tasks / aggregate`, running on the existing process pool and `JobRegistry`.
* Both are server-side Python today; the SDK exposes them as data.

### 5.6 Mobile decision

**No native app. No offline PWA.** Reasons: simulation is server-side so offline use is moot; there is no sensor or camera need; one engineer cannot maintain an extra platform; and the real mobile problem — *"is my long study finished and what did it find?"* — is solved by responsive, read-only status and results pages. V3.0 commits to that (tested at 375 px). An installable manifest is a half-day stretch; push notifications wait for webhooks.

### 5.7 Embedding in another application's workflow

Other tools should not need UrbanFlow's screens: they submit a spec through the SDK or HTTP, poll or fetch, and consume JSON/CSV/GeoJSON plus the package. A planning application can therefore embed *capabilities* (run a robustness check, fetch an evidence summary) rather than iframe a UI. Embeddable read-only widgets and webhooks come after the token model has soaked.

---

## 6. Feature boundaries

### In V3.0 (committed)

V2.0 closure (planner UI, access control, private suites, docs) · I-1 Robustness Lab · I-2 Control Lab with environment, baselines, policy shell and one honestly labelled learned policy · `/api/v3` experiments, packages, tokens and quotas · Python SDK · plugin seams · CSV/GeoJSON import/export · responsive read-only views.

### Conditional

I-3 pre-emption (gate G4, 12 Nov) · installable PWA manifest · SUMO net import (only if a day frees up).

### Deferred (stated, not hidden)

Parameter calibration and any "calibrated" claim · multi-junction simulation and network visualisation · surrounding-traffic yielding · PPO / multi-agent / roundabout learning · weather as a modelled effect · incidents · V2V, platooning, autonomous intersection management · digital twin / live data feeds · webhooks · embeddable widgets · organisation sharing · native mobile · absolute emissions.

---

## 7. Main risks (strategy level)

| Risk | Effect | Mitigation |
| --- | --- | --- |
| V2.0 planner UI slips | Robustness has no home in the UI | Sprint 0 is built around it; cut the field-data step first |
| Compute too slow for convincing ensembles | Thin sample counts → weak claims | Preset ladder; short durations; parallel workers; guardrails make thin results *say* indicative |
| RL fails to beat baselines | Weak "AI" story | The protocol and baselines are the deliverable; reported honestly; demo does not depend on a win |
| Emergency touches reproduction-critical code | Regression in validated physics | Absent block ⇒ identical; existing determinism tests as gate; first item cut |
| Single-engineer review bottleneck | Merged-quality drops | ≤ 85 % loading, hard feature freezes, one integration branch per initiative |
| Security surface of external access | Data exposure | M2/M3 first; tokens private by default; no code upload; no webhooks |

## 8. Decisions requiring approval

| # | Decision | Recommendation |
| --- | --- | --- |
| D1 | Scope: B + A + C′ (gated) + integration spine | Approve; C′ is first to be cut |
| D2 | Add **NumPy** to backend requirements; no deep-learning framework | Approve |
| D3 | Suites private to creator | Approve (audit Q1) |
| D4 | `/api/v3` namespace, personal access tokens, no uploaded code | Approve |
| D5 | One supported Python version across local, CI and Docker (today 3.14.7 vs 3.11) | Pick 3.11 (what ships) unless there is a reason not to |
| D6 | Edit `ROADMAP.md` to add V3.0 and re-statuses V1.6–V2.0 (audit M5) | Approve |
| D7 | Review and commit the 26 pending working-tree entries before new work | Required |
| D8 | Confirm capacity (single engineer, no other contributors) | Confirm or supply names and hours |
