# Architecture Decision Records (ADRs)

This directory contains historical **Architecture Decision Records (ADRs)**. They record intended rationale and trade-offs at the time of the decision; they are not a substitute for the current implementation guide. When an ADR differs from the code, use [the operations guide](../operations.md) and the source tree as the current authority.

## ADR Library Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| **[ADR-001](adr-001-repository-structure.md)** | Repository Structure | Accepted | 2026-07-23 |
| **[ADR-002](adr-002-backend-frontend-separation.md)** | Backend / Frontend Separation | Accepted | 2026-07-23 |
| **[ADR-003](adr-003-shared-contract-layer.md)** | Shared Contract Layer | Accepted | 2026-07-23 |
| **[ADR-004](adr-004-snapshot-based-communication.md)** | Snapshot-Based Communication | Accepted | 2026-07-23 |
| **[ADR-005](adr-005-metric-contract-design.md)** | Metric Contract Design | Accepted | 2026-07-23 |
| **[ADR-006](adr-006-scenario-configuration-format.md)** | Scenario Configuration Format | Accepted | 2026-07-23 |
| **[ADR-007](adr-007-rest-websocket-communication-strategy.md)** | REST + WebSocket Communication Strategy | Accepted | 2026-07-23 |
| **[ADR-008](adr-008-repository-branching-strategy.md)** | Repository Branching Strategy | Accepted | 2026-07-23 |
| **[ADR-009](adr-009-engineering-standards.md)** | Engineering Standards | Accepted | 2026-07-23 |
| **[ADR-010](adr-010-documentation-organization.md)** | Documentation Organization | Accepted | 2026-07-23 |
| **[ADR-011](adr-011-versioning-strategy.md)** | Versioning Strategy | Accepted | 2026-07-23 |
| **[ADR-012](adr-012-future-controller-extensibility.md)** | Future Controller Extensibility | Accepted | 2026-07-23 |

## ADR Structure

Each record follows the standard format:
1.  **Title**: The index ID and descriptive name.
2.  **Status**: Current lifecycle state of the decision (`Accepted`, `Proposed`, `Superseded`).
3.  **Context**: The environment parameters or constraints prompting the choice.
4.  **Problem Statement**: The central architectural question.
5.  **Decision**: The chosen technical path and details.
6.  **Alternatives Considered**: Other architectural paths evaluated and why they were rejected.
7.  **Trade-offs**: Direct positive (pros) and negative (cons) consequences.
8.  **Consequences**: Workflow and tooling adjustments resulting from the decision.
9.  **Future Considerations**: Future paths of optimization or changes.
10. **Related ADRs**: Cross-linked dependency records.

---

## Implementation decisions (V1.0)

Decisions taken while building V1.0 that constrain V1.1+ work. They were previously kept in the roadmap; they live here so the [roadmap](../ROADMAP.md) stays a plan. Each is accurate for the V1.0 code.

| # | Decision | Rationale | Revisit in |
| --- | --- | --- | --- |
| D1 | **The versioned schema takes one `roads.lanesPerApproach` integer for all approaches.** The dashboard compiles per-direction counts internally. | Roundabout ring count derives from approach lanes; asymmetric lanes without independent rings would contradict the geometry. | V1.2 (lane model), V1.4 (rings), V1.5 (junction layouts) |
| D2 | **`controller.circulatingLanes` is accepted but inert.** | Keeps the schema forward-compatible without half-implemented ring routing. | V1.4 |
| D3 | **Collisions are audited after each update (oriented bounding boxes, SAT, debounced), not prevented by the audit.** Prevention is the job of IDM, the controllers, `ConflictManager` and the predictive resolver. | An honest, deterministic count of model failures without extra cost in the physics loop. | V1.4 (multi-lane validation), V1.6 (safety proxies) |
| D4 | **Fixed-time is the only signal controller in V1.0.** | A stable comparative baseline first. | V1.3 (adaptive control) |
| D5 | **FastAPI's default 422 body is preserved** while application errors use the `{"error": {...}}` envelope. | Existing clients and tests rely on the Pydantic error array. | Next API major version |
| D6 | **Live runs are ephemeral unless saved; versioned API runs and sweeps persist automatically.** | Prevents database growth from casual interaction while keeping formal studies. | V1.7 (scenario batches) |
| D7 | **The backend is the single metric authority.** | Live, saved, exported and study numbers must be identical (ADR-005). | — |
| D8 | **Controllers implement `BaseController` and are chosen by `controllers/factory.py`; the engine loop has no strategy-specific branches.** | New strategies plug in without touching `SimulationEngine.step()` (ADR-012). The factory is a simple branch on `intersectionType`, not a decorator registry. | V1.3 |
| D9 | **The comparison is calibrated for one lane per approach; every study result carries a `calibration` status.** | Multi-lane roundabout runs are not collision-free across the demand range. | V1.4 |
| D10 | **No cross-geometry composite score in the planner experience.** | Evidence, not a verdict; the fixed composite is structurally unfair across layouts. | — |
