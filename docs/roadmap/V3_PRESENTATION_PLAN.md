# V3.0 Presentation Plan — Preview (29 October), Interim Presentation (26 November) and Final Showcase (7 January 2027)

> **Status:** PROPOSED — **revision 3** (creative expansion, 2026-10-12) · dates and run times are *proposed / unverified* until approved and measured
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)
> **Authority:** [`docs/ROADMAP.md`](../ROADMAP.md) is the authoritative roadmap.
> **Direction of dependence:** *this plan follows the implementation; it never drives it.* A demo segment exists only if the capability behind it has passed its acceptance checks. No claim in this document justifies building anything.

### What changed in revision 3

* **Three events, not two.** Preview Thu 29 Oct (unchanged: V2.0 closure + V3.0 design), **interim presentation Thu 26 Nov** (what W1–W3, and W4 only if its gate passed, actually delivered), **final showcase Thu 7 Jan 2027** (the full demonstrable set). The sprint plan explains why the original single 26 Nov presentation cannot hold the expanded scope.
* **New demonstrations:** a **signalised-roundabout experiment**, **High driver aggression shown as a declared model assumption**, and **both AI features** end to end — each with a verified fallback for live AI or simulation failure.
* **New label sets:** AI-generated vs measured content (§4.2), aggression profile, EXPERIMENTAL candidates.
* **Rule unchanged:** only implemented features are demonstrated; everything else is shown as **PLANNED** on a status slide.

---

## 1. Principles and capability status

1. **Show only what runs, and say how sure we are.** Anything experimental is labelled on screen and aloud.
2. **Evidence, not a verdict.** No "best", "optimal", "proves", "wins", "calibrated", "AI-verified", "AI-optimised" (except the narrow phrase *engine capacity calibration*, explained).
3. **Every number has an address:** package or study id → fingerprint → N conditions / r replications / total runs → assumptions → limitation. A number without a row in the claims register (§5) is cut.
4. **Two labels, always separate:** *Robustness eligibility* and *Real-world validity* (default: **None — assumptions only**).
5. **Inputs are labelled** `assumed`, `observed` or `user`. **Driver aggression is a declared assumption, not data.**
6. **AI content is labelled and separated:** model-generated text is shown in a distinct panel titled "Model-generated interpretation"; measured numbers are in the table beside it. A language model is never shown as connected until its evaluation passed.
7. **Every live step has a pre-tested fallback** that looks the same to the audience, including a deliberate **AI-provider failure** and a deliberate **simulation failure**.
8. **Rehearse on the presenting machine, offline, from a cold start.**

### Capability status as of 12 October 2026 (the source of truth for what may be claimed)

| Capability | Status today | Evidence required before it may appear in a demo | Claim allowed now |
| --- | --- | --- | --- |
| V2.0 planning API (backend) | **Implemented, tested** (21 s scripted run; `reproduced=True`) | Gate rows R2.1–R2.6 on the gate commit | "The backend exists and ran end to end" |
| V2.0 planner UI | **NOT IMPLEMENTED** (audit R1.1 FAIL) | R1.1, R2.7, R2.8 PASS | None |
| Access control / private data | **Defects open** (audit R1.2–R1.4, R3.3–R3.5 FAIL) | R3.x PASS | None |
| Calibration framework (API) | **Implemented** (level 0, strategy §8) | — | "A framework exists"; **no** validation or calibration claim |
| Robustness Lab (sampler → analysis → viewer) | **PLANNED** (W1) | Strategy §5 contract tests; PA-1…PA-7 | "Designed; here is the contract" |
| Signalised roundabouts | **PLANNED** (W2). **Does not exist in the code** (verified: geometry types are fixed-time signal and roundabout; adaptive + roundabout is rejected by validation) | Gate G-SR: bit-identity, collision, deadlock, starvation, spillback | "Designed; here is the safety argument" |
| Composable strategies / registry | **PLANNED** (W3) | Gate G-CS: fingerprint parity, compat rules | "Designed" |
| Adaptive signalised roundabout | **PLANNED, conditional** (W3, after G-SR) | Oscillation tests | None |
| High driver aggression default | **PLANNED** (W4). **No aggression parameter exists** (verified; only `aggressiveTwoWheelers` and `unstructuredTraffic`, both default off) | Gate G-AG | "Designed; defined in terms of IDM parameters; default `standard` for stored scenarios" |
| AI Traffic Experiment Copilot | **PLANNED** (W5). No LLM integration exists | Gate G-AI-A, provider decision D-AI1 | "Designed; proposal-only, validated by the backend" — **no claim that a model is connected** |
| AI Control Strategy Discovery Lab | **PLANNED** (W6) | Gate G-AI-B | "Designed; an optimisation search, evaluated on held-out seeds" |
| `.ufpkg` / manifest / verify | **PLANNED** (W7) | Verify rejects a tampered package | "Designed" |
| Python client, tokens, quotas | **PLANNED** (W7) | Security regression tests | "Designed" |
| Chaos / Breakpoint | **PLANNED, conditional** (W8) | Gate G-W8 | None |
| CSV / GeoJSON | **PLANNED, conditional** | — | None |
| Emergency / priority control | **PLANNED, expected to defer** (G-E) | — | None |
| Production deployment | **Not verified** (two failed runs on 9 Oct; fix on `main` but not on `deployment`) | R6.1–R6.3 | State the true status |

