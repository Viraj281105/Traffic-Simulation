# ADR-017: AI Validation Boundary

## Status

**Proposed** — draft for the G-D design-approval review (task B0-2, [#173](https://github.com/Viraj281105/Traffic-Simulation/issues/173)). The provider choice is a separate decision (**D-AI1**, due before Fri 27 Nov); this ADR does not select a provider.

## Date

2026-10-14 (draft)

## Context

V3.0 has two AI features: the **Experiment Copilot** (language-model proposals and interpretation, W5, #166) and the **Strategy Discovery Lab** (bounded multi-objective evolutionary search, W6, #157). Neither may weaken the platform's guarantees: authentication, ownership, quotas, input validation, determinism, honest claims. The Discovery Lab is optimisation, not a learned model, and is named that way. Source: strategy §15.

## Problem Statement

How do generative and search components propose experiments and strategies while the deterministic backend remains the only authority over what runs and what is claimed?

## Decision

1. **Output is a proposal or an interpretation**, never an executed experiment or a verified result. Measured output and model-generated text are structurally separate in every API and screen.
2. **One deterministic validation boundary** sits between every AI component and the engine: `extra="forbid"` schemas, the existing config validators, the strategy compatibility validator (ADR-014) and the quota estimator. Validity fields (`validated`, `issues[]`) are set by the backend, never by the model. A model may paraphrase an error but may not repair silently; a repair is a new proposal, validated again (at most 2 attempts).
3. **No tools, no network, no files for the model.** It sees only the question, the versioned capability catalogue and (for summaries) the evidence object of the caller's own experiment. The provider key stays server-side.
4. **Inspect-and-confirm.** Submission needs explicit user confirmation with a single-use token bound to the user and the content hash; another user's proposal id is 404. The search runs only on the user's explicit request within a budget.
5. **Grounded interpretation.** A grounding check verifies every numeral and named entity in model text appears in the evidence object. Mandatory sections (eligibility class, N/r/total-runs line, real-world-validity line, limitations, every unfavourable finding for the user's preferred alternative) are inserted deterministically. A failed check suppresses the model text and shows the template summary.
6. **Fallback.** With the provider off, timed out, over budget, schema-invalid or grounding-failed, the deterministic proposer and template summary take over, and the UI says so. Core workflows never depend on a model. The deterministic proposer is **not called AI**.
7. **Cost and abuse controls.** Per-user daily proposal and summary caps and token caps, a global monthly spend cap with a kill switch, metadata-only logging (no prompt or output payloads by default), prompt-injection and exfiltration tests.
8. **Discovery Lab integrity.** Search only over registered strategies; every genome passes the compatibility validator before simulation; tuning, selection and held-out seed pools are disjoint and the held-out list is hash-committed before the search; a spy test proves held-out results are never read early; baselines are existing controllers evaluated unchanged; the report always shows held-out results, including a planted case where the best candidate loses.
9. **Claims.** "AI feature" is claimed only when the evaluation passes: Copilot acceptance C1–C9 on `copilot-eval-v1` with a connected provider, Discovery Lab D1–D10. Otherwise the Copilot ships as the deterministic assistant and the AI-feature count is stated as one. Allowed: "AI-assisted proposal, validated and confirmed". Not allowed: "AI-verified", "AI-optimised", or any statement that a model ran or measured anything.

## Alternatives Considered

- **Let the model call the API directly with tools:** removes a review step but lets prompt injection reach quotas and data; rejected.
- **Auto-run valid proposals:** faster, but removes the user's check and the cost estimate; rejected.
- **Learned (DQN/RL) strategy search:** deferred; would enter later as `experimental` descriptors.
- **Trust the model's own validity claims:** rejected; validity is computed by the backend.

## Trade-offs

- **Pros:** an AI failure cannot corrupt results or bypass limits; claims are measurable and withdrawable; a no-provider path still works.
- **Cons:** extra latency and clicks; deterministic summaries can read stiffly; evaluation sets cost effort (about 0.5 ED).

## Consequences

- W5 gate G-AI-A may withdraw the AI claim; W6 gate G-AI-B may hold the Lab back as "experimental, not released".
- Quotas from ADR-013 apply to AI calls and to search budgets, at submission and during execution.
- Privacy: what leaves the system for a provider must be listed in `docs/ai/copilot.md` before launch (data handling is part of D-AI1).

## Future Considerations

Learned policies, an AI report generator, regime discovery and incident simulation are deferred (strategy §16). A shared store for spend caps is needed before running more than one process.

## Related ADRs

[ADR-013](adr-013-v3-integration-contract-and-versioning.md) · [ADR-014](adr-014-strategy-registry-and-entry-gate-seam.md) · [ADR-015](adr-015-robustness-lab-uncertainty-design.md) · [ADR-016](adr-016-driver-aggression-profile.md)
