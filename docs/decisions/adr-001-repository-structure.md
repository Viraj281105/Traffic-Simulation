# ADR-001: Repository Structure

## Status

Accepted

## Date

2026-07-23

## Context

The **Traffic Intersection Control Comparison Framework** project involves two developers working in parallel. Developer A is responsible for the simulation engine, vehicle physics, metrics computation, and API server. Developer B is responsible for the user interface, real-time visual playback, chart generation, and data visualization. 

To execute the project efficiently, both developers need to work on their respective scopes without blocking each other or causing conflicts in the codebase. However, they must also agree on interfaces, APIs, and data structures (contracts) that define how the frontend and backend communicate.

## Problem Statement

How should the codebase be structured to:
1. Ensure logical and physical separation between the simulation engine (backend) and the visual dashboard (frontend)?
2. Enable both developers to work independently with clear boundaries and minimal merge conflicts?
3. Provide a single, shared source of truth for communication contracts (APIs and schemas)?
4. Simplify local environment setup, bootstrapping, and CI/CD automation?

## Decision

We will adopt a **Monorepo** structure organized by logical layers rather than physical frameworks. The repository will be structured into three primary directories:

*   **`backend/`**: Contains the Python 3.11+ simulation engine, Intelligent Driver Model (IDM) physics, metrics engine, and FastAPI REST/WebSocket server. Owned and modified exclusively by Developer A.
*   **`frontend/`**: Contains the React 18+ and TypeScript dashboard, HTML5 Canvas renderer, and Vite configuration. Owned and modified exclusively by Developer B.
*   **`shared/`**: Contains language-agnostic JSON Schema definitions, enums, constants, and contract documentation. Jointly owned by both developers; changes require coordinated reviews.

### Repository Layout
```
traffic-intersection-control-comparison/
├── backend/                    # Python simulation engine & API
├── frontend/                   # React/TS visualization dashboard
├── shared/                     # Language-agnostic schemas & contracts
├── docs/                       # Project documentation & decisions
├── scripts/                    # Bootstrap & validation automation
└── examples/                   # Sample configs and snapshots
```

## Alternatives Considered

### Alternative 1: Multi-Repository Setup (Separate Repositories)
In this approach, the backend, frontend, and shared contracts would live in three separate Git repositories.
*   *Why it was rejected:* A multi-repo setup introduces significant coordination overhead for a two-person project. Synchronizing contract changes requires publishing packages or coordinating multiple pull requests across repositories. It also complicates local setup (requiring developers to clone and link multiple repos) and makes cross-cutting features harder to track in commit histories.

### Alternative 2: Monolith with Mixed Layers (e.g., Python Web Framework with Integrated Frontend)
In this approach, the backend framework (such as Django or Flask) serves the frontend bundle directly, and the frontend code is nested inside the backend directory structures (e.g., `templates/` and `static/`).
*   *Why it was rejected:* This tightly couples the frontend tooling with the backend runtime. It forces Developer B to run and understand backend setup steps simply to compile or modify UI components. It also makes it easier to violate architectural boundaries by mixing server-side rendering with client-side state.

## Trade-offs

### Pros
*   **Single Source of Truth:** All code and documentation live in one repository, allowing complete system builds from a single command.
*   **Atomic Commits:** Changes to a data schema in `shared/` and the corresponding implementations in `backend/` and `frontend/` can be committed and merged in a single Pull Request.
*   **Environment Isolation:** The backend uses Python-specific tooling (virtual environments, pip, ruff) and the frontend uses Node-specific tooling (npm, eslint, vite), remaining completely decoupled at run time.

### Cons
*   **Accidental Cross-Imports:** Without guardrails, there is a risk of a developer accidentally referencing files from the other's directory (e.g., frontend code importing Python utilities).
*   **Unified Git History:** The commit log contains mixed messages for backend and frontend changes, which requires disciplined naming conventions (e.g., using `feat(BE):` or `feat(FE):`) to remain readable.

## Consequences

*   Developers A and B have full autonomy within their respective directories (`backend/` and `frontend/`).
*   Strict import rules are enforced: code in `backend/` must never import from `frontend/`, and code in `frontend/` must never import from `backend/`. Both may reference `shared/` assets.
*   Changes to the `shared/` directory require a Pull Request reviewed and approved by **both** developers.
*   A global `scripts/` directory is created to house scripts that automate tasks for the entire repository (e.g., one-command setup, validating JSON schemas).

## Future Considerations

If the project scope expands to include mobile applications or additional simulation runtimes (e.g., C++ for performance), they can easily be added as new top-level directories (e.g., `mobile/` or `simulation-cpp/`) without disrupting the existing monorepo structure.

## Related ADRs

*   [ADR-002: Backend / Frontend Separation](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-002-backend-frontend-separation.md)
*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