---

## 2. Preview — Thursday 29 October 2026

### 2.1 Options (decision D-PV, product owner; recommended: PV-1)

| Option | What is shown | Needs |
| --- | --- | --- |
| **PV-1 (default)** | V2.0 closure demonstrated end to end, then a **design walkthrough** of the V3.0 plan: statistical contract, manifest, priorities, deferred list. **No V3.0 result is shown** | G-V2 passed by Fri 23 Oct |
| PV-2 | PV-1 plus a **labelled design prototype** of the Robustness sampler (a table of sampled conditions from a seeded specification; unit tests passing). No simulation results | G-V2 and G-D passed; sampler skeleton tests green by Tue 27 Oct 12:00 |
| PV-3 | Move the preview so a real V3.0 slice can be shown (about Thu 12 Nov) | Stakeholders' agreement; PO decision |

If G-V2 has not passed by Wed 28 Oct, the preview reports **V2.0 status honestly** — which gate rows pass, which do not, and the dates — rather than demonstrating unverified work.

### 2.2 What the audience should leave with (PV-1)

1. V2.0's backend was complete but had no front door; it now has one, with other users' data protected, **or** here is exactly what is still open.
2. V3.0 will treat *"how stable is the answer under assumed uncertainty?"* as the unit of evidence, with a published statistical contract and a verifiable package format.
3. What is funded, what is conditional, what is deferred — and why.

### 2.3 Demo flow — 14 minutes + 6 minutes Q&A (PV-1)

The timings sum to 14:00 and include time for one fallback switch; the live segments are bounded.

| Time | Segment | Content | Live or recorded | Fallback |
| --- | --- | --- | --- | --- |
| 0:00–1:30 | **Status** | One slide: the V2.0 gate result (rows PASS/accepted-gap/open), the V3.0 plan in one line, what is *not* claimed | Slide | — |
| 1:30–4:30 | **Planner: build and run** | Choose a preset scenario; pick fixed-time / adaptive / roundabout; show the **pre-run cost** (number of simulations; time shown only if measured). Run the small study | **Live, bounded** — only if the rehearsal-measured duration on this machine is ≤ 45 s on three consecutive runs | Open the precomputed study by id (same page) |
| 4:30–7:30 | **Planner: read the evidence** | Comparison table with paired intervals; a tie shown as *inconclusive*; findings with their evidence paths; the validity banner ("not field-calibrated"); caveats. **State aloud:** the intervals describe seed-to-seed variation for one scenario, **not** uncertainty about demand or driver behaviour | Precomputed | Static capture |
| 7:30–9:30 | **Provenance and reproduce** | Source commit, scenario and result fingerprints, seeds; press *Reproduce* | Live if the same ≤ 45 s rule holds | Recorded clip |
| 9:30–10:30 | **Protection of data** | Slide of the recorded gate test output: second user gets 404 for the first user's study, anonymous access refused | Slide | — |
| 10:30–11:30 | **Export** | Download JSON / Markdown / CSV. State: a verifiable portable package (`.ufpkg`) is **planned**, not available | Live download | Files on disk |
| 11:30–13:30 | **V3.0 design walkthrough** | Slide 1: *conditions vs replications vs runs* (e.g. "100 conditions × 3 alternatives × 2 replications is 600 runs but **100** conditions"). Slide 2: win/tie/loss, regret, flip definitions; eligibility checklist; *eligibility ≠ real-world validity*. Slide 3: manifest and exact vs comparable replay. Slide 4: funding table | Slides | — |
| 13:30–14:00 | **Limits and the ask** | Limitations; decisions pending; gaps accepted | Slide | — |
| 14:00–20:00 | Q&A | | | |

