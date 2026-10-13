# V3.0 Product Strategy

> **Status:** PROPOSED — **revision 3** (creative expansion, 2026-10-12) · all scope, dates and estimates are *proposed* until the product owner approves them
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Authority:** [`docs/ROADMAP.md`](../ROADMAP.md) is the single authoritative roadmap and is **not edited by this revision**. On approval (decision D7) a V3.0 section is added *there* (its §7) and Future Scope items FS-1, FS-2 and FS-6 are moved without duplication. Until then, the synchronisation required is listed in [§12](#12-decisions-requiring-the-product-owner) and in the [sprint plan §9](V3_WEEKLY_SPRINT_PLAN.md#9-roadmapmd-synchronisation-required-not-performed).
> **Gating:** **Nothing in this document authorises V3.0 implementation.** Implementation of V3.0 product features starts only after the V2.0 release gate (G-V2, [audit §7](V2_COMPLETION_AUDIT.md#7-v20-release-gate-g-v2)) has passed. Architecture and design may be documented beforehand; that is what this document is.
> **GitHub:** umbrella [#150](https://github.com/Viraj281105/Traffic-Simulation/issues/150); issue map in [sprint plan §8](V3_WEEKLY_SPRINT_PLAN.md#8-github-issue-map-synchronised).

### What changed in revision 3

Revision 2 made V3.0 a production-hardening-plus-robustness release (Robustness Lab and a minimum developer platform). Revision 3 keeps all of that — the statistical contract (§5), manifest (§6), platform minimums (§7) and calibration terminology (§8) are **unchanged** — and adds the creative scope the product needs to be worth building:

* **Composable Traffic-Control Strategies** (§13) with **signalised roundabouts** as the flagship simulation feature, and an adaptive variant as a conditional follow-on.
* **High driver aggression as the default for new scenarios** (§14). Verified finding: **no driver-aggression parameter exists today**; this is a new, versioned parameter, not a default flip.
* **Two AI features** (§15): the **AI Traffic Experiment Copilot** (language model, proposal-only, validated, grounded summaries) and the **AI Control Strategy Discovery Lab** (bounded multi-objective evolutionary search with held-out evaluation — described accurately as *optimisation*, not a learned model).
* **Creative candidates** ranked and classified (§16); **one major demonstrable feature every implementation week** (sprint plan).
* **Capacity result, stated plainly:** this scope does **not** fit the original 26 Nov calendar. The proposed schedule is extended to a final showcase on **Thu 7 Jan 2027**, with 26 Nov kept as an **interim** presentation (§3, [sprint plan §1–§2](V3_WEEKLY_SPRINT_PLAN.md)). The earlier "AI controller (DQN) ships" and "emergency pre-emption ships" claims remain withdrawn.

---

## 1. Product direction

**UrbanFlow V3.0 evolves the application from a traffic-intersection simulator into a composable, AI-assisted traffic-control experimentation platform** that can be driven from the UI or from code. A planning officer asks *"does the preferred control choice hold up if demand and driver behaviour differ from what we assumed — and is there a combination of geometry and control I have not thought of?"* and receives evidence with its limits attached. A researcher runs the same question from a script and receives a portable package that another machine can verify.

**The principle stays: EVIDENCE, NOT A VERDICT.** V3.0 never says an intersection, controller or AI-discovered strategy is "best". It states what happened under named, *assumed* conditions, how often, with what uncertainty, and what was not tested.

Differentiators (each is a funded or conditional item in §2):

1. **Unconventional combinations of geometry and control** through a validated strategy registry — signalised roundabouts first (§13).
2. **AI-assisted experimentation** — a copilot that turns research questions into validated proposals and grounded interpretations, and a search lab that discovers candidate strategies and evaluates them on held-out seeds (§15).
3. **Robustness and uncertainty analysis** under the statistical contract (§5).
4. **High-aggression traffic as the default** for new scenarios, declared as a model assumption (§14).
5. **Reproducible experiments** with a manifest and verifiable packages (§6, §7).
6. **A safe extension architecture** — behavioural contracts and a compatibility registry, never unsafe class mixing or uploaded code (§13, §7).

| User | Needs | V3.0 gives them (if funded as in §2) |
| --- | --- | --- |
| **Municipal planning officer** (not a traffic engineer) | A defensible, plain-language answer; a way to ask a question without knowing the model | The V2.0 planner (closed first), the copilot's validated proposals and plain-language evidence summaries, a robustness view with explicit assumptions |
| **Traffic researcher / student** | Fair comparison, repeatable runs, citable provenance, unusual junction designs | Signalised roundabouts, a strategy registry, discovery-lab candidates with held-out evidence, scripted experiments, verifiable packages |
| **Integrator / developer** | A stable contract, credentials, quotas | A versioned `/api/v3`, personal access tokens, a Python client, JSON Schemas |

### Claim rules (apply to every screen, document and slide)

1. Results are **conditional**: every result states scenario fingerprint, assumptions, number of sampled conditions, replications, seeds, duration and limitations.
2. **Robustness eligibility is not real-world validity.** A result may be *eligible for robustness statements* (§5.7) and still have **no real-world validity**; the two are always labelled separately.
3. **Assumed inputs are labelled assumed.** Distributions chosen by the analyst are assumptions, never estimates from data, unless an observation record is attached (§8).
4. **No field-calibration claim** exists in V3.0 (§8).
5. **Total simulation runs are never presented as a sample size** (§5.2).
6. Learned controllers and **AI-discovered policies are labelled EXPERIMENTAL** with regimes and held-out seed counts beside every number; a null result ("no candidate beat the baselines") is a valid, reportable result.
7. Emergency response times, queue-clearance times and safety proxies (hard-braking, conflict counts) are **model outputs, not predictions** of real-world outcomes.
8. A capability the backend only stubs is not shown as available.
9. Exact replay is promised **per source revision and runtime** only (§6).
10. **AI output is a proposal or an interpretation, never a measurement.** Model-generated text is visually and structurally separated from measured simulation output; no AI recommendation is presented as proof that a strategy is universally superior.
11. **No language model is described as connected or functional until its integration is implemented and has passed the evaluation in §15.** Without an approved provider the copilot is shown as the deterministic assistant it then is (§15.1).
12. **Driver aggression is a simulation assumption**, not a measurement of real-world driver behaviour (§14).

---

## 2. Ranked priorities and what is actually funded

Ranking is by research value, dependency and risk (scoring in §4). **Funding** is by capacity (§3). A feature that ranks high but is unfunded is *deferrable*, and the core release is defined so that it does not need it. Effort figures are **proposed, unverified estimates** (engineer-days, ED; see §3 and the [sprint plan](V3_WEEKLY_SPRINT_PLAN.md)).

| Rank | Capability | Role | Funding status | If deferred, what is lost | Blocks the core release? |
| :-: | --- | --- | --- | --- | :-: |
| **1** | **Robustness Lab** (uncertainty and robustness analysis) | Evidence engine for every other feature | **Committed** (≈ 6.5 ED across W1, W3, W4, W7, W9; the API share now sits under rank 7) | The statistical foundation | — (it is the core) |
| **2** | **Signalised roundabouts** (§13.3) — *flagship simulation feature* | New geometry × control combination | **Committed** (≈ 4.25 ED, W2) | The headline simulation novelty | — |
| **3** | **Composable Traffic-Control Strategies**: registry, compatibility validation, safe strategy interface (§13) | Architecture that makes combinations safe | **Committed** (≈ 2.5 ED, W3) | Extensibility; clean fingerprints for new strategies | Needed by 2 (partially), 6 |
| **3b** | **Adaptive signalised roundabout** (§13.4) | Second strategy through the registry | **Conditional** on gate G-SR (≈ 1.5 ED, W3) | Demand-responsive entry control | No |
| **4** | **High driver aggression default** (§14) | Behavioural default and its regression matrix | **Committed** (≈ 3.0 ED, W4) | Consistent assumption declared everywhere | No (but touches fingerprints: must land before any new-scenario authoring ships) |
| **5** | **AI Traffic Experiment Copilot** (§15.1) | AI flagship A (language model) | **Committed** (≈ 4.25 ED, W5), AI claim conditional on provider decision D-AI1 | Guided question → validated experiment | No |
| **6** | **AI Control Strategy Discovery Lab** (§15.2) | AI flagship B (bounded multi-objective search) | **Committed** (≈ 4.25 ED, W6) | Automated discovery of candidate strategies | No |
| **7** | **Developer platform and experiment portability** (`/api/v3`, manifest, `.ufpkg`, Python client, tokens, quotas, ownership) | Minimum coherent supporting capability | **Committed**, minimum viable form (≈ 5.0 ED: 0.75 in W1 for the `/api/v3` base, 4.25 in W7) | Outside use; verifiable hand-off | No for the research demo; yes for the "platform" claim |
| **8** | **Traffic Chaos and Stress-Test Lab** + **Strategy Breakpoint Explorer** (§16, candidates 1 and 4) | Robustness-of-strategy stress analysis | **Conditional** (≈ 4.25 ED, W8; needs gate G-W8, and no demand-surge unless approved, §16) | Automated hard-scenario generation; breakpoint map | No |
| **9** | **CSV import**, then **GeoJSON export** | Interoperability | **Conditional**: funded only from capacity freed if rank 8 is dropped (≈ 1.5 ED) | Spreadsheet-to-study path | No |
| **10** | **Responsive read-only views** | Secondary | Folded into the viewer (W9, checked at 375 px) | Phone readability | No |
| — | Emergency-vehicle pre-emption; bus/emergency priority control | Conditional on gate **G-E** (§9.2) | **Not funded; expected to fail G-E** (≈ 4.5 ED) — an explicit decision (D8), not a hidden commitment | Safety-research story | No |
| — | Learned (DQN / RL) controllers; Strategy DNA *visual* composer; Traffic Regime Discovery; Incident & recovery; AI report generator; full explainable-comparison UI; PWA | **Deferred** (§16) | — | See §16 | No |

**Never deferrable:** the V2.0 gate, the statistical contract (§5), the reproducibility manifest (§6), ownership/privacy tests, the limitations page, the validation boundary around every AI feature (§15), and the scenario-fingerprint integrity rule (§13.6).

---

## 3. Capacity assumptions and the result of the capacity analysis

| Assumption | Value |
| --- | --- |
| People | One primary engineer, who is also the **integration owner**. No other contributor is assumed available (assignees named on GitHub issues reflect the owner's area split of 2026-10-12, not confirmed availability) |
| Time | **1 engineer-day (ED) = 1 working day ≈ 6 focused hours**, covering implementation, code review, integration, tests, debugging and documentation. Weekends are **unplanned contingency** |
| Coding agents | Potential throughput; **not** counted in planned capacity. Agent output is reviewed and merged by the engineer |
| Holidays | **None assumed in the calendar, but 25 Dec – 1 Jan is a likely holiday period** (W8–W9, risk R-HOL); any leave shifts dates one-for-one |
| Compute | Engine speed measured **once, on the developer machine**: 233–405 steps/s at moderate load, 39–48 steps/s at saturation under contention. **No benchmark exists for the presentation machine.** Every runtime in this strategy is an *unverified estimate* until benchmarked there (sprint plan task B0-1) |

**Capacity analysis ([sprint plan §1](V3_WEEKLY_SPRINT_PLAN.md#1-capacity-model)).** Phase B needs 51 working days (Mon 26 Oct – Wed 6 Jan) to deliver nine weekly features plus preview and showcase preparation; planned load is **43.25 ED = 85 %** (committed work alone: 37.5 ED, 74 %; conditional work: 5.75 ED).

| Fit test | Result |
| --- | --- |
| Original calendar (to Thu 26 Nov, 22 working days, 18.75 ED planned) | **Does not fit.** Committed scope is ≈ 37.5 ED — twice the capacity. Not claimed |
| Proposed extended calendar (to Thu 7 Jan 2027, 51 working days, 43.25 ED planned) | **Fits at 85 % load** only if V2.0 closes on time, no leave occurs 25 Dec – 1 Jan, and conditional items are dropped on any slip |
| If the PO requires 26 Nov as the **final** date | Option S: Robustness, signalised roundabouts, strategy registry and the aggression default only (W1–W4), **no AI feature**. The PO must choose; see D-SCOPE |

Illustrative compute estimates (**unverified**, from the single measurement above; one 300 s run ≈ 3,000 ticks ≈ 10–70 s):

| Workload | Calculation | Wall time, 1 core → 6 workers |
| --- | --- | --- |
| 24 conditions × 3 alternatives × 1 replication, 180 s runs (72 runs) | 72 × ~12 s | ~15 min → ~3 min |
| 100 conditions × 3 alternatives × 2 replications, 300 s runs (600 runs) | 600 × ~25 s | ~4 h → ~45 min |
| Discovery-lab search, 12 candidates × 8 generations × 3 tuning seeds, 120 s runs (288 runs) + held-out evaluation | 288 × ~10 s + held-out | ~50 min → ~10 min plus held-out phase |

---

## 4. Initiative evaluation (scoring ranks value and risk, it does not fund)

Score 1–5 per criterion against the repository as it is. Weights: value 15 · novelty 10 · scientific credibility 15 · demonstrable by the first feasible date 15 · feasible by 7 Jan 15 · low dependency on unfinished work 10 · integration value 10 · low risk 10. Weighted score = Σ(score × weight) ÷ 100. Scores for revision-2 items are unchanged; the new rows below are scored on the same scale.

| # | Candidate | Weighted /5 | Notes |
| --- | --- | :-: | --- |
| **B** | Uncertainty & robust simulation (FS-6) | **4.35** | Orchestration over proven code; foundation for the evaluation of every other feature |
| **S** | Signalised roundabouts + composable strategies | **4.10** | Highest novelty with credible feasibility: reuses `RoundaboutController` yield logic and the fixed-time `Phase` machinery behind a narrow *entry-gate* seam; baseline is bit-identical when the gate is absent |
| **D** | AI Control Strategy Discovery Lab (search) | **3.95** | Depends on S and B; compute-bound; accurately an optimisation method |
| **P** | Developer platform / portability (rank 7) | 3.90 | Unchanged |
| **H** | High driver aggression default | 3.85 | Cheap, but reproducibility-sensitive (new parameter; fingerprints) |
| **C** | AI Traffic Experiment Copilot | **3.70** | Valuable and demonstrable; quality bounded by provider decision; deterministic fallback keeps the workflow safe |
| **X** | Chaos Lab + Breakpoint Explorer | 3.45 | Needs B; "surges" need an engine capability that does not exist (verified: stationary Poisson arrivals only) |
| **A** | Learned (DQN) controller (FS-2) | 3.10 | Withdrawn from V3.0; the discovery lab replaces the "AI" headline with a more defensible one |
| **C′** | Emergency pre-emption, scoped to signals | 3.40 | Touches reproduction-critical code; ≈ 4.5 ED; deferred (G-E) |
| G | Weather & road condition (FS-7) | 3.15 | No calibration source; folded into B as a *labelled sensitivity factor*, not a modelled effect |
| — | Incidents, platooning, digital twin, large-scale networks, connected vehicles, autonomous intersections | 2.05 – 2.75 | Depend on capabilities that do not exist (audit A-31: networks are representation only; no incident or lane-closure code exists — verified) |

Overlap check: V1.3 adaptive control, V1.7 rate sweeps, V1.0 seed repeats and `vehicles/stochastic_idm.py` (a fixed "unstructured traffic" noise mode) already exist and are **not** the capabilities proposed; no emergency, priority, learning or LLM code exists, and `backend` has no LLM or NumPy dependency today (verified).

---

## 5. Robustness Lab — statistical contract (normative)

This contract defines what the Robustness Lab must compute and may claim. Tests (sprint plan B1) are written against it; the viewer, API and slides inherit its wording.

### 5.1 Inputs and assumptions

* An **uncertainty specification** (`urbanflow-uncertainty-spec` v1) declares factors, each with: id, kind, distribution (uniform, triangular, truncated normal, lognormal), bounds, a **`basis`** (`assumed` | `observed` | `user`), and a mandatory **rationale** text when `basis = assumed`. The specification is fingerprinted **before** any run.
* Factors (all through existing scenario inputs or the `advanced` merge; **no change to simulation physics**): global and per-approach demand scale, turning-share shift, vehicle-mix shift, IDM time-headway scale, desired-speed scale, maximum-acceleration scale. The engine has **no explicit reaction delay**; headway scale is a *proxy* for driver behaviour and is labelled so.
* A perturbed scenario that fails validation is **rejected and counted**, never repaired (a mix is never rescaled).
* **All factor distributions are assumptions of the analyst.** They are not estimates from data unless `basis = observed` and an observation record (§8) is attached, and even then only for the compared quantities.

### 5.2 Conditions, replications and runs (kept separate everywhere)

| Term | Definition | Appears as |
| --- | --- | --- |
| **Sampled condition** | One draw of all factors from the specification (Latin-hypercube stratified; seeded) | **N conditions** |
| **Replication** | An independent engine seed on the same condition | **r replications** |
| **Run** | One simulation: (condition, alternative, replication) | **Total runs = N × alternatives × r** |

**The unit of inference is the condition**, not the run. Within a condition, the replications of an alternative are averaged into one outcome *Y(i, a)* for condition *i* and alternative *a*. Replications reduce stochastic noise **within** a condition; they do **not** add conditions. Statements about uncertainty in demand or driver behaviour therefore have an effective sample size of **N_valid conditions** (§5.6) — **never** the number of runs. A UI or slide that shows "600 runs" must show "100 conditions × 3 alternatives × 2 replications" beside it.

### 5.3 Paired comparison (common random numbers)

For every condition *i* and replication *k*, **all alternatives use the same sampled scenario and the same engine seed** (they differ only in control). The paired difference against the baseline is *D(i, a) = Y(i, a) − Y(i, baseline)* on the **pre-declared primary indicator** (default: mean delay after warm-up; lower is better). Secondary indicators are reported but **eligibility and headline statements use the primary indicator only** (no indicator shopping).

### 5.4 Win / tie / loss

With the pre-declared **tie tolerance τ** for the primary indicator (default: the existing tolerance in `study/tolerances.py` unless the specification overrides it before the run):

* **win** (alternative better than baseline) if *D < −τ*; **loss** if *D > +τ*; **tie** otherwise.
* Reported per alternative as **P(win), P(tie), P(loss)** across valid conditions with **95 % Wilson intervals**, plus the median, mean and 5th/95th percentiles of *D* with **bootstrap 95 % intervals** (conditions resampled; seeded). The intervals treat conditions as exchangeable draws; with Latin-hypercube stratification they are approximate and slightly conservative, and the viewer says so.
* A **tie** is a result, not a missing value; it is inside every denominator.
* No p-value ranking and no "winner": with K alternatives the K−1 comparisons against the baseline are descriptive.

### 5.5 Regret, preference share and flip point

* **Regret** of alternative *a* in condition *i*: *Y(i, a) − min over alternatives of Y(i, ·)* (≥ 0, in indicator units). Reported: **mean regret** and the **95th percentile** of regret (the sample maximum is shown only as "sample maximum", since it depends on N). Regret depends on the alternative set; the set is displayed with it.
* **Preference share:** the fraction of valid conditions in which *a* is within τ of the best alternative. Shares may sum to more than 100 % and are described as "not ranked".
* **Preference flip point** (descriptive, one factor at a time): split valid conditions into 5 equal-count strata on factor *f*; compute P(win) per stratum with Wilson intervals. A **flip** is reported between adjacent strata when their majority class differs **and** their P(win) intervals do not overlap, and each stratum has ≥ 10 conditions. The result is the *stratum boundary range*, not a point estimate. If the conditions are not met, the output is "no flip detected in the sampled range" or "too few conditions to assess" — never silence. Interactions between factors are **not** resolved and the text says so.
* **Sensitivity:** Spearman rank correlation between each factor and *D*, with Fisher-z intervals; described as monotonic association, not causation; no significance claims across factors.

### 5.6 Missing, invalid and inconclusive runs

| Case | Handling |
| --- | --- |
| Condition fails validation | **Excluded** and counted by reason; never repaired |
| A run fails or times out | The **whole condition is excluded for every alternative** (pairing preserved) and counted |
| `vehicleLimitReached`, deadlock flag or non-finite metric | Condition excluded for every alternative; counted |
| Tie | Kept (§5.4) |
| Experiment cancelled or incomplete | Result is labelled **incomplete**, shows N_valid so far, and is **never eligible**; *resume* must regenerate the identical conditions (task fingerprint) |
| Exclusions | Reported by reason and by factor stratum; **N_valid = N − excluded**. If excluded > 10 % of N, or > 20 % in any factor stratum, the result is **not eligible** |

### 5.7 Minimum sample guidance and eligibility to be called "robust"

There is **no universal sufficient N**; 100 is not automatically enough. The rules below are checks, computed and displayed:

* **Below 30 valid conditions:** *exploratory only*; no robustness statement of any kind.
* **30 and above, but any eligibility criterion unmet:** *indicative*.
* **Eligible for robustness statements** requires **all** of:
  1. **Precision:** the 95 % Wilson half-width of each reported P(win)/P(loss) for the primary comparison ≤ 0.10 (worst case this needs about 97 valid conditions; fewer suffice when proportions are extreme, more when they are not — N is *derived*, not fixed).
  2. **Stability (split-half):** over 20 random splits of valid conditions into halves, in ≥ 90 % of splits the half-estimates of each P(win)/P(loss) differ by less than the full-sample half-width and the class of the median *D* agrees.
  3. **Replications:** r ≥ 2 per condition, so within-condition noise can be estimated; the **variance split** (between conditions vs within conditions) is reported.
  4. **Exclusions** within §5.6 limits.
  5. **Pre-declaration:** specification, primary indicator and τ fingerprinted before the run.
* **Meaning of "eligible":** the *evidence statement* is adequately sampled **for the declared assumptions**. It does **not** mean the preference is large, that the model is correct, or that any real junction behaves this way.
* **Real-world validity is shown separately** on every result, with exactly one of: *None — assumptions only*; or *Partial — see observation record*, with the quantities compared. In V3.0 the default and expected value is *None*.

### 5.8 Required output (what the API, viewer and package must carry)

Specification and its fingerprint · assumptions with `basis` and rationale · **N conditions, r replications, total runs** (separately) · N_valid and exclusions by reason · primary indicator, τ · P(win/tie/loss) with intervals · distribution of *D* with intervals · regret · preference share · flip result · sensitivity · convergence/stability result · variance split · eligibility checklist with each criterion's pass/fail · *real-world validity* line · limitations · the reproducibility manifest (§6).

---

## 6. Reproducibility manifest and replay classes (normative)

Every experiment result, and every `.ufpkg`, carries an **`urbanflow-experiment-manifest`** (v1):

| Group | Fields |
| --- | --- |
| **Source** | repository, commit hash, **dirty flag** (a dirty tree is recorded and makes exact replay *unverifiable*), simulator version and engine/schema versions |
| **Inputs** | scenario fingerprint; specification fingerprint; alternatives and their patch fingerprints; vehicle mix and base demand; factor distributions with `basis` |
| **Randomness** | base seed; sampling seed; sampling method and ordering; the **deterministic rule** deriving each engine seed from (base seed, condition index, replication); common-random-number policy |
| **Simulation settings** | time step; duration; warm-up; replications; vehicle limit |
| **Runtime** | Python version and implementation; operating system and CPU architecture; **pinned dependency versions** (and a hash of the lock/requirements file); relevant environment variables (e.g. `PYTHONHASHSEED`, `STUDY_WORKERS`) |
| **Execution** | worker count; pool type; wall time; host description (recorded for diagnosis; **not** expected to change results — the aggregation must sort by task id so completion order cannot) |
| **Outputs** | result fingerprint (canonical JSON of the results, excluding timestamps); exclusions summary; checksums of every file in a package |
| **Tolerances and caveats** | `exactFields` (fingerprints); `comparableTolerances` (§ below); **known nondeterminism**: cross-platform and cross-Python floating-point differences, dependency upgrades, any module that iterates unordered sets; creation time (outside the fingerprint) |

**Two replay classes — never confused:**

| Class | Condition | Pass rule | Reported as |
| --- | --- | --- | --- |
| **Exact replay** | Same source revision (clean), same Python minor version and dependency pins, same OS/CPU class, same fingerprints and seeds | **Result fingerprint identical** | `exact` |
| **Statistically comparable rerun** | Anything else (different revision, runtime or seeds) | Each reported proportion within the *larger* of the two Wilson half-widths; mean-difference intervals overlap; eligibility class unchanged | `comparable` — **explicitly not exact** |
| Neither | Otherwise | — | `differs (engine or runtime changed)` |

Verification tooling reports which class applied and why.

---

## 7. Developer platform — minimum requirements (normative)

**Out of scope, permanently for V3.0:** arbitrary code upload, remote code execution, webhooks.

| Area | Minimum requirement |
| --- | --- |
| **Personal access tokens (PATs)** | Created only in an authenticated browser session (a PAT cannot create a PAT); 256-bit random secret shown **once**; only a **SHA-256 hash** and a short id stored; **scopes** `experiments:read`, `experiments:run`, `packages:read`, `packages:write` (no admin scope exists for PATs); **mandatory expiry** (default 30 days, maximum 90); **immediate revocation** (checked on every request); at most 10 active tokens per user; last-used time; tokens accepted only in the `Authorization` header, never in URLs; redacted from logs; invalid-token attempts count against the rate limit |
| **Quotas** | Per user: concurrent experiments (default 2), simulations per experiment by preset, simulated-seconds per day, request body ≤ 1 MB, package ≤ 10 MB, requests per minute per token. **Enforced at submission** (rejected with 429/413/422 naming the quota) **and during execution**; reported by `GET /api/v3/capabilities`. Enforcement is in-process (single uvicorn process); a shared store is required before scaling out — recorded as a limitation |
| **Auditability** | Append-only audit table: token created / revoked / used-first-time-from-new-address, experiment submitted / denied / cancelled / deleted, with user id, token id, kind, counts and reason — **no payloads, no secrets** |
| **Ownership and access** | Every v3 resource has an owner; default **private**; another user's id is **404**; no admin PAT; support access requires a separate, audited administrative path; users can **delete** their resources; retention documented |
| **`.ufpkg` format** | A zip with a manifest (§6). **Import validation:** size and entry-count limits; **zip-slip / path-traversal rejected**; filename allow-list; every JSON file validated against its schema with `extra="forbid"`; per-file SHA-256 checked against the manifest; **format and version compatibility** (readers accept versions ≤ their own; unknown major rejected; unknown minor accepted with a warning); mandatory provenance fields; **nothing in a package is ever executed**. **Integrity is not authenticity:** checksums show a package is internally consistent, not who made it; signing is out of scope and the verifier says so |
| **Signal-policy interface** (applies to the strategy registry, §13.6; the `mlp-v1` learned-policy type is deferred, §9.1) | A policy is **data** for a built-in model type (for example a bounded fully-connected network `mlp-v1` described by JSON weights), or a **built-in code policy that was added to the repository by reviewed pull request**. External users **cannot upload code**; no `pickle`, `eval` or `exec`; weight files are size- and shape-bounded; inference is deterministic. A server-side **safety shell** owns lamp colours and enforces legal phase order, minimum green, yellow, all-red and maximum green; illegal requests are clamped and counted (`policyViolations`) |
| **Compatibility** | `/api/v1` and `/api/v2` are frozen (additive-only). New work lives under `/api/v3`; documents keep `format` + integer `version` + `extra="forbid"`; OpenAPI is snapshotted and checked by a contract test |

---

## 8. Calibration terminology (normative)

Four distinct things; documents and screens use exactly these words.

| Level | Name | Meaning | State in the repository |
| :-: | --- | --- | --- |
| 0 | **Calibration framework availability** | Software exists that can compare a simulation with supplied observations (V1.8 `/api/v2/calibration`) | **Exists** (audit A-20) |
| 1 | **Validation against supplied observations** | The framework was run on actual observations and the agreement for the *compared quantities* was reported | **No real observations have been run** (audit A-22) |
| 2 | **Parameter calibration / tuning** | Model parameters are searched or fitted to improve agreement | **Not implemented** (`options.tune`, audit A-21). The "demand fit" is *input assimilation*: it writes observed flows into the scenario and flags those rows `inputWasFitted` |
| 3 | **Calibration against real-world field data** | Levels 1 and 2 on documented, provenance-checked field data | **None. Not claimable.** |

Rules: an API's existence is level 0 only. The word **"calibrated"** is never used for UrbanFlow results in V3.0 except in the existing, narrow phrase *"engine capacity calibration"* (UrbanFlow's own one-lane capacity curve, `study/calibration.py`), which is explained wherever it appears. V3.0 priors are **assumptions** (§5.1).

---

## 9. The other capabilities

### 9.1 Control Lab → superseded by the strategy registry (§13) and the Discovery Lab (§15.2)

The revision-2 "Control Lab" (signal-policy interface, Webster-tuned and max-pressure baselines, optional DQN) is **absorbed**: the *safe strategy interface* is delivered by the registry in W3 (issue #156); *paired held-out evaluation* is delivered by the Discovery Lab in W6 (issue #157). Webster-tuned fixed-time and max-pressure baselines are an **optional extension** of the Discovery Lab's baseline set (not funded). The **learned (DQN / RL) policy remains deferred**: if ever built it enters through the registry as an `experimental` policy type, is evaluated on disjoint seeds, is labelled EXPERIMENTAL, and a null result is valid. Safety acceptance for any externally supplied policy parameters: a random-action fuzz of ≥ 10,000 decisions over 10 seeds produces zero conflicting greens and zero collisions, and every clamp is counted (carried forward from revision 2).

### 9.2 Emergency pre-emption and priority-aware control (conditional, readiness gate G-E)

Considered only if **all** hold at a gate the PO calls: (1) core gates passed; (2) at least **4.5 ED** are unallocated *after* the contingency reserve; (3) an approved design note defines the absent-block bit-identity test (no `emergency` block ⇒ every pre-existing determinism and reproduction test passes unmodified) and the safety tests (pre-emption during yellow/all-red, simultaneous requests, request storm, cancelled request, randomised-arrival fuzz with zero conflicting greens and zero collisions); (4) the PO approves. **On the revised capacity plan this gate is expected to fail** (every Phase B week is allocated; contingency is 7.75 ED only if conditional items are dropped), which defers the work (and bus/emergency priority control, §13.5) to a post-3.0 release, to be recorded by the owner in `ROADMAP.md` / Future Scope. Surrounding-traffic yielding is out of scope regardless. Simulated emergency response times, if ever produced, are model outputs, not predictions.

### 9.3 CSV / GeoJSON

Conditional on capacity freed by dropping rank 8 (Chaos/Breakpoint). Order of intake: CSV turning counts → `urbanflow-observations` (strict format, line-numbered errors); GeoJSON export of results; arms-GeoJSON → draft scenario via the existing `assign_slots` (only if time remains). Importing counts is **level-0 plumbing** in the §8 sense; it does not make anything calibrated.

### 9.4 Mobile

No native app and no offline PWA. The real need — *"is my long job finished and what did it find?"* — is met by **responsive read-only status and results pages**, checked at 375 px as part of the viewer's acceptance (W9). An installable manifest is a stretch and unfunded; push notifications wait for webhooks, which are out of scope.

---

## 10. Feature boundaries

**Committed (core release):** V2.0 closure first · Robustness Lab (§5) · Signalised roundabouts + strategy registry/compatibility (§13) · High-aggression default (§14) · AI Traffic Experiment Copilot (§15.1; AI claim conditional on D-AI1) · AI Control Strategy Discovery Lab (§15.2) · experiment portability and the minimum developer platform (§6, §7).
**Conditional:** Adaptive signalised roundabout (gate G-SR) · Traffic Chaos and Stress-Test Lab and Strategy Breakpoint Explorer (gate G-W8; stationary-demand stress only unless a demand-profile capability is approved) · CSV import and GeoJSON export (only with freed capacity).
**Not funded (expected to defer):** emergency pre-emption and bus/emergency priority control (G-E).
**Deferred (stated, not hidden):** learned (DQN/RL) controllers · Strategy DNA *visual* composer (a read-only strategy summary card ships with the registry) · Traffic Regime Discovery · Incident and recovery experiments · AI Research Report Generator (the copilot's grounded summary ships; a full structured report does not) · full explainable-comparison UI (controllers record decision events; the comparison UI is deferred) · PWA · parameter tuning and any calibration claim · multi-junction simulation and network visualisation · surrounding-traffic yielding · weather as a modelled effect · V2V, platooning, autonomous intersections · digital twin · webhooks · embeddable widgets · organisation sharing · native mobile · absolute emissions.

## 11. Main risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| V2.0 closure overruns (≈ 7–8 ED estimate, 97 % loaded) | Phase B starts late; every date shifts one-for-one | Gate-slip rule in the sprint plan; the preview is defined so it succeeds on V2.0 alone |
| **Scope exceeds capacity** (revision 3 is ≈ 2× the original calendar) | Quality drops or dates slip | Extended calendar (to 7 Jan); explicit conditional items; scope-reduction ladder (sprint plan §7); PO decision D-SCOPE |
| Signalised-roundabout deadlock/collision | Credibility; flagship feature unusable | `metered_entry` mode keeps all gap-acceptance logic (cannot be less safe at the conflict zone than the baseline); entry-gate seam is bit-identical when absent; collision/deadlock/starvation/spillback regression before the gate G-SR |
| New aggression parameter changes old results | Broken reproduction of V2.0 studies | Absent field ⇒ `standard` profile (today's parameters); default applies only at authoring boundaries (§14.3); fingerprint includes the profile |
| LLM quality, cost, injection or key leakage | Wrong proposals; unexpected spend; data exposure | Proposal-only; deterministic validation boundary; quotas and token caps; provider off by default; adversarial test set; fallback (§15.1) |
| Discovery search overfits the simulator | False confidence in a candidate | Disjoint tuning / selection / held-out seeds; unseen demand and mix conditions; null result valid; EXPERIMENTAL label |
| Statistical code is wrong | False confidence | Contract-based tests with hand-computed values; a planted-flip stub; split-half checks |
| Single-engineer review bottleneck | Quality drops | ≤ 88 % planned load; one integration owner; hard freezes; the 85 % plan carries 7.75 ED of removable conditional work |
| Holiday period 25 Dec – 1 Jan (R-HOL) | W8/W9 slip by about a week | Showcase date is conditional; W8 is the first item dropped |
| External access widens the attack surface | Data exposure | Phase A security rows first; §7 minimums; no code upload, no webhooks; AI keys server-side only |
| Engine lacks time-varying demand (verified) | "Surge" stress scenarios not possible | Chaos Lab v1 uses stationary extremes; a demand-profile capability is a separate, approved engine change (§16) |

## 12. Decisions requiring the product owner

| # | Decision | Recommendation | Schedule impact |
| --- | --- | --- | --- |
| D1 | Approve the ranking and funding table (§2) | Approve | Defines Phase B |
| **D-SCOPE** | Choose the delivery option: **E** (extended to 7 Jan 2027, all committed weeks; 26 Nov becomes an *interim* presentation) or **S** (26 Nov final, W1–W4 only, no AI feature) | **E** | Defines the calendar and what "V3.0" means |
| D2 | NumPy: **not required** by this plan (evolutionary search and statistics are pure Python). Add only if Bayesian/surrogate search or an array-based policy is later approved | Defer | None |
| D3 | `/api/v3` namespace, PAT design (§7), no code upload, no webhooks | Approve | Defines W7 |
| D4 | One supported Python version across local, CI and Docker (today 3.14.7 locally, 3.11 in CI and Docker) | 3.11 unless there is a reason | Affects exact-replay claims |
| D5 | Approve the statistical contract (§5) and manifest (§6) | Approve **before** Phase B starts (G-D) | Blocks W1 if late |
| D6 | Confirm capacity (§3) or supply names and hours; confirm holiday availability 25 Dec – 1 Jan | Confirm | All dates |
| D7 | Authorise edits to `ROADMAP.md` (V2.0 statuses now; V3.0 section after approval) | Approve | Blocks audit R4.2 |
| D8 | Emergency pre-emption and priority control: accept deferral past V3.0 | Accept | Frees ≈ 4.5 ED of nominal capacity |
| **D-AI1** | **LLM provider, budget and data handling for the Copilot (§15.1.6).** Options: (a) none — Copilot ships as the deterministic assistant and is **not counted as an AI feature**; (b) hosted API with a hard monthly cap and server-side key; (c) self-hosted open-weight model. No paid dependency is adopted without this decision | (b) with a hard cap, behind a provider-agnostic adapter | AI claim in W5 depends on it; must be decided before W5 (Fri 27 Nov) |
| **D-AG1** | High-aggression semantics (§14.3): new field `traffic.driverAggression`; absent ⇒ `standard`; default `high` written at authoring boundaries only | Approve | Defines W4 and V2.0 compatibility |
| **D-AG2** | Whether `High` also implies the existing `aggressiveTwoWheelers` flag (recommended: **no**, separate flags, documented) | No | W4 |
| **D-SR1** | Signalised-roundabout scope: `metered_entry` mode is the committed v1; `phased_priority` (circulating-priority suspension) is conditional/stretch (§13.3) | Approve | W2 |
| D-PV | Preview option (sprint plan §5.2) | PV-1 | Preview content |

---

## 13. Composable Traffic-Control Strategies (flagship simulation initiative)

### 13.1 Problem and today's state (verified in the repository, 2026-10-12)

UrbanFlow offers three isolated choices: a fixed-time signal, an adaptive signal and a conventional roundabout. They are selected by `geometry.intersectionType ∈ {fixed_time_signal, roundabout}` and `controller.signalControl ∈ {fixed_time, adaptive}` (`core/config_models.py`, `controllers/factory.py`). The combination *adaptive + roundabout* is explicitly **rejected** by validation (`core/config_validation.py`, adaptive "applies to a signalised junction"). `RoundaboutController` (≈ 1,250 lines of gap-acceptance, exit-yield, keep-clear and queue-spillback logic) and `FixedTimeSignalController` (phase sequences, yellow/all-red, stop-line `VirtualObstacle`s) share only the `BaseController` interface (`update`, `get_state`, `reset`). Conflict-point and PET safety metrics are **gated off for roundabouts** (curved connection lanes make the straight-chord conflict points invalid). The signalised-roundabout concept therefore **does not exist** in the code; planning documents that mention it describe intent only.

### 13.2 Layered model (behavioural contracts first, no class mixing)

A **strategy** is a declarative composition of six layers. Each layer has a contract; combinations are checked against the contracts *before* any simulation object is built.

| Layer | Question it answers | Exists today? | Contract (summary) |
| --- | --- | :-: | --- |
| 1. **Geometry** | Arms, lanes, ring, lengths | Yes (`roads/`, `geometry` config) | Validated by existing lane/geometry validators |
| 2. **Movement topology** | Which movements exist and where they conflict | Partly: `RoadNetwork` connections; conflict points for signals; zone model inside the roundabout controller | Exposes `movements()` and `conflicts(m1, m2)`; roundabout conflicts are *zone-based*, signal conflicts *point-based* — the contract hides which |
| 3. **Right-of-way rule** | Who yields to whom | Implicit in each controller | Explicit enum: `signal`, `yield_to_ring`, `signal_over_yield` (new) |
| 4. **Control policy** | How signals/meters are timed | Fixed-time plan; adaptive extension | `phase_plan` (sets of movements, min/max green, yellow, all-red) or `metering` |
| 5. **Adaptation logic** | Detection and thresholds | `controllers/signal_detection.py`, adaptive controller | Declares inputs (detectors, queue thresholds) and bounds; deterministic given the seed |
| 6. **Priority overlay** | Bus/emergency | No | **Deferred** (§9.2); layer reserved |

A **strategy descriptor** (`urbanflow-strategy` v1, `extra="forbid"`) records `id`, `version`, `status` (`stable` | `experimental`), the six layer selections, a parameter schema with bounds, declared invariants and a `fingerprint`.

### 13.3 Signalised roundabouts (committed flagship)

**User problem.** Roundabouts handle moderate demand well but can lock up or starve one arm under heavily uneven or near-saturated demand; fixed-time signals handle uneven demand through green splits but waste capacity at low demand. Signalised roundabouts (signals on selected entries) are used in practice to meter flow; planners cannot currently test them.

**Two right-of-way modes — the safety argument is the design.**

| Mode | Behaviour | Status | Safety reasoning |
| --- | --- | --- | --- |
| **`metered_entry`** (v1, committed) | A signal at a chosen entry's stop line decides *whether a vehicle may proceed to the yield line*. When green, the **existing roundabout gap-acceptance, exit-yield and keep-clear logic still applies unchanged**. Red can only *remove* entry opportunities | Committed (W2) | At the conflict zone it can never be less safe than the conventional roundabout, because signal states only restrict what the unchanged logic already allows; collision tests must show no increase over the baseline |
| **`phased_priority`** (conditional) | Signals also suspend circulating priority for phases (full or partial signalisation); the ring is cleared by phase plan | Conditional / stretch; requires its own movement-conflict contract and a ring-clearance proof | Genuinely new right-of-way rules; needs the layer-2 conflict contract first; **not** in the committed scope |

**Architecture.** A new `SignalisedRoundaboutController` is built by **composition**: it owns a `RoundaboutController` and a phase engine reusing the existing `Phase` structure, and connects them through one narrow seam — an `EntryGate` protocol (`allows(approach, lane, now) -> GateDecision`) consulted by the roundabout controller where it decides whether a head vehicle may proceed. The default gate is `AlwaysOpen`; **a test proves the conventional roundabout is bit-identical** (same metrics fingerprint, same snapshots) with `AlwaysOpen`. The gate returns a *decision with reason* (`red`, `yellow`, `ring_spillback_hold`, `queue_cap`), which the controller records as **decision events** (supporting explainability, candidate 6). No `isinstance` ladders and no multiple inheritance.

**Phase plans.** Entries are grouped into phases (e.g. N+S together, then E+W; or each entry in turn for a four-phase plan); each phase has minimum green, yellow, all-red and a maximum green; the plan is validated (every metered entry appears in at least one phase; no entry has zero green; cycle ≥ sum of minimums). **Queue-aware entry control:** an optional guard holds red on an upstream entry when the ring or the downstream exit queue exceeds a declared spillback threshold (ring storage is finite), and an optional per-entry queue cap shortens red for a long queue within bounds.

**Required tests (regression, extend the slow CI jobs):** collision count = 0 (`VehiclePool.collision_count`) across a seed × demand matrix; no deadlock (existing deadlock detector extended to the new controller); **starvation:** no metered entry waits longer than `maxRed + yellow + allRed` (property test); **spillback:** ring-blocking events do not exceed the baseline; **throughput:** at low demand, mean delay is not worse than the conventional roundabout by more than a declared tolerance (a *finding*, reported, not hidden if it fails); **equivalence:** `AlwaysOpen` gate ≡ conventional roundabout; **layouts:** 3-arm (`arms`), 4-arm, 1–3 ring lanes, multi-lane approaches. Baselines compared through the paired-comparison machinery: conventional roundabout, fixed-time signalised intersection, adaptive signalised intersection.

**Benchmarks:** runtime and memory per simulated second against the conventional roundabout (target: ≤ 1.3× runtime — an unverified target to be measured in W2).

**Limitations stated with the feature:** signal-timing literature values are *not* used as calibration; no claim that signalised roundabouts are better or safer in the real world; safety proxies for roundabouts are limited to collisions, hard-braking events and zone-based conflicts (PET remains unavailable until the conflict contract of layer 2 supports curved paths).

### 13.4 Adaptive signalised roundabouts (conditional on gate G-SR)

Adaptive entry control reuses `signal_detection.py` and the adaptive controller's extension logic: demand-responsive green extension/termination per entry within hard bounds (min/max green), queue detectors with threshold hysteresis. Delivered *through the registry* in W3 to prove composition works. **Stability and oscillation tests:** no phase flapping (minimum-green respected 100 %, phase-change rate bounded under constant demand), bounded green-time variance; performance compared across low, medium and saturated demand against `metered_entry` fixed-plan and the conventional roundabout. If gate G-SR (signalised-roundabout safety and equivalence tests green, Thu 12 Nov) fails, the 1.5 ED returns to fixing the flagship feature.

### 13.5 Hybrid and unconventional combinations (investigated; most are not committed)

| Combination | Status | Why |
| --- | --- | --- |
| Signal-controlled approaches feeding a roundabout (different valid policy per approach) | **Supported by design:** per-entry policy in the descriptor (`metered` / `open`); validated per entry | Falls out of the layered model |
| Entry metering + upstream signal coordination | **Deferred** | Requires multi-junction simulation (audit A-31: networks are representation-only) |
| Priority-aware (bus/emergency) control | **Deferred** (§9.2) | Reproduction-critical code; ≈ 4.5 ED |
| Multi-objective control (delay vs spillback) | **Delivered through the Discovery Lab** (§15.2) as the search objective, not as a separate controller | Avoids a bespoke controller |
| Experimental strategies proposed by the Discovery Lab | **Delivered as `experimental` descriptors** | Search produces parameter sets of registered strategies only |

### 13.6 Registry, compatibility validation, fingerprints (committed, W3)

* **Registry:** built-in strategies register at import; each descriptor passes a self-check. **No uploaded code** (§7); new strategies enter only through reviewed pull requests (this is the safe strategy/plugin interface, issue #156).
* **Compatibility validation:** a rule table over layer selections rejects physically invalid or contradictory combinations *before execution* with a coded, human-readable message and, where possible, a suggestion (e.g. `adaptive` + `phased_priority` ⇒ "not supported: adaptive detectors assume a fixed-time phase plan; use metered_entry"). The existing error `adaptive applies to a signalised junction` is superseded by the registry's explanation. Every rejection has a unit test.
* **Fingerprints:** the existing three strategies map to the registry **without changing any existing scenario fingerprint or result fingerprint** (test: every existing fixture scenario fingerprints identically before and after). New strategies' fingerprints include the descriptor `id`, `version` and resolved parameters. Aggression profile (§14) and strategy are independent fingerprint components.
* **Read-only strategy summary card** (a textual "Strategy DNA" of the six layers) ships with the registry; the *visual composer* (candidate 2) is deferred.

---

## 14. High driver aggression as the default for new scenarios

### 14.1 Verified state

There is **no driver-aggression setting** in the product today. What exists:

| Mechanism | Where | Default | What it does |
| --- | --- | --- | --- |
| `traffic.aggressiveTwoWheelers` (bool) | `config_models.py`, `vehicles/lane_change.py`, UI toggle in `ScenarioSetup.tsx` | `false` (schema, `frontend/src/types/config.ts` ×4 presets) | Lane-change only: min gap 0.2 m, safe-deceleration 8, politeness 0, threshold 0.05, end-margin 1.0, cooldown 0.2 s — and only when `unstructuredTraffic` is also on |
| `traffic.unstructuredTraffic` (bool) | `engine.py`, `stochastic_idm.py` | `false` | Swaps in `StochasticIDM`: per-tick random "aggression" ∈ [0.5, 1.5] that halves or ×1.5 the minimum gap and time headway, plus random hesitation and nudge-forward; enables the deadlock detector |
| Vehicle-class parameters | `vehicles/vehicle_types.py` | per class (car: T = 1.5 s, s₀ = 2.0 m, a = 2.0 m/s², politeness 0.3; desired-speed factor range per class) | The car-following and lane-change base values |
| Global IDM overrides | `vehicleGeneration` (`maxAcceleration`, `comfortDeceleration`, `desiredTimeHeadway`, `minimumGap`, `idmDelta`) | 2.0 / 3.0 / 1.5 / 2.0 / 4.0 | Used by `engine.py` for the shared IDM |
| Roundabout safety constants | `controllers/roundabout.py` (`_EXIT_SAFETY_HEADWAY` = 1.0 s, `_EXIT_COMMIT_MARGIN`, …) | fixed constants | Gap acceptance/exit-yield margins; **not configurable today** |

So **"High aggression by default" is a new feature**: a named, parameterised, versioned behavioural profile, with a defined meaning, a default at authoring boundaries, and tests. It is not a flag flip, and it must not silently duplicate or contradict the two existing flags.

### 14.2 Definition: parameters that actually control the intended behaviour

Aggression is a **profile** `traffic.driverAggression ∈ {standard, moderate, high}` (`standard` = today's behaviour bit-for-bit). A profile is a set of *multipliers/offsets applied on top of each vehicle class's base values* — never a replacement of unrelated IDM parameters. Candidate levers, with the reason each is included (starting values are **proposed**; the design spike AG-1 fixes them by sensitivity analysis and records the evidence):

| Lever | Why it is a genuine aggression lever | `high` starting value (proposed) |
| --- | --- | --- |
| IDM desired time headway **T** | Directly sets following distance at speed; dominant effect on saturation flow | × 0.7 (car: 1.5 → ≈ 1.05 s) |
| IDM minimum gap **s₀** | Standstill/queue spacing; affects queue length and discharge | × 0.75 (car: 2.0 → 1.5 m) |
| IDM max acceleration **a** | Launch from the stop line | × 1.15 |
| Desired-speed factor (relative to limit) | Speed choice; bounded so vehicles do not exceed a declared ceiling | + 0.05 of the class range, ceiling 1.10 × limit |
| Lane-change gap/politeness/threshold | Willingness to change lanes with small gaps | politeness × 0.5; acceptance threshold × 0.5; **safe deceleration unchanged** (so the safety criterion is not simply switched off) |
| Roundabout critical gap (entry/exit yield margins) | The decisive driver-behaviour parameter at a roundabout; currently hard-coded | **Parametrised only if AG-1 shows it is the dominant lever;** proposed `_EXIT_SAFETY_HEADWAY` × 0.7. Changing it is a physics-adjacent change recorded in an ADR |
| Comfort deceleration **b**, IDM δ | **Not changed** — b only enters the braking interaction term, δ the free-road acceleration shape; altering them would conflate aggression with vehicle dynamics | unchanged |

`high` must keep every parameter inside the validated ranges of `config_validation` and must not make IDM unstable (T and s₀ stay > 0 by the model's own guard). `unstructuredTraffic` (random per-tick noise) stays a **separate** flag: aggression is a *systematic profile*, unstructured traffic is *random noise*; both can be on. `aggressiveTwoWheelers` stays separate (decision D-AG2).

**Observable behaviour (the acceptance language):** mean time headway and mean standstill gap in queues; saturation flow at the stop line; lane-change rate; accepted critical gap at roundabout entries; hard-braking events per 1,000 vehicles; conflict counts where the metric exists; collision count; throughput; queue length; delay. `high` must produce measurably shorter headways and higher saturation flow than `standard` (a directional test with a declared minimum effect), and `standard` must reproduce current fingerprints exactly.

### 14.3 Default semantics — protecting reproducibility and the frozen APIs

| Boundary | Rule |
| --- | --- |
| Stored configs, `/api/v1`, `/api/v2` (frozen, additive-only), existing scenario fixtures, V2.0 reports | **Absent `driverAggression` ⇒ `standard`**. No stored scenario changes meaning; existing fingerprints are unchanged (test) |
| New-scenario **authoring** boundaries: UI new-scenario defaults and the three presets, scenario builders, the Python client's scenario helper, `/api/v3` experiment specifications, Copilot proposals, `.ufpkg` creation | **Write `driverAggression: "high"` explicitly** into the saved configuration (so the value is always visible and fingerprinted) |
| Explicit user choice (any boundary) | **Always preserved**; an explicit `standard` is never overwritten |
| Fingerprint and manifest | `driverAggression` (and the resolved parameter set's hash) is a **fingerprint component** and is recorded in the manifest's assumptions block; `.ufpkg` verify checks it |
| Documentation and UI | Labelled **"driver aggression — a simulation assumption, not a measurement of real-world driver behaviour"** wherever shown; V3.0 results under `high` are not comparable to V2.0 reports unless the profile is stated |

### 14.4 Required tests

Defaults at every authoring boundary (UI, presets, builder, SDK, `/api/v3`, Copilot, package) · overrides preserved · absent ⇒ `standard` with unchanged fingerprints on a fixture corpus · serialisation round trip (JSON Schema, TypeScript types, `.ufpkg`) · determinism (same spec + seed ⇒ identical result fingerprint under each profile) · **interaction matrix:** profile (3) × vehicle class mix (car-only, mixed, heavy-vehicle-dominated) × strategy (fixed-time, adaptive, roundabout, signalised roundabout) × density (low, medium, saturated): assert collisions = 0, no deadlock, spillback and throughput **reported against `standard`** with the directional expectations above; unexpected directions are findings, not hidden · schema-consistency test that mirrors the shared schema, backend model and frontend types.

---

## 15. AI features

Two substantive AI features are core V3.0 deliverables. They are *different in kind*, and the strategy is explicit about what each is.

| | **A. AI Traffic Experiment Copilot** | **B. AI Control Strategy Discovery Lab** |
| --- | --- | --- |
| Kind | Language-model-assisted **proposal and interpretation** (generative, schema-constrained) | **Bounded multi-objective evolutionary search** over registered strategies (optimisation; **not** a learned model — described that way everywhere) |
| Needs a paid/external service? | Optionally (provider decision D-AI1); **core workflow works without it** | No; pure Python, runs on the existing task pool |
| Week | W5 (Fri 27 Nov – Thu 3 Dec) | W6 (Fri 4 – Thu 10 Dec) |
| Counts as an "AI feature" when | A provider is approved, connected, **and** passes the §15.1.7 evaluation | The search passes §15.2.8 (determinism, validity, hygiene, planted-optimum recovery); a null result on real regimes does not fail it |

**Common rules for both.** AI output is a *proposal* or *interpretation*, never an executed experiment or a verified result. Every generated configuration passes the **deterministic backend schema and rules** (`extra="forbid"` models, existing config validators, the strategy compatibility validator, quota estimator). A model or search procedure **cannot** alter simulation state except through those validated interfaces, cannot bypass authentication, quotas, input validation or execution limits, and cannot submit work without an explicit user confirmation (or, for the search, the user's explicit run request within a budget). Measured output and model-generated text are structurally separate in every API and screen.

### 15.1 AI Traffic Experiment Copilot

**15.1.1 User problem and expected value.** A planning officer cannot easily translate "compare a conventional roundabout, a signalised roundabout and an adaptive signal under highly aggressive driving and uneven peak-hour demand" into a valid, well-designed experiment (alternatives, demand ranges, aggression, replications, sensitivity factors), and cannot easily read the result. The Copilot reduces setup time and error, suggests the comparisons and checks a researcher would want, and explains results *without* inventing data.

**15.1.2 Architecture.**

```
research question (free text, ≤ 2,000 chars) ──► Proposer ──► ExperimentProposal (JSON)
                                         │                       │
                    deterministic proposer (always)         ▼ Validation boundary (deterministic)
                    LLM proposer (provider-gated)           schema · config validators · strategy compat · quota estimate
                                                                  │  issues → coded explanations + suggested valid alternatives
                                                                  ▼
                                   Inspect-and-confirm (UI diff, cost estimate, AI-flagged fields)
                                                                  │  user confirms (proposal id + hash must match)
                                                                  ▼
                                     ordinary /api/v3/experiments submit (auth, ownership, quotas, limits)
                                                                  ▼
                           measured result ──► Evidence object ──► Summariser (LLM or template)
                                                                  ▼ grounding check ──► "Model-generated interpretation" panel
```

* **Proposers.** (a) *Deterministic proposer* (baseline and fallback; explicitly **not** called AI): slot-filling from keywords/presets and a guided form that covers the same fields. (b) *LLM proposer*: a provider-agnostic adapter that receives the question plus the **capability catalogue** (registered strategies and parameter bounds, vehicle classes, aggression profiles, quota limits) and must return JSON matching the proposal schema. Provider selected by configuration `AI_PROVIDER` (default `none`).
* **Input/output contracts.** Input: question text, optional "start from" scenario id (must be owned by the caller). Output (`urbanflow-experiment-proposal` v1, `extra="forbid"`): scenario patch, alternatives (strategy descriptor ids + parameters), uncertainty specification (factors with `basis = assumed` and rationale), replications and seeds policy, primary indicator and tolerance τ, suggested sensitivity checks, `fieldProvenance` (each field `user` | `rule` | `model`), `assumptions[]`, `warnings[]`, `estimatedRuns`, `estimatedSeconds` (**unverified** label), `reproducibilityMetadata` (proposer id and version, provider and model identifier, prompt-template version, catalogue hash). `validated: bool` and `issues[]` are set by the backend, never by the model.
* **Invalid configurations.** Validator errors carry stable codes; the Copilot returns the code, a plain-language explanation, and one or more *deterministically computed* valid alternatives (e.g. nearest valid mix). A model may paraphrase an explanation but **may not repair silently**: a repaired proposal is a new proposal that is validated again (at most 2 repair attempts).
* **Interpretation.** The summariser input is the structured *evidence object* (the verified result JSON and its eligibility checklist); it returns text. A **grounding check** parses numerals and named entities from the text and verifies each appears in the evidence object; mandatory sections (eligibility class, N conditions / r replications / total runs separately, real-world-validity line, limitations, and **every unfavourable finding for the user's preferred alternative**) are inserted deterministically if the model omits them. Failure of the check suppresses the model text and shows the template summary.

**15.1.3 Failure and fallback.** Provider disabled, timing out (default 20 s), rate-limited, over budget, schema-invalid after two repairs, or grounding-failed ⇒ the UI says "AI assistance unavailable" and offers the deterministic proposer and template summary. **Core workflows (submit, inspect, compare, export) never depend on a model.**

**15.1.4 Security and cost controls.** Model input is untrusted text; the model has **no tools, no file or network access, no ability to call APIs**, and sees only its own question plus the capability catalogue and (for summaries) the evidence of the caller's own experiment. Provider key lives only server-side (secrets store; never in browser, logs, packages or the client). Per-user quotas: proposals/day, summaries/day, input and output token caps; global monthly spend cap with a kill switch; requests logged as metadata (user, provider, token counts, outcome code) — **no prompt or output payloads by default**. Prompt-injection tests (§15.1.7) are part of the suite. A proposal carries a short-lived id and content hash; confirm requires both and belongs to the creator (another user's id is 404).

**15.1.5 Evaluation set.** `copilot-eval-v1`: **40 research questions** authored and labelled before prompts are tuned — 30 in-scope (varied geometry, strategy, demand regime, aggression, vehicle mix, uncertainty ask), 5 ambiguous (must ask a clarifying question or state assumptions), 5 adversarial (prompt injection, requests for quota bypass or secrets, out-of-scope claims such as "prove strategy X is best"). 10 in-scope questions are **held out** and used once for the final measurement. Each in-scope item has an expert-labelled checklist (required alternatives, regime, aggression, replications ≥ 2, primary indicator, an appropriate sensitivity check).

**15.1.6 Baseline and provider decision.** Baseline: the deterministic proposer on the same set. **No paid or external service is adopted without decision D-AI1** (provider, price cap, data handling). If D-AI1 = *none* or the evaluation fails, the Copilot ships as the deterministic assistant, labelled as such, and the **AI claim for flagship A is not made** — the PO is told in the W5 gate that the AI-feature count for V3.0 is one (B).

**15.1.7 Measurable acceptance (proposed thresholds; PO to approve).**

| # | Criterion | Threshold |
| --- | --- | --- |
| C1 | Every proposal that becomes confirmable passed backend validation | 100 % (by construction; tested with invalid model stubs) |
| C2 | Raw model output valid against schema + rules on in-scope items (≤ 2 repairs) | ≥ 85 % of the 30 in-scope; the rest are surfaced as invalid with a coded explanation, never executed |
| C3 | Key-element recall against the expert checklist, **held-out 10** | ≥ 80 % **and** ≥ 15 percentage points above the deterministic baseline; otherwise the AI claim is withdrawn and the result reported |
| C4 | Adversarial items (5) | 0 cause an unvalidated submission, secret disclosure, quota bypass or a "proof of superiority" statement |
| C5 | Summary grounding on all evaluation experiments | 100 % of numerals trace to the evidence object; 100 % include eligibility class, N/r/total-runs line, validity line and limitations |
| C6 | Planted unfavourable result (the user's preferred alternative loses) | The loss appears in the summary in 100 % of trials |
| C7 | Fallback | With provider off or timed out, the full workflow completes using the deterministic proposer and template; UI states the mode |
| C8 | Cost controls | Per-user daily cap and global cap enforced (tests); p95 tokens/proposal ≤ the configured cap |
| C9 | Confirm step | A proposal cannot be submitted without confirm; the confirm token is single-use and bound to the user and content hash |

**15.1.8 Limitations and safe claims.** Allowed: "AI-assisted proposal — validated by the backend and confirmed by you"; "model-generated interpretation of the measured results shown". Not allowed: "AI-verified", "AI-optimised", any statement that the model ran or measured anything. A language model's reading of results can be wrong; the measured tables are the evidence. Proposal quality depends on the provider and on the catalogue, which is versioned in the metadata.

### 15.2 AI Control Strategy Discovery Lab

**15.2.1 User problem and expected value.** The valid combinations of geometry, signal plan, entry metering, adaptation thresholds and lane allocation are too many to try by hand. A researcher wants candidate strategies for a *stated traffic regime*, compared fairly against the standard baselines, with the conditions under which the preferred candidate changes — and a package that lets someone else repeat it.

**15.2.2 Approach (accurately named).** **Bounded multi-objective evolutionary search** (NSGA-II-style non-dominated sorting with crowding distance), implemented in pure Python on the existing process pool, over the **bounded parameter space of registered strategies** (§13). It is a black-box optimiser, not a learned model; surrogate-assisted/Bayesian variants need NumPy and are out of scope (D2). Rationale: discrete-and-continuous mixed space, noisy evaluations, multiple conflicting objectives, no gradients; evolutionary search is simple, reproducible and easy to bound.

**15.2.3 Search space (v1, bounded).** For a user-declared regime (arms, lanes per arm ≤ declared cap, demand level and split, vehicle mix, aggression profile, uncertainty ignored during search): `strategy` ∈ registry entries valid for the geometry (fixed-time, adaptive, conventional roundabout, `metered_entry`, adaptive `metered_entry` if G-SR passed) · cycle length (40–120 s) and green split shares (each phase ≥ minimum green) · yellow/all-red within validated bounds · metering queue threshold and spillback guard · adaptive extension limits · ring lanes ≤ 3. Genomes are repaired only by *clamping into declared bounds*; combinations rejected by the compatibility validator are counted as `rejected_by_validator` with the reason and are **never simulated**.

**15.2.4 Objectives.** Minimise mean delay after warm-up; maximise throughput; minimise 95th-percentile queue length; minimise a **safety proxy** (hard-braking events per 1,000 vehicles and, where defined, conflict counts; collisions > 0 is a hard constraint violation that disqualifies a candidate). Safety proxies are **model outputs, not predictions of real crashes.** Emergency response is not an objective.

**15.2.5 Evaluation protocol (the integrity core).**

| Seed pool | Used for | Rule |
| --- | --- | --- |
| **Tuning seeds** (e.g. 3) | Fitness during search | Fixed list drawn by the search seed |
| **Selection seeds** (e.g. 5) | Choosing among the final non-dominated set | Disjoint from tuning |
| **Held-out seeds** (≥ 10, `commit-before-search`) | Final evaluation of the shortlisted candidates and all baselines, **touched once**, after the search | Disjoint from both; the held-out seed list's hash is recorded *before* the search starts; a test with a spy proves the search never reads held-out results |

Additionally, **unseen conditions**: the final report re-evaluates candidates on a grid of demand levels, directional imbalance, vehicle mixes and aggression profiles not used during search (re-using the Robustness Lab's sampler and analysis), so the report can state *where the preferred candidate changes* — with its uncertainty and the sampling limits. Baselines (fixed-time, adaptive, conventional roundabout) are the **existing controllers evaluated unchanged**, on the same seeds (common random numbers).

**15.2.6 Budgets, cancellation, limits.** Per-search maximum evaluations (default population 12 × 8 generations × tuning seeds 3 = 288 runs, plus selection and held-out phases) counted against the user's quotas **at submission and during execution**; per-run timeout; at most 2 concurrent searches per user; cancellation takes effect at the next batch boundary and leaves a consistent *incomplete* result; a budget can never be exceeded (hard stop). Runtimes are **unverified** until benchmarked.

**15.2.7 Output and provenance.** The Pareto set (tuning evidence) and its **held-out re-evaluation with 95 % intervals** (paired differences against each baseline using the statistical contract §5.3–§5.4); a "preference changes" table over the unseen-condition grid; trade-off narrative as measured differences (a template; the Copilot may summarise it under the grounding rules); **EXPERIMENTAL** badge, seed counts and regimes beside every number. Saved: the candidate descriptor (a registry configuration — validated, reusable, runnable by anyone), the search specification and fingerprint, the RNG seed, the **full evaluation log** (every genome, its fingerprint, seeds, objectives, generation), seed-pool hashes, source revision and the manifest (§6); exportable as `.ufpkg`.

**15.2.8 Measurable acceptance (proposed thresholds).**

| # | Criterion | Threshold |
| --- | --- | --- |
| D1 | Determinism | Same search spec + seed ⇒ identical search-trace fingerprint (exact replay class) |
| D2 | Validity | A fuzz of ≥ 10,000 random genomes: 0 reach the engine unless valid; every rejection has a reason code |
| D3 | Budget and cancellation | Evaluations never exceed the budget (+0); cancel returns a consistent incomplete result within one batch; per-run timeout enforced |
| D4 | Seed hygiene | Tuning ∩ selection ∩ held-out = ∅ (asserted); spy test: held-out results are never read before the search ends |
| D5 | Algorithm correctness (simulator-independent) | On a synthetic evaluator with a known Pareto front, the search reaches ≥ 90 % of the known hypervolume within the budget |
| D6 | Baselines | The three baselines are evaluated unchanged on identical held-out seeds; a test proves the baseline metrics equal a direct run of the same scenario |
| D7 | Honest reporting | The report always shows held-out results; a planted case where the best tuning candidate loses on held-out is reported as such (no cherry-picking) |
| D8 | Provenance | A saved search can be re-run from its package and reproduces the trace fingerprint (`exact`) or reports `comparable` / `differs` |
| D9 | Real-regime evaluation | Run on ≥ 3 declared regimes (e.g. balanced, uneven peak, near-saturated + high aggression); **results are reported whatever they are**. *Not* a pass criterion: that a candidate beats a baseline |
| D10 | Runtime | Benchmark recorded on the presentation machine; documented defaults fit it |

**15.2.9 Limitations and safe claims.** Candidates are tuned to this simulator under declared assumptions (including the aggression profile); they say nothing about real-world performance or safety. "Discovered" means "found by search under these conditions". Learned controllers and AI-discovered policies remain **EXPERIMENTAL** until independently evaluated; the lab never describes a candidate as best, optimal or recommended.

**15.3 Extensibility.** The candidate-generation component is an interface (`propose(history) -> genomes`); a Bayesian or learned-policy generator can be added later without changing the evaluation protocol, because all candidates are registry configurations evaluated on the same harness.

---

## 16. Creative feature candidates — ranking and classification

Scored on novelty, user value, dependency on existing capabilities, risk and effort (relative). **Classification** is the decision for V3.0.

| # | Candidate | Verified dependency check | Class | Where / when |
| :-: | --- | --- | --- | --- |
| 1 | **Traffic Chaos and Stress-Test Lab** | Stationary Poisson arrivals only (no time-varying demand); `arms` subsets exist; no incident/lane-closure code. So v1 = **extreme stationary scenarios**: uneven directional/turning splits, mixed aggression, heavy-vehicle-dominated mixes, near-capacity and over-saturated demand, unusual-but-valid geometries (arm subsets, 1–3 ring lanes). **Surges and temporary lane closures need a new engine capability and are not in scope** unless separately approved (≈ 1.5 ED, reproduction-critical) | **Conditional** | W8; gate G-W8 |
| 2 | **Strategy DNA / Visual Control Composer** | Needs the registry (13.6). A read-only DNA summary card ships with the registry; the drag-and-assemble composer does not | **Deferred** (card: supporting) | Post-3.0 |
| 3 | **Traffic Regime Discovery** (clustering of operating regimes) | Needs many runs and a clustering method with uncertainty; risk of unsupported accuracy claims | **Deferred** | Post-3.0 |
| 4 | **Strategy Breakpoint Explorer** | Extends the Robustness flip-point analysis (§5.5) to the registry's strategies and the discovery lab's candidates; every breakpoint is a stratum-boundary *range* with uncertainty and sample-size limits | **Conditional** | W8 (with 1) |
| 5 | **Incident and recovery experiments** | No incident capability; would change engine state | **Deferred** | Post-3.0 |
| 6 | **Explainable policy comparison** | Controllers record **decision events** (phase changes, gate decisions with reasons, queue thresholds, detected demand); a controller is called explainable only for the decisions and inputs actually recorded. Gap accept/reject events for roundabouts: recorded only if the existing logic exposes them (AG-1/SR spike decides) | **Supporting** (event recording) / **Deferred** (comparison UI) | Recording in W2/W3; UI post-3.0 |
| 7 | **Experiment reproduction and sharing** | Is the `.ufpkg` + manifest work (§6, §7) extended with source revision, seeds, model assumptions, software metadata, outputs and integrity | **Core** | W7 |
| 8 | **AI Research Report Generator** | The Copilot's grounded summary covers interpretation; a full structured report generator needs the same grounding checks across more sections | **Deferred** | Post-3.0 (candidate for spare capacity after W9) |

Not selected, with reasons: incidents (1 engine dependency), regime discovery (credibility), visual composer (UI cost), report generator (grounding surface). Each can be revisited with real evidence of demand.

## 17. Cross-cutting quality and research validity

Quality work is **assigned to the weeks where it is relevant** (sprint plan), not deferred to a final sprint: authentication/authorisation/ownership (W1 base, W5 AI endpoints, W7 PATs) · input validation and quotas (W1 base quota, W5 AI quotas, W7 full) · collision/deadlock/gridlock/starvation regression (W2, W3, W4, W8) · performance and resource benchmarks (W2 signalised roundabout, W6 search, W9 whole system) · API schema compatibility (OpenAPI snapshot from W1; shared-schema parity tests for each new schema) · reproducibility metadata (each feature adds its fingerprint component) · UI accessibility and usability (axe on every new screen as it ships; 375 px check in W9) · logging and failure diagnostics (decision events, request ids, no payload logging) · test coverage and deterministic regression (coverage floor 85 % retained) · documentation and research limitations (a limitations paragraph ships with every feature).

**AI-specific research validity.** Evaluation sets are authored before tuning; held-out items are used once; null results are reported; every AI-assisted statement is traceable to a proposal id, a result fingerprint and a source revision.
