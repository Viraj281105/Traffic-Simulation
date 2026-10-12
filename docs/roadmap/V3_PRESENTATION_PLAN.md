# V3.0 Presentation Plan — Preview (29 October) and Full Presentation (26 November)

> **Status:** PROPOSED — pending review · **Written:** 2026-10-12 · **Depends on:** [strategy](V3_PRODUCT_STRATEGY.md) and [sprint plan](V3_WEEKLY_SPRINT_PLAN.md)
> **Series:** [V2 completion audit](V2_COMPLETION_AUDIT.md) · [V3 product strategy](V3_PRODUCT_STRATEGY.md) · [V3 weekly sprint plan](V3_WEEKLY_SPRINT_PLAN.md) · [V3 presentation plan](V3_PRESENTATION_PLAN.md)

**This document contains no results.** Every number a presentation will show is produced by the sprints and traced to a package; the plan below names *which* numbers, in *what form*, and *what is said if they are unexpected*. Predicting outcomes here would be exactly the unsupported claim the product forbids.

---

## 1. Presentation principles

1. **Show only what runs.** Anything experimental is labelled on screen and in speech. Anything the backend only stubs is not shown.
2. **Evidence, not a verdict.** No slide says "best", "optimal" or "AI wins". Sentences take the form *"under these conditions, in this share of sampled cases, with this interval"*.
3. **Every number has an address:** package id → fingerprint → N → regime → limitation. Numbers without one are cut.
4. **The demo must survive failure.** Each live step has a pre-verified fallback that looks the same to the audience.
5. **Say what V2.0 and V3.0 do not do** — out loud, on one slide, before questions.
6. **Rehearse on the presenting machine, offline, cold.**

---

## 2. Preview — Thursday 29 October 2026

### 2.1 Three demo stories considered

| # | Story | Concrete problem | Intervention / experiment | Visible outcome | Evidence of credibility | Risk by 29 Oct | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **P1** | **"Does the answer survive uncertainty?"** — *driven from Python, inspected in the UI* | A council must choose between a fixed-time signal, an adaptive signal and a roundabout, but its traffic count is one day's data | Robustness ensemble over uncertain demand and driver headway, submitted by an external client through the SDK | A view of how often each option is better, the regret of choosing wrongly, and the demand level where the preference flips | Paired common-random-number design; guardrail badge; analytic tests; known-effect check against the documented V1.3 behaviour; verifiable package | Medium — compute time (mitigated: Quick preset + precomputed package) | **Selected** |
| P2 | "Learned versus conventional signal control" | Can a learned policy beat adaptive control? | Train/evaluate a policy against five baselines | A paired comparison table | Held-out seeds, strong baselines | **High** — the training and protocol land in S3, after the preview; any preview number would be premature | Rejected for the preview; appears as one labelled *environment-only* slide |
| P3 | "Emergency response through a junction" | How much time does pre-emption save and what does it cost others? | Pre-emption on a signal | Response-time saving and collateral delay | Safety suite | **Very high** — I-3 does not start until S4 | Rejected for the preview; shown as roadmap only |

**Selected: P1**, with the "external client" idea (the fourth candidate in the brief) built *into* it: the experiment is launched from a Python script and then opened in the browser. This demonstrates the platform direction (API + SDK + portable package) and a research capability (uncertainty) with one coherent story, using only code that exists and is tested by 23 October.

### 2.2 What the audience should leave with

1. UrbanFlow is now a platform you can script, not only a website.
2. A single-seed or single-scenario comparison is no longer the unit of evidence: *the question is how stable the preference is*.
3. Results travel as verifiable packages.
4. Learned control and emergency priority are coming, with honest evaluation — and V2.0's planner front door has just been completed.

### 2.3 Exact demo flow (target 14 min + 6 min Q&A)

