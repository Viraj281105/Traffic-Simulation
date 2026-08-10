# ADR-010: Documentation Organization

## Status

Accepted

## Date

2026-07-23

## Context

A research and comparative software engineering project like the **Traffic Intersection Control Comparison Framework** requires comprehensive documentation:
1.  **Architecture Specifications**: Detailed definitions of directory roles, engine mechanics, rendering workflows, and network protocols.
2.  **Contracts & Schemas**: Explanations of fields, types, and units for configurations and snapshots.
3.  **Architectural Decisions**: Historic records of *why* specific structures, frameworks, and patterns were chosen.
4.  **Operational Instructions**: Setup procedures, run scripts, and linter settings.

If documentation is scattered across external sites (such as wikis, Google Docs, or Slack threads) or mixed arbitrarily within source code folders, it becomes difficult to find, becomes out of date, and loses its value.

## Problem Statement

How should we organize and maintain project documentation so that:
1.  It is easily discoverable by all team members and future contributors?
2.  It remains in lockstep with code updates, preventing "documentation drift"?
3.  It preserves the historic context behind technical decisions (the "why") rather than just documenting current functionality (the "what")?
4.  It can be reviewed, edited, and versioned using the same workflows we use for code?

## Decision

We will adopt a **Documentation-as-Code** model, centralizing all project documentation inside a top-level `docs/` directory within the Git repository.

1.  **Logical Structure**: The `docs/` directory is partitioned into specific subfolders:
    *   `docs/architecture/`: Technical specifications detailing the architecture. Files are numbered sequentially to guide the reader:
        *   `01-repository-architecture.md`
        *   `02-backend-architecture.md`
        *   ...
        *   `10-repository-bootstrap.md`
    *   `docs/decisions/`: The Architecture Decision Record (ADR) library (this folder). Files are named using the prefix `adr-###-kebab-case.md`.
2.  **Markdown Standards**: All documents are written in standard GitHub Flavored Markdown (GFM). Visual layouts (like API flows or dependency diagrams) are embedded using native Mermaid.js text blocks rather than static binary image files where possible.
3.  **ADR Lifecycle**: ADRs are **immutable history**. Once an ADR is marked as "Accepted," it is never modified to reflect new designs. If an architectural decision is changed in the future:
    *   A new ADR is created (e.g., `ADR-015`).
    *   The new ADR links to the old one (e.g., "Supersedes ADR-002").
    *   The old ADR's status is changed to "Superseded" with a link pointing to the new decision record.

```
docs/
├── architecture/              # Sequential specifications (Current state)
│   ├── 01-repository-architecture.md
│   └── ...
└── decisions/                 # Historic Decision Records (Changelog of "Why")
    ├── adr-001-repository-structure.md
    └── ...
```

## Alternatives Considered

### Alternative 1: External Documentation Portal (e.g., Confluence, Notion, Google Drive)
Store documentation in a corporate wiki or shared cloud drive.
*   *Why it was rejected:* External portals are physically separated from the code. When a developer modifies a function or changes a config property, they must log in to a separate site to update the documentation. This friction almost always leads to documentation drift, where the wiki describes a system that no longer matches the code. Furthermore, external portals do not support code-reviews (PRs) or git-blame histories, making it impossible to see exactly which code change prompted a documentation rewrite.

### Alternative 2: Inline Code Comments and Docstrings Only
Document the architecture entirely within code files using comments, readme files in source folders, and generated API pages (like JSDoc or Sphinx).
*   *Why it was rejected:* While code comments are excellent for detailing specific variables or algorithms, they are poorly suited for high-level architectural explanations. A developer trying to understand the communication protocol between React and FastAPI should not have to dig through Python socket routers or TypeScript hook code to piece together the design. High-level architecture requires a dedicated, source-independent home.

## Trade-offs

### Pros
*   **Zero Tool Friction:** Developers write markdown in the same code editor they use for Python and TypeScript.
*   **PR Coordinated Updates:** If a Pull Request changes the shared contract, the PR *must* update the corresponding architecture markdown file in the same commit. Reviewers can verify code and documentation changes side-by-side.
*   **Full Searchability:** Because all docs are plain text inside the repository, developers can use standard search utilities (like `grep` or IDE search) to find architectural references across the entire codebase instantly.

### Cons
*   **Formatting Overhead:** Writing markdown tables, equations, and Mermaid diagrams requires minor markup knowledge.
*   **Static Asset Management**: Storing binary assets (like PowerPoint proposals or pipeline PDFs) inside Git can increase repository size, requiring discipline in asset optimization.

## Consequences

*   The root `README.md` will serve as the gateway, linking directly to the files inside `docs/architecture/` and `docs/decisions/`.
*   A pull request that changes architectural behavior (e.g., adding a new controller type) without updating the relevant documentation in `docs/architecture/` will be flagged during code review.
*   Documentation files are fully version-controlled. We can view the historical architecture of the system at any git commit or release tag.

## Future Considerations

If the team or user base grows, we can easily integrate static site generators like **MkDocs** or **Docusaurus** into our CI/CD pipeline. These tools can automatically read the `docs/` folder and publish a styled, searchable, internal documentation website on every commit to `main`.

## Related ADRs

*   [ADR-001: Repository Structure](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-001-repository-structure.md)
*   [ADR-009: Engineering Standards](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-009-engineering-standards.md)
