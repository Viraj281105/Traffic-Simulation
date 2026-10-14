# ADR-016: Driver Aggression Profile

## Status

**Proposed** — draft for the G-D design-approval review (task B0-2, [#173](https://github.com/Viraj281105/Traffic-Simulation/issues/173)). Depends on product-owner decisions **D-AG1** and **D-AG2**. Starting values are fixed only after spike AG-1 (W4).

## Date

2026-10-14 (draft)

## Context

There is **no driver-aggression setting** today. Related mechanisms exist but are different things: `traffic.aggressiveTwoWheelers` (lane-change gaps only, and only with `unstructuredTraffic`), `traffic.unstructuredTraffic` (random per-tick noise in `StochasticIDM`), per-class IDM parameters, global IDM overrides, and hard-coded roundabout safety constants. The project wants high aggression as the default for **new** scenarios. Stored scenarios, `/api/v1`, `/api/v2` and V2.0 reports must not change meaning. Source: strategy §14.

## Problem Statement

How do we introduce a systematic, named aggression assumption as the default for new scenarios without changing any existing result or duplicating the two existing flags?

## Decision

1. **A profile, not a flag flip.** New field `traffic.driverAggression ∈ {standard, moderate, high}`. `standard` is today's behaviour **bit for bit**. A profile is a set of multipliers or offsets applied on top of each vehicle class's base values.
2. **Levers (proposed `high` starting values, to be fixed by spike AG-1 with recorded evidence):** time headway T × 0.7; minimum gap s₀ × 0.75; max acceleration × 1.15; desired speed +0.05 of the class range, ceiling 1.10 × limit; lane-change politeness × 0.5 and acceptance threshold × 0.5 with **safe deceleration unchanged**. Comfort deceleration b and IDM δ are **not** changed. The roundabout critical gap is parametrised **only if** AG-1 shows it is the dominant lever, with its own ADR (physics-adjacent).
3. **Defaults.** Absent `driverAggression` ⇒ `standard` everywhere stored or frozen. New-scenario **authoring boundaries** (UI defaults and presets, builders, the Python client helper, `/api/v3` specifications, Copilot proposals, `.ufpkg` creation) **write `high` explicitly**. An explicit user choice is always preserved, including an explicit `standard`.
4. **Fingerprint and manifest.** `driverAggression` and the hash of the resolved parameter set are fingerprint components and appear in the manifest assumptions block; `.ufpkg` verify checks them.
5. **Separate from existing flags.** `unstructuredTraffic` (random noise) stays separate. **D-AG2:** `high` does **not** imply `aggressiveTwoWheelers` (recommended).
6. **Wording.** Wherever shown: "driver aggression — a simulation assumption, not a measurement of real-world driver behaviour". V3.0 results under `high` are not comparable to V2.0 reports unless the profile is stated.
7. **Validity bounds.** Every profile stays inside the validated ranges of `config_validation`; T and s₀ stay positive; a property test asserts no out-of-range result.
8. **Release timing.** The default is merged only at the **end of W4**, so W1–W3 results are not redefined mid-sprint; their demos declare their profile explicitly.

## Alternatives Considered

- **Reuse `unstructuredTraffic`:** random noise is not a systematic assumption and cannot be fingerprinted as one.
- **Single boolean `aggressive`:** hides which parameters change and cannot be tested lever by lever.
- **Change global defaults:** would silently redefine every stored scenario and break fingerprints.
- **Tune b and δ as well:** conflates aggression with vehicle dynamics.

## Trade-offs

- **Pros:** reproducibility preserved; behaviour declared and testable; the matrix shows what aggression does to each strategy.
- **Cons:** about 3.0 ED of work including a 108-cell matrix; `high` results are not comparable to earlier reports.

## Consequences

- Required tests: defaults at every authoring boundary, overrides preserved, absent ⇒ `standard` with unchanged fixture fingerprints, schema/TypeScript/package round trip, determinism per profile, and the profile × mix × strategy × density matrix (collisions = 0 and no deadlock asserted; spillback and throughput reported).
- Gate G-AG (Wed 25 Nov 17:00): if it fails, the default is not merged and W4 is not shown at the interim presentation.

## Future Considerations

Per-class or per-approach profiles; calibration against observed headways if real data ever exists (not claimable in V3.0).

## Related ADRs

[ADR-006](adr-006-scenario-configuration-format.md) · [ADR-013](adr-013-v3-integration-contract-and-versioning.md) · [ADR-014](adr-014-strategy-registry-and-entry-gate-seam.md) · [ADR-015](adr-015-robustness-lab-uncertainty-design.md)
