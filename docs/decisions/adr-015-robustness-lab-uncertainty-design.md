# ADR-015: Robustness Lab Uncertainty Design

## Status

**Proposed** — draft for the G-D design-approval review (task B0-2, [#173](https://github.com/Viraj281105/Traffic-Simulation/issues/173)). Depends on product-owner decision **D5** (statistical contract and manifest). Blocks W1 (#151, #152) if late.

## Date

2026-10-14 (draft)

## Context

V2.0 planning studies report seed-to-seed uncertainty only. Planners also need to know whether a preferred control strategy **survives uncertainty in demand and driver behaviour**. That is parameter uncertainty, and the inputs are assumptions, not data. The engine has no explicit reaction delay and no time-varying demand, and V3.0 may not change simulation physics. Source: strategy §5 (normative); [V2.0 audit](../roadmap/V2_COMPLETION_AUDIT.md).

## Problem Statement

How do we compute and report robustness honestly: what is sampled, what counts as a sample, what may be claimed, and when a result is adequate?

## Decision

1. **Specification.** `urbanflow-uncertainty-spec` v1: factors with id, kind, distribution (uniform, triangular, truncated normal, lognormal), bounds, `basis` (`assumed` | `observed` | `user`) and a mandatory rationale when assumed. It is fingerprinted **before** any run.
2. **Factors only through existing inputs** (demand scales, turning shift, mix shift, IDM headway scale, desired-speed scale, max-acceleration scale). **No physics edits.** Headway scale is labelled a proxy.
3. **Unit of inference is the condition**, not the run. Results always show **N conditions, r replications and total runs** separately; effective sample size is N_valid.
4. **Sampling:** seeded Latin-hypercube stratification. A perturbed scenario that fails validation is rejected and counted, never repaired.
5. **Paired common random numbers:** all alternatives share the sampled scenario and engine seed; difference D(i, a) against the baseline on one pre-declared primary indicator (default mean delay after warm-up).
6. **Statistics:** win/tie/loss with tolerance τ and 95 % Wilson intervals; bootstrap intervals for D; regret (mean and p95); preference share; one-factor flip detection by strata reported as a boundary range; Spearman sensitivity as association only. No p-value ranking and no "winner".
7. **Invalid runs:** a failed, timed-out, limit-reached or non-finite run excludes the **whole condition for every alternative**; exclusions are counted by reason and stratum; more than 10 % overall or 20 % in a stratum makes the result not eligible.
8. **Eligibility** (below 30 valid conditions exploratory; otherwise indicative until all of precision ≤ 0.10 half-width, split-half stability, r ≥ 2, exclusion limits and pre-declaration pass). "Eligible" means adequately sampled for the declared assumptions, **not** that the model is correct.
9. **Real-world validity** is shown separately and defaults to *None — assumptions only*. The word "calibrated" is not used (strategy §8).
10. **Determinism:** aggregation sorts by task id so completion order cannot change results; same specification and seed give an identical result fingerprint.

## Alternatives Considered

- **Treat runs as the sample size:** inflates apparent precision; rejected as misleading.
- **Sobol indices and 2-D flip surfaces:** richer but larger and harder to explain; excluded from V3.0.
- **Declare a fixed "sufficient N" (such as 100):** rejected; N is derived from precision, not fixed.
- **Repair invalid perturbations:** biases the sample; rejected.

## Trade-offs

- **Pros:** claims are limited to what the method supports; the wording is testable; the same machinery serves signalised roundabouts, aggression, the Copilot, the Discovery Lab and the breakpoint explorer.
- **Cons:** conservative output can look unexciting; more runs needed than a naive comparison; intervals are approximate under Latin-hypercube stratification (stated in the viewer).

## Consequences

- Hand-computed fixtures and a planted-flip stub are required tests (W1).
- Flip detection and sensitivity (W3), split-half stability and variance split (W4), cancel/resume (W7) and the full viewer (W9) are scheduled completions.
- Compute estimates stay "unverified" until benchmarked on the presentation machine (B0-1).

## Future Considerations

Observation-backed factors (`basis = observed`) once real data exists; demand surge scenarios need a separate time-varying-demand capability (about 1.5 ED, not in V3.0).

## Related ADRs

[ADR-013](adr-013-v3-integration-contract-and-versioning.md) · [ADR-016](adr-016-driver-aggression-profile.md) · [ADR-017](adr-017-ai-validation-boundary.md)
