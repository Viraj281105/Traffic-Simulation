# UrbanFlow — User Narrative, Information Architecture and Metric Strategy

Status: implemented on `viraj-dev` (2026-09-25). This document is the product
reference for who UrbanFlow is for, the journey it offers, and how research-grade
measurements are presented to someone who is not a traffic engineer.

It answers two mentor findings:

1. There was no defined user, entry point or end-to-end story — the app was six
   equal-weight dashboard tabs.
2. Results required research knowledge (control delay, Jain's index, Welch's
   t-test, Cohen's d, seeds, warm-up) to understand.

---

## A. The UrbanFlow user narrative

> *A junction on your road is up for redesign: keep the traffic lights, or build a
> roundabout? UrbanFlow lets you try both on the same virtual junction with exactly
> the same cars, then shows you in plain language how much time drivers would lose, how
> much traffic gets through, how queues build, whether every direction is treated
> alike — why — and how sure you can be. It shows the evidence; the decision stays
> yours.*

One sentence: **UrbanFlow turns "signal or roundabout?" into a fair, repeatable
test you can read without a manual.**

## B. Primary user

**A non-specialist decision participant facing a specific junction decision** —
concretely, a municipal planning officer (not a traffic engineer) who must form
and explain a view on a proposal to convert a signalised junction to a roundabout,
or the reverse. Councillors' staff, community-association representatives and
students have the same need and are served by the same flow.

| | |
| --- | --- |
| **Problem** | Has to weigh in on "signal or roundabout?" for one junction, and explain the reasoning to others (a committee, residents). Opinions are loud; evidence is scarce. |
| **Knows** | Roughly how busy the junction is ("quiet", "busy at rush hour"), how many lanes it has, and what waiting at lights or a roundabout feels like. |
| **Does not know** | veh/s, IDM, critical gap / follow-up headway, control delay, Jain's index, p-values, effect sizes, random seeds, warm-up periods, TTC/PET. |
| **Wants to learn** | For *this kind of junction at these traffic levels*: how long drivers wait, how much gets through, how bad queues get, whether some directions suffer, why the two differ, and whether the difference is real or luck. |
| **Needs from UrbanFlow** | A fair test, plain answers with the numbers visible, the reason behind them, an honest reliability check, stated limits, and an easy way to try alternatives. Not a verdict. |

**Secondary user — the researcher / traffic engineer** — needs every metric,
statistics, sweeps, exports and reproducibility. They are fully supported, one
layer down (the specialist table on every result and the Research lab), but they
no longer define the default experience.

## C. End-to-end journey

```
Landing (/)                         "Signal or roundabout? Try both."
  │  understands what UrbanFlow does, who it is for, that it gives evidence not a verdict
  ▼
Compare · Step 1 — Your junction    (/app/comparative)
  │  How busy? (Quiet / Steady / Busy / Rush hour, shown in vehicles per hour)
  │  How many lanes per approach? (1 recommended/calibrated; 2–3 flagged as indicative)
  │  How long to watch? (2 / 5 / 10 min)
  │  Sees both options described in words; Advanced settings for specialists
  │  → "Run the comparison"
  ▼
Compare · Step 2 — Watch both run
  │  Two maps, same vehicles. Progress "1:14 of 2:00", warm-up explained,
  │  three live numbers per side, "what to look for"
  │  Specialist live charts one toggle away
  │  → "See results so far" (after warm-up) / "See your results" (when finished)
  ▼
Compare · Step 3 — Results
  │  In short — one sentence per question, both values stated
  │  What people would notice — 4 question cards (time lost / throughput / queues / fairness)
  │  Why did this happen? — mechanisms + this run's own evidence
  │  How reliable is this? — fairness of the test, limits, cautions,
  │                          "Check reliability" (repeat over 5–10 traffic patterns)
  │  Try another scenario — busier / quieter / change junction; session table
  │  All measurements & method (for specialists) — every metric, charts, weighting, CSV
  ▼
User reaches their own conclusion; optionally Saves it (Saved section)
```

Where the user was confused before, and what replaced it:

| Before | Confusion | Now |
| --- | --- | --- |
| Landing "WHICH ONE WINS?" | Promised a verdict the method cannot give | "Signal or roundabout? Try both." + "No verdict: your call" |
| Six emoji tabs (Signal only, Roundabout only, Comparative, History, Volume, Validation) | No starting point or order | Three sections: **Compare** (default), **Saved**, **Research lab** |
| Scenario hidden in a "⚙️ Scenario settings" drawer in veh/s, t_c, t_f | Could not describe their junction | Three everyday questions; specialist drawer behind "Advanced settings" |
| Seed badge, "Re-roll", stop-line / queue-label toggles on top | Research controls first | Moved to the single-control research views |
| Footer: Sim time, Tick, Tick rate (Hz), `RUNNING` | Jargon | "Simulated time 1:14 / 2:00", "Running"; "Start over" |
| Side panel: 6 pills, ~35 metrics, Δ(R−S) | No answer to "is this good?" or "which differs?" | Plain live panel; results page with lead sentences |
| No "why" anywhere | — | "Why did this happen?" section |
| Reliability on a separate Validation tab running a *different* fixed scenario (2 lanes, 0.35 veh/s, 30 s, 5 s warm-up) | Its verdict said nothing about the user's scenario | "Check reliability" repeats *the user's own* scenario |
| Multi-lane roundabout limitation documented but not shown | Over-trust | Flagged at setup and on results; default is the calibrated 1 lane |

## D. Information architecture

```
/                       Landing — narrative, how it works, what you learn, method
/app/comparative        COMPARE  (default)   Step 1 Your junction → 2 Watch → 3 Results
/app/history            SAVED                saved comparisons & runs
  /app/runs/<id>                             run record, provenance, re-run, exports
  /app/compare?runs=…                        compare up to six saved runs
/app/research           RESEARCH LAB hub     tool cards + plain↔technical metric map
  /app/volume                                traffic-level sweep
  /app/validation                            Monte Carlo statistical study
  /app/signal                                signal on its own (full live metrics)
  /app/roundabout                            roundabout on its own
```

Layering principle — **simple by default, deep by choice**:

| Layer | Where | Audience |
| --- | --- | --- |
| 1. Answer | "In short", card lead sentences | Everyone |
| 2. Evidence | Card rows (both values, bars), grades, bands | Everyone |
| 3. Meaning | "How is this measured?" (catalog name, key, definition, thresholds) | Curious users |
| 4. Reason & trust | "Why did this happen?", "How reliable is this?", reliability check | Everyone |
| 5. Full data | "All measurements & method", charts & weighting modal, CSV, statistics table | Specialists |
| 6. Studies | Research lab | Researchers |

## E. Metric translation / presentation strategy

All plain-language readings come from one module,
`frontend/src/metrics/plainLanguage.ts`. It reads values only through the
existing catalog (`metrics/catalog.ts` → `metricState`), so warm-up, "no vehicles
yet" and "not measured for this geometry" behave exactly as in the technical
tables. It computes no new metric and never ranks the controls.

### Every catalog metric

| Metric (key) | Disposition | Plain presentation |
| --- | --- | --- |
| Average delay (`averageDelay`) | **Visible, translated** | "Time lost per driver, on average" + HCM grade word |
| 95th percentile delay (`p95Delay`) | **Visible, translated** | "1 in 20 drivers lost more than …" |
| Stops per vehicle (`averageStopsPerVehicle`) | **Visible** | "Stops per driver"; also a "why" line |
| Throughput (`throughput`) | **Visible, translated** | "Got through in the N measured" |
| Vehicles in network (`activeVehicleCount`) | **Visible, translated** | "Still waiting or moving when the clock stopped"; drives "one side was falling behind" |
| Average queue (`averageQueueLength`) | **Visible** | "Typical queue on one approach" |
| Maximum queue (`maxQueueLength`) | **Visible** | "Longest queue seen" |
| Time congested (`congestionRecoveryTime`) | **Visible, translated** | "Time with more than 5 vehicles queued" (+ share of measured time) |
| Directional fairness (`directionalFairnessIndex`) | **Grouped into bands** | Very even / Mostly even / Uneven / Very uneven (+ index) |
| Idle green loss (`idleOpportunityLoss`) | **Why layer** | "Signal showed green to an empty road while vehicles queued on red for X%" (shown when ≥ 5%) |
| Collisions (`collisionCount`) | **Trust layer** | Model-integrity caution when > 0, never presented as crash risk |
| Planning time index (`travelTimeReliability`) | Specialist; its low-sample flag drives a trust caution | "Fewer than 20 vehicles got through…" |
| Median / min / max / std delay, queued time (`averageWaitTime`), throughput rate, current mean speed, active-queue average, total stops, queue std, queue stability index, speed variance index | **Specialist layer** | Full table only (two different "wait" numbers side by side confused users) |
| Min TTC, low-TTC events, min PET, low-PET events, TTC/PET samples | **Removed from primary UX** (specialist only) | Surrogate safety is exploratory; the plain layer states "crash risk is not modelled" |
| Vehicles generated, critical saturation volume, service utilization, junction footprint | **Specialist layer** | Full table only |
| Composite score (`masterEfficiencyScore`) and the user-weighted scoring panel | **Composite: within one layout only** (never side by side signal vs roundabout); **weighted panel: specialist only, hidden until warm-up is over** | A 0–100 score reads as a verdict, and the fixed composite is structurally unfair across layouts (see `urbanflow-evaluation-metrics.md` §15) |

### Study and scenario concepts

| Concept | Plain presentation |
| --- | --- |
| Arrival rate (veh/s) | "How busy?" levels with vehicles per hour (0.10 / 0.20 / 0.30 / 0.45 veh/s) |
| Simulation duration | "How long to watch?" (2 / 5 / 10 min) and "1:14 of 2:00" |
| Warm-up | "The first 30 s are a warm-up while traffic builds up; not counted" (live and results) |
| Random seed | "Traffic pattern #N"; "both got exactly the same vehicles" |
| Repetitions / seeds | "Check reliability: repeat with 5 new traffic patterns" |
| Statistical significance (Welch, p < 0.05) | "Consistent difference — unlikely to be luck (p = …)" vs "not consistent enough to rule out chance" |
| Effect size (Cohen's d) | "Compared with how much results vary from pattern to pattern, the gap is small / medium / large" |
| Confidence interval, df, per-seed data | "Show the statistics" disclosure |
| Signal timings, critical gap | Used verbatim in "Why": "25 s of green… a 60 s cycle", "a gap of at least 4.5 s" |

### Declared presentation thresholds

These are presentation choices, not model outputs, and each is shown to users
where a label depends on it:

- **About the same** (`SIMILARITY`): a gap counts only if it exceeds both an
  absolute and a relative tolerance — delay 1 s / 5 %, vehicles 3 / 2 %,
  queue 0.5 veh / 10 %, stops 0.1 / 10 %, fairness 0.03.
- **"Is that a lot of time lost?"** (`LOS_THRESHOLDS`, the app's single set of level-of-service bands): Highway Capacity Manual delay
  bands — signals A ≤ 10, B ≤ 20, C ≤ 35, D ≤ 55, E ≤ 80 s; roundabouts
  (stricter) A ≤ 10, B ≤ 15, C ≤ 25, D ≤ 35, E ≤ 50 s. Labelled indicative.
- **Fairness words** (`FAIRNESS_BANDS`): ≥ 0.95, ≥ 0.85, ≥ 0.70, below.
- **Effect size words**: Cohen's conventional 0.2 / 0.5 / 0.8.

## F. Research vs layman UX strategy

1. **One product path.** Everyone starts in Compare; nothing research-only is on
   that path by default.
2. **State both values.** Every plain sentence quotes both numbers, so a summary
   word never hides the data ("11 s less per driver (7 s at the signal, 18 s at
   the roundabout)").
3. **No verdict.** No "wins", "best" or composite score in the plain layer; the
   results page says "UrbanFlow shows the evidence; it does not pick a winner". The
   Validation tool's "Roundabout won / win rate" wording was changed to "had the
   lower delay in k of n seeds".
4. **Explain before exposing.** Each card's "How is this measured?" shows the
   catalog label, key and definition; the specialist section shows the complete
   table, charts, weighting and CSV — nothing was removed.
5. **Trust is part of the answer.** The fair-test note, warm-up, short/partial
   runs, low samples, multi-lane roundabout scope, vehicle overlaps and model scope
   (no pedestrians, cyclists, heavy vehicles or crash risk) are stated next to the
   results, and the reliability check runs on the user's own scenario.
6. **Research tools keep their full vocabulary** in the Research lab, which now
   explains what each tool answers and publishes the plain↔technical metric map.

## G. Implemented changes

### Frontend

- `src/metrics/plainLanguage.ts` — **new** translation layer: side summaries via
  the catalog, similarity, HCM grade, fairness bands, headline findings, "why"
  explanations, trust notes, reliability readings, and the plain↔metric map.
- `src/components/guided/` — **new** guided comparison:
  `ScenarioSetup` (step 1), `LiveGuide` (step 2), `ResultsReport` (step 3),
  `ReliabilityCheck`, `StepNav`, `comparisonRun.ts` (contexts, session runs, CSV),
  `Guided.css`.
- `src/components/ResearchHub.tsx` — **new** Research lab hub.
- `src/App.tsx` — three-section navigation (Compare / Saved / Research lab),
  research sub-navigation, three-step comparison stage machine, config-sync-then-play
  handshake, session scenario table, saved comparisons open on the results step;
  single-control views keep the scenario drawer, display toggles and seed bar.
- `src/routing.ts`, `templates/default.conf.template` — `/app/research` route.
- `src/types/config.ts` — `dashboardPayload()` (one definition of the scenario
  body), demand levels, run lengths, signal cycle; default scenario is 1 lane
  per approach (the calibrated comparison).
- `src/components/PlaybackControls.tsx` — plain mode (time vs run length, status
  word, "Start over").
- `src/components/ConfigurationSidebar.tsx` — `draftOnly` wording when opened
  from setup.
- `src/services/api.ts` — `runReliabilityCheck()`; live calls wait for the session.
- `src/services/liveSession.ts` — **new**; `hooks/useWebSocketSnapshot.ts`,
  `hooks/useSimulationPolling.ts` — see "Defects found" below.
- `src/components/ValidationDashboard.tsx`, `VolumeAnalysisDashboard.tsx` —
  verdict wording removed; both state that they use their own study scenario.
- `src/landing/App.tsx`, `index.html`, `app.html` — narrative rewrite and titles.

### Backend (only what the journey genuinely required)

- `POST /api/v1/study/validate/monte-carlo` accepts `scenario` (the dashboard
  body) and repeats exactly that scenario, including the live 30 s warm-up and
  the scenario's duration. The dashboard config compilation was extracted into
  `_compile_dashboard_config()` so the live run and the check share one
  definition. Statistics (`run_statistical_validation`, Welch's test, Cohen's d)
  are unchanged.
- Simulation physics, controllers, metric definitions and evaluation methods are
  **unchanged**.

### Defects found while verifying the journey (both pre-existing)

1. **First visit streamed the wrong simulation.** The live-session cookie is set
   by the first `/api/simulation` response. On a first visit the dashboard opened
   its WebSocket and fired several REST calls at once, before any cookie existed:
   each REST call started its own session and the socket joined the backend's
   shared "default" session. The user watched a simulation other than the one
   they configured and started. Fix: `services/liveSession.ts` makes one
   side-effect-free request first; all live REST calls and the stream wait for it.
2. **A new scenario could run the previous one.** `update_simulation_config`
   cleared the dual orchestrator before assigning the new config; the dual stream
   rebuilds a missing orchestrator every frame, so it could rebuild the *old*
   scenario in that gap, and Play ran it (observed: a 2-minute comparison still
   running at 2:13). Fix: assign the new config first, then tear down old runs; a
   rejected config now leaves the running scenario untouched.

## H. Validation results

| Check | Result |
| --- | --- |
| Frontend tests (`vitest run`) | **192 passed**, 22 files (baseline 165 / 19) |
| Type check (`tsc --noEmit`) | clean |
| Lint (`eslint .`) | clean |
| Format (`prettier --check .`) | clean |
| Production build (`npm run build`) | succeeded |
| Backend lint / format (`ruff check`, `ruff format --check`) | clean |
| Backend types (`mypy src/`) | no issues (45 files) |
| Backend tests (`pytest -m "not slow"`) | all passed, coverage 95.2 % (gate 85 %) |

New tests: `plainLanguage.test.ts` (18), `GuidedComparison.test.tsx` (5, the
whole journey against mocked hooks), `liveSession.test.ts` (3),
`test_scenario_reliability.py` (5), `test_live_config_ordering.py` (2 — both fail
on the old ordering and pass with the fix). Existing App tests were updated for
the new navigation; no metric, catalog or statistics test changed.

**Live journey** (real backend + Vite, fresh browser origin): landing → Compare →
Busy, 1 lane, Quick look → Run: config reached the backend before Play; the
stream and the session agreed; the run finished at exactly 2:00; the results page
rendered every section; "Check reliability" repeated the same scenario over 5
patterns in about 40 s and reported a consistent delay difference with its tally
and statistics. At 375 px wide the setup page and Research lab have no horizontal
overflow.

**Layman test** — can a first-time visitor answer…

1. *What is UrbanFlow?* Landing hero and step 1 intro.
2. *What am I supposed to do?* Three questions, one button; step bar.
3. *What am I comparing?* "The two options being compared" card; scenario chips.
4. *What do the results mean?* "In short" + card leads with both values, grades
   and bands; "How is this measured?".
5. *Why is one different?* "Why did this happen?" — mechanism plus this run's
   idle-green share, stops and backlog.
6. *How reliable is it?* Trust notes and the one-click reliability check in words.
7. *What can I investigate next?* Busier/quieter, change junction, session table,
   specialist layer, Research lab.

Issues the layman test surfaced and fixed: the "1 in 20 drivers" and fairness
readings were shown without caution on runs with fewer than 20 vehicles (a
per-card note now appears); the reliability headline read "The traffic signal
lost less time" (now "Drivers lost less time at the traffic signal").

## I. Remaining limitations

- **Real-time watching.** The live comparison runs at 1× speed; a 5-minute
  scenario takes 5 minutes. "See results so far" mitigates it; a faster-than-real-
  time or headless "results only" run would help but was out of scope.
- **Reliability check is synchronous.** One HTTP request runs every repetition
  (about 40 s for five 2-minute patterns on a quiet 1-lane junction; a heavy
  2-lane 5-minute scenario was measured at ~28 s per pattern, so ~2.5 min for 5).
  There is no progress bar or cancel.
- **Monte Carlo seeds are drawn at random** by the existing study code, so a
  reliability check is not itself reproducible (its seeds are listed).
- **Session scenario table is in memory**; it is lost on refresh unless each
  comparison is saved.
- **Saved comparisons opened from Saved** show results without warm-up/measured
  time (older saves did not record them), so rate-based wording falls back to counts.
- **Presentation thresholds** (similarity, fairness bands) are judgement calls;
  they are declared here and shown in the UI, but were not user-tested.
- **Model scope unchanged**: multi-lane roundabouts remain indicative only; no
  pedestrians, cyclists, heavy vehicles or crash-risk model.
- **Research tools** (Volume, Validation) still use their own configurable study
  scenarios and technical language by design; they are not wired to the guided
  scenario.
- The live-session cookie is still unavailable to a cross-origin dev setup
  (`VITE_API_URL` pointing straight at `:8000`), as documented in the backend
  middleware.