**Optional PV-2 addition (inside 11:30–13:30, ≤ 1 minute):** show the sampler's condition table, labelled **"design prototype — no simulation results"**.

### 2.4 Preview acceptance (end to end)

The preview is ready only when the **PV-1 column of the preview acceptance table** (sprint plan §5.1, checks PA-1 … PA-7) has passed on the presenting machine:

1. a study is submitted through the planner **and** through the documented API;
2. the same study opens by id after a reload;
3. results show intervals, tie handling, the validity banner and caveats, labelled as seed-to-seed uncertainty;
4. the V2.0 report exports and `reproduce` verifies it (`.ufpkg` not claimed);
5. commit, fingerprints and seeds are visible;
6. a deliberately failing job shows its error, the job cap is explained, and cancellation is stated as unsupported;
7. the precomputed study, its exports and the recorded video exist, were generated on the preview commit, are checksummed, and the fallback was used in a rehearsal.

### 2.5 Data and scenario preparation

| Item | Specification | Status |
| --- | --- | --- |
| Demo scenario | Four arms, one lane each, cars only, a signalised baseline, alternatives fixed-time / adaptive / roundabout — chosen because the engine's own one-lane capacity calibration applies (this is the existing, narrow *engine capacity calibration*, **not** field calibration) | To be created in W1 testing |
| Live study size | Small enough to meet the 45 s rule (the earlier scripted run of 9 simulations of 60 s ran in about 21 s *for the whole demo script* on the development machine) | **Unverified on the presenting machine** — benchmark task B0-1 |
| Precomputed assets | Study id, JSON/MD/CSV exports, screenshots, video, checksums — all from the **preview commit** | B0-3 |
| Machine | The presenting laptop; local backend with `DEV_AUTH_BYPASS=1`; production build served locally; no AWS, no Cognito, no internet required (the UI loads Roboto from Google Fonts and falls back to system fonts offline; layout is checked in the offline rehearsal) | Rehearsal 2 |

### 2.6 Fallback ladder and recovery steps

| Level | Trigger | Recovery action |
| --- | --- | --- |
| F0 | Normal | Live bounded run |
| F1 | Live run exceeds 45 s, errors, or the machine is slow | Say "here is one I ran earlier"; open the precomputed study by id — same page |
| F2 | UI fails | Show the exported JSON/Markdown and the API response in a terminal |
| F3 | Backend will not start | Play the recorded video; show checksums |
| F4 | Laptop fails | Backup laptop (same repository and assets) or the video from a USB stick |

Each level was **exercised in a rehearsal**; an untested fallback is not a fallback.

### 2.7 Hardest expected questions (honest answers, prepared)

1. *"Is it calibrated to real traffic?"* No. A comparison framework exists (level 0); no real observations have been run; no parameter tuning exists.
2. *"What uncertainty do the intervals show?"* Seed-to-seed variation for one scenario. Parameter uncertainty is the planned Robustness Lab, not yet built.
3. *"Is the public site running this?"* Not verified. Two production deployments failed on 9 Oct; the fix is on `main` but not on the deployment branch; redeployment needs authorisation.
4. *"Why isn't the V3.0 demo live?"* V3.0 implementation starts only after V2.0 passes its gate; that left three working days before today.
5. *"Does the roundabout win?"* UrbanFlow does not rank; here are the intervals and the conditions.
6. *"Is my data private?"* Planning studies are per-user and tested; the other areas were fixed in Phase A — here is the test output (or "still open", as the gate says).

### 2.8 Preview gates and rehearsals

