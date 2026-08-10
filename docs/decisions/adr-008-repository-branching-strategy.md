# ADR-008: Repository Branching Strategy

## Status

Accepted

## Date

2026-07-23

## Context

In our monorepo setup, two developers (Developer A and Developer B) are working in parallel. Because they are working on separate layers (`backend/` and `frontend/`) but sharing a core layer (`shared/`), we need to define how they use Git to manage source code changes. 

Without a clear branching and review strategy, developers might overwrite each other's configuration, introduce breaking changes to shared interfaces, or clog the commit history with uninformative messages, making debugging difficult.

## Problem Statement

What Git branching and merge strategy should be used to:
1.  Guarantee that the `main` branch is always stable and production-ready?
2.  Allow both developers to work in parallel on their respective folders without blocking each other's day-to-day work?
3.  Ensure that any changes to the `shared/` contract directory are reviewed and approved by *both* developers before integration?
4.  Maintain a clean, readable commit log that makes it easy to identify when and why specific architectural changes were introduced?

## Decision

We will adopt a hybrid **Trunk-Based / Git Flow Branching Strategy** combined with **Directory-Based Review Ownership**:

1.  **Branching Structure**:
    *   **`main` Branch**: Protected. Represents the stable, production-ready release state. No direct commits or force-pushes allowed.
    *   **`develop` Branch**: Protected. The active integration branch. All features and bug fixes merge here first.
    *   **Feature Branches**: Created from `develop`. Named according to scope:
        *   `feature/BE-<short-name>`: Backend feature branch (Developer A).
        *   `feature/FE-<short-name>`: Frontend feature branch (Developer B).
        *   `feature/SH-<short-name>`: Shared contract change branch (either developer).
        *   `fix/<short-name>`: Bug fix branch.
        *   `docs/<short-name>`: Documentation-only updates.
    *   **Release Branches (`release/v*`)**: Created from `develop` when preparing for a major or minor milestone (e.g., preparing v1.0.0). Only bug fixes are allowed here. Merged back to `main` and `develop`.
2.  **Pull Request (PR) Approval Rules**:
    *   **Backend PRs (`backend/`)**: Reviewed and approved by Developer A.
    *   **Frontend PRs (`frontend/`)**: Reviewed and approved by Developer B.
    *   **Shared PRs (`shared/` or schemas)**: **Strict Rule**: Must be reviewed, tested, and approved by **both** Developer A and Developer B.
3.  **Merge Convention**:
    *   **Squash and Merge**: The default merge strategy for merging feature branches into `develop`. This condenses feature development commits into a single, clean commit on the target branch.
4.  **Commit Message Format**: Follow **Conventional Commits**:
    *   `feat(BE): add IDM physics model`
    *   `fix(FE): correct canvas vehicle scaling`
    *   `docs(shared): update metrics schema version`

```
main       ───────────────────────────┬───────────────► (Tagged Releases)
                                      │ Merge Release
develop    ──────┬────────────────────┴──────┬────────► (Integration)
                 │                           ▲
feature/BE-x     └─► [Dev A code] ───────────┤ Squash Merge
                                             │
feature/SH-y     └─► [Coordinated Schema] ───┘ Approved by BOTH Dev A & B
```

## Alternatives Considered

### Alternative 1: Direct Commits to Main (No Pull Requests)
Developers push code directly to the `main` branch as they write it.
*   *Why it was rejected:* While very fast, this lacks guardrails. A developer could push a breaking schema change to the server that immediately breaks the other's environment, causing lost development time. It also prevents the team from performing code reviews and run-time validations in CI/CD before integrating code.

### Alternative 2: Strict Git Flow (Feature, Develop, Release, Hotfix, Master)
Standard Git Flow, where release branches and hotfix branches are maintained strictly, and merge commits are always preserved (no squashing).
*   *Why it was rejected:* Git Flow was designed for large teams with slow release cycles. For a two-person internship/research project, managing merge loops, resolving conflicts across multiple long-lived branches (like `master` and `develop` manually), and avoiding squash merges adds unnecessary process overhead. A simplified model that focuses on directory-based CODEOWNERS is much more pragmatic.

## Trade-offs

### Pros
*   **Safety for Shared Contracts:** The double-approval rule guarantees that neither developer can be surprised by changes to the JSON schemas, API routes, or constants they depend on.
*   **Clean History:** Squash-merging hides messy "fix typo", "test commit" history from the integration branches, making rollback operations and changelog generation straightforward.
*   **Autonomy:** Developer A and B do not need to wait for each other to review changes that are 100% contained in their own owned directories.

### Cons
*   **Discipline Required:** Developers must write descriptive commit messages and ensure they tag their branch names and PR titles with correct scopes (`BE`, `FE`, `shared`).
*   **Branch Management Overhead:** Developers must create and manage local branch tracks and keep their local `develop` branches updated.

## Consequences

*   A `PULL_REQUEST_TEMPLATE.md` is added to the `.github/` folder to guide developers through the review checklist.
*   Branch protection rules will be established in the repository hosting settings (e.g., GitHub/GitLab) to block merges to `develop` without passing status checks (linter, schema validations) and obtaining the required reviews.
*   A `CODEOWNERS` file will be created to automate review assignments:
    ```
    /shared/   @developer-a @developer-b
    /backend/  @developer-a
    /frontend/ @developer-b
    ```

## Future Considerations

If CI/CD is added to the project later, merges into `develop` will trigger automatic deployments to a development/staging server, while merges into `main` will trigger releases to production.

## Related ADRs

*   [ADR-001: Repository Structure](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-001-repository-structure.md)
*   [ADR-003: Shared Contract Layer](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-003-shared-contract-layer.md)
*   [ADR-009: Engineering Standards](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-009-engineering-standards.md)