| Time | Step | On screen | Live or recorded | Fallback |
| --- | --- | --- | --- | --- |
| 0:00 | **Framing** (1 slide): V2.0 backend was complete but had no front door → closed this month; V3.0 direction | Slide | — | — |
| 1:00 | **The decision**: scenario card for the demo junction (four arms, one lane each, cars only, base demand) and the three alternatives; show the planner (`/app/planning`) result for the base case: findings read "inconclusive / similar" where that is what the data says | Browser | Live (small, precomputed study loads instantly) | Precomputed study opened by id |
| 3:00 | **The doubt**: "this was one demand level and N seeds — what if traffic is different?" — notebook cell prints the uncertainty spec: factors, distributions, and the `basis: assumed` labels | Notebook | Live (instant) | Screenshot in deck |
| 4:00 | **The external client**: `client.submit_experiment(kind="robustness", preset="quick")`; prints run count and estimated time; progress callback | Notebook + terminal | **Live Quick run (≈ 3 min)** — while it runs: explain pairing and the guardrails | F1: switch to the identical precomputed Quick result by id |
| 7:00 | **The same experiment in the UI**: open `/app/experiments/<id>` via `client.ui_url(id)`; evidence badge reads *Indicative* (24 samples) and the tooltip states the rule (< 30 or unconverged ⇒ indicative); tabs: Distribution → Preference → What drives it → Conditions | Browser | Live | F1 |
| 10:00 | **The Standard result**: open the precomputed Standard package (≥ 100 samples, converged) — badge now *Robust-eligible*; read P(better) with intervals, regret, preferred-share, and the **flip point** | Browser | Precomputed (always) | — |
| 12:00 | **Provenance and portability**: fingerprint chain; `urbanflow verify standard.ufpkg` → integrity OK; `--reproduce` shown on the Quick package (small) → `reproduced` | Terminal | Live (Quick, ≤ 1 min) | Recorded clip |
| 13:00 | **Experimental teaser** (one slide, no live run): the signal-control environment exists; baselines (Webster, max-pressure) are being added; *no learned-policy result is claimed* | Slide | — | — |
| 13:30 | **Limits and what's next** (one slide): priors are assumptions; headway scale is a proxy, the engine has no reaction delay; single junction; not field-calibrated; roadmap to 26 Nov | Slide | — | — |
| 14:00 | Q&A | | | |

### 2.4 Data and scenario preparation

