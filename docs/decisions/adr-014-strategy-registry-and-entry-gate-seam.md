# ADR-014: Strategy Registry and Entry-Gate Seam

## Status

**Accepted** — the product owner passed the V3.0 design-approval gate G-D on 2026-10-14 (recorded on [#150](https://github.com/Viraj281105/Traffic-Simulation/issues/150)) and accepted this ADR, with decision **D-SR1** (`metered_entry` committed, `phased_priority` conditional/stretch), on 2026-10-19 so that W2 ([#163](https://github.com/Viraj281105/Traffic-Simulation/issues/163)) can begin. The W2 implementation plan is [`docs/engineering/v3-w2-signalised-roundabout-plan.md`](../engineering/v3-w2-signalised-roundabout-plan.md). Drafted under task B0-2 ([#173](https://github.com/Viraj281105/Traffic-Simulation/issues/173)).

## Date

2026-10-14 (draft) · 2026-10-19 (accepted)

## Context

Today UrbanFlow offers three isolated control choices (fixed-time signal, adaptive signal, conventional roundabout) selected by `geometry.intersectionType` and `controller.signalControl`. The combination adaptive + roundabout is rejected by validation. `RoundaboutController` is about 1,250 lines of tuned gap-acceptance logic with no signal hook. Signalised roundabouts (signals on selected entries) are used in practice to meter flow and cannot be tested in UrbanFlow. Source: strategy §13; supersedes the implementation note in [ADR-012](adr-012-future-controller-extensibility.md) (decorator registry not built).

## Problem Statement

How can new geometry-by-control combinations be added **without** changing existing results, weakening the roundabout's safety logic, or allowing arbitrary code to run?

## Decision

1. **Layered strategy descriptor** (`urbanflow-strategy` v1, `extra="forbid"`): geometry · movement topology · right-of-way rule · control policy · adaptation logic · priority overlay (reserved, deferred). It records `id`, `version`, `status` (`stable` | `experimental`), parameter bounds, invariants and a fingerprint.
2. **Registry with compatibility validation.** Built-in strategies register at import and pass a self-check. A rule table rejects contradictory layer combinations **before** any simulation object is built, with a coded, human-readable message and, where possible, a suggestion. Every rule has a rejecting unit test. The old error "adaptive applies to a signalised junction" is superseded by registry messages.
3. **No uploaded code.** New strategies enter only through reviewed pull requests; the registry cannot register from request data (tested).
4. **Fingerprint parity.** The three existing strategies map into the registry **without changing any existing scenario or result fingerprint** (a test fingerprints every fixture scenario before and after). New strategies' fingerprints include descriptor `id`, `version` and resolved parameters; the aggression profile (ADR-016) is an independent component.
5. **Signalised roundabout by composition.** `SignalisedRoundaboutController` owns a `RoundaboutController` and a phase engine reusing the existing `Phase` structure. They connect through one narrow seam, an **`EntryGate`** protocol, `allows(approach, lane, now) -> GateDecision`, consulted where the roundabout decides whether a head vehicle may proceed. The default gate is `AlwaysOpen`. No multiple inheritance and no `isinstance` ladders.
6. **Committed mode is `metered_entry`.** A signal decides only *whether a vehicle may proceed to the yield line*; the existing gap-acceptance, exit-yield and keep-clear logic stays in force, so red can only remove entry opportunities. `phased_priority` (suspending circulating priority) is **conditional/stretch** and needs its own movement-conflict contract and ring-clearance proof (D-SR1).
7. **Hard test.** With `AlwaysOpen`, the conventional roundabout is **bit-identical** (same metric and snapshot fingerprints) to the unmodified behaviour. Touching `controllers/roundabout.py` is physics-adjacent and requires this test and a recorded reason.

## Alternatives Considered

- **Subclass `RoundaboutController`:** shorter, but couples signal logic to about 1,250 lines of tuned code and invites accidental behaviour change.
- **Add signals inside the roundabout controller:** no seam, so bit-identity would be hard to prove.
- **Plugin loading of external code:** most flexible but a permanent security risk; rejected for V3.0 (strategy §7).
- **Full `phased_priority` first:** more realistic for some designs but genuinely new right-of-way rules with no safety argument yet.

## Trade-offs

- **Pros:** the safety argument is structural (red can only remove opportunities); existing results provably unchanged; extensible by pull request.
- **Cons:** the seam must be spiked and tested before the controller exists (0.5 ED); `metered_entry` cannot represent fully phased rings.

## Consequences

- W2 starts with an ADR-plus-seam spike, then the seam and equivalence test, before the controller (SP §3.3).
- W3's registry shrinks to its core if gate G-SR fails.
- The adaptive signalised roundabout (#164) is conditional on G-SR.

## Future Considerations

`phased_priority`; priority-aware (bus/emergency) layer 6, deferred behind gate G-E; learned policies as `experimental` descriptors (deferred); multi-junction coordination (needs network simulation).

## Related ADRs

[ADR-012](adr-012-future-controller-extensibility.md) · [ADR-013](adr-013-v3-integration-contract-and-versioning.md) · [ADR-016](adr-016-driver-aggression-profile.md)