| Gate / event | When | Criteria (full detail: sprint plan §4) |
| --- | --- | --- |
| **G-V2** | Fri 23 Oct | Dimensions 1–5 of the V2.0 gate PASS or accepted in writing |
| **G-PF** preview freeze | Tue 27 Oct 12:00 | PA checks pass; fallback assets exist |
| Rehearsal 1 | Tue 27 Oct | Timed, presenting machine |
| Rehearsal 2 | Wed 28 Oct | Cold start, **network disabled**, F0 → F1 → F3 drilled; a second person asks the §2.7 questions if available |
| **G-PV** go/no-go | Wed 28 Oct 17:00 | Two rehearsals ≤ 14 min; benchmark recorded; claims register complete; suites green on the preview commit |
| **Preview** | Thu 29 Oct | |

---

## 3. Interim presentation — Thursday 26 November 2026

**Purpose.** Report what four implementation weeks (W1–W4) really delivered. This replaces the earlier plan of a single "full presentation" on this date, which the capacity analysis (sprint plan §1.4) shows cannot hold the expanded scope. If the PO chooses Option S (26 Nov final, no AI), this becomes the final presentation with the W1–W4 scope.

### 3.1 Content by gate outcome

| Segment | Shown live or from recorded evidence only if… | Otherwise |
| --- | --- | --- |
| **Robustness Lab vertical slice** (W1) | G-R1 passed | Shown as design (contract slides) |
| **Signalised-roundabout experiment** (W2) | G-SR passed | Shown as design with the safety argument and the test plan |
| **Composable strategies** (W3): registry, a rejected combination and its explanation, an unchanged fingerprint | G-CS passed | Design |
| **Adaptive signalised roundabout** | Conditional segment passed its oscillation tests | Not shown |
| **High aggression as a declared assumption** (W4) | G-AG passed by **Wed 25 Nov 17:00** | Design only; the demo declares today's behaviour as `standard` |
| AI Copilot, Discovery Lab, platform, stress testing | — | **PLANNED** status slide with dates; no demonstration |

### 3.2 Demo flow — 20 minutes + 10 minutes Q&A (segments marked † are conditional)

| Time | Segment | Content | Fallback |
| --- | --- | --- | --- |
| 0:00–2:00 | **Where we are** | V2.0 gate result; the revised calendar and why; funded vs conditional vs deferred | — |
| 2:00–7:00 | **Robustness slice** | Open a precomputed study: design line, assumptions with `basis`, win/tie/loss, eligibility checklist, real-world validity line | Precomputed study by id |
| 7:00–13:00 | **Signalised roundabout** | Same demand, three strategies; queues and signal states on the canvas; paired comparison with intervals; the **declared limitations**; state aloud that no real-world superiority is claimed | Recorded clip + precomputed comparison |
| 13:00–16:00 | **Composable strategies** | Assemble a strategy from the summary card; a rejected combination with its explanation; fingerprint parity of an old scenario | Static capture |
| 16:00–18:00 † | **High aggression** | `standard` vs `high` on one scenario, with the profile and its parameter values visible in the report | Static capture |
| 18:00–20:00 | **Limits and what comes next** | Limitations; AI features are designed, not built; dates | — |
| 20:00–30:00 | Q&A | | |

### 3.3 Acceptance for the interim presentation

Every shown result comes from a gate-passed feature, is in the claims register (§5) and is generated on the interim commit; a precomputed fallback exists for every live step; one rehearsal on the presenting machine, cold and offline. Gate **G-INT (Wed 25 Nov 17:00)**: these conditions met; otherwise the segment becomes design-only.

---

## 4. Final showcase — Thursday 7 January 2027

### 4.1 The end state this plan can support

Scoped to the **funded** items in the strategy; conditional items appear only if they passed their gates.

