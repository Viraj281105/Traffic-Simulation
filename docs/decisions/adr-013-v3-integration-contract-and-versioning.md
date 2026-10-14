# ADR-013: V3.0 Integration Contract and Versioning

## Status

**Proposed** — draft for the G-D design-approval review (task B0-2, [#173](https://github.com/Viraj281105/Traffic-Simulation/issues/173)). Becomes *Accepted* only when the product owner approves decisions D3–D5 at G-D. Nothing here authorises implementation.

## Date

2026-10-14 (draft)

## Context

V2.0 is released (gate G-V2 passed 2026-10-13) and `/api/v1` and `/api/v2` are frozen. V3.0 adds experiments, packages, a Python client, personal access tokens and two AI features, all of which share documents, identifiers, fingerprints and ownership rules. Without one agreed integration contract each feature would invent its own, and a contract change would break consumers silently. Source: [V3 product strategy](../roadmap/V3_PRODUCT_STRATEGY.md) §6, §7, §12 (D3–D5).

## Problem Statement

How do new V3.0 interfaces coexist with the frozen APIs, stay compatible across versions, and make every result reproducible and verifiable?

## Decision

1. **Namespace.** All new HTTP surface lives under `/api/v3`. `/api/v1` and `/api/v2` stay **additive-only**; existing responses are not reshaped.
2. **Documents.** Every new document carries `format` plus an integer `version`, is validated with `extra="forbid"` and has a JSON Schema under `shared/schemas/`. Readers accept versions ≤ their own; an unknown **major** is rejected, an unknown **minor** is accepted with a warning.
3. **Manifest.** Every experiment result and every `.ufpkg` carries an `urbanflow-experiment-manifest` v1 (strategy §6): source revision and dirty flag, input fingerprints, seeds and the seed-derivation rule, simulation settings, runtime and pinned dependencies, execution details, output fingerprint, known nondeterminism.
4. **Replay classes.** Verification reports exactly one of `exact`, `comparable` or `differs`. A dirty tree makes `exact` unverifiable. The classes are never merged.
5. **Ownership.** Every v3 resource has an owner and is private by default; another user's id returns **404**. There is no admin personal access token.
6. **Schema changes.** Additive only, using the existing inline-migration pattern, rehearsed on a **copy** of `simulation.db`; one migration per pull request.
7. **Contract tests.** The OpenAPI document is snapshotted and checked by a contract test; every contract change ships with a schema diff and a test that feeds the new shape to every consumer, including `null`.
8. **Shared files** (`main.py` router mounting, `shared/schemas/**`, migrations, frontend routing, OpenAPI snapshot, the strategy compatibility table) are changed only by the integration owner.

## Alternatives Considered

- **Extend `/api/v2` in place:** simpler, but breaks the "frozen, additive-only" promise and mixes V2.0 and V3.0 semantics.
- **Per-feature versioning:** lets each feature move independently but multiplies compatibility rules and makes packages hard to verify.
- **Date-based versions instead of integers:** harder to compare and to reject unknown majors mechanically.

## Trade-offs

- **Pros:** one set of rules for every feature; frozen APIs cannot regress; packages and results are verifiable.
- **Cons:** extra ceremony per change (schema, test, snapshot); a single integration owner is a bottleneck.

## Consequences

- W1 creates the `/api/v3` base and the OpenAPI snapshot; W7 adds tokens, quotas and packages on the same rules.
- The supported Python version (decision D4; recommendation 3.11) determines which replays can be called `exact`.
- Pre-existing determinism and reproduction tests stay green and unmodified.

## Future Considerations

A shared quota store is required before scaling past one uvicorn process (recorded as a limitation). Package signing (authenticity, as opposed to integrity) is out of scope for V3.0.

## Related ADRs

[ADR-003](adr-003-shared-contract-layer.md) · [ADR-006](adr-006-scenario-configuration-format.md) · [ADR-011](adr-011-versioning-strategy.md) · [ADR-015](adr-015-robustness-lab-uncertainty-design.md) · [ADR-017](adr-017-ai-validation-boundary.md)
