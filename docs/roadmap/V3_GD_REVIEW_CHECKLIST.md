# G-D review checklist — V3.0 design approval

> **Purpose:** a working checklist for the product owner's G-D review. It does not approve anything by itself; record the outcome on #150.
> **Gate:** G-D, proposed Fri 23 Oct 2026 (fallback Mon 26 Oct). Defined in [V3 weekly sprint plan §4](V3_WEEKLY_SPRINT_PLAN.md#4-gates).
> **Source:** [V3 product strategy](V3_PRODUCT_STRATEGY.md). Section numbers below refer to it.
> **Reading time (estimate, unverified):** about 2–3 hours for the full pass; the "must decide" boxes alone are about 30 minutes.
> **How to use:** tick *Approve*, *Change* (write what) or *Reject* for each item. A *Change* or *Reject* on a "blocks" item means G-D does not pass until it is resolved.

Legend: **Blocks** = what cannot start if this is unresolved.

---

## 0. Before you start

- [ ] G-V2 passed (13 Oct, commit `6b609ce`) — already satisfied
- [ ] Revision-3 plan documents read as one set: strategy, sprint plan, presentation plan, V2.0 audit
- [ ] You know your November availability (exam leave) — needed for D6

---

## 1. Funding and priorities — strategy §2 (decision D1)

Read: the ranking table. Blocks: all of Phase B.

- [ ] Committed set is what you want built: Robustness Lab · signalised roundabouts · strategy registry · high-aggression default · AI Copilot · Discovery Lab · developer platform (minimum)
- [ ] Conditional set is acceptable as droppable: adaptive signalised roundabout · W8 chaos/breakpoint · CSV/GeoJSON
- [ ] Deferred list is acceptable: learned (DQN/RL) controllers, visual strategy composer, regime discovery, incident/recovery, AI report generator, PWA
- [ ] "Never deferrable" list is correct (V2.0 gate, statistical contract, manifest, ownership/privacy tests, limitations page, AI validation boundary, fingerprint integrity)
- [ ] **D8:** emergency pre-emption deferred past V3.0 (frees about 4.5 ED)

## 2. Delivery option — decision D-SCOPE (strategy §3, §12)

Blocks: the whole calendar.

- [ ] **Option E** (recommended): extended calendar, interim presentation 26 Nov, final showcase Thu 7 Jan 2027
- [ ] Option S: final on 26 Nov, W1–W4 only, **no AI feature**
- [ ] Your June horizon is noted: 7 Jan is then an interim milestone, and Jan–Jun is a re-forecast after gate G-R1 (5 Nov)
- [ ] Planned load of 85 % is acceptable given exam leave (see D6)

## 3. Robustness Lab statistical contract — strategy §5 (decision D5)

Blocks: W1 if late. This section is **normative**: tests, API, viewer and slides inherit its wording.

- [ ] §5.1 Inputs: factors are only existing scenario inputs, **no physics change**; headway scale labelled a proxy; invalid perturbations are rejected and counted, never repaired
- [ ] §5.1 All factor distributions are stated as **analyst assumptions**, with a mandatory rationale when `basis = assumed`
- [ ] §5.2 Unit of inference is the **condition**, not the run; N, r and total runs always shown separately
- [ ] §5.3 Paired comparison with common random numbers; one pre-declared primary indicator (default: mean delay after warm-up)
- [ ] §5.4 Win/tie/loss with tie tolerance τ; Wilson and bootstrap intervals; no p-value ranking, no "winner"
- [ ] §5.5 Regret, preference share, flip point by strata (reported as a boundary range, not a point); Spearman sensitivity is association, not causation
- [ ] §5.6 Any failed run excludes the **whole condition** for every alternative; more than 10 % excluded (or 20 % in a stratum) means not eligible
- [ ] §5.7 Eligibility thresholds: below 30 conditions exploratory; precision half-width ≤ 0.10; split-half stability; r ≥ 2; exclusions in limits; pre-declaration
- [ ] §5.7 "Eligible" is understood as *adequately sampled for the declared assumptions*, **not** that the model is correct
- [ ] §5.7 Real-world validity shows *None — assumptions only* by default
- [ ] §5.8 Required output list is complete

## 4. Reproducibility manifest — strategy §6 (decision D5)

Blocks: W1 and W7.

- [ ] Manifest fields are what you want recorded (source and dirty flag, fingerprints, seeds, runtime and pinned dependencies, outputs, known nondeterminism)
- [ ] Two replay classes are acceptable and never confused: **exact** (identical fingerprint) vs **comparable** (statistical); otherwise **differs**
- [ ] A dirty working tree makes exact replay *unverifiable* (accepted)
- [ ] **D4:** one supported Python version across local, CI and Docker — recommended 3.11 (today 3.14.7 locally, 3.11 in CI and Docker). Decision: ______

## 5. Developer platform — strategy §7 (decision D3)

Blocks: W7.

- [ ] `/api/v3` namespace; `/api/v1` and `/api/v2` stay frozen (additive-only)
- [ ] Personal access tokens: created only in a browser session, hash stored, scopes, mandatory expiry (default 30 days, max 90), immediate revocation, max 10 active
- [ ] Quotas enforced at submission **and** during execution; in-process only (limitation recorded: needs a shared store before scaling out)
- [ ] Append-only audit table with no payloads or secrets
- [ ] Default-private resources; another user's id returns 404; no admin PAT
- [ ] `.ufpkg` import rules: size and entry limits, zip-slip rejected, schema validation, checksums, nothing executed; "integrity is not authenticity" stated
- [ ] **No code upload, no webhooks** — permanent for V3.0

## 6. Calibration terminology — strategy §8

- [ ] The four levels are the only allowed wording (framework availability · validation against supplied observations · parameter calibration · field-data calibration)
- [ ] The word "calibrated" is not used for UrbanFlow results except the narrow phrase "engine capacity calibration"
- [ ] You accept that V3.0 results carry **no real-world validity claim**

## 7. Composable strategies and signalised roundabouts — strategy §13 (decision D-SR1)

Blocks: W2, W3.

- [ ] §13.2 Six-layer model and the strategy descriptor are acceptable
- [ ] §13.3 **`metered_entry` is the committed v1**: the signal only decides whether a vehicle may proceed to the yield line, and the existing gap-acceptance logic stays in force. **D-SR1:** `phased_priority` stays conditional/stretch and is not scheduled
- [ ] §13.3 Design hinge accepted: the `EntryGate` seam in `RoundaboutController` (physics-adjacent), with a **bit-identity test** against the unmodified roundabout
- [ ] §13.3 Required tests accepted: collisions = 0, no deadlock, starvation bound, spillback not worse, benchmark ≤ 1.3× (unverified target)
- [ ] §13.3 Stated limits accepted: no claim of real-world superiority or safety; PET unavailable on curved paths
- [ ] §13.4 Adaptive variant is conditional on gate G-SR and droppable
- [ ] §13.5 Hybrid combinations: only per-entry policy is in scope; the rest is deferred
- [ ] §13.6 Registry takes built-ins only, no uploaded code; every rule has a rejecting test; **existing fingerprints must not change** (parity test)

## 8. High driver aggression — strategy §14 (decisions D-AG1, D-AG2)

Blocks: W4.

- [ ] **D-AG1:** new field `traffic.driverAggression ∈ {standard, moderate, high}`; **absent ⇒ `standard`**; `high` is written explicitly at new-scenario authoring boundaries only. Decision: ______
- [ ] **D-AG2:** `high` does **not** imply the existing `aggressiveTwoWheelers` flag (recommended: no). Decision: ______
- [ ] §14.2 Levers and proposed `high` starting values (T × 0.7, s₀ × 0.75, a × 1.15, speed +0.05 with ceiling 1.10 × limit, lane-change politeness × 0.5) are acceptable as *starting values to be fixed by spike AG-1*
- [ ] §14.2 `b` and IDM δ are **not** changed
- [ ] §14.2 Roundabout critical gap is parametrised **only if** the spike shows it dominates, with an ADR
- [ ] §14.3 Stored configs, `/api/v1`, `/api/v2` and V2.0 reports keep their meaning and fingerprints
- [ ] §14.3 `high` results are labelled "a simulation assumption, not a measurement of real-world driver behaviour"
- [ ] §14.4 108-cell interaction matrix accepted (collisions = 0 and no deadlock asserted; throughput and spillback **reported**)
- [ ] The default is merged only at the **end of W4**, so W1–W3 results are not redefined mid-sprint

## 9. AI features — strategy §15 (decision D-AI1 is separate and due by Fri 27 Nov)

Blocks: W5, W6.

**Common rules**
- [ ] AI output is a proposal or interpretation, never an executed experiment or verified result
- [ ] Every generated configuration passes the deterministic backend schema, rules, strategy compatibility check and quota estimator
- [ ] The model has no tools or network access; keys stay server-side
- [ ] No AI feature is described as functional until its evaluation passes

**A. AI Traffic Experiment Copilot (§15.1)**
- [ ] Flow accepted: question → validated proposal → inspect-and-confirm → ordinary `/api/v3` experiment
- [ ] The deterministic proposer is the fallback and is **not** called AI
- [ ] Acceptance criteria C1–C9 (§15.1.7) are acceptable. The AI claim is granted only if C3–C6 pass with a connected provider; otherwise it ships as a deterministic assistant and the AI-feature count becomes one
- [ ] Cost and abuse controls accepted: per-user caps, monthly spend cap with kill switch, prompt-injection tests, metadata-only logging

**B. AI Control Strategy Discovery Lab (§15.2)**
- [ ] Accurately named *bounded multi-objective evolutionary search*, not a learned model
- [ ] Searches registered strategies only; all candidates pass the compatibility validator
- [ ] Evaluated against the three baselines on held-out seeds and unseen conditions, with seed-pool disjointness asserted
- [ ] Acceptance D1–D10 (§15.2.8) accepted, including D7 honest reporting and D9 *run and reported, not required to win*
- [ ] Limitation accepted: tuned to this simulator, not to reality

## 10. Cross-cutting — strategy §9–§11, §16–§17

- [ ] §9.2 Emergency pre-emption gate G-E: expected to fail and defer (consistent with D8)
- [ ] §10 Feature boundaries (what is explicitly out)
- [ ] §11 Main risks read; capacity risk and the cut order are accepted (W8 → adaptive roundabout → viewer charts → Copilot LLM adapter → PATs → Discovery search)
- [ ] §17 Quality and research-validity rules (claims register, limitations on every screen)

## 11. Decisions that are not G-D but are due soon

| Decision | Due | Recommendation | Your choice |
| --- | --- | --- | --- |
| **D-PV** preview option | Fri 16 Oct | PV-1 | ______ |
| **D7** authorise `ROADMAP.md` edits (V3.0 section after approval) | with G-D | Approve | ______ |
| **D2** NumPy not required | with G-D | Defer | ______ |
| **D6** capacity and holiday availability (25 Dec – 1 Jan) | with G-D | Confirm; supply November leave dates | ______ |
| **D-AI1** LLM provider, budget, data handling | before Fri 27 Nov | (b) hosted API with hard monthly cap, behind a provider-agnostic adapter | ______ |

---

## 12. Outcome (fill in, then copy to #150)

- [ ] **PASS** — all "blocks" items approved
- [ ] **PASS with changes** — list: ______
- [ ] **FAIL** — B0 (26–28 Oct) is spent completing design and later dates slip one-for-one

Decided by: ______ · Date: ______ · Open items carried: ______