| Aspect | Definition |
| --- | --- |
| **Committed (must be demonstrable)** | V2.0 closed (planner, protected data, documentation) · **Robustness Lab** with viewer · **Signalised roundabouts** (`metered_entry`) with regression evidence · **Composable strategy registry** · **High driver aggression default** · **AI Traffic Experiment Copilot** (as an AI feature only if gate G-AI-A passed with a connected provider; otherwise as the deterministic assistant, said plainly) · **AI Control Strategy Discovery Lab** · **`.ufpkg` with manifest, verify, exact/comparable replay** · `/api/v3`, Python client, tokens with quotas and audit |
| **Conditional (shown only if it passed its gate)** | Adaptive signalised roundabout · Chaos Lab and Breakpoint Explorer · CSV import / GeoJSON export |
| **Not planned for 7 Jan** | Learned controllers; emergency/priority control; incidents; regime discovery; visual composer; PWA |
| **Primary user journey** | A planning officer asks a question in words → the Copilot proposes a validated experiment (with the backend's issues shown) → the officer inspects and confirms → results arrive with intervals, eligibility and the (absent) real-world validity → the officer exports a package → a colleague **verifies** it |
| **Research workflow** | From the Python client: run a Robustness study, a signalised-roundabout comparison and a Discovery search; inspect in the browser; cancel and resume; export, verify, classify replay |
| **Quantitative evaluation** | **E1** robustness study (fixed-time vs adaptive vs roundabout). **E2** signalised roundabout vs conventional roundabout vs signalised intersection under declared `high` aggression, across low/medium/saturated demand. **E3** a Copilot-proposed study (its proposal id, the backend issues, the confirmed run). **E4** a Discovery search on one declared regime with held-out re-evaluation **reported whatever the outcome**. No other study is promised |
| **Reproducibility** | Every number maps to a package; `verify` results shown with their replay class |
| **Limitations (own slide per feature)** | Assumed priors; headway scale is a proxy (no reaction delay in the engine); single junction; no field calibration; aggression is an assumption; safety proxies are model outputs; AI proposals can be wrong and are validated, not trusted; discovered candidates are tuned to this simulator; intervals treat conditions as exchangeable draws; determinism per revision and runtime; production status as verified |

### 4.2 Labels that must appear on every relevant slide

| Element | Required content |
| --- | --- |
| Design line | **"N conditions × r replications × K alternatives = total runs"**, each shown; inference is over **N** conditions |
| N_valid | Valid conditions after exclusions, with exclusion counts by reason |
| Inputs | Each factor with `basis` (assumed / observed / user) and rationale |
| **Driver aggression** | **"Driver aggression: high — a simulation assumption, not a measurement of real-world driver behaviour"**, with the parameter values or a link to them |
| **Strategy** | Strategy descriptor id and version, fingerprint; for signalised roundabouts the mode (`metered_entry`) |
| Primary indicator and tie tolerance | Stated before the results |
| Win / tie / loss | With 95 % intervals |
| Eligibility | The checklist; **"Eligible for robustness statements"** / **"Indicative"** / **"Exploratory"** |
| Real-world validity | **"None — assumptions only"** unless an observation record is attached |
| **AI-generated content** | Panel title **"Model-generated interpretation — numbers come from the measured table"**, provider/model id, proposal id; or **"Deterministic assistant — no language model used"** |
| **Discovered candidates** | **"EXPERIMENTAL — found by search under these conditions"**; tuning / selection / held-out seed counts; regimes; baselines on the same seeds; *including the cases where no candidate beat a baseline* |
| Safety proxies | **"Model proxy (hard-braking events, conflict counts), not a prediction of real-world crashes"** |
| Provenance | Source commit, dirty flag, fingerprints, seeds, runtime, **verification status and replay class** |

### 4.3 Demo script — 35 minutes + 10 minutes Q&A (segments marked † are conditional)

| Time | Segment | Content | Live or recorded | Fallback |
| --- | --- | --- | --- | --- |
| 0:00–2:00 | **Where we are** | V2.0 gate result; what shipped, what is conditional/deferred | Slide | — |
| 2:00–5:00 | **Planner journey** | Build, compare, read evidence and limits | Precomputed study | Static capture |
| 5:00–11:00 | **Signalised-roundabout experiment** | E2: three strategies under declared `high` aggression and uneven peak demand; signal states and queues on the canvas; paired intervals; decision events ("held red: ring spillback guard"); limitations | Short live run only if the benchmark allows; else precomputed | Precomputed E2 package; recorded clip |
| 11:00–13:00 | **Aggression as an assumption** | `standard` vs `high` on the same scenario; the profile, its parameter values and its fingerprint | Precomputed | Static capture |
| 13:00–19:00 | **AI Feature A — Copilot (end to end)** | Type the example question; the proposal appears with fields tagged `rule`/`model`; the backend flags an invalid choice and offers a valid alternative; inspect the diff and cost estimate; **confirm**; show the measured results from E3; read the separate model-generated interpretation and point to its grounding | **Live proposal** (provider call) with the deterministic proposer as an immediate switch; results precomputed | **Provider failure drill:** the UI says "AI assistance unavailable", the deterministic proposer produces the same validated proposal, the template summary appears |
| 19:00–25:00 | **AI Feature B — Discovery Lab** | E4: the regime, the search budget, the Pareto set, the **held-out** re-evaluation against the three baselines, the preference-change table, the saved candidate; say where a candidate did **not** beat a baseline | Precomputed (live search is not attempted unless benchmarked) | Recorded terminal + package; if a second AI segment cannot run, this one is shown from the recorded package |
| 25:00–29:00 | **Portability and external access** | Export `.ufpkg`; `verify` passes; a **tampered copy is rejected**; replay class; the client with a scoped, expiring token; quota refusal; audit entry | Recorded terminal / live if safe | Recorded |
| 29:00–31:00 † | **Stress test and breakpoints** | A failure table and one breakpoint with its uncertainty and grid | Precomputed | Static capture |
| 31:00–33:00 † | **CSV import** | Plumbing, not validation | Recorded | — |
| 33:00–35:00 | **Limits and readiness** | One limitations slide per feature; test and security summary; deployment status stated plainly | Slide | — |
| 35:00–45:00 | Q&A | | | |

If a † segment did not pass its gate, its time is returned to the portability and AI segments; nothing is shown that was not accepted. **If both AI features are implemented, both are demonstrated** (A live-with-fallback, B from recorded evidence); **if only one passed its gate**, it is shown and the other is stated as not delivered.

### 4.4 Evidence requirements

* **Claims register** (§5, also an appendix slide): `claim → package/study/proposal id → fingerprint → N / r / total runs → regime or conditions → limitation sentence → verification status → who checked`. A slide number without a row is removed.
* Every chart caption carries the design line, scenario fingerprint, aggression profile and source commit.
* **Language check** by someone other than the author, or a scripted search for *best, optimal, proves, wins, calibrated, validated, robust, AI-verified, optimised, safe, safer* (each use must match §4.2 or the narrow engine-capacity phrase).
* **Test summary slide** — backend non-slow **and slow**, frontend ×3, lint, types, formatting, schema validation, contract test, production build, axe, coverage, **AI evaluation results (C1–C9, D1–D10)** — each with date and commit. Items not run are shown as **NOT RUN**, not omitted.
* **AI evaluation slide:** `copilot-eval-v1` results *including* the deterministic baseline and the cases that failed; Discovery acceptance table.
* **Runtime figures** are shown only if measured on the presenting machine; otherwise labelled "unverified".

### 4.5 Fallback plan

As §2.6, extended:

| Failure | Detection | Recovery |
| --- | --- | --- |
| AI provider down, slow, rate-limited or over budget | Timeout 20 s or error code | UI switches to the deterministic assistant; presenter says so; the pre-recorded Copilot clip is the second fallback |
| AI answer fails validation or grounding | Backend issues / grounding check | Show the issues (this is the validation boundary working); fall back to the stored proposal and summary |
| Live simulation too slow or fails | > 45 s or error | Open the precomputed result by id |
| Discovery search | Never run live unless benchmarked | Package replay (`verify`) and recorded terminal |
| Wi-Fi absent | Cold-start rehearsal | Provider segment uses the recording and the deterministic path; local backend needs no network |
| Backend will not start / laptop fails | As §2.6 F3, F4 | Video, backup laptop |

Every segment is independent, so a failed segment is skipped without breaking the next; the printed one-pager and the claims register let the talk continue without a screen. Each fallback is **exercised in a rehearsal**.

### 4.6 Readiness gates and final acceptance (G-RC, Thu 31 Dec 17:00; G-SHOW, Wed 6 Jan 17:00)

| Gate | When | Criteria |
| --- | --- | --- |
| G-R1 · G-SR · G-CS · G-AG · G-AI-A · G-AI-B | 5 Nov · 12 Nov · 19 Nov · 25 Nov · 3 Dec · 10 Dec | As the sprint plan §4 |
| **G-B1** core workflow stable | Thu 17 Dec | Full-form PA-1…PA-7; contract tests; tampered package rejected; resume equivalence |
| **G-FF** feature freeze | Wed 30 Dec 18:00 | Funded items merged or dropped |
| **G-RC** | Thu 31 Dec 17:00 | Checklist below |
| Rehearsals | Tue 5, Wed 6 Jan | Timed; one cold and offline; both AI-failure drills |
| **G-SHOW** | Wed 6 Jan 17:00 | Two rehearsals ≤ 35 min; claims register frozen |

**Final acceptance checklist (G-RC)** — each item PASS / FAIL / NOT RUN with evidence; any non-PASS is hidden via `/capabilities` and listed under limitations:

- [ ] V2.0 gate G-V2 passed (or its accepted gaps published).
- [ ] Backend non-slow **and slow** suites, frontend ×3, `ruff`, `mypy`, `prettier`, schema validation, OpenAPI contract test, **production build** green on the RC commit; coverage ≥ the project floor.
- [ ] Pre-existing determinism and reproduction tests unmodified and passing; the conventional-roundabout bit-identity test (`AlwaysOpen` gate) passing.
- [ ] Statistical-contract tests (hand-computed fixtures, planted flip, eligibility rules, exclusions, cancel/resume) green.
- [ ] Signalised-roundabout regression (collision, deadlock, starvation, spillback, layouts) green; benchmark recorded.
- [ ] Fingerprint-parity tests for the registry and the aggression profile green; defaults verified at every authoring boundary.
- [ ] **AI:** Copilot C1–C9 and Discovery D1–D10 measured and published; no AI claim beyond what passed; adversarial set results recorded; cost caps tested.
- [ ] Ownership, token, quota and audit tests green; no anonymous access to private data; AI keys absent from the browser bundle, logs and packages (scan).
- [ ] `.ufpkg` verify accepts an untouched package, rejects a tampered one, reports the replay class; ≥ 5 packages `verify` on a clean checkout (exact or documented comparable).
- [ ] axe: 0 serious/critical on the planner, experiment viewer, strategy card, Copilot and Discovery screens, token page; keyboard-only primary journey; 375 px read-only pages.
- [ ] Clean-checkout `docker compose` run passes.
- [ ] Two timed rehearsals ≤ 35 min, one cold and offline; benchmark recorded on the presenting machine.
- [ ] Claims register complete; language check done; limitations slides reviewed.
- [ ] Documentation set complete; `ROADMAP.md` and `README.md` agree with what shipped (PO-authorised edit).
- [ ] Production deployment status stated truthfully ("deployed and smoke-tested at commit …" or "not deployed").

### 4.7 Minimum viable versus conditional

| | Scope | Success without the rest |
| --- | --- | --- |
| **Minimum viable V3.0** | V2.0 closed · Robustness Lab · signalised roundabouts · registry · aggression default | The showcase succeeds with E1, E2 and the aggression demonstration |
| **Full committed set** | + both AI features · `.ufpkg` + manifest + verify + tokens/quotas | The target of this plan |
| **Conditional** | Adaptive signalised roundabout · Chaos/Breakpoint · CSV/GeoJSON | Each can be cut independently |
| **Not planned** | Learned policies · emergency/priority · incidents · regime discovery · visual composer · PWA | Not required |

---

## 5. Claims register (template — rows are filled as evidence is produced)

| Claim | Evidence id | Fingerprint | N / r / total runs | Conditions and assumptions (incl. aggression profile) | Limitation | Verification | Checked by |
| --- | --- | --- | --- | --- | --- | --- | --- |
| *(example, empty)* | | | | | | | |

Status of the register today: **empty** — no V3.0 result exists, so no V3.0 claim may be made.

## 6. Open decisions that affect the presentations

| Decision | Owner | Impact |
| --- | --- | --- |
| D-PV preview option (PV-1 / PV-2 / PV-3) | PO | Content of 29 Oct; decide by Fri 16 Oct |
| **D-SCOPE** extended calendar vs 26 Nov final | PO | Whether the 7 Jan showcase exists; decide by Fri 23 Oct |
| G-V2 outcome | PO | Whether the preview shows a finished or in-progress V2.0 |
| **D-AI1** LLM provider, budget, data handling | PO | Whether AI Feature A is demonstrated as an AI feature; decide before Fri 27 Nov |
| D-V2-4 production deployment authorisation | PO | What the deployment slide can say |
| D6 capacity and holiday confirmation | PO | Whether the 7 Jan date holds (else 14 Jan) |
| Availability of a second person for rehearsals | PO | Quality of the question drill; otherwise rehearsals are recorded and reviewed |
