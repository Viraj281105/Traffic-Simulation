# V3.0 Weekly Sprint Plan — Phase A (V2.0 closure) and Phase B (nine feature weeks), 13 October 2026 – 7 January 2027

> **Status:** PROPOSED — **revision 3** (creative expansion, 2026-10-12) · **every date, estimate and load below is proposed until the product owner approves it**
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Authority:** [`docs/ROADMAP.md`](../ROADMAP.md) remains the authoritative roadmap and is **not edited by this revision**. This plan is subordinate to it.
> **Gating:** Nothing here authorises V3.0 implementation. Phase B cannot begin until the V2.0 release gate **G-V2** and the design-approval gate **G-D** have passed.

### What changed in revision 3

* **One major, demonstrable, end-to-end feature every implementation week** (W1–W9). Security, quality, accessibility, documentation and performance work is scheduled **inside** each week, with an explicit ED figure, not parked in a final sprint.
* **New major features:** signalised roundabouts (W2), composable strategies (W3), high driver aggression default (W4), AI Traffic Experiment Copilot (W5), AI Control Strategy Discovery Lab (W6), Traffic Chaos and Strategy Breakpoint Explorer (W8, conditional). The Robustness Lab (W1) and developer platform (W7) are kept and re-sequenced.
* **Capacity result (§1.4): the original calendar (to 26 Nov) cannot hold this scope.** The proposed calendar extends Phase B to a final showcase on **Thu 7 Jan 2027**; **26 Nov becomes an interim presentation.** Planned load is 85 % and falls to 74 % if conditional items are dropped. The earlier plan's Phase A (V2.0 closure, 8 working days, 7.75 ED) is **unchanged**; V2.0 closure is not compressed.
* **Gates re-timed:** one gate per major feature, plus the existing release gates (§4).
* Emergency pre-emption stays conditional and is expected to be deferred (decision D8).

---

## 1. Capacity model

### 1.1 Working capacity

| Quantity | Value (assumption — owner to confirm, decision D6) |
| --- | --- |
| Engineers | One (the *Engineer*), who is also the integration owner. Assignees on GitHub issues follow the owner's area split of 2026-10-12 (frontend → khushik8605, otherwise Viraj281105); **availability is unconfirmed** |
| 1 engineer-day (ED) | One working day ≈ **6 focused hours**: implementation, **code review**, integration, tests, debugging, documentation. Every ED figure in this plan **includes** its tests and documentation |
| Weekends | **Unplanned contingency only.** No deliverable and no gate is scheduled on a Saturday or Sunday |
| Coding agents | Potential throughput. A day's agent output still needs the Engineer's review and merge; it is **not** added to capacity |
| Holidays / leave | None assumed in the dates; **25 Dec – 1 Jan is a likely holiday period** (risk R-HOL); any leave shifts dates one-for-one |
| Planned load ceiling | Phase A is the exception (97 %, §2.3). Phase B plans **≤ 88 %** of capacity per period |

### 1.2 Calendar and capacity by period

| Period | Dates (proposed) | Working days | Capacity (ED) | Planned (ED) | Load | Major feature |
| --- | --- | :-: | :-: | :-: | :-: | --- |
| **Phase A** V2.0 closure | Tue 13 – Thu 22 Oct (gate review Fri 23) | 8 | 8.0 | 7.75 | 97 % | Decision-support release gate |
| **B0** preview preparation | Mon 26 – Wed 28 Oct | 3 | 3.0 | 2.5 | 83 % | *None — not an implementation week* (preview prep; V2.0 + design only) |
| *Thu 29 Oct — preview (no development)* | | — | — | — | — | |
| **W1** | Fri 30 Oct – Thu 5 Nov | 5 | 5.0 | 4.25 | 85 % | **Robustness Lab vertical slice** |
| **W2** | Fri 6 – Thu 12 Nov | 5 | 5.0 | 4.25 | 85 % | **Signalised roundabouts** (✅ Implemented 2026-10-21) |
| **W3** | Fri 13 – Thu 19 Nov | 5 | 5.0 | 4.25 | 85 % | **Composable control strategies** (+ adaptive signalised roundabout, conditional) |
| **W4** | Fri 20 – Thu 26 Nov | 5 | 5.0 | 4.25 | 85 % | **High-aggression behaviour experiments** · Thu 26 Nov: *interim presentation* |
| **W5** | Fri 27 Nov – Thu 3 Dec | 5 | 5.0 | 4.25 | 85 % | **AI Traffic Experiment Copilot** |
| **W6** | Fri 4 – Thu 10 Dec | 5 | 5.0 | 4.25 | 85 % | **AI Control Strategy Discovery Lab** |
| **W7** | Fri 11 – Thu 17 Dec | 5 | 5.0 | 4.25 | 85 % | **Python SDK and portable `.ufpkg` experiment packages** |
| **W8** *(conditional)* | Fri 18 – Thu 24 Dec | 5 | 5.0 | 4.25 | 85 % | **Traffic Chaos / Strategy Breakpoint Explorer** |
| **W9** final integration | Fri 25 – Thu 31 Dec (5 working days; Fri 1 Jan unplanned) | 5 | 5.0 | 4.25 | 85 % | **Release candidate and evaluation showcase** |
| **Showcase preparation** | Mon 4 – Wed 6 Jan 2027 | 3 | 3.0 | 2.5 | 83 % | Rehearsals, fallbacks |
| *Thu 7 Jan 2027 — final showcase* | | — | — | — | — | |
| **Phase B total** | | **51** | **51.0** | **43.25** | **85 %** | |

**Committed vs conditional.** Committed: B0 2.5 + W1 4.25 + W2 4.25 + W3 2.75 + W4 4.25 + W5 4.25 + W6 4.25 + W7 4.25 + W9 4.25 + showcase preparation 2.5 = **37.5 ED (74 %)**. Conditional: adaptive signalised roundabout 1.5 (inside W3) + W8 4.25 = **5.75 ED**. Unallocated contingency (weekly 15 % buffer plus weekends): 7.75 ED of nominal capacity plus the 5.75 ED of conditional work that may be dropped.

### 1.3 Roles and integration ownership

* **Engineer** — builds, reviews, merges.
* **Integration owner** — *the Engineer*, unless the product owner (PO) names someone else. The integration owner is the **only** person who changes **shared files**: router mounting in `backend/src/main.py`, `shared/schemas/**`, database migrations, frontend routing (`routing.ts`, nginx template, `vite.config.ts`), the OpenAPI snapshot, the strategy registry's compatibility table and the frontend/backend service contracts.
* **Product owner** — approves scope, accepts gaps, authorises edits to `ROADMAP.md`, authorises any deployment, decides gates and decisions D1–D8, D-SCOPE, D-AI1, D-AG1/2, D-SR1.
* **Working rules for agents and branches:** each agent works in its own git worktree/branch on files it alone owns; it proposes shared-file changes as a small diff to the integration owner; one migration per pull request; every contract change ships with a schema diff and a test that feeds the new shape to every consumer (including `null`); no more than one branch touching `main.py` at a time.
* Names are **not** recorded in the repository except where the owner assigned issues on GitHub (2026-10-12); decision D-V2-0 asks the PO to name the PO, Engineer and reviewer.

