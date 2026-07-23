# ADR-003: Shared Contract Layer

## Status

Accepted

## Date

2026-07-23

## Context

Because the backend (Python) and frontend (React/TypeScript) run in separate environments and are written in different languages, they must agree on the exact format of the data they exchange. If the backend changes a field name (e.g., from `vehicleSpeed` to `speed`) or modifies a metric formula, the frontend will break unless it is updated simultaneously. 

To maintain system integrity, we need a mechanism to define, validate, and document our data interfaces in a way that serves both languages equally.

## Problem Statement

How can we define data contracts (simulation snapshots, configurations, metrics, and errors) so that:
1. There is a single, language-agnostic source of truth.
2. Both Python and TypeScript can validate payloads against this source of truth at runtime.
3. Contract changes are explicit, trackable, and require mutual agreement between the backend and frontend developers.
4. Contract documentation and examples remain perfectly synchronized with actual implementations.

## Decision

We will establish a dedicated, joint-ownership **Shared Contract Layer** in the `shared/` directory. 

1.  **Canonical Format**: We will use **JSON Schema (Draft 2020-12)** as our canonical, language-agnostic schema format. All data shapes passing across the boundary are defined in `shared/schemas/`.
2.  **Shared Schemas**:
    *   `config.schema.json`: Schema for input scenario configurations.
    *   `snapshot.schema.json`: Schema for high-frequency state updates.
    *   `metrics.schema.json`: Schema for performance metric summaries.
    *   `messages.schema.json`: Schema for WebSocket frame envelopes.
    *   `errors.schema.json`: Schema for HTTP/WebSocket error details.
3.  **Local Implementations**:
    *   *Backend (Python)*: Pydantic models in `backend/src/api/schemas/` and validation logic in `backend/src/config/validator.py` reference the shared schemas.
    *   *Frontend (TypeScript)*: Type definitions in `frontend/src/types/` are mapped to match the properties defined in the shared schemas.
4.  **Verification**: We will write a validation script (`scripts/validate-schemas.sh`) to run in local environments and CI/CD pipelines. This script validates all example JSON payloads in `shared/*/examples/` against the JSON schemas to ensure documentation and schemas never drift.

```
                  ┌──────────────────────┐
                  │    shared/schemas/   │
                  │  (JSON Schema Draft)  │
                  └──────────┬───────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
   ┌────────────────────┐         ┌───────────────────┐
   │  backend/ (Python) │         │  frontend/ (TS)   │
   │  - Pydantic        │         │  - TS Interfaces  │
   │  - JSON Validation │         │  - Payload parser │
   └────────────────────┘         └───────────────────┘
```

## Alternatives Considered

### Alternative 1: Code-First Sharing (e.g., generating TS from Python or vice-versa)
Write Pydantic models in Python, and use a tool to export them as TypeScript interfaces, or write TypeScript first and compile to Python.
*   *Why it was rejected:* This creates a directional dependency (one layer must be written first to generate the other). If TypeScript is generated from Python, Developer B is blocked until Developer A writes and compiles code. It also couples the contract to language-specific framework quirks (such as Pydantic's internal serialization rules), making the contract less clean and language-agnostic.

### Alternative 2: Protocol Buffers (Protobuf / gRPC)
Define contracts using `.proto` files and compile them into Python and TypeScript modules using the Protobuf compiler.
*   *Why it was rejected:* While Protobuf is excellent for high-performance binary serialization, it adds build-time complexity (requiring the `protoc` compiler and specific plugins) and complicates debugging. Because the frontend runs in a browser, debugging raw binary streams requires extra browser extensions or decoding layers. JSON is native to the web and FastAPI, making it the most pragmatic and debuggable format for our team.

### Alternative 3: OpenAPI / Swagger Specification Only
Rely solely on FastAPI's auto-generated `openapi.json` to define the contract.
*   *Why it was rejected:* OpenAPI is designed for REST APIs and does not natively support detailing WebSocket message schemas or verifying standalone configuration files loaded from disk. By using JSON Schema directly, we can validate configuration files loaded by the backend command-line interface independently of the web server.

## Trade-offs

### Pros
*   **Decoupled Development:** Both developers can read the JSON Schema files and implement their code independently, knowing that if their code passes schema validation, it will integrate successfully.
*   **Automated Validation:** The schemas can validate incoming API requests on the backend automatically, reducing boilerplate error checking.
*   **Documentation Alignment:** Example files (`shared/config/examples/*.json`) are guaranteed to be correct because they are tested against the schemas in CI.

### Cons
*   **Schema Duplication (Initial Setup)**: JSON Schema files must be authored, and Python/TypeScript models must be created to match. (This can be mitigated by automating type generation in the future).
*   **Syntax Complexity:** JSON Schema syntax can be verbose and tedious to write manually compared to native code interfaces.

## Consequences

*   Any change to a contract requires modifying the schema files in `shared/schemas/` first.
*   A pull request modifying `shared/` requires approval from **both** Developer A and Developer B.
*   The API endpoints will reject any client requests that violate the corresponding schemas with standard `422 Unprocessable Entity` errors.

## Future Considerations

If manual TypeScript type maintenance becomes a source of bugs, we will introduce `json-schema-to-typescript` into the frontend build step to automatically generate TypeScript interface files directly from the `shared/schemas/` folder.

## Related ADRs

*   [ADR-001: Repository Structure](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-001-repository-structure.md)
*   [ADR-004: Snapshot-Based Communication](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-004-snapshot-based-communication.md)
*   [ADR-005: Metric Contract Design](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-006: Scenario Configuration Format](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-006-scenario-configuration-format.md)
*   [ADR-011: Versioning Strategy](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-011-versioning-strategy.md)