| Item | Specification | When |
| --- | --- | --- |
| Demo scenario | Four arms, 1 lane each, cars only (so the engine's own capacity calibration applies — `calibration_status` reports it calibrated; no mixed-traffic "exploratory" caveat on the headline), signalised baseline, alternatives fixed-time / adaptive / roundabout (all inside the validated one-lane range), 180 s runs for Quick, 300 s for Standard, warm-up per scenario defaults | S1 |
| Uncertainty spec | Global demand scale (triangular, bounds spanning below to above capacity), headway scale (uniform, ±15 %), approach-split skew; every factor `basis: assumed` and shown as such; vehicle-mix factor **off** in the preview (mixed traffic is exploratory) | S1 |
| Presets | **Quick:** 24 samples × 3 alternatives × 1 replicate (72 runs, ≈ 3 min on 6 workers). **Standard:** ≥ 100 samples × 3 × 2 (600 runs, ≈ 45 min — **precomputed**) | Quick measured in S1; Standard run in the S1 weekend and re-run on the final commit in S2 |
| Packages | `quick.ufpkg`, `standard.ufpkg` generated on the **final preview commit**; SHA-256 recorded in the runbook | S2 (Tue 27) |
| Backup | Screen recording of the full flow; static `report.md` per package; deck with screenshots | S2 (Tue 27) |
| Machine | The presenting laptop; `DEV_AUTH_BYPASS=1` local backend; production build served locally; **no AWS, no Cognito, no internet needed** | Rehearsed S2 |

**Known-effect check (done in S1, reported honestly):** the repository already documents that adaptive control lowers delay below saturation and gains nothing measurable at or above capacity, and that on one lane the roundabout keeps the lowest delay from busy demand upwards ([validation §4.1](../research/validation.md#41-fixed-time-vs-adaptive-vs-roundabout-v13-2026-10-06)). If the ensemble reproduces that pattern, the demo says so — an independent consistency check of the new tool. **If it does not, the demo shows what the ensemble shows and states the discrepancy as an open question** rather than tuning priors until the story fits.

### 2.5 Quantitative outputs shown (form, not value)

| Output | Form shown | Source |
| --- | --- | --- |
| Number of sampled conditions, alternatives, runs, wall time | "N = …; … runs; … min" | experiment header |
| Probability each alternative is better than the baseline by more than the tie tolerance | "x % (95 % interval a–b)" | Preference tab |
| Expected and worst-case regret of choosing each alternative | seconds of mean delay | Preference tab |
| Preferred-share per alternative | "preferred in x % of sampled conditions" — never "winner" | Preference tab |
| Strongest drivers of the difference | rank correlation per factor | What-drives-it tab |
| Flip point along the strongest factor | "advantage indistinguishable above demand ×y" or "no flip observed in the sampled range" | What-drives-it tab |
| Exclusions and failures | counts | Conditions tab |
| Evidence strength | *Indicative* / *Robust-eligible* | badge |
| Integrity | checksum OK; `reproduced` | CLI |

### 2.6 Working versus experimental

| Capability | State on 29 Oct | How it is labelled |
| --- | --- | --- |
| Planner UI (scenario → alternatives → results → export) | **Working** (V2.0 closure, core flow) | Normal; field-data step shown as "coming" |
| Robustness experiments (API + UI) | **Working, new** | "New in V3.0"; priors are assumptions |
| Python SDK, package export/verify | **Working, minimal** | "Minimal client — tokens arrive later" (local dev token only) |
| Access control hardening (M2/M3) | Working | Mentioned in the V2.0-closure line |
| Control Lab environment | Code exists only if S3 has started — **not demonstrated** | "Next" slide |
| Learned policy results | **Not available** | Not claimed |
| Emergency priority | **Not started** | "Next" slide |
| Personal access tokens, quotas | **Not available** | "Next" slide |
| Field calibration / network simulation | **Not available (and not planned for V3.0)** | Limits slide |

### 2.7 Fallback ladder (decide in order; the audience should barely notice)

| Level | Trigger | Action |
| --- | --- | --- |
| F0 | Normal | Live Quick run |
| F1 | Quick run slower than 5 min, or a worker fails | Say "while that finishes, here is one I ran earlier"; open the precomputed Quick experiment by id — **same page** |
| F2 | Browser/UI fails | Continue in the notebook: print the preference table from the package JSON; show `report.md` |
| F3 | Backend fails to start | Play the recorded video of the same flow while narrating; show package checksums |
| F4 | Laptop fails | Backup laptop with the same repo and packages; or the video from a USB stick |

### 2.8 Readiness gates

| Gate | When | Criteria |
| --- | --- | --- |
| **G1 — Feature freeze** | Fri 23 Oct 18:00 | AC-1.1 – AC-1.8 met; known-effect check run and written up; no open data-isolation defect |
| **Rehearsal 1** | Tue 27 Oct | Full timed run (≤ 15 min) on the presenting machine; notes become the defect list |
| **Rehearsal 2** | Wed 28 Oct | Cold start of the machine, **network disabled**, run through F0 → F1 → F3 deliberately; a second person asks the five hardest questions (§2.9) |
| **G2 — Go/no-go** | Wed 28 Oct 17:00 | AC-2.1 – AC-2.6; packages and video verified by checksum; frontend and backend suites green on the final commit; code frozen |

Offline note: the application loads Roboto from Google Fonts (`frontend/app.html`). Offline it falls back to system fonts; layout was verified not to break in Rehearsal 2. Self-hosting the font is optional.

### 2.9 Hardest expected questions (prepare honest answers)

1. *"Is this calibrated to real traffic?"* No. Field calibration does not exist; the priors are labelled assumptions; V1.8 compares simulation with counts but no real dataset has been run.
2. *"Why is `robust` not on the badge?"* Because the Quick run has 24 samples; the rule is written in the tooltip.
3. *"Does the roundabout win?"* UrbanFlow does not rank. Here is the preference share, the interval and the conditions.
4. *"Where is reaction time?"* The engine has none; headway scale is a proxy and labelled so.
5. *"Can I use this from my own tool?"* Yes — the client and the package format are the integration path; credentials and quotas for outside clients arrive in Sprint 4.
6. *"Is the public site running this?"* Not yet; the production pipeline failed twice on 9 Oct, the fix is on `main`, and a redeploy is scheduled for 30 Oct subject to authorisation (audit A-03).

---

## 3. Full presentation — Thursday 26 November 2026

### 3.1 The V3.0 end state

| Aspect | Definition |
| --- | --- |
| **Integrated feature set** | V2.0 complete (planner with field-data step, access control, private suites) · **Robustness Lab** · **Control Lab** (environment, policy shell, five baselines, one labelled-experimental learned policy, held-out protocol) · **Emergency pre-emption** (if G4 passed; otherwise reduced as in the fallback ladder) · `/api/v3` experiments · personal access tokens and quotas · Python SDK · packages · CSV in / GeoJSON out · responsive read-only views |
| **Primary user journey** | *A planning officer evaluates a junction proposal:* load the junction → import a turning-count CSV → compare simulation with the counts (and read the "input assimilation" caveat) → set alternatives (fixed, adaptive, roundabout, and a registered policy) → run the planner → ask "does it survive uncertainty?" → read preference, regret and flip → export report, package and a GeoJSON map layer |
| **Research workflows** | Train and evaluate a policy against baselines on held-out seeds; add a custom policy through the registry; run a paired emergency study; script any of it with the SDK; hand a package to a colleague who verifies and reproduces it |
| **External integration story** | A program with its own revocable token submits planning, robustness or control-evaluation experiments, polls, receives JSON/CSV/GeoJSON and a package; quotas protect the server; no code is uploaded |
| **Quantitative evaluation** | Three recorded studies (below), each a package with N, regimes, fingerprints and written limitations — including null or unfavourable results |
| **Reproducibility** | Every published number maps to a package; `urbanflow verify --reproduce` run on a clean checkout |
| **Limitations (own slide)** | Not field-calibrated; single junction only; priors are assumptions; headway is a reaction-time proxy; learned policy experimental and regime-bound; emergency model has no yielding or pull-over and no roundabouts; fuel/CO₂ are labelled estimates; determinism holds per commit and Python version |
| **Deployment and operations** | Clean-checkout `docker compose` demo; production redeploy only with authorisation (status stated honestly); runbook; token and quota administration documented; known single-process constraint for in-process limits |

### 3.2 Evaluation studies the presentation stands on

| Study | Question | Design (Standard preset) | Reported as |
| --- | --- | --- | --- |
| **E1 Robustness** | Does the fixed vs adaptive vs roundabout (and Webster / max-pressure / learned) preference survive uncertain demand and headway? | ≥ 100 sampled conditions, CRN, ≥ 2 replicates | P(better) with intervals, regret, preferred-share, flip, variance split (parametric vs stochastic) |
| **E2 Control Lab** | Is a learned policy competitive with five non-learning controllers in named regimes? | 5 controllers × 3 regimes × ≥ 30 paired held-out seeds | Paired differences with intervals per regime; regime and N beside every number; EXPERIMENTAL badge |
| **E3 Emergency** *(if G4 passed)* | Time saved for the emergency vehicle versus cost to others | ≥ 5 demand levels × ≥ 20 paired seeds, with/without pre-emption | Response-time saving, collateral delay by approach, recovery time, safety invariants (0 collisions, 0 conflicting greens) |

If a study produces no advantage for the new capability, that is presented as the result.

### 3.3 Demo script (25 min + 10 min Q&A)

| Time | Segment | What is shown | Fallback |
| --- | --- | --- | --- |
| 0:00 | **Where we are** | One slide: V2.0 closed (what changed), V3.0 scope, what is not in V3.0 | — |
| 2:00 | **Primary journey, part 1** | Planner on the demo junction; import the sample counts CSV; compare with counts; caveat shown | Precomputed study; recorded import |
| 6:00 | **Part 2: alternatives incl. a learned policy** | Add `policy:<id>` as an alternative; run Quick | Precomputed experiment by id |
| 9:00 | **Part 3: uncertainty** | Open the Standard robustness result (precomputed, E1); preference, regret, flip, variance split | — |
| 13:00 | **Control Lab** | Tested-conditions panel first; the E2 table; read the null or positive result as it stands | Static capture |
| 16:00 | **Emergency** *(if G4 passed)* | Ambulance through the signal on the live map; paired saving vs collateral; safety statement | E3 package; recorded clip |
| 19:00 | **External integration** | In a terminal: create a token, run the SDK script (robustness Quick through `/api/v3`), `urbanflow verify --reproduce` on a package from the clean checkout; export GeoJSON → opened in a map viewer | Recorded terminal |
| 22:00 | **Limits and readiness** | Limitations slide; tests/coverage/accessibility summary; deployment status stated plainly | — |
| 24:00 | **What next** | Deferred list from the strategy | — |
| 25:00 | Q&A | | |

### 3.4 Evidence requirements

* **Claims register** (a table in the runbook and an appendix slide): `claim → package id → fingerprint → N / regime → limitation sentence → who checked`. A slide may contain a number only if it has a row.
* Every chart has regime, N, duration and the scenario fingerprint in its caption.
* Language check against the strategy's claim rules (§1) by someone other than the author, or by a scripted search for the words *best*, *optimal*, *proves*, *wins*, *calibrated*.
* Test summary slide: backend non-slow **and slow** suites, frontend ×3, `ruff`, `mypy`, schema validation, contract test, coverage — each with the date and commit.
* The audit's status table updated: every V2.0 item either COMPLETE or listed as an open limitation.

### 3.5 Fallback plan

Same ladder as the preview (§2.7), extended: the **primary journey** has a complete precomputed variant at every step, so the whole demo can run with no live simulation; each live segment is independent, so a failed segment is skipped without breaking the next.

### 3.6 Readiness gates and final acceptance

| Gate | When | Criteria |
| --- | --- | --- |
| **G3** | Thu 5 Nov | Policy-shell safety proof (AC-3.1) |
| **G4** | Thu 12 Nov | Emergency go / partial / no-go |
| **G5 — Feature freeze** | Thu 19 Nov 18:00 | AC-5.1 – AC-5.7; E1–E3 packages exist |
| **RC cut** | Fri 20 Nov | `v3.0.0-rc1` tagged **by the owner**; no features after |
| **Rehearsal 1** | Tue 24 Nov | Full timed run on the presenting machine |
| **Rehearsal 2** | Wed 25 Nov | Cold start, offline, deliberate failure drills |
| **G6 — Go/no-go** | Wed 25 Nov 17:00 | The checklist below |

**Final acceptance checklist (G6)**

- [ ] Backend non-slow **and** slow suites, frontend ×3, `ruff`, `mypy`, `prettier`, schema validation, OpenAPI contract test all green on the RC commit; coverage ≥ 90 %.
- [ ] Pre-existing determinism and reproduction tests unmodified and passing.
- [ ] Ownership/token/quota tests pass; no anonymous access to calibration data, suites or experiments.
- [ ] ≥ 5 packages `verify --reproduce` on a clean checkout (or the version difference is documented).
- [ ] Claims register complete; limitations slide reviewed.
- [ ] axe: 0 serious/critical on planner, experiment viewer, Control Lab, tokens page; keyboard-only primary journey passes; 375 px read-only pages pass.
- [ ] Clean-checkout `docker compose` run and `scripts/v3_demo.py` pass.
- [ ] Two timed rehearsals ≤ 25 min, one cold/offline.
- [ ] Documentation set complete; `ROADMAP.md` and `README.md` agree with what shipped.
- [ ] Production deployment status stated truthfully (deployed and smoke-tested, or "not deployed").
- [ ] Anything not meeting the above is hidden via `/capabilities` and listed under limitations.

### 3.7 Minimum viable versus stretch

| | Scope | Success without the other |
| --- | --- | --- |
| **MVP V3.0** (must succeed) | V2.0 closure (core planner, M2/M3) · Robustness Lab · `/api/v3` robustness + control-evaluation kinds · tokens/quotas · SDK · packages · Control Lab with environment, shell, baselines, protocol (a learned policy *if* trained) · docs, reproducibility, limitations | Presentation succeeds with E1 and E2 even if E2's learned policy shows no advantage |
| **Planned, gated** | Emergency pre-emption (G4) · CSV import · GeoJSON export · field-data planner step | Each can be cut independently (sprint plan §9) |
| **Stretch (not required)** | Arms-GeoJSON → draft scenario · installable PWA manifest · SUMO net import · replicate-variance charts · self-hosted fonts | Nothing in the main presentation depends on them |

---

## 4. Rehearsal calendar

| Date | Event |
| --- | --- |
| Fri 23 Oct | Preview feature freeze (G1) |
| Tue 27 Oct | Preview rehearsal 1 (timed) |
| Wed 28 Oct | Preview rehearsal 2 (cold, offline) → G2 go/no-go 17:00 |
| **Thu 29 Oct** | **Preview** |
| Fri 30 Oct | Retrospective (30 min): what the audience asked; adjust S3–S6 |
| Thu 19 Nov | Feature freeze (G5) |
| Fri 20 Nov | Release candidate cut |
| Tue 24 Nov | Full rehearsal 1 |
| Wed 25 Nov | Full rehearsal 2 → G6 go/no-go 17:00 |
| **Thu 26 Nov** | **Full V3.0 presentation** |

## 5. Roles (single-engineer assumption)

The engineer presents and drives. If a second person is available for rehearsals, they run the clock, play the sceptical reviewer, and read the claims register against the slides. If nobody is available, record rehearsals and review them against the language check in §3.4.
