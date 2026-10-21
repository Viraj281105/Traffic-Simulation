# Next-generation UrbanFlow — product requirements (Guided Scenario Builder, City Studio, AI Traffic Analyst)

> **Status:** 🔭 PLANNING — **nothing in this document exists in the application and nothing here is scheduled.** It was prepared alongside V3.0 so that discovery does not have to be repeated later; it authorises no implementation. Gates are in the [roadmap and parallel-work policy](next-generation-roadmap.md#4-gates).
> **Series:** [Requirements](next-generation-requirements.md) (this) · [Architecture and dependencies](next-generation-architecture.md) · [Phased roadmap and parallel-work policy](next-generation-roadmap.md) · evidence for the current UI in [UX audit](../product/ux-audit-v3-w2-followup.md)
> **Authority:** [`ROADMAP.md`](../ROADMAP.md) and [Future Scope](future_scope.md) remain authoritative; this series elaborates FS-11 … FS-13 and edits neither roadmap. Where a requirement overlaps a scheduled V3.0 capability it **reuses** it and says so (§9).
> **Labels:** **[V]** verified in the repository on 2026-10-21 (source named) · **[P]** proposal, not a decision · **[U]** unverified estimate. Relative sizes are S/M/L with stated assumptions; **no dates or effort in days are given** because there is no measured velocity for this work.

---

## 1. Direction and principles

UrbanFlow's long-term direction is to make traffic simulation usable by people without traffic-engineering training **without taking capability away from experts**. The progression the three initiatives serve is:

> describe or build a network → configure a scenario → validate it → simulate it → compare outcomes → understand trade-offs → refine the scenario.

| # | Principle | Source / meaning here |
| --- | --- | --- |
| P1 | **Evidence, not a verdict** | Product story and [V3 strategy §1 claim rules](../roadmap/V3_PRODUCT_STRATEGY.md#claim-rules-apply-to-every-screen-document-and-slide). No screen, recommendation or AI text says a strategy is "best" or "safe". |
| P2 | **Simple by default, deep by choice** | [Product story](../product/README.md). Guided choices first; every expert control stays one deliberate step away. |
| P3 | **One scenario definition** | Guided mode, City Studio and the Analyst all read and write the same `urbanflow-scenario` / `urbanflow-network` documents and pass the same backend validation. No second model, no guided-only fields that change simulation semantics. |
| P4 | **The backend is the only authority** on validity and on every number ([ADR-005](../decisions/adr-005-metric-contract-design.md), [ADR-017](../decisions/adr-017-ai-validation-boundary.md)). The frontend explains; it does not re-derive or silently repair. |
| P5 | **Never lose the user's work** when moving between guided and expert views; never rewrite input silently. |
| P6 | **A capability the backend does not provide is not shown** (claim rule 8). |
| P7 | **Facts, assumptions, recommendations and measurements are labelled apart** (§7.2). |

---

## 2. Users and representative use cases

Categories are taken from the [product story](../product/README.md#who-it-is-for) and [V3 strategy §1](../roadmap/V3_PRODUCT_STRATEGY.md#1-product-direction); no new user research has been done, so every need below is an assumption to be tested (§10, OQ-1).

| ID | User | Knows | Needs from the next generation |
| --- | --- | --- | --- |
| U1 | **Planning officer / community representative** (not a traffic engineer) | How busy the junction is, how many lanes | Describe a junction and a question in everyday words; defaults that are safe to accept; to be told what a choice will change; to read trade-offs without a verdict |
| U2 | **Student / researcher** | Gap acceptance, delay, confidence intervals | Unusual layouts and controls, repeatable runs, provenance, scripted access |
| U3 | **Traffic engineer / technical reviewer** | Phase plans, saturation flow, HCM | Full parameter control; to inspect exactly what will run; no guided step that hides or blocks a parameter |
| U4 | **Integrator / developer** | REST, JSON Schema | A stable contract that guided, visual and AI features all use |

| ID | Use case | Initiative |
| --- | --- | --- |
| UC-1 | "A four-arm junction with a busy main road and a quiet side road — should I try signals or a roundabout?" without first learning what a phase plan is | Guided |
| UC-2 | Switch a roundabout between conventional and metered entry and see what changed | Guided (today only partly served: [audit O1](../product/ux-audit-v3-w2-followup.md#2-observed-problems)) |
| UC-3 | Sketch a T-junction and a nearby roundabout, connect them with a road, send a flow through both | City Studio |
| UC-4 | Start from a template ("suburban crossroads"), change two roads, save it | City Studio / Guided |
| UC-5 | "Here is my junction and the evening peak; what could I try?" — receive a short, labelled list of candidate configurations, run them, read the measured trade-offs | AI Analyst |
| UC-6 | An expert opens the scenario a guided session produced, edits a green time by hand, goes back, and nothing is lost or contradicted | Cross-cutting |

---

## 3. Current pain points (verified)

Detail and file references are in the [UX audit](../product/ux-audit-v3-w2-followup.md#2-observed-problems); the points that motivate the next generation are:

| # | Pain point | Evidence |
| --- | --- | --- |
| PP-1 | The user can describe only the **three controls the junction builder lists**; a fourth (metered entry) was reachable only inside "Advanced" until the follow-up change | `components/scenario/builderOptions.ts` [V] |
| PP-2 | A scenario is **one junction with four compass slots** (arms may be absent; each arm's bearing may deviate ≤ 30° from its slot); no free-form layout | `scenario/scenarioTypes.ts` (`MAX_SLOT_DEVIATION = 30`), [configuration contract](../architecture/06-scenario-configuration-contract.md) [V] |
| PP-3 | A **network document exists** (nodes, edges, routes, demand) with validate/compile/fingerprint endpoints, but **multi-junction networks are not simulated and there is no network editor or viewer** | `backend/src/networks/*`, `/api/v2/networks`, [ROADMAP V1.9](../ROADMAP.md) [V] |
| PP-4 | The user must already know **what to compare**: the planner's alternatives are strategies chosen from a list; suggestions for reasonable alternatives do not exist | `components/planner/PlannerPage.tsx` [V] |
| PP-5 | The engine has **no time-varying demand and no incident or lane-closure support**, so "evening peak" can only be a stationary demand level | [V3 strategy §16, item 1](../roadmap/V3_PRODUCT_STRATEGY.md) [V] |
| PP-6 | Terminology (critical gap, all-red, spillback) appears without explanation in Advanced settings | `components/scenario/AdvancedSettings.tsx` [V] |

---

## 4. Journeys

### J-G · Guided (U1)

1. **Purpose** — "What do you want to find out?" (pick one: compare control types · see whether a design copes with more traffic · check a junction layout) [P].
2. **Junction** — arms, lanes (existing step 1–2 vocabulary).
3. **Traffic** — "how busy" levels (existing `BUSY_LEVELS`), time period as a *stationary* level only (PP-5).
4. **Controls to try** — the supported controls with one-line descriptions and the default pre-selected.
5. **Summary and validation** — a plain-language statement of what will run, with the backend's verdict; blocking issues name the field and offer a one-click fix only where the fix is deterministic.
6. **Run → watch → results** — the existing three-stage flow.
7. **Refine** — "change one thing and compare again" re-enters step 2–4 with the document intact.

### J-C · City Studio (U1–U3)

Start from template or blank → place and connect elements → inspect validation and topology → assign traffic sources/destinations → configure each junction (the existing builder, opened on that node) → compile to documents → run → results per node and per route.

### J-A · AI Analyst (U1–U2)

Supply or build network → deterministic completeness check ("what is missing?") → user states objective and constraints → structured **assessment** → ≤ N candidate configurations → backend validation of each → reproducible scenarios generated → ordinary experiment run → measured comparison against the stated objective → trade-off explanation with assumptions and uncertainty → refine.

### J-X · Round trip (all)

At any point the user may open the **same** scenario in the expert builder; edits there appear in the guided summary; the guided view never reverts an expert edit it does not understand (it shows it as "customised").

---

## 5. Guided Scenario Builder (GSB)

### 5.1 What it is — and is not

A **guided lens** over the existing scenario builder: a short sequence of plain-language choices that fill the same `ScenarioDocument` the expert builder edits. It is **not** a wizard that must be completed, a separate document type, or a gate in front of Advanced settings. [P]

### 5.2 Information architecture [P]

| Area | Content | Existing component it extends |
| --- | --- | --- |
| Purpose and objective | Question to answer; which metrics the results lead with | Planner objective field (`PlanningStudyRequest.objective`) [V] |
| Network structure | Arms, lanes, template | Builder steps 1–2, presets |
| Controls | Supported controls + explanation | `JUNCTIONS`, entry-control choice (follow-up change) |
| Demand | Busy levels, vehicle mix, stationary period | Builder steps 3–4 |
| Run settings | Duration, seed, replications | Builder step 5, planner repetitions |
| Summary and validation | Plain-language summary, backend verdict, "what happens if I leave defaults" | `describeScenario`, `useScenarioValidation` |
| Compare | Alternatives, evaluation metrics | Planner alternatives (backend already accepts a per-alternative merge `patch` [V] `backend/src/planning/models.py:36`) |

### 5.3 Functional requirements

| ID | Requirement | Verification (planned) |
| --- | --- | --- |
| GSB-F-01 | Every guided choice reads and writes the `urbanflow-scenario` document; a guided session's export imports into the expert builder unchanged and vice versa. | Round-trip test over presets and guided outputs |
| GSB-F-02 | Guided mode adds **no field** to the scenario contract. Guidance metadata (which step was visited) is client-local. | Schema-diff test = empty |
| GSB-F-03 | The control list offers only strategies the backend lists in its capability response; an unsupported control is absent, not disabled-with-promise. | Capability-driven render test |
| GSB-F-04 | Each control shows a ≤ 2-sentence description of what it changes and one thing it does **not** model. | Content review; test that every control has both |
| GSB-F-05 | Defaults are visible: the summary states which values are defaults and what they are. | Component test |
| GSB-F-06 | Validation runs before Run, with the backend's messages; a message that names a fixable field links to it. A fix is offered only if deterministic and is applied only on click (P5). | Test per fixable code (start: `metering.missing_arm`, turning shares into an absent arm) |
| GSB-F-07 | Guided and expert views share one validation call and one error vocabulary. | Single `useScenarioValidation` consumer test |
| GSB-F-08 | "Customised" indicator when the document differs from what guided choices would produce. | Test with an expert edit |
| GSB-F-09 | The user can leave guided mode at any step into the expert builder with all input retained (UC-6). | E2E test |
| GSB-F-10 | Suggested alternatives are drawn from a **deterministic** list owned by the backend or a versioned frontend table; each is validated like user input and labelled "suggested". | Test that a suggestion that fails validation is not shown as runnable |
| GSB-F-11 | Time-of-day is expressed only as stationary demand levels until the engine supports time-varying demand. The UI says so. | Copy test |
| GSB-F-12 | Evaluation metrics offered are the existing catalogue; no new metric, no composite "score". | Catalogue-membership test |

### 5.4 Usability and accessibility [P, building on existing practice]

GSB-U-01 every control has a visible label and a programmatic name; GSB-U-02 keyboard-complete, visible focus; GSB-U-03 status never by colour alone (text label as in the metered-entry status panel [V]); GSB-U-04 axe clean on every new screen (existing `axeViolations` harness [V] `frontend/src/test/axe.ts`); GSB-U-05 usable at 375 px for read-only steps (the V3 plan already targets 375 px read-only views for W9 [V]); GSB-U-06 plain-language terms are defined once in a glossary reused by tooltips and the results text (no second copy).

### 5.5 MVP and exclusions

**MVP [P]:** a "Purpose → Junction → Traffic → Controls → Summary" path over **one junction**, using today's controls, defaults, deterministic fixes for the two known invalid-state cases, the J-X round trip, and a read-only summary. **Excluded from the MVP:** multi-junction, time-varying demand, free-text input, AI suggestions, new metrics, a persisted "guided session" object, a redesigned navigation model.

**Success criteria [P, to be measured with moderated sessions, not assumed]:** a first-time U1 participant reaches a valid run without opening Advanced; no participant is blocked from reaching an expert parameter; zero guided-only validation rules (parity test).

---

## 6. Visual City Studio (CS)

### 6.1 What it is — and is not

A visual editor for **a road network that compiles into the existing `urbanflow-network` v1 document** (nodes, edges, routes, demand) with each junction node holding an ordinary `urbanflow-scenario`. It is not a new simulator, not a GIS importer, and not a replacement for the junction builder. [P]

### 6.2 Reusable foundation (verified)

| Capability | Where | Status |
| --- | --- | --- |
| Network document, strict models, canonical form, fingerprint | `backend/src/networks/models.py` | Implemented [V] |
| Network validation, compile, from-scenario, result structure | `backend/src/networks/{validate,compile,from_scenario,execution}.py`, `/api/v2/networks` | Implemented; API only [V] |
| Execution model | `one-way-coupled-sequential` through a `JunctionExecutor` protocol | Composition logic exists; **no network run is exposed** [V] |
| Junction as a scenario; present/absent arms; bearings ≤ 30° from slot | `ScenarioDocument` | Implemented [V] |
| Junction preview rendering | `components/scenario/JunctionPreview.tsx`, `RoundaboutMap.tsx`, `IntersectionMap.tsx` | Implemented [V] |

### 6.3 Functional requirements

| ID | Requirement | Verification (planned) |
| --- | --- | --- |
| CS-F-01 | The studio's saved form is the existing `urbanflow-network` document. Visual-only data (positions, zoom) is stored in a separate, optional, ignorable `layout` companion that does not enter the fingerprint. **[Decision needed — OQ-4.]** | Fingerprint equal with and without layout |
| CS-F-02 | A node is exactly one of: junction (holds a scenario), origin, destination — the current `NodeSpec.kind`. | Model test |
| CS-F-03 | An edge connects two node arms, is one-way with `lanes` 1–8 and the existing bounds, and shows its length and speed limit. | Bounds copied from the model, not re-typed (parity test) |
| CS-F-04 | The studio shows the backend's `/networks/validate` result, anchored to the offending element, using the backend's messages. No second topology validator in the client beyond preventing impossible gestures (connecting an edge to a nonexistent arm). Today the messages are prose that names the element (`Edge 'e1': …`) without stable codes [V]; anchoring on prose would be brittle, so stable codes (or structured locations) are an additive backend prerequisite ([architecture §5.1](next-generation-architecture.md#51-validation-requirements-for-networks-p)). | Test that every anchored message is a backend message and anchors by code |
| CS-F-05 | Junction nodes open the existing junction builder; closing it writes the scenario back unchanged. | E2E |
| CS-F-06 | Templates are saved ordinary network documents; "generated from a description" is a **later** phase and produces a document the user can edit. | Phase gate |
| CS-F-07 | Routes are chosen from origin→destination paths the topology allows; demand per route is in vehicles per hour using the existing bound (≤ 7,200). | Test |
| CS-F-08 | Until a network can be simulated, the studio's primary result is **validation, topology and compile output**, and says that multi-junction simulation is not available. It does not display fabricated network results. | Copy and capability test |
| CS-F-09 | Importing real-world geographic data is out of scope until the repository supports it reliably. | — |
| CS-F-10 | Round trip: `network → document → studio → document` yields an equal document (canonical form). | Property test using `serialize_network` / `canonical_network` |

### 6.4 Usability and accessibility [P]

CS-U-01 every canvas operation has a **non-pointer** equivalent (keyboard placement, list/table view of nodes and edges, form-based edge editing); CS-U-02 a text or table alternative to the canvas that exposes topology and validation (the canvas is never the only representation); CS-U-03 selection, focus and validation state never by colour alone; CS-U-04 undo/redo; CS-U-05 pan/zoom without pointer-only gestures; CS-U-06 axe clean on the non-canvas surfaces, with canvas semantics specified before build.

### 6.5 MVP and exclusions

**MVP [P]:** a **single-junction visual composer** — place a junction, set arms (present/absent), draw edges to origin/destination gates, set lanes and demand — that compiles to `scenario_to_network`'s shape and validates with the existing endpoints; templates; the table view. This delivers the network editing model and the compile/round-trip contract **without** requiring multi-junction simulation. **Excluded:** multi-junction runs, free geometry beyond the 30° slot rule, GIS import, curved roads, pedestrians/cyclists, lane-level turn pockets beyond the existing lane metadata, collaborative editing.

---

## 7. AI Traffic Analyst (AIA)

### 7.1 What it is — and how it relates to V3.0's AI features

The Analyst is an **assessment-and-recommendation layer built on the V3.0 Copilot and Robustness Lab**, not a third parallel AI system. The Copilot ([strategy §15.1](../roadmap/V3_PRODUCT_STRATEGY.md#151-ai-traffic-experiment-copilot)) turns a **question** into a validated `ExperimentProposal`; the Analyst adds an upstream step that derives facts from a **network** and states what is missing, then feeds the same proposal contract, validation boundary ([ADR-017](../decisions/adr-017-ai-validation-boundary.md)) and experiment runner. It is gated on the Copilot's evaluation having passed. **Nothing in this section is an AI integration; no provider, dependency or backend is added by this planning.**

### 7.2 Evidence taxonomy (required in every output)

| Class | Meaning | Source | Display |
| --- | --- | --- | --- |
| **Fact (user-supplied)** | Stated by the user | Form/text, with field provenance | "You said" |
| **Derived** | Computed deterministically from the network/scenario | Backend (counts of arms, lanes, total demand, capacity ratio, validity) | "From your network" |
| **Assumption** | Introduced for analysis; may be changed | Rule table or model, `basis = assumed`, with rationale | "Assumed" + editable |
| **Recommendation** | A candidate configuration to test | Proposer (deterministic or model) | "Suggested to try — not a finding" |
| **Measured** | Produced by the simulation engine | Experiment result and evidence object | "Measured" with N/r/total runs |
| **Uncertain / unknown** | Missing data, ineligible comparison, out-of-scope | Eligibility checklist, missing-information list | "Not established" |

### 7.3 Functional requirements

| ID | Requirement | Verification (planned) |
| --- | --- | --- |
| AIA-F-01 | Every output item carries exactly one class from §7.2; unclassified text is not rendered. | Schema requires `class`; render test |
| AIA-F-02 | Missing information is computed **deterministically** (a rule table over the validated network and scenario) and shown before any recommendation; a model may not hide or add items to it. | Rule-table unit tests |
| AIA-F-03 | Recommendations use the Copilot's `urbanflow-experiment-proposal` v1 contract; the Analyst adds no configuration field of its own. | Schema-diff test |
| AIA-F-04 | A recommendation is a candidate configuration only if the backend validation boundary marks it `validated`; the model never sets `validated`. | Invalid-stub test (C1 equivalent) |
| AIA-F-05 | Scenarios generated from recommendations are reproducible from `(proposal id, catalogue hash, seed policy)`; the Analyst never changes seeds unless the user does. | Fingerprint equality test |
| AIA-F-06 | The Analyst never states that a strategy is optimal or safe, never presents a simulation as proof of real-world effect, and never invents network properties or observations. | Adversarial set (extends `copilot-eval-v1`) |
| AIA-F-07 | A comparison against the user's stated objective uses the existing indicators and the Robustness eligibility rules; an ineligible comparison is reported as such. | Test |
| AIA-F-08 | The explanation of results is grounded (every numeral traces to the evidence object); unfavourable findings for the user's preferred option are always included. | Grounding check (Copilot C5/C6) |
| AIA-F-09 | Provider off / failed / over budget ⇒ the deterministic assessment and the rule-based candidate list still work, labelled as not AI. | Fallback test |
| AIA-F-10 | What leaves the system for a provider is listed before use; no network geometry or demand leaves the system without a stated reason and consent (data handling is D-AI1). | Privacy review |
| AIA-F-11 | Recommendations are limited to what the engine supports; features the engine lacks (time-varying demand, incidents, weather) are not proposed. | Catalogue-membership test |

### 7.4 MVP, limitations and non-goals

**MVP [P]:** the **deterministic** part only — a "what is missing / what is this network" assessment from derived facts, plus a rule-based list of ≤ 3 candidate configurations drawn from the strategy catalogue, each validated and runnable through the existing planner. Model-written text is a **later** increment, after the Copilot passes its evaluation.
**Limitations to state in the product:** simulated results are conditional on stated assumptions, are not calibrated to any real site, and are not a prediction. **Non-goals:** claiming a universally best model or controller; training or fine-tuning models; autonomous execution without user confirmation; reading real-world data feeds; any change to engine physics or seeds.

---

## 8. Cross-cutting requirements

| ID | Requirement |
| --- | --- |
| XC-01 | **Shared definitions.** Scenario, network, validation, strategies, metrics and fingerprints come from the existing documents and registries; no feature may define its own copy. |
| XC-02 | **Provenance.** Every run started from a guided, studio or analyst flow carries the scenario fingerprint; flows that involve generated content also record the generator id and version (the Copilot's `reproducibilityMetadata` pattern). |
| XC-03 | **Explanation parity.** Any text explaining a control, metric or limitation is written once and reused (the audit found copy that contradicted a feature: [audit O4](../product/ux-audit-v3-w2-followup.md#2-observed-problems)). |
| XC-04 | **Determinism.** No new feature changes seeds, execution order, physics, time-step or existing fingerprints; parity tests are part of each phase's exit. |
| XC-05 | **Backward compatibility.** Existing scenarios, packages and API clients keep working; additions are additive and versioned per [ADR-013](../decisions/adr-013-v3-integration-contract-and-versioning.md). |
| XC-06 | **Accessibility baseline.** axe-clean new screens, keyboard completeness, no colour-only status, a non-canvas alternative for every visual editor surface. |
| XC-07 | **Honest claims.** The claim rules of strategy §1 apply to every new screen and document. |

---

## 9. Dependencies and assumptions

| Depends on | Used by | State [V] |
| --- | --- | --- |
| `urbanflow-scenario` v1 + `/api/v1/scenarios/validate` | all | Implemented |
| `urbanflow-network` v1 + `/api/v2/networks/*` | City Studio, Analyst | Implemented, API only; multi-junction not simulated |
| Planner alternatives with merge `patch` | Guided compare, Analyst candidates | Backend implemented; frontend request type does not expose `patch` |
| Strategy registry and compatibility validator (V3.0 W3, ADR-014) | Guided control list, Analyst catalogue | **Planned** — not built |
| Copilot proposal contract, validation boundary, evaluation set (V3.0 W5, ADR-017 *Proposed*) | Analyst | **Planned** — not built; provider decision D-AI1 open |
| Robustness Lab and `/api/v3/experiments` (V3.0 W1) | Analyst evaluation | Implemented |
| Capability endpoint reporting what the backend supports | Guided (GSB-F-03) | `/api/v3/capabilities` exists (W1) and reports feature flags (`aiCopilot`, `discoveryLab` and others, all `false` today) and the strategy list; it does **not** list scenario-level options such as roundabout entry control, so the guided control list would need an additive extension (ADR-013) [V] `backend/src/experiments/service.py:361` |
| Time-varying demand | Guided time-of-day, Analyst "peak" scenarios | **Not available**; would be a reproduction-critical engine change (sprint plan §3.9 estimate ≈ 1.5 ED, unverified) |

**Assumptions:** one engineer; V3.0 delivery has priority; the existing frontend stack (React, Vite, vitest, axe-core) is retained; no new testing framework.

---

## 10. Open questions (for the product owner)

| ID | Question | Why it matters |
| --- | --- | --- |
| OQ-1 | Is there any access to real U1 participants for moderated sessions? | All needs here are assumptions until observed |
| OQ-2 | Should guided mode be a mode of the existing Compare/Planner pages or a separate route? | Navigation model changes need approval (policy §3) |
| OQ-3 | Is a single-junction visual composer an acceptable City Studio MVP, or is multi-junction simulation a prerequisite? | Determines whether City Studio waits for network execution |
| OQ-4 | May visual layout be stored as an optional companion to the network document? | A contract decision (ADR candidate) |
| OQ-5 | Are time-varying demand and incident support wanted before "peak hour" guidance is offered? | Engine change; reproduction-critical |
| OQ-6 | D-AI1: provider, budget and data-handling for any model-written text | Gates the model part of the Analyst |
| OQ-7 | Should planner alternatives expose per-alternative control settings (e.g. conventional vs metered roundabout in one study)? | Backend supports it; needs a UX decision about where the timings come from |
| OQ-8 | Which level-of-service band set should a metered-entry roundabout use? Today roundabouts use the unsignalised bands ([audit O7](../product/ux-audit-v3-w2-followup.md#2-observed-problems)) | Metric interpretation; a PO/research decision, not a UI one |
