# UX audit and change record — scenario workflow and metered-entry roundabouts (V3.0 W2 follow-up)

> **Status:** Record · 2026-10-21 · baseline commit `06a92cc` on `viraj-dev` (identical to `origin/viraj-dev`; the W2 pull request [#196](https://github.com/Viraj281105/Traffic-Simulation/pull/196) was merged on 2026-10-21, so no W2 PR is open).
> **Scope:** a small usability pass over the existing scenario, launch, watch and results workflow. It is **not** a redesign, adds no field, endpoint or schema, and changes no simulation behaviour. The longer-term product direction is planned separately in [Future Scope](../future-scope/future_scope.md) (FS-11 … FS-13).
> **Principle followed:** every change below answers a verified problem; nothing was changed to make the interface look different.

---

## 1. Baseline

### 1.1 How a user creates, configures and runs a scenario today (verified in the running app, `/app/comparative`)

| Question | Baseline behaviour | Where |
| --- | --- | --- |
| How is a scenario created? | *Step 1 of 3 — Describe the junction*: either **Answer a few questions** (traffic level, lanes, signal timing basics) or **Build your own junction** (the scenario builder: 1 Junction · 2 Roads & lanes · 3 Traffic · 4 Vehicles · 5 Simulation · 6 Advanced), with presets and JSON import/export. The same builder sits inside the Planner (`/app/planner`) and the Research Lab. | `components/guided/ScenarioSetup.tsx`, `components/scenario/ScenarioBuilder.tsx` |
| How are traffic-control options discovered? | Builder step 1 lists three cards: fixed-time signal, adaptive signal, roundabout. The Planner offers the same three in a per-alternative dropdown; the Research Lab as three checkboxes. **Metered entry was reachable only inside "6 · Advanced".** | `builderOptions.ts` (`JUNCTIONS`), `PlannerPage.tsx`, `ScenarioStudy.tsx`, `AdvancedSettings.tsx` |
| How are intersections and roundabouts configured? | Arms, lanes and lane arrows (step 2), traffic per arm (step 3), mix (4), run settings (5). Signal timing, adaptive thresholds, roundabout design and roads are in Advanced, which renders only while open. | `ScenarioBuilder.tsx:467-487` (baseline) |
| How is a run started? | *Comparison*: **Run the comparison →** after the builder is valid; a readiness line states the backend's verdict. *Planner*: alternatives table then **Start**. | `ScenarioBuilder.tsx:582-622`, `PlannerPage.tsx` |
| How are results read? | *Step 2 · Watch* (`LiveGuide`: measures table and a "what to look for" tip), *Step 3 · Results* (`ResultsReport`: findings, "Why did this happen?", reliability, configuration list). | `components/guided/` |

### 1.2 Existing patterns that must stay unchanged

Choice cards (`.choice-grid` / `.choice-card`), chips (`.chip`, `aria-pressed`), segmented control (`.seg`), field blocks (`.sb-field`, `NumberField`), help text (`.q-help`), caution notes (`.q-note.is-caution`), `.link-btn`, `.config-hint`, the design tokens (`--color-*`, `--radius-*`), the three-stage Compare flow, the Planner table, and the product principles *evidence, not a verdict* and *simple by default, deep by choice* ([product story](README.md)). **No new colour, component library, page or navigation entry was introduced; one small CSS rule was added (§4.4).**

### 1.3 Behaviours, contracts and tests that could be affected

| Area | Risk | Handled by |
| --- | --- | --- |
| Scenario document / fingerprints | A UI path writing `entryControl`/`entryMetering` into conventional scenarios | `setEntryControl("conventional")` removes both fields; test asserts the exported JSON is byte-identical after a round trip |
| Planner request | A label field changing the study request | Only for a metered roundabout with no user label; conventional requests asserted equal to before |
| Backend validation | Duplicating or re-wording it | Frontend only adds a hint keyed on the stable code `(metering.missing_arm)`; no rule was added or copied |
| Existing S8 tests (`signalisedRoundabout.test.tsx`, 54 matches) | Weakening | Not edited; all pass |
| Determinism | Seeds, order, physics | No backend, engine or schema file changed ([§6](#6-scope-and-regression-assessment)) |

---

## 2. Observed problems

Each is reproducible; line numbers are at the baseline commit.

| # | Problem | Evidence and reproduction |
| --- | --- | --- |
| **O1** | **Metered entry is hard to discover.** The control is the last of six sections, inside a collapsed "Advanced" whose summary does not mention it ("junction geometry, signal timing, adaptive settings, roundabout design, roads"). A user choosing "Roundabout" is told only "No signal: …". | `ScenarioBuilder.tsx:467-487`, `AdvancedSettings.tsx:262-446`, `builderOptions.ts:18`. Open *Build your own junction*; nothing before step 6 mentions metering. |
| **O2** | **The metered mode is invisible where the roundabout is named.** With metering on, the readiness line says "Ready to simulate as Fixed-time signal, Roundabout."; the comparison call to action says "Comparing a traffic signal with a roundabout"; planner dropdown, labels and (via the server) findings say "Roundabout". A conventional and a metered roundabout share one name. | `ScenarioBuilder.tsx:593`, `ScenarioSetup.tsx:159-166`, `PlannerPage.tsx:292,424,434`, `ScenarioStudy.tsx` (title uses). Turn metering on, read the status card. |
| **O3** | **A dead end after changing the roads.** With metering on, switching a road off leaves the phase plan naming it. The status card then shows the raw backend text `phase 0 entry 'north' is not present at the junction (metering.missing_arm)`; the Advanced editor only edits greens, not which roads a phase holds, so the user cannot fix it except by switching metering off and on (which also discards their greens). | Metered on → toggle **North** off → read the status card (observed in the running app). Phase `entries` have no editor: `AdvancedSettings.tsx:298-315`. |
| **O4** | **Text states something false for a metered roundabout.** The live tip says "nobody waits for a light"; the results explanation says "Nobody gets a red light at the roundabout." | `LiveGuide.tsx:213-216`, `metrics/plainLanguage.ts:389`. Run a metered comparison; the signal panel shows a red head while the tip says nobody waits for a light. |
| **O5** | **Results do not record the entry control.** The configuration list under results gives lanes, critical gap and follow-up time for the roundabout, but not that its entries were metered or with which phases — so a saved or exported reading cannot be interpreted without the scenario file. | `ResultsReport.tsx` configuration list (baseline ~770-780). |
| **O6** | **Unmetered roads are unexplained.** The backend model leaves a road in no phase unmetered and always open ([signalised-roundabout §1.2](../simulation/signalised-roundabout.md)); the UI never says so, so adding a road after the plan was made silently yields an unmetered road. | `AdvancedSettings.tsx` (no text); `defaultEntryMetering` runs once at switch-on. |
| **O7** | **Conventional-vs-metered cannot be compared in one planner study from the UI.** The frontend `AlternativeSpec` carries only `strategy`, so every "Roundabout" row follows the one scenario. The backend already accepts a per-alternative merge `patch` (`backend/src/planning/models.py:36-47`), so this is a frontend/UX gap, **not** a contract gap (not exercised in this audit). | `services/v2/planning.ts:30-34` |
| **O8** | **Level-of-service bands for a metered roundabout.** Roundabouts use the stricter *unsignalised* HCM-style bands "because drivers expect less time lost where there is no red light"; a metered roundabout has a red light. Whether the grade is still meaningful is a research/PO question, not a copy fix. | `metrics/plainLanguage.ts` (`LOS_THRESHOLDS`) |
| **O9** | **"Answer a few questions" mode cannot choose metering.** Quick mode builds a conventional scenario; a user who never opens the builder never meets the option. Acceptable by design (simple by default) but worth recording. | `ScenarioSetup.tsx` quick branch |
| **O10** | **The Research Lab and three-way pages describe the roundabout as having no signal.** Accurate for the conventional strategy they describe. | `research/ControlStrategies.tsx:57`, `ThreeWayStudyPage.tsx:62` |

Not found, and therefore not changed: labelling or keyboard problems in the controls reviewed, colour-only status in the metered panel (the panel already names each arm's state in text), validation-limit mismatches (the builder passes the backend's limits through).

---

## 3. Proposed-change table

Priority: **P0** prevents a confusing or inaccurate workflow · **P1** small, high-value · **P2** documented for a later iteration.

| Problem | Proposed improvement | Affected components | Risk | Validation | Class |
| --- | --- | --- | --- | --- | :-: |
| O4 false statements | Metered-aware wording in the live tip and the results explanation; unchanged text for conventional | `LiveGuide.tsx`, `plainLanguage.ts` (`ScenarioFacts.meteredEntry`), `ResultsReport.tsx`, `App.tsx` (one prop) | Low: text selection on a boolean | Tests on both branches; observed in the running app | **P0** |
| O3 dead end | A "Rebuild phases for the current roads" action next to the choice, shown only when a phase names a missing road; an explanatory note; the server error gains a pointer to it | `EntryControlChoice.tsx`, `scenarioModel.ts`, `ScenarioBuilder.tsx` | Low: explicit user action; keeps clearances, guard, cap | Model and component tests; observed in the running app | **P0** |
| O1 discoverability | Entry-control choice in builder step 1 (two choice cards with plain descriptions) whenever a roundabout is part of the run; Advanced summary names metered-entry timing; the Roundabout card no longer says only "No signal" | `EntryControlChoice.tsx`, `ScenarioBuilder.tsx`, `builderOptions.ts`, one CSS rule | Low: same document field the Advanced chips edit | Component tests; axe | **P1** |
| O2 naming | `strategyTitle(strategy, scenario)`; used in the readiness line, comparison call to action, Planner dropdown/placeholder/warning titles, Research Lab titles; Planner sends the label only for a metered roundabout with no user label | `scenarioTypes.ts`, `ScenarioBuilder.tsx`, `ScenarioSetup.tsx`, `PlannerPage.tsx`, `plannerRequest.ts`, `ScenarioStudy.tsx` | Low–medium: a label is added to a study request for metered scenarios | Request-equality test for conventional; label test for metered; fingerprint independent of label (read in `alternatives.py`) | **P1** |
| O5 results record | Add the entry control and its phases to the configuration list | `ResultsReport.tsx` | Low | Observed; text only for metered | **P1** |
| O6 unmetered roads | One sentence in step 1 (roads signalled / not signalled) and one in Advanced | `EntryControlChoice.tsx`, `AdvancedSettings.tsx` | Low | Test | **P1** |
| O7 per-alternative control | Expose `patch` in the Planner for a roundabout row; decide where timings come from | `services/v2/planning.ts`, `PlannerPage.tsx` | Medium: new request content, UX decision (OQ-7) | — | **P2** |
| O8 LOS bands | Research/PO decision on the band set for metered entry | `plainLanguage.ts` | Metric interpretation | — | **P2** |
| O9 quick mode | Decide whether quick mode should mention metered entry | `ScenarioSetup.tsx` | Navigation/UX | — | **P2** |
| O10 copy | Add a metered note to the strategy descriptions once the W3 registry owns the text | `ControlStrategies.tsx`, `ThreeWayStudyPage.tsx` | Low | — | **P2** |

**Placement.** The W2 pull request is merged and its gate (G-SR) is recorded as passed in [signalised-roundabout.md](../simulation/signalised-roundabout.md); these changes are follow-up polish to a W2 feature, not part of W3. They are committed separately from the future-product planning documents.

---

## 4. Implemented improvements

### 4.1 Honest wording for a metered roundabout (O4, P0)

| | |
| --- | --- |
| **Problem** | "Nobody waits for a light" / "Nobody gets a red light at the roundabout" shown beside a signal head. |
| **Solution** | `LiveGuide` takes `meteredEntry` (from the scenario, so it is right before the first snapshot, and from the live controller state afterwards). A metered roundabout is described as: drivers wait for a gap *and* for a green; a green never forces a driver in; nothing inside the ring is signalled; timings are a simulation assumption. `explanations()` takes `ScenarioFacts.meteredEntry` for the same. Conventional text is unchanged, verified by test. |
| **Files** | `components/guided/LiveGuide.tsx`, `metrics/plainLanguage.ts`, `components/guided/ResultsReport.tsx`, `App.tsx` |
| **Why smallest** | One boolean selects between two sentences; no new component, no new data. |

### 4.2 A way out of the stale-plan dead end (O3, P0)

| | |
| --- | --- |
| **Problem** | Metering on, road switched off → raw `metering.missing_arm` text and no editable remedy. |
| **Solution** | `meteringCoverage()` (pure) reports roads signalled, roads not in any phase and phase entries naming a road the junction no longer has. When there are any of the latter, step 1 shows an alert and **Rebuild phases for the current roads**, which re-derives the phases (north–south, then east–west, as at switch-on) and keeps yellow, all-red, offset, guard and cap; greens return to their defaults and the note says so. The status card's server message is kept verbatim and gains a pointer to the button. The action runs only on click; nothing is rewritten silently. |
| **Files** | `components/scenario/EntryControlChoice.tsx` (new), `scenario/scenarioModel.ts`, `components/scenario/ScenarioBuilder.tsx` |
| **Why smallest** | Reuses `defaultEntryMetering`; no phase-entry editor (a larger feature, P2) and no backend change. |

### 4.3 Entry control where the junction is described (O1, O6, P1)

| | |
| --- | --- |
| **Problem** | The choice that changes what a roundabout *is* sat in the last, collapsed section. |
| **Solution** | Step 1 gains **How do vehicles enter the roundabout?** with two choice cards (*Conventional roundabout* — default; *Metered entry (signals)*), each with one plain sentence that also says what metering does **not** do (a green never forces a vehicle in; nothing is signalled inside the ring). When metered, one line names the signalled roads, any road in no phase, and points to Advanced for timings, guard and queue cap, with the standing "simulation assumption, not calibrated" statement. It appears only when a roundabout is part of the run (comparison, Planner with a roundabout alternative, Research Lab). The Advanced chips remain, edit the same field through the same function (`setEntryControl`), and keep their existing tests; the Advanced summary now names "metered-entry timing". |
| **Files** | `EntryControlChoice.tsx`, `ScenarioBuilder.tsx`, `AdvancedSettings.tsx`, `builderOptions.ts` (Roundabout card text), `ScenarioBuilder.css` |
| **Why smallest** | No new page, wizard or navigation; the existing choice-card pattern; timings stay in Advanced (progressive disclosure). |

### 4.4 A metered roundabout is named as one (O2, O5, P1)

| | |
| --- | --- |
| **Solution** | `strategyTitle(strategy, scenario)` returns "Roundabout (metered entry)" for a metered roundabout and the existing title otherwise. Used in the readiness line, the Compare call to action ("…with a metered-entry roundabout"), the Planner dropdown, label placeholder and warning titles, and the Research Lab. The Planner request carries that label for a metered roundabout row **only when the user has not typed one**, so the study's own findings and exports use it; a conventional request is identical to before (asserted). The results configuration list now states "metered entry (signals on the entries): north and south 20 s green, then …; yellow 3 s, all-red 2 s". |
| **Files** | `scenario/scenarioTypes.ts`, `ScenarioBuilder.tsx`, `ScenarioSetup.tsx`, `PlannerPage.tsx`, `planner/plannerRequest.ts`, `ScenarioStudy.tsx`, `ResultsReport.tsx` |
| **CSS** | One rule block, `.sb-entry-control`, that makes the new group a bare fieldset like the builder's other field groups (without it the browser draws a default groove border and legend). Existing tokens only. |

---

## 5. Deferred (P2) and recommendations

| Item | Why deferred | Where it goes |
| --- | --- | --- |
| Per-alternative control selection in the Planner (O7) | UX decision on where timings come from; new request content; backend already supports it | Open question OQ-7; [requirements](../future-scope/next-generation-requirements.md#10-open-questions-for-the-product-owner) |
| Level-of-service bands for metered entry (O8) | Metric interpretation, research decision | OQ-8 |
| Quick mode and metering (O9) | Navigation/UX decision | Guided Scenario Builder (FS-11) |
| Editing which roads a phase holds | A real editor; today rebuild-and-edit-greens is enough | With the registry/strategy summary (V3.0 W3) |
| Metered note in Research Lab strategy descriptions (O10) | Text should come from one source once W3's registry holds it | W3 descriptor amendment ([architecture §8](../future-scope/next-generation-architecture.md#8-decisions-that-need-an-adr--and-decisions-that-can-be-deferred)) |
| Signal heads in the builder's plan preview | Drawing change, no usability evidence | Not planned |

---

## 6. Scope and regression assessment

| Question | Answer |
| --- | --- |
| Backend or simulation contract changed? | **No.** No file under `backend/`, `shared/` or the OpenAPI snapshot changed (`git diff --stat` below). The planner request gains a `label` only for a metered roundabout with no user label; `label` is an existing optional field and is not part of the scenario fingerprint (`alternatives.py` fingerprints the patched document). |
| Determinism-sensitive code changed? | **No.** No seed, execution-order, physics, time-step, metric or controller code. |
| Conventional-roundabout compatibility? | **Verified:** `setEntryControl("conventional")` removes both fields and a metered→conventional round trip exports byte-identical JSON; the selector does not call `onChange` on render; conventional planner request equals the previous shape; conventional text is unchanged. |
| Existing acceptance criteria still met? | The existing 451 frontend tests pass unchanged alongside 19 new ones (§7). Backend suites were not run because no backend file changed. |
| Anything to review separately? | The Planner label for metered roundabouts (a request-content change, small) and the wording of the metered descriptions (product-owner review of claims). |

---

## 7. Tests and validation performed

New file `frontend/src/test/entryControlDiscoverability.test.tsx` (19 tests):

- **Model:** a conventional roundabout never carries metering fields (byte-identical export); choosing metered keeps an edited plan; coverage names signalled / unmetered / missing roads; rebuilding keeps clearances, guard and cap and resets greens; only a metered roundabout is renamed.
- **Builder:** the control is offered without opening Advanced; rendering writes nothing; switching to metered is named in the readiness line; hidden when no roundabout is run; returning to conventional removes the fields; the stale-phase alert and its repair; unmetered roads named and the document untouched; axe clean in plain and repair states.
- **Planner request:** conventional unchanged; metered labelled unless the user chose a label.
- **Text:** conventional explanation and live tip unchanged; metered ones do not say "nobody gets a red light" / "nobody waits for a light", and keep the gap rule and the limits.

Results are in the final report; the checks run were `npm run type-check`, `npm run lint`, `npm run format` (prettier `--check`), the full `vitest run`, a production `vite build`, `git diff --check`, and manual verification in the running app (Docker dev stack bind-mounting the working tree) of: step-1 choice, readiness line, stale-phase alert and repair, call to action, live tip before and during a run, results explanation and configuration list.

## 8. Known limitations

- Screens were checked at the browser pane's ~800 px width and by computed style; no 375 px or dark-theme pass was made for the new group.
- The study label for metered roundabouts is set by the client; a client that omits it still gets the server's title "Roundabout".
- `ResultsReport`'s configuration text and `LOS` bands are not covered by a dedicated component test (the results text change was verified in the running app and through `explanations()` tests).
- No moderated user testing was done; problems O1–O6 are verified by inspection and reproduction, not by observing users.
