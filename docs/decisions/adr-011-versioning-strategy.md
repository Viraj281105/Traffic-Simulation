# ADR-011: Versioning Strategy

## Status

Accepted

## Date

2026-07-23

## Context

As the Traffic Intersection Control Comparison Framework evolves, we will update the simulation algorithms, add new metrics, adjust the road layouts, and modify the dashboard interface. These updates will require changing the data schemas inside `shared/schemas/` and the API endpoints.

Because the backend and frontend are independent systems, we need a versioning strategy that ensures clients can detect when they are communicating with an incompatible server version.

## Problem Statement

What versioning strategy should be applied to the packages, contract schemas, and API endpoints to:
1.  Communicate API compatibility and breaking changes clearly to both developers?
2.  Enable the frontend to check at runtime whether the streaming snapshots match its parser requirements?
3.  Coordinate package releases for the backend and frontend without adding excessive release management overhead?

## Decision

We will adopt a project-wide **Semantic Versioning (SemVer 2.0.0)** strategy combined with **API Path Versioning**:

### 1. Project and Package Versioning
*   **Version Format**: `MAJOR.MINOR.PATCH` (e.g., `1.2.0`).
    *   **MAJOR**: Breaking changes to APIs, shared schemas, or core engine execution.
    *   **MINOR**: New features, new optional schema fields, or new metrics (backward-compatible).
    *   **PATCH**: Bug fixes, documentation corrections, or performance tweaks.
*   **Version Synchronization**: The backend (`pyproject.toml`) and frontend (`package.json`) will keep their **MAJOR and MINOR** versions in lockstep for milestones and releases. Patch versions may diverge for independent bug fixes.

### 2. Schema and Snapshot Versioning
*   Each schema file in `shared/schemas/` includes an internal `version` property tracking its SemVer.
*   Every snapshot payload emitted by the backend over the WebSocket includes a `schemaVersion` string field (e.g., `"schemaVersion": "1.0.0"`).
*   **Runtime Compatibility Check**: At startup, when the frontend establishes a WebSocket connection, it checks the `schemaVersion` of the first received snapshot:
    *   *Matching Major Version* (e.g., frontend expects `1.x.x` and receives `1.1.0`): The connection is accepted.
    *   *Mismatching Major Version* (e.g., frontend expects `1.x.x` and receives `2.0.0`): The frontend logs a critical error, halts rendering, and displays a warning asking the user to update their frontend client.

### 3. Web API Path Versioning
*   All REST endpoints and WebSocket channels are prefixed with a major version identifier representing the API contract:
    *   `http://localhost:8000/api/v1/simulations`
    *   `ws://localhost:8000/ws/v1/stream`
*   The path version is only incremented (e.g., to `/v2/`) if there is a breaking change to the endpoint structure or payload format that cannot be handled via backward-compatible adjustments.

```
                                  V1 Release Pipeline
                    ┌──────────────────────────────────────────────┐
                    │  API Prefix: /api/v1/                        │
                    │  Schemas: v1.0.0                             │
                    │  Backend: v1.0.0     ◄──►     Frontend: v1.0.0│
                    └──────────────────────────────────────────────┘
                                         │
                         Breaking Schema Change (Major Bump)
                                         ▼
                                  V2 Release Pipeline
                    ┌──────────────────────────────────────────────┐
                    │  API Prefix: /api/v2/                        │
                    │  Schemas: v2.0.0                             │
                    │  Backend: v2.0.0     ◄──►     Frontend: v2.0.0│
                    └──────────────────────────────────────────────┘
```

## Alternatives Considered

### Alternative 1: Calendar Versioning (CalVer)
Use a date-based versioning scheme (e.g., `v2026.07.23`).
*   *Why it was rejected:* Calendar versioning is excellent for marketing desktop applications or operating systems, but it fails to communicate API compatibility. A date-based version does not tell a developer whether pulling the latest backend update will break their frontend compilation. SemVer is the industry standard for APIs because it directly encodes compatibility guarantees.

### Alternative 2: Independent Package Versioning (No Lockstep)
The backend, frontend, and shared schemas are versioned independently. The backend might be at `v4.2.1` while the frontend is at `v1.0.3` and the snapshot schema is at `v12.0.0`.
*   *Why it was rejected:* This makes integration testing and release documentation highly confusing. A user or developer has no simple way to know which frontend release matches which backend release. Keeping the primary application versions in lockstep for major and minor milestones ensures clarity and simplifies deployment configurations.

### Alternative 3: API Versioning via Headers
Version the API using custom HTTP headers (e.g., `X-API-Version: 1.0`) or Accept headers instead of putting the version in the URL path.
*   *Why it was rejected:* While header-based versioning is mathematically clean, it makes debugging and manual testing harder. Developers cannot simply paste an API URL into a web browser, curl command, or WebSocket client to test it; they must configure custom headers. URL path versioning is highly visible, easy to trace in server access logs, and simpler to configure in routing layers.

## Trade-offs

### Pros
*   **Fail-Safe Operations:** The frontend runtime check prevents the browser from crashing due to unexpected null fields if a developer runs a mismatched frontend/backend version pair.
*   **Explicit Deprecation Path:** Incrementing the API prefix to `/v2/` allows the backend to host both V1 and V2 routers simultaneously during a transition period, giving the frontend developer time to migrate without being blocked.
*   **Predictable Release Cadence:** Linking versions to SemVer rules forces developers to think about backward compatibility before modifying schemas.

### Cons
*   **Release Coordination:** Bumping versions requires modifying files in multiple folders (`backend/pyproject.toml`, `frontend/package.json`, and the schemas) which can lead to mistakes if done manually.

## Consequences

*   The backend's FastAPI instance must use APIRouter prefixes for `/api/v1` and `/ws/v1`.
*   A pre-commit check or a test in `backend/tests/` should verify that the backend engine emits the correct `schemaVersion` string matching the current project version.
*   Additive changes (adding optional fields) are designated as minor version bumps and must be implemented defensively (e.g., the frontend must ignore unknown JSON fields instead of throwing exceptions).

## Future Considerations

If release management becomes tedious, we can write a simple shell script (`scripts/bump-version.sh`) that takes a version argument, updates all relevant configuration files and schemas across the monorepo, and commits the changes with a standard Git tag.

## Related ADRs

*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-004: Snapshot-Based Communication](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-004-snapshot-based-communication.md)
*   [ADR-007: REST + WebSocket Communication Strategy](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-007-rest-websocket-communication-strategy.md)
