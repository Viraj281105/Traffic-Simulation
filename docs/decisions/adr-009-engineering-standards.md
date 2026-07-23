# ADR-009: Engineering Standards

## Status

Accepted

## Date

2026-07-23

## Context

The framework is a multi-language project: the backend is written in Python 3.11+, and the frontend is written in TypeScript and React 18+. To ensure long-term codebase health, maintainability, and ease of collaboration, the code must look and feel unified. 

If developers write code using different formatting styles (e.g., mixing spaces and tabs, using different naming styles like `camelCase` vs `snake_case` in Python, or omitting type definitions), the codebase will become difficult to read, merge conflicts will increase, and hidden runtime errors will go unnoticed until production.

## Problem Statement

What engineering standards, code styles, naming conventions, static analysis tools, and testing frameworks should be adopted to:
1.  Establish uniform naming and style conventions across Python, TypeScript, and JSON layers?
2.  Automate code formatting and linting to eliminate style debates during code reviews?
3.  Ensure code correctness and prevent type-related runtime exceptions before code execution?
4.  Standardize testing and coverage requirements to maintain high system reliability?

## Decision

We will adopt a suite of industry-standard static analysis tools and formal coding guidelines.

### 1. Naming Conventions

We establish strict, directory-scoped naming conventions to match language-specific ecosystems:

| Context | Folder naming | File Naming | Symbols Naming |
|---------|---------------|-------------|----------------|
| **Backend (Python)** | `snake_case` | `snake_case.py` | Classes: `PascalCase`<br/>Functions/Variables: `snake_case`<br/>Constants: `UPPER_SNAKE_CASE` |
| **Frontend (TS/React)** | Components: `PascalCase`<br/>Others: `kebab-case` | Components: `PascalCase.tsx`<br/>Others: `camelCase.ts` | Classes/Interfaces: `PascalCase`<br/>Functions/Variables: `camelCase`<br/>Constants: `UPPER_SNAKE_CASE` |
| **Shared Layer** | `kebab-case` | `kebab-case.schema.json` | JSON Properties: `camelCase` |
| **Docs / Scripts** | `kebab-case` | `kebab-case.md` / `kebab-case.sh` | — |

### 2. Backend Tooling (Python)

We will configure Python quality tools inside `backend/pyproject.toml`:

*   **Linter & Formatter**: **`ruff`**. We will use `ruff` for both linting and formatting. It replaces `flake8`, `black`, `isort`, and `autoflake` in a single tool that runs 10-100x faster.
*   **Static Type Checking**: **`mypy`**. Run with `--strict` flags on all core simulation code. Type annotations are mandatory for all public functions.
*   **Testing Framework**: **`pytest`** along with `pytest-cov`.
    *   *Coverage Target*: We target a minimum of 80% line coverage for core simulation algorithms (`backend/src/core/`, `backend/src/vehicles/`, `backend/src/metrics/`).

### 3. Frontend Tooling (TypeScript / React)

We will configure JavaScript/TypeScript quality tools in the frontend:

*   **Linter**: **ESLint** (configured via `eslint.config.js` using TypeScript ESLint defaults).
*   **Formatter**: **Prettier** (configured via `.prettierrc` for consistent braces, quotes, and indentation).
*   **Static Type Checking**: **TypeScript (`tsc`)**. The compiler runs with `strict: true` in `tsconfig.json`. Casting with `as any` is strictly forbidden.
*   **Testing Framework**: **Vitest**. Used for fast, in-memory component and hook testing.

### 4. Code Documentation

*   **Python**: Google-style docstrings are required for all public classes, methods, and functions.
*   **TypeScript**: JSDoc comments are required for all utility helpers and React hooks.
*   **Comment Tags**: Standardized tags must be used for inline annotations: `// TODO:`, `// FIXME:`, `// NOTE:`, `// HACK:`.

## Alternatives Considered

### Alternative 1: Manual Quality Enforcement (Review-only)
Rely on code reviews to catch formatting issues, naming discrepancies, and potential type bugs.
*   *Why it was rejected:* Manual styling review is highly inefficient. It wastes developers' energy arguing over code formatting (such as single vs double quotes) in Pull Requests. Humans are also poor compilers; they fail to spot unused imports, dead variables, or subtle type mismatches that static analysis tools find instantly.

### Alternative 2: Separate Python Formatters (Black + Flake8 + Isort + Autoflake)
Use the standard, separate tools that have traditionally populated Python environments.
*   *Why it was rejected:* Installing, configuring, and running four separate Python tools slows down local development loops and CI pipelines. `ruff` unifies these tools, reads a single config section, and executes nearly instantaneously, improving developer satisfaction.

## Trade-offs

### Pros
*   **No Style Friction:** Code formatting is completely automated. Developers configure their IDEs to format on save, meaning code style is never a discussion point in PRs.
*   **Early Bug Detection:** Type checkers (`mypy`, `tsc`) catch errors (such as passing a null object or referencing a missing property) before code is run.
*   **Self-Documenting Code:** Unified naming and type standards make it easy for Developer A to read Developer B's code (or the shared contracts) without learning new patterns.

### Cons
*   **Strictness Friction:** Writing strictly annotated code and resolving compiler warnings can initially slow down coding speed.
*   **Setup Overhead**: Requires maintaining config files (`pyproject.toml`, `eslint.config.js`, `.prettierrc`, `tsconfig.json`) and keeping dependencies updated.

## Consequences

*   Before submitting any Pull Request, developers must run the linting, formatting, and test commands locally (or via pre-commit hooks):
    *   *Backend*: `ruff check .`, `ruff format .`, `mypy src/`, `pytest`
    *   *Frontend*: `npm run lint`, `npm run format:check`, `vitest run`
*   Any PR that fails these checks will be blocked from merging by the automated GitHub Actions CI pipeline.

## Future Considerations

We will commit a shared `.vscode/` or IDE settings folder to the repository. This pre-configures VS Code for both developers to format files automatically on save and display inline type errors, ensuring immediate compliance with these standards.

## Related ADRs

*   [ADR-001: Repository Structure](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-001-repository-structure.md)
*   [ADR-008: Repository Branching Strategy](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-008-repository-branching-strategy.md)
*   [ADR-010: Documentation Organization](file:///c:/VIRAJ/Internship/Traffic_Simulation_Project_1/docs/decisions/adr-010-documentation-organization.md)