### 1.4 Capacity analysis (the honest answer to "does this fit?")

| Question | Answer |
| --- | --- |
| Does the original calendar (Phase B to Thu 26 Nov: 22 working days, 18.75 ED planned) hold the committed scope? | **No.** Committed Phase B scope is **37.5 ED** — about **2×** the planned capacity of the original calendar |
| Does the extended calendar hold it? | **Yes, at 85 % planned load**, if V2.0 closes on time (G-V2 Fri 23 Oct), no leave falls in 25 Dec – 1 Jan, and conditional items are dropped on any slip |
| What breaks first on a one-week slip? | The conditional W8 (Chaos/Breakpoint) is dropped; then CSV/GeoJSON never starts; then the adaptive signalised roundabout is dropped; only then does a committed week slip (§7) |
| What if the PO needs a final date of 26 Nov? | **Option S:** W1 Robustness, W2 signalised roundabouts, W3 registry and W4 aggression only, with the release-candidate work compressed into the last 3 days of W4 — **no AI feature**, no developer platform. Not recommended; decision **D-SCOPE** |
| What if the 25 Dec – 1 Jan holiday is real? | W9 moves to Mon 4 – Fri 8 Jan, preparation to 11 – 13 Jan, showcase **Thu 14 Jan 2027** (+1 week) |
| Is the per-week estimate evidence? | **No.** Every ED is an unverified estimate by analogy with the V2.0 closure packages; the first measured week (W1) re-baselines W2–W9. The plan includes a **re-forecast checkpoint at G-R1 (Thu 5 Nov)** and again at G-SR (12 Nov) |

### 1.5 Working rules that hold in both phases

* Existing strategies are baselines and are never edited to be beaten.
* No change to simulation physics or scientific parameters without a recorded reason and an ADR; pre-existing determinism and reproduction tests stay green and unmodified. The two physics-adjacent changes in V3.0 — the **`EntryGate` seam** in `RoundaboutController` (W2) and the **parametrised roundabout critical gap** (W4, only if the spike shows it is the dominant lever) — each require a bit-identity test against the unmodified behaviour.
* Schema changes are additive, use the existing inline-migration pattern, and are rehearsed on a **copy** of `simulation.db`.
* Estimates for runtime and performance are labelled **unverified** until measured on the intended machine.
* The UI shows a capability only if the backend provides it. **No AI feature is described as functional until its evaluation (strategy §15) has passed.**
* Every weekly gate requires: new tests green, existing suites green, schema/OpenAPI parity, axe clean on new screens, a limitations paragraph shipped with the feature, and a recorded end-to-end demo run.

---

## 2. Phase A — V2.0 closure (Tue 13 Oct – Fri 23 Oct)

**Rule: no V3.0 product feature is scheduled, started or merged in Phase A.** Architecture and design documents (the strategy, the statistical contract, the manifest, security minimums — already written) are the only V3.0 activity allowed.

### 2.1 Objective and exit

