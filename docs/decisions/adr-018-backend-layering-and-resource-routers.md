# ADR-018: Backend Layering and Resource Routers

## Status

**Proposed** — implemented on `viraj-dev` on 2026-10-16 for review; not yet accepted.

## Date

2026-10-16

## Context

`backend/src/main.py` had grown to 2,904 lines. It created the app and also held the API-key guard, CORS policy, error envelope, a second loader for the config schema, the per-client live-session registry, the dashboard payload compiler, the versioned simulation registry, and the study, replay, suite and user routes, some with raw SQL. Newer features (`planning/`, `experiments/`, `history/`, `calibration/`, `networks/`) already owned their routers; the V1.x routes did not.

## Problem Statement

Where should each backend responsibility live so that a contributor can find it, test it on its own and extend it without editing an unrelated file?

## Decision

1. **Four layers**: delivery (routes, `api/`), application (use cases such as `live/`, `simulations/registry.py`, `study/`), domain (the simulation: `core/ roads/ vehicles/ controllers/ intersection/ metrics/ snapshot/`) and infrastructure (`database/`, `access.py`). Imports point downward only; the rules and their few documented exceptions are in [02 — Backend architecture §2](../architecture/02-backend-architecture.md).
2. **`main.py` is only the composition root**: app, middleware, error handler, database initialisation and router mounting. Nothing imports it.
3. **Each resource family owns its router** in the package that owns the behaviour: `live/`, `simulations/`, `study/router.py`, `replays/`, `suites/`, beside the existing `history/`, `planning/`, `experiments/`, `calibration/`, `networks/`.
4. **Shared HTTP plumbing lives in `api/`**: `security.py` (API key), `errors.py` (envelope), `origins.py` (CORS/WebSocket origins), `validation.py` (configuration and scenario failures worded as 400s once), `meta.py`.
5. **Routers hold no SQL.** Ownership and listing queries are DAO methods.
6. **Behaviour is preserved exactly**: same routes, methods, status codes, dependencies, middleware order, error bodies and same-seed results (verified against the previous commit with a route-table and OpenAPI diff, a same-seed run comparison and the full test suite).

## Alternatives Considered

- **Keep `main.py` and add section comments**: cheapest, but leaves six responsibilities in one module and every new route editing the same file.
- **A generic `routes/` package with one file per URL prefix**: separates by URL, not by owner, so the live-session state would still be far from the routes that use it.
- **Ports-and-adapters interfaces for every DAO and service**: more boundaries than the codebase needs; most have one implementation.

## Trade-offs

- More files, each smaller and with one owner.
- Tests that patched module globals of `main.py` now patch the module that owns the name (for example `src.api.security.API_KEY`).
- One generated OpenAPI component name changed (`src__main__ScenarioRequest` → `src__simulations__router__ScenarioRequest`); the request shape is unchanged and no client references the name.

## Consequences

- A new route goes in the owning package's router and is mounted in `main.py`; a new configuration rule goes in `core/`, and `api/validation.py` words its failure.
- The dashboard payload compiler is shared by the live session, the reliability check and suite batches from one module.

## Future Considerations

- Split `core/` into a leaf kernel (enums, clock, limits) and the engine/scenario compiler.
- Converge the older factory-style routers (`build_router(require_api_key)`) on direct imports of `api/security.py`.

## Related ADRs

- [ADR-001](adr-001-repository-structure.md) — Repository Structure
- [ADR-009](adr-009-engineering-standards.md) — Engineering Standards
- [ADR-012](adr-012-future-controller-extensibility.md) — Future Controller Extensibility
- [ADR-013](adr-013-v3-integration-contract-and-versioning.md) — V3.0 Integration Contract and Versioning