Satisfy every row of the [V2.0 release gate](V2_COMPLETION_AUDIT.md#7-v20-release-gate-g-v2) or have the PO accept the gap in writing. Exit = gate **G-V2** (§4).

### 2.2 Work packages (from audit §7.9)

| Package | Content | ED | Gate rows |
| --- | --- | :-: | --- |
| W7 | Push the four local commits, open the PR, get CI running **first** (early feedback) | 0.25 | R1.7, R2.6 |
| W3 | Per-user auth on calibration, `planning/validate`, `networks`; calibration-run ownership; request-size cap; route-level auth tests | 1.25 | R1.2, R1.3, R3.1, R3.3, R3.5 |
| W4 | Private suites (migration + scoping + ownership tests) | 0.75 | R1.4, R3.4 |
| W6 | Pipeline verification without production change: read both failed runs, static-check scripts, review workflow | 0.5 | R5.1, R5.3 |
| W1 | Planner UI minimum viable workflow (audit §7.1, PL-1…PL-10) | 3.0 | R1.1, R2.7 |
| W2 | Evidence runs: slow suite (CI dispatch), production build, axe, scripted real-backend run | 0.75 | R2.2, R2.5, R2.8 |
| W5 | Documentation: `/api/v2` API reference, planner guide, validation addendum, operator notes; README/ROADMAP edits **after PO authorisation** | 1.0 | R4.1–R4.5 |
| W8 | Evidence pack and gate review | 0.25 | all |
| | **Total** | **7.75** | |

The audit's estimate of ≈ 7–8 ED is **kept as an estimate**; this plan commits to the upper end.

### 2.3 Day plan (proposed; working days only)

| Day | Date | Work | Cum. ED |
| --- | --- | --- | :-: |
| 1 | Tue 13 Oct | W7 (push, PR, CI) · start W3 | 1.0 |
| 2 | Wed 14 | W3 finish · start W4 | 2.0 |
| 3 | Thu 15 | W4 finish · W6 (0.25 ED slack) | 2.75 |
| 4 | Fri 16 | W1: client, routing, scenario + alternatives steps | 3.75 |
| — | Sat–Sun 17–18 | **Contingency only** | — |
| 5 | Mon 19 | W1: run/progress, comparison, findings | 4.75 |
| 6 | Tue 20 | W1: report, reproduce, re-open, UI tests | 5.75 |
| 7 | Wed 21 | **Code frozen at end of day** (gate-candidate commit) · W2 (slow suite dispatched on that commit) · W5 start | 6.75 |
| 8 | Thu 22 | W2 results, fixes only · W5 finish · W8 evidence pack | 7.75 |
| gate | Fri 23 | **G-V2 review** by the PO (no development scheduled) | — |

After the Wed 21 code freeze only documentation commits are allowed; the evidence pack records the frozen code commit and shows (`git diff --stat`) that later commits touch documentation only. A code fix after the freeze restarts the affected evidence runs (slow suite included) and slips the gate.

Load = 7.75 / 8.0 = **97 %**. This is deliberately close to full because the ≈ 7–8 ED range *is* the uncertainty; there is **no hidden buffer**.

### 2.4 Gate-slip rule

If the actual work exceeds the plan, **G-V2 slips day for day**. V3.0 implementation does not start early; Phase B dates shift one-for-one. The preview (Thu 29 Oct) does not move: it already defaults to V2.0 plus design (PV-1), so a slip changes only how much of V2.0 is finished by then — if G-V2 has not passed by Wed 28 Oct, the preview reports V2.0 status honestly, with the failing gate rows listed. Rejecting any accepted-gap candidate (audit §7.8) adds up to ≈ 2 ED to Phase A.

### 2.5 What Phase A delivers (user-visible)

A planner can build a scenario, compare fixed-time/adaptive/roundabout with intervals, read the evidence and its limits, export a report and reproduce the study — in the browser, with other users' data protected. The API reference and README tell the truth.

---


## 3. Phase B — V3.0 implementation (starts only after G-V2 and G-D)

**Entry condition:** G-V2 = PASS or PASS-with-accepted-gaps, **and** the V3.0 design-approval gate **G-D** (§4) has passed: the PO has approved strategy §2 (funding), §5–§8 (contracts), §13–§15 (strategies, aggression, AI) and decisions D1, D3–D7, **D-SCOPE, D-AG1, D-SR1** (D-AI1 is needed by Fri 27 Nov, not earlier). If G-D has not passed on Mon 26 Oct, B0 is spent completing design and every later date slips one-for-one.

**Weekly template.** Each week lists: **Major feature** (one user-visible, end-to-end capability) · **Minor improvements** · **Security** · **Quality** (tests, refactoring, performance, accessibility) · **Documentation** · **Demo** (a reproducible end-to-end scenario with a fallback) · **Gate** (measurable go/no-go) · **ED breakdown** (sums to the week's planned 4.25 ED). Owners: the Engineer (integration owner) unless stated; frontend-labelled items follow the owner's assignment (khushik8605), availability unconfirmed.

### 3.1 B0 — Mon 26 – Wed 28 October: preview preparation (3 days, 2.5 planned; *not an implementation week*)

| Task | ED | Notes |
| --- | :-: | --- |
| B0-1 **Benchmark the presentation machine:** time the V2.0 planner study and (if used) ensemble units, three consecutive runs, record in the runbook | 0.25 | Until done, every runtime is "unverified" |
| B0-2 ADR-013 *integration contract and versioning*, ADR-014 *strategy registry and entry-gate seam* (strategy §13), ADR-015 *uncertainty design*, ADR-016 *driver-aggression profile* (strategy §14), ADR-017 *AI validation boundary* (strategy §15) | 0.75 | Documentation of approved design; no product code |
| B0-3 Preview fallback assets: precomputed planner studies with exports, recorded video, printed one-pager, checksums | 0.5 | Generated on the preview commit |
| B0-4 Rehearsal 1 (Tue) and Rehearsal 2 (Wed) with fixes | 0.5 | Cold start, offline, deliberate failure drills |
| B0-5 *(Conditional — only after G-V2 and G-D)* Robustness **sampler skeleton:** specification model, stratified sampler, condition/seed derivation, unit tests; **no UI, no runner** | 0.5 | Shown only if its tests pass by Tue 27 noon, and only as "design prototype" |
| B0-6 Defect reserve | 0.0 | Absorbed by the 0.5 ED weekly slack of B0 |
| | **2.5** | |

**Preview-eve gates:** G-PF Tue 27 Oct 12:00 · G-PV Wed 28 Oct 17:00 (§4).

### 3.2 W1 — Fri 30 Oct – Thu 5 Nov: Robustness Lab vertical slice

| Row | Content |
| --- | --- |
| **Major feature** | **Robustness Lab vertical slice** (#151, #152 minimal view, #153 base): submit an uncertainty specification through `/api/v3/experiments`, run paired common-random-number ensembles, receive the contract-conforming analysis (strategy §5) and read it in a results table |
| **Minor improvements** | Minimal results page `/app/experiments/:id` (N conditions · r replications · total runs shown separately; P(win/tie/loss) with Wilson intervals; eligibility checklist; "Real-world validity: None — assumptions only") |
| **Security** | `/api/v3` owner scoping (another user's id is 404) · request-size cap · base per-user concurrent-experiment and simulations-per-experiment quota · input validation `extra="forbid"` |
| **Quality** | Hand-computed fixtures (Wilson, bootstrap, regret) · determinism test · CRN equivalence · exclusion accounting · eligibility rules (N = 29/30/100) · OpenAPI snapshot started · pre-existing determinism tests unmodified |
| **Documentation** | `docs/research/uncertainty.md` (method, assumptions, meaning of "eligible", what is not modelled) |
| **Demo** | A 24-condition × 3-alternative study (fixed-time vs adaptive vs conventional roundabout) submitted by script, opened in the browser, with a precomputed fallback |
| **Gate G-R1 (Thu 5 Nov)** | Contract tests green · same spec + seed ⇒ identical result fingerprint · ownership tests green · demo run recorded · **re-forecast of W2–W9 using the measured velocity** |
| **ED breakdown** | spec model + fingerprint + sampler 0.75 · CRN runner + exclusion accounting 0.75 · analysis core (win/tie/loss, bootstrap, regret, preference share, eligibility) 1.25 · `/api/v3` submit/status/result + `/capabilities` + ownership 0.75 · minimal results page 0.5 · security review + review/integration 0.25 = **4.25** |
| **Dependencies** | G-V2, G-D; B0-1 benchmark for preset sizing |
| **Carried forward** | Flip detection and Spearman sensitivity (W3, 0.25) · split-half stability and variance split (W4, 0.25) · cancel/resume (W7, 0.25) · full viewer and 375 px layout (W9, 1.0) |

### 3.3 W2 — Fri 6 – Thu 12 Nov: Signalised roundabouts (flagship)

| Row | Content |
| --- | --- |
| **Major feature** | **Signalised roundabouts, `metered_entry` mode** (#163): signals on chosen roundabout entries with explicit phase plans, queue-aware spillback guard and the unchanged gap-acceptance logic, runnable from a scenario and comparable against the conventional roundabout and the signalised intersection through the existing planner/paired-comparison machinery |
| **Minor improvements** | Decision-event recording (`red`, `yellow`, `ring_spillback_hold`, `queue_cap`) in the controller state for later explainability · minimal entry-control selector in the scenario setup (frontend) · baseline-comparison study with intervals |
| **Security** | Bounds on all new config inputs (green/yellow/all-red/cycle/queue thresholds) · fuzz of the phase-plan validator (≥ 10,000 random plans: none crash, invalid ones rejected with a code) · no new network surface |
| **Quality** | **`AlwaysOpen` gate ≡ conventional roundabout** bit-identity test (metrics and snapshot fingerprints) · collision = 0 over a seed × demand matrix · deadlock · starvation property (`wait ≤ maxRed + yellow + allRed`) · ring-spillback not worse than baseline · layouts (3-arm, 4-arm, 1–3 ring lanes) · runtime/memory benchmark vs conventional roundabout (target ≤ 1.3×, unverified) · slow CI job added |
| **Documentation** | `docs/simulation/signalised-roundabout.md`: movement/phase model, right-of-way modes, what `metered_entry` can and cannot claim, limitations (no real-world calibration, no PET on curved paths) |
| **Demo** | One scenario, three strategies, uneven peak demand, with today's engine behaviour declared as such (the aggression profile does not exist until W4, so the demo does not claim `high`). Shows queues, signal states on the canvas, the paired comparison and the limitations banner |
| **Gate G-SR (Thu 12 Nov)** | Bit-identity, collision, deadlock, starvation and spillback tests green on the slow suite · benchmark recorded · demo recorded · decision whether adaptive signalised roundabout (W3, conditional) proceeds |
| **ED breakdown** | ADR + `EntryGate` seam spike 0.5 · seam + equivalence test 0.5 · controller (phase engine, metering, queue guard) 1.25 · validation + config fields + schema parity 0.5 · regression suite 0.75 · baseline study + benchmark + docs 0.25 · entry-control selector 0.25 · security/fuzz + review 0.25 = **4.25** |
| **Dependencies** | W1 only for the comparison study; ADR-014 |
| **If G-SR fails** | W3 is spent fixing the controller; the registry (W3 major) shrinks to its core |
| **Carried forward** | `phased_priority` mode (conditional/stretch, not scheduled) |

### 3.4 W3 — Fri 13 – Thu 19 Nov: Composable control strategies

| Row | Content |
| --- | --- |
| **Major feature** | **Composable Traffic-Control Strategies** (#162, #156): a strategy registry with layered descriptors, compatibility validation with explanatory errors, scenario-fingerprint parity, and a read-only strategy summary card; the three existing strategies and `metered_entry` register through it |
| **Conditional addition** | **Adaptive signalised roundabout** (#164), 1.5 ED, **only if G-SR passed**: demand-responsive green extension on `metered_entry` through the registry, with stability/oscillation tests |
| **Minor improvements** | Robustness completion A: one-factor preference-flip detection and Spearman sensitivity (strategy §5.5) · the superseded error `adaptive applies to a signalised junction` is replaced by registry messages |
| **Security** | No uploaded code (registry accepts built-ins only; test: attempting to register at runtime from request data fails) · parameter bounds enforced in the descriptor schema · compat table is integration-owner-only |
| **Quality** | **Fingerprint parity:** every existing fixture scenario fingerprints identically before and after · every compatibility rule has a rejecting unit test with its message · registry self-check · adaptive-SR stability: min-green respected 100 %, bounded phase-change rate under constant demand, performance at low/medium/saturated demand |
| **Documentation** | `docs/simulation/strategies.md` (layers, contracts, how to add a strategy by PR, the compatibility table) · ADR-012 completed |
| **Demo** | Build a strategy from the summary card, observe a rejected combination with its explanation, run a valid one, show an unchanged fingerprint for an old scenario |
| **Gate G-CS (Thu 19 Nov)** | Parity test green · compat rules complete · registry docs · if adaptive-SR included: oscillation tests green; else it is moved out and recorded |
| **ED breakdown** | registry + descriptors + built-in registrations 1.0 · compat validator + messages + tests 0.75 · fingerprint parity + shared schema 0.5 · summary card 0.25 · Robustness completion A 0.25 · **(conditional) adaptive signalised roundabout 1.5** = **4.25** (2.75 committed) |
| **Dependencies** | W2 (G-SR) for the adaptive variant; ADR-012/014 |
| **If the conditional is dropped** | The 1.5 ED goes to W2 fixes, the viewer, or contingency |

### 3.5 W4 — Fri 20 – Thu 26 Nov: High-aggression behaviour experiments · interim presentation

| Row | Content |
| --- | --- |
| **Major feature** | **High driver aggression as the default for new scenarios** (#165): the `traffic.driverAggression` profile (`standard`/`moderate`/`high`), the defaults at every authoring boundary, and the **regression matrix** showing what aggression does to headways, saturation flow, queues, collisions and deadlock across strategies and vehicle mixes |
| **Minor improvements** | Robustness completion B: split-half stability and variance split (§5.7) · consistency test mirroring shared schema ↔ backend model ↔ TypeScript types ↔ presets ↔ builder |
| **Security** | Profile input is an enum (no free numbers from users); no parameter outside validated ranges can result (property test) |
| **Quality** | Defaults and overrides at UI/presets/builder/`/api/v3`/Copilot-contract/package · **absent ⇒ `standard` with unchanged fingerprints** on the fixture corpus · determinism per profile · interaction matrix: profile (3) × mix (car-only, mixed, heavy) × strategy (4) × density (3) = 108 cells, collisions = 0 and no deadlock asserted, spillback/throughput **reported** vs `standard` |
| **Documentation** | `docs/simulation/driver-aggression.md`: the levers and their values, the evidence for each, "a simulation assumption, not a measurement of real-world driver behaviour" |
| **Demo** | The same scenario under `standard` and `high` (fixed-time and signalised roundabout), headway distributions and the matrix summary; the profile and its fingerprint visible in the report |
| **Interim presentation (Thu 26 Nov)** | See the [presentation plan §3](V3_PRESENTATION_PLAN.md#3-interim-presentation--thursday-26-november-2026): W1–W3 features (and W4 only if its gate passed by Wed 25 Nov 17:00), with recorded evidence; everything else shown as **planned** |
| **Gate G-AG (Wed 25 Nov 17:00)** | Profile tests green · fingerprint-parity green · matrix run and reviewed · ADR-016 closed. If not met, W4 is not shown on 26 Nov and the aggression default is **not merged** into authoring boundaries |
| **ED breakdown** | AG-1 spike + sensitivity analysis + ADR 0.5 · AG-2 backend model, shared schema, TS types, presets, UI, builder 0.75 · AG-3 fingerprint/manifest/reproducibility tests 0.5 · AG-4 regression matrix 1.0 · docs/limitations (inside AG items) · interim-presentation preparation (2 rehearsals + fallback assets) 1.0 · Robustness completion B 0.25 · security/quality review 0.25 = **4.25** |
| **Dependencies** | W2/W3 strategies for the matrix; D-AG1/D-AG2 decided |
| **Note** | The default is **merged only at W4's end** so that W1–W3 results are not silently redefined mid-sprint; W1–W3 demos declare their profile explicitly |

### 3.6 W5 — Fri 27 Nov – Thu 3 Dec: AI Traffic Experiment Copilot

| Row | Content |
| --- | --- |
| **Major feature** | **AI Traffic Experiment Copilot** (#166): natural-language question → validated `ExperimentProposal` → inspect-and-confirm → ordinary `/api/v3` experiment; and an evidence-grounded interpretation of the measured result. **Decision D-AI1 must be made before this week starts** |
| **Minor improvements** | Deterministic proposer and guided form (the fallback, not called AI) · coded explanations and deterministic valid alternatives for invalid configurations · suggested comparisons, replications and sensitivity checks |
| **Security** | The model has no tools or network access · provider key server-side only · per-user daily proposal/summary caps and token caps · global monthly spend cap and kill switch · prompt-injection and exfiltration tests (the 5 adversarial items) · confirm token single-use, bound to user and content hash · metadata-only logging |
| **Quality** | Schema + rules validation of every proposal (invalid model stubs cannot reach confirm) · grounding check (every numeral in a summary traces to the evidence object) · planted-unfavourable-result test · fallback tests (provider off, timeout, over budget, schema-invalid) · `copilot-eval-v1` run on the deterministic baseline and, if a provider is approved, on the model |
| **Documentation** | `docs/ai/copilot.md`: architecture, validation boundary, claims allowed, data sent to the provider, cost controls, how to disable; limitations |
| **Demo** | The brief's example question ("compare a conventional roundabout, a signalised roundabout and an adaptive signal under highly aggressive driving and uneven peak-hour demand") → proposal → backend issues shown → confirm → run → measured table and a clearly separate "model-generated interpretation" panel; fallback = the same with the deterministic proposer |
| **Gate G-AI-A (Thu 3 Dec)** | Acceptance C1–C9 (strategy §15.1.7) measured on `copilot-eval-v1` (held-out 10 used once). **AI claim granted only if C3–C6 pass with a connected provider;** otherwise the feature ships labelled as the deterministic assistant and the PO is told the AI-feature count is one |
| **ED breakdown** | proposal contracts + catalogue 0.5 · deterministic proposer + guided form 0.75 · validation boundary + explanations 0.5 · LLM adapter + prompts + repair loop (provider stubbed in tests) 0.75 · inspect-and-confirm UI + confirm token + submit path 0.75 · grounded summariser + grounding check 0.5 · evaluation set + adversarial tests + AI quotas and cost caps 0.5 = **4.25** |
| **Dependencies** | W1 (`/api/v3`), W3 (catalogue from the registry), W4 (profile in proposals), **D-AI1** |

### 3.7 W6 — Fri 4 – Thu 10 Dec: AI Control Strategy Discovery Lab

| Row | Content |
| --- | --- |
| **Major feature** | **AI Control Strategy Discovery Lab** (#157): bounded multi-objective evolutionary search over registered strategies for a declared regime, evaluated against the three baselines on held-out seeds and unseen conditions, with a Pareto set, "where the preference changes", and full provenance |
| **Minor improvements** | Search budget and cancel controls · saved candidate descriptor (a registry configuration, reusable and runnable by anyone) · Pareto table and plot (table first) |
| **Security** | Budgets counted against the user's quotas at submission and during execution · max 2 concurrent searches · per-run timeout · all genomes pass the compatibility validator before simulation · ownership of searches and candidates (404 for others) |
| **Quality** | Determinism (same spec + seed ⇒ same trace fingerprint) · 10,000-genome validity fuzz · budget and cancellation tests · seed-pool disjointness and the held-out spy test · synthetic-evaluator hypervolume test (≥ 90 %) · baselines-unchanged equivalence test · runtime benchmark on the presentation machine · slow-suite job |
| **Documentation** | `docs/research/discovery-lab.md`: method (accurately "evolutionary multi-objective search"), search space, objectives and safety-proxy limits, protocol, claims allowed; limitation: tuned to this simulator |
| **Demo** | Declare a regime (uneven peak, near-saturated, `high` aggression), run a small search (precomputed fallback, since live runtime is unverified), show the Pareto set, the held-out re-evaluation against the baselines **including a case where a candidate does not beat a baseline**, and the saved package |
| **Gate G-AI-B (Thu 10 Dec)** | Acceptance D1–D10 (strategy §15.2.8); D9 requires the regimes to be *run and reported*, not to be won |
| **ED breakdown** | search space + genome validator 0.75 · NSGA-II-style search + budget/cancel 1.0 · seed pools + commit/hygiene + spy test 0.5 · evaluation harness (baselines, held-out, CRN reuse of Robustness) 0.75 · Pareto + preference-change table + provenance + package hook 0.5 · results UI 0.5 · docs/benchmark/fuzz 0.25 = **4.25** |
| **Dependencies** | W1 (analysis and paired harness), W3 (registry), W2 (strategies to search) |

### 3.8 W7 — Fri 11 – Thu 17 Dec: Python SDK and portable experiment packages

| Row | Content |
| --- | --- |
| **Major feature** | **Python SDK and `.ufpkg` packages** (#153 SDK part, #154, #155): run an experiment (Robustness, Copilot-confirmed, Discovery) from code with a personal access token, export a package, and verify it on another machine (`exact` / `comparable` / `differs`) |
| **Minor improvements** | Cancel/resume for Robustness experiments (Robustness completion C) · `/api/v3/capabilities` reporting quotas · package for Discovery candidates and Copilot proposals (with proposal metadata) |
| **Security** | Personal access tokens: hashed storage, scopes, mandatory expiry, revocation checked per request, redaction, no PAT creates a PAT · quotas enforced at submission and during execution (429/413/422 naming the quota) · append-only audit table · **zip-slip / traversal, size and entry-count limits, schema validation and checksum verification on import** · "integrity is not authenticity" statement in the verifier |
| **Quality** | Tampered-package rejection test · replay-class tests (exact, comparable, differs) · cancel/resume equivalence (resumed fingerprint equals uninterrupted) · token lifecycle tests · SDK tested against a live local backend · OpenAPI contract test |
| **Documentation** | API v3 reference · SDK guide · package format and verification guide · security notes |
| **Demo** | A script with a token submits a study, waits with progress, cancels and resumes a second, exports a package and verifies it, then verifies a deliberately tampered copy and is told why it fails |
| **Gate G-B1 (Thu 17 Dec)** | Core research workflow stable: acceptance PA-1…PA-7 (full forms) pass; security regression green; tampered package rejected; no open P1 defect. Decision point for the conditional W8 |
| **ED breakdown** | PATs + scopes + expiry + revocation + audit 1.5 · quotas + capabilities 0.5 · manifest + `.ufpkg` export/import/verify 1.25 · Python client 0.5 · cancel/resume 0.25 · security regression + docs 0.25 = **4.25** |
| **Dependencies** | W1, W5, W6 (artefacts to package); D3 |
| **If G-B1 fails** | W8 is cancelled and its capacity is spent on platform fixes |

### 3.9 W8 — Fri 18 – Thu 24 Dec *(conditional)*: Traffic Chaos and Strategy Breakpoint Explorer

| Row | Content |
| --- | --- |
| **Major feature** | **Traffic Chaos and Stress-Test Lab** (#167) and **Strategy Breakpoint Explorer** (#168): generate reproducible hard scenarios, classify failures and report where the preference between strategies changes, with uncertainty and sampling limits |
| **Scope limit (verified)** | The engine has **no time-varying demand and no lane-closure/incident support**; v1 stress scenarios are *stationary extremes*: uneven directional and turning splits, mixed aggression and heavy-vehicle-dominated mixes, near-capacity and over-saturated demand, unusual-but-valid geometries (arm subsets, 1–3 ring lanes). "Surge" and "recovery" scenarios require a separate approved demand-profile capability (≈ 1.5 ED, reproduction-critical) and are **not** in this week |
| **Minor improvements** | Failure classification (collision, deadlock/gridlock, vehicle-limit, starvation, excessive queue, spillback) · comparative results through the registry · breakpoint tables with stratum-boundary ranges |
| **Security** | Stress generation counts against quotas; generated scenarios pass the same validators; a cap on scenario count per request |
| **Quality** | Generated scenarios are reproducible from `(generator version, seed)` · failure classifier tests on planted failures · breakpoint recovery of a planted flip (re-uses the W1 stub) · "too few conditions to assess" outputs tested |
| **Documentation** | `docs/research/stress-testing.md` and the breakpoint method note |
| **Demo** | Generate 30 stress scenarios, run the four strategies, show the failure table and one breakpoint (aggression level at which the preferred strategy changes) with its uncertainty and the sampling grid |
| **Gate G-W8 (Thu 24 Dec)** | Tests green; classification verified on planted failures; holiday availability confirmed (D6). If any condition fails by Fri 18 Dec the week is cancelled and its capacity reassigned |
| **ED breakdown** | stress-scenario generator 1.25 · failure classification 0.75 · comparative results 0.5 · breakpoint explorer 1.25 · tables UI 0.25 · docs + tests 0.25 = **4.25** |
| **Dependencies** | W1, W3, W4, G-B1 |
| **If dropped** | Freed capacity funds CSV import → GeoJSON export (#158, 1.5 ED) and the remaining 2.75 ED is buffer |

### 3.10 W9 — Fri 25 – Thu 31 Dec: final integration, release candidate and evaluation showcase

| Row | Content |
| --- | --- |
| **Major feature** | **Release candidate and evaluation showcase** (#161, #160, #152 completion): the integrated system on one commit with a reproducible evaluation, the complete viewer and the responsive read-only views |
| **Minor improvements** | Full results viewer (regret, preference share, flip, sensitivity, variance split, provenance, limitations; table first, charts second) · 375 px read-only views for status and results · recorded evaluation studies as packages (E1 robustness; E2 signalised roundabouts vs baselines under `high` aggression; E3 Copilot-proposed study; E4 Discovery search) |
| **Security** | Final security review (auth, ownership, quotas, AI controls, package import, PAT lifecycle) · dependency/audit scan · secrets scan of the repository and packages |
| **Quality** | Whole-system regression on the RC commit: backend non-slow **and slow**, frontend ×3, lint, types, formatting, schema validation, OpenAPI contract, production build, axe on all new screens, 375 px check · performance and memory benchmark table (all strategies, search, ensemble) |
| **Documentation** | API v3 reference, SDK guide, methods and limitations pages (one page per feature), claims register, runbook, fallback pack |
| **Demo** | The §3 showcase script of the [presentation plan](V3_PRESENTATION_PLAN.md) |
| **Gate G-RC (Thu 31 Dec 17:00)** | Full checklist in presentation plan §4.6 (`V3_PRESENTATION_PLAN.md`); anything failing is hidden via `/capabilities` and listed as a limitation |
| **ED breakdown** | viewer completion + 375 px 1.0 · whole-system regression + performance/memory 0.75 · reproducibility audit (every shown number traced to a package) 0.75 · documentation set 0.75 · recorded evaluation runs 0.5 · local release dry-run 0.25 · final security review 0.25 = **4.25** |
| **Dependencies** | Everything funded; freeze (G-FF Wed 30 Dec 18:00 proposed) |

### 3.11 Showcase preparation — Mon 4 – Wed 6 January 2027 (2.5 ED)

Rehearsal 1 (Tue) and Rehearsal 2 (Wed) on the presenting machine, cold start and offline; fallback-ladder drills for each live step, including a deliberate AI-provider failure and a deliberate simulation failure; claims-register freeze; checksums. Showcase **Thu 7 Jan 2027** (proposed).

---

## 4. Gates

Decision owner for every gate is the **PO** unless stated; the Engineer assembles the evidence. A gate that fails never passes by omission: the failure outcome is applied.

| Gate | Date (proposed) | Measurable acceptance criteria | Required evidence | If it fails |
| --- | --- | --- | --- | --- |
| **G-V2** V2.0 release | Fri 23 Oct | Audit §7: dimensions 1–5 all PASS, or each non-PASS row is in the accepted-gap register with the PO's written acceptance | Evidence pack on the gate commit | Phase B does not start; dates slip day for day |
| **G-D** V3.0 design approval | Fri 23 Oct (same review) or Mon 26 Oct | PO approves strategy §2, §5–§8, §13–§15 and decisions D1, D3–D7, D-SCOPE, D-AG1, D-SR1 | Marked-up documents; decision log | B0 is spent on design; dates slip one-for-one |
| **G-PF** Preview freeze | Tue 27 Oct 12:00 | Preview acceptance checks (§5) pass for the chosen option; fallback assets generated | Acceptance run log; checksums | Next-lower option (§5.2) |
| **G-PV** Preview go/no-go | Wed 28 Oct 17:00 | Two rehearsals ≤ 14 min, one cold-start and offline; benchmark recorded (B0-1); suites green on the preview commit; every claim in the register | Rehearsal notes; benchmark; checksums | Fallback ladder (presentation plan §2.6) |
| **G-R1** Robustness slice | Thu 5 Nov | W1 gate (§3.2) | Test output; demo recording; re-forecast | W2 delayed one-for-one; re-forecast presented |
| **G-SR** Signalised-roundabout safety | Thu 12 Nov | W2 gate (§3.3): bit-identity, collision, deadlock, starvation, spillback green | Slow-suite run; benchmark; demo | ✅ Technical criteria verified 2026-10-21; PO sign-off pending |
| **G-CS** Composable strategies | Thu 19 Nov | W3 gate (§3.4) | Parity test; compat table | Registry limited to built-ins; documented |
| **G-AG** Aggression default | Wed 25 Nov 17:00 | W4 gate (§3.5) | Matrix report; parity test | Default **not** merged; W4 not shown |
| **G-INT** Interim presentation | Wed 25 Nov 17:00 | Presentation plan §3.3: every shown result from a gate-passed feature, in the claims register, with a tested fallback | Claims register; rehearsal note | Segment becomes design-only |
| **G-AI-A** Copilot | Thu 3 Dec | Strategy §15.1.7 C1–C9 | Evaluation report; adversarial log | Ships as deterministic assistant; AI claim withdrawn |
| **G-AI-B** Discovery Lab | Thu 10 Dec | Strategy §15.2.8 D1–D10 | Evaluation report; fuzz and spy-test output | Held back as "experimental, not released" |
| **G-B1** Core research workflow stable | Thu 17 Dec | PA-1…PA-7 (full forms); security regression green; tampered package rejected; resume equivalence; no open P1 | Test output; recorded acceptance run | W8 cancelled; capacity to fixes |
| **G-E** Emergency / priority readiness | Any date the PO calls | Strategy §9.2 criteria (1)–(4), including ≥ 4.5 ED unallocated | Capacity table; design note | **Expected outcome:** deferred past V3.0 (D8) |
| **G-W8** Stress-test week | Thu 24 Dec (go/no-go for starting: Fri 18 Dec) | W8 gate (§3.9) | Tests; classification on planted failures | Week cancelled, capacity reassigned |
| **G-FF** Feature freeze | Wed 30 Dec 18:00 | All funded items merged or formally dropped | Merge list | Items not merged are dropped, not rushed |
| **G-RC** Release-candidate acceptance | Thu 31 Dec 17:00 | Presentation plan §4.6 checklist | Evidence pack | Hide affected features via `/capabilities`, list as limitations |
| **G-SHOW** Showcase go/no-go | Wed 6 Jan 2027 17:00 | Two rehearsals ≤ 25 min; fallbacks drilled; claims register frozen | Rehearsal notes | Fallback ladder; present what is verified |
| **G-PROD** Production deployment | Any time, **separately authorised** | Written PO authorisation naming the commit; audit R6.1–R6.3 | Deployment run, `/api/version`, smoke-test record | "Released, not deployed" |

---

## 5. End-to-end preview acceptance

The preview cannot be called ready because individual features exist. It must pass an **end-to-end workflow** that proves seven things. Which form applies depends on the preview option (§5.2).

### 5.1 Acceptance checks

| # | The workflow must prove | Form for **PV-1** (default; V2.0 mechanisms) | Form for **PV-2** (adds a V3.0 prototype) and for the interim (26 Nov) and final (7 Jan) presentations |
| --- | --- | --- | --- |
| PA-1 | An experiment can be **submitted through a supported interface** | A planning study submitted through the planner UI **and** through the documented API (`scripts/v2_demo.py`-style call) | Robustness experiment submitted through the Python client or `/api/v3/experiments` |
| PA-2 | The **same experiment can be inspected in the UI** | Open the study by id in the planner after reload | Open `/app/experiments/<id>` for the client-submitted experiment |
| PA-3 | Results include **uncertainty and limitations** | Paired intervals across seeds, tie handling, validity banner, caveats. **Labelled as seed-to-seed uncertainty, not parameter uncertainty** | Full output of strategy §5.8, including assumptions, N/r/total runs, eligibility and real-world validity |
| PA-4 | A **portable export can be exported and verified** | V2.0 report (JSON/MD/CSV) with fingerprints; verified by the `reproduce` action. **`.ufpkg` is not claimed** | `.ufpkg` export; `verify` accepts it and **rejects a tampered copy**; replay class reported |
| PA-5 | **Provenance and reproducibility metadata** are available | Commit, scenario/result fingerprints, seeds visible | Full manifest (strategy §6), exact/comparable/differs |
| PA-6 | **Failure, cancellation and incomplete runs** are handled safely | A failed job shows its error; the 2-job cap is explained; **cancellation is stated as not supported in V2.0** | Cancel mid-run leaves a consistent *incomplete* result; resume reproduces the uninterrupted fingerprint; failed runs exclude their condition and are counted |
| PA-7 | A **precomputed fallback exists and is tested** | Precomputed study + exports, opened by id; recorded video; fallback exercised in a rehearsal | Same for the experiment and package; `verify` re-run on the fallback package |

### 5.2 Preview options (decision D-PV — the PO decides)

| Option | Content | Feasibility given the gating rule | Recommended |
| --- | --- | --- | --- |
| **PV-1** | V2.0 closure demonstrated end to end (PA forms in the PV-1 column) **plus a V3.0 design walkthrough** (statistical contract, manifest, priorities, deferred list). No V3.0 result is shown | Fully feasible if G-V2 passes by Fri 23 Oct | **Yes (default)** |
| **PV-2** | PV-1 **plus** a labelled *design prototype* of the Robustness sampler (B0-5): the sampled conditions table, unit-tested. No simulation results claimed | Feasible only if G-V2 and G-D pass by Fri 23 Oct and B0-5 tests pass by Tue 27 noon | Optional upgrade |
| **PV-3** | Ask the stakeholders to move the preview so a real V3.0 slice (Robustness core + viewer, ~B1–B2) can be shown | Needs an external decision; preview would move to about Thu 12 Nov | Alternative if a V3.0 demonstration is mandatory |

Choosing "full V3.0 slice on 29 Oct" is **not** offered: it would require starting V3.0 before V2.0 closes or compressing V2.0 closure below its estimate, both of which are rejected.

### 5.3 Performance assumptions

Any runtime in this plan is **unverified** until measured on the intended presentation machine (task B0-1). Until then the demo uses precomputed assets for anything slower than a few seconds, and live runs are limited to the small planner study whose duration is measured in rehearsal.

---

## 6. What is explicitly deferred (and where it goes)

| Item | Status | Where recorded |
| --- | --- | --- |
| Learned (DQN/RL) controllers | Deferred; would enter through the registry as `experimental` | Strategy §9.1 |
| Phased-priority signalised roundabout (`phased_priority`) | Conditional/stretch; not scheduled | Strategy §13.3 |
| Bus / emergency priority control, emergency pre-emption | Gate G-E; expected deferral | Strategy §9.2 |
| Strategy DNA visual composer, Traffic Regime Discovery, Incident and recovery, AI report generator, full explainable-comparison UI, demand-surge scenarios | Deferred | Strategy §16 |
| CSV import, GeoJSON export, arms-GeoJSON | Conditional on capacity freed by dropping W8 | Strategy §9.3 |
| PWA | Unfunded stretch | Strategy §9.4 |
| Field-data planner step, parameter tuning, real data case study | Accepted-gap candidates (audit §7.8) | Audit |
| Job cancellation in V2.0 | Accepted gap; supplied by Robustness (W7) | Audit §7.8 |

## 7. Scope-reduction ladder (cut in this order; each step keeps a complete, honest release)

1. **W8** Chaos/Breakpoint (4.25 ED) — first to go on any slip.
2. **Adaptive signalised roundabout** (1.5 ED, inside W3).
3. Viewer charts → tables; standard evaluation presets → smaller presets with *indicative* labels.
4. **Copilot LLM adapter** → ship the deterministic assistant only (AI-feature count becomes one; the PO is told).
5. PATs → keep Cognito sessions only and document the API as trusted-network (the client still works with the development token).
6. **Discovery Lab** → ship the harness and baselines evaluation without the search (not recommended; the feature is then not an AI feature).

**Never cut:** the V2.0 gate, ownership/privacy tests, the statistical contract's guardrails and wording, the manifest and verification, the limitations pages, the AI validation boundary and quotas, the aggression-profile fingerprint rule, the `EntryGate` bit-identity test.

## 8. GitHub issue map (synchronised)

Dates are proposed; every issue carries the status "PLANNED — blocked by the V2.0 release gate (#142 / #149)". Milestones and issue descriptions mirror this table. **Owner** is shown only where the project owner assigned it on 2026-10-12; new issues are unassigned until confirmed.

| Issue | Title | Week / dates | Funding | Priority | Milestone |
| --- | --- | --- | --- | :-: | --- |
| [#150](https://github.com/Viraj281105/Traffic-Simulation/issues/150) | **V3.0 umbrella:** composable, AI-assisted traffic-control experimentation platform | Phase B | — | — | V3.0 W9: Release candidate & showcase |
| [#151](https://github.com/Viraj281105/Traffic-Simulation/issues/151) | Robustness Lab: uncertainty sampling, paired ensembles and analysis | W1 (+ completions W3, W4, W7) | Committed | P0 | V3.0 W1: Robustness Lab slice |
| [#152](https://github.com/Viraj281105/Traffic-Simulation/issues/152) | Robustness Lab: experiment viewer, assumption labelling, limitations | W1 minimal, W9 complete | Committed | P0 | V3.0 W1: Robustness Lab slice |
| [#163](https://github.com/Viraj281105/Traffic-Simulation/issues/163) | **Signalised roundabouts** (`metered_entry`) | W2 · Fri 6 – Thu 12 Nov | Committed (flagship) | P0 | V3.0 W2–W4: Control strategies & aggression |
| [#162](https://github.com/Viraj281105/Traffic-Simulation/issues/162) | **Composable Traffic-Control Strategies:** registry, compatibility, fingerprints | W3 · Fri 13 – Thu 19 Nov | Committed | P0 | V3.0 W2–W4: Control strategies & aggression |
| [#156](https://github.com/Viraj281105/Traffic-Simulation/issues/156) | Safe strategy / plugin interface (no uploaded code) | W3 | Committed | P1 | V3.0 W2–W4: Control strategies & aggression |
| [#164](https://github.com/Viraj281105/Traffic-Simulation/issues/164) | Adaptive signalised roundabouts | W3 (conditional on G-SR) | Conditional | P1 | V3.0 W2–W4: Control strategies & aggression |
| [#165](https://github.com/Viraj281105/Traffic-Simulation/issues/165) | **High driver aggression default** | W4 · Fri 20 – Wed 25 Nov | Committed | P0 | V3.0 W2–W4: Control strategies & aggression |
| [#166](https://github.com/Viraj281105/Traffic-Simulation/issues/166) | **AI Traffic Experiment Copilot** | W5 · Fri 27 Nov – Thu 3 Dec | Committed; AI claim conditional on D-AI1 | P0 | V3.0 W5–W6: AI features |
| [#157](https://github.com/Viraj281105/Traffic-Simulation/issues/157) | **AI Control Strategy Discovery Lab** (re-scoped from "Control Lab") | W6 · Fri 4 – Thu 10 Dec | Committed | P0 | V3.0 W5–W6: AI features |
| [#153](https://github.com/Viraj281105/Traffic-Simulation/issues/153) | `/api/v3` experiments (W1 base) and Python SDK (W7) | W1, W7 | Committed (min.) | P1 | V3.0 W7–W8: Platform & stress testing |
| [#154](https://github.com/Viraj281105/Traffic-Simulation/issues/154) | Personal access tokens, scopes, expiry, revocation and quotas | W7 · Fri 11 – Thu 17 Dec | Committed (min.) | P1 | V3.0 W7–W8: Platform & stress testing |
| [#155](https://github.com/Viraj281105/Traffic-Simulation/issues/155) | `.ufpkg` packages, integrity verification, provenance, reproducibility manifests | W7 | Committed (min.) | P1 | V3.0 W7–W8: Platform & stress testing |
| [#167](https://github.com/Viraj281105/Traffic-Simulation/issues/167) | Traffic Chaos and Stress-Test Lab | W8 · Fri 18 – Thu 24 Dec (conditional) | Conditional | P2 | V3.0 W7–W8: Platform & stress testing |
| [#168](https://github.com/Viraj281105/Traffic-Simulation/issues/168) | Strategy Breakpoint Explorer | W8 (conditional) | Conditional | P2 | V3.0 W7–W8: Platform & stress testing |
| [#158](https://github.com/Viraj281105/Traffic-Simulation/issues/158) | CSV turning-count import and GeoJSON export | Only with capacity freed by dropping W8 | Conditional | P3 | V3.0 W9: Release candidate & showcase |
| [#159](https://github.com/Viraj281105/Traffic-Simulation/issues/159) | Emergency-vehicle pre-emption (and bus/emergency priority) | Gate G-E; expected deferral | Not funded | — | V3.0 W9: Release candidate & showcase (decision only) |
| [#160](https://github.com/Viraj281105/Traffic-Simulation/issues/160) | Responsive read-only views (PWA stretch) | W9 | Committed (folded into #152 acceptance) | P3 | V3.0 W9: Release candidate & showcase |
| [#161](https://github.com/Viraj281105/Traffic-Simulation/issues/161) | Integration, regression, evaluation studies, documentation, RC and showcase | W9 · Fri 25 – Thu 31 Dec; showcase Thu 7 Jan | Committed | P0 | V3.0 W9: Release candidate & showcase |

V2.0 issues #142 – #149 are **unchanged by this revision** and stay open until the V2.0 release gate is formally approved (#142 via #149). V2.0 milestone: "V2.0: Release gate", proposed due date Fri 23 Oct 2026.

## 9. `ROADMAP.md` synchronisation required (not performed)

`docs/ROADMAP.md` is **not modified** by this revision (decision D7 is open). On approval, the owner should: add a V3.0 section (its §7) listing the committed items of strategy §2 and the conditional/deferred sets; move Future Scope items FS-1 (emergency), FS-2 (AI control: replaced by the Discovery Lab, with learned controllers remaining in Future Scope) and FS-6 (uncertainty) without duplication; update the V1.x/V2.0 status rows (V2.0 statuses are covered by audit R4.2); and add the signalised roundabout, strategy registry, driver-aggression profile and the two AI features to the capability matrix (§5) as **PLANNED**, not implemented. Until then the roadmap and these four documents intentionally differ and this section is the record of the difference.

## 10. Unresolved decisions that move the schedule

| Decision | Owner | Impact if late |
| --- | --- | --- |
| D-V2-0 name roles; D-V2-1…6 (audit §7.11) | PO | Phase A rows blocked; each day late slips G-V2 a day |
| **D-SCOPE** extended calendar (E) or 26 Nov (S) | PO | Defines the entire Phase B; decide by Fri 23 Oct |
| D-PV choose preview option (§5.2) | PO | Preview content undefined; decide by Fri 16 Oct |
| G-D design approval incl. D-AG1/D-AG2, D-SR1 | PO | B0 absorbs design; Phase B slips |
| **D-AI1** LLM provider, budget and data handling | PO | W5's AI claim; decide before Fri 27 Nov |
| D6 confirm capacity and holiday availability | PO | Every date |
| D4 Python version | PO | Exact-replay claims in the manifest |
| D2 NumPy | PO | Not needed by this plan |
| D8 accept emergency deferral | PO | Frees nominal capacity |
