# Phase 0: Setup & Docs Issues

## ISSUE-001: Root Repository Structure and CODEOWNERS Initialization
- **Description**: Configure the initial directory structure of the monorepo, set up root `.gitignore` files, and define CODEOWNERS file for strict review ownership.
- **Objective**: Establish the workspace boundaries for Developer A (Backend), Developer B (Frontend), and Shared folders, preventing unauthorized code modifications.
- **Technical Background**: In a monorepo setup, clear ownership prevents developers from inadvertently editing dependencies in other domains. CODEOWNERS automatically maps folder changes to PR reviewers.
- **Acceptance Criteria**:
  *   Create top-level directories: `backend/`, `frontend/`, `shared/`, `docs/`, `scripts/`, `examples/`.
  *   Add a root `.gitignore` merging Python-specific and Node-specific ignore patterns.
  *   Create a `.github/CODEOWNERS` file assigning `backend/` to @developer-a, `frontend/` to @developer-b, and `shared/` and `docs/` to both developers.
- **Dependencies**: None
- **Estimated Effort**: XS
- **Priority**: Critical
- **Suggested Labels**: `type: chore`, `scope: shared`, `phase: 0`
- **Suggested Assignee**: Both
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: Folders created, CODEOWNERS pushed, and PR successfully merged with approvals from both Developers.

---

## ISSUE-002: Monorepo Schema Validator Script Setup
- **Description**: Implement a central validation script in the `scripts/` folder that validates the JSON example payloads in the codebase against their respective draft schemas in `shared/schemas/`.
- **Objective**: Ensure that documentation examples and schemas do not drift during parallel development.
- **Technical Background**: The script will read files like `shared/schemas/config.schema.json` and validate all `.json` files in `shared/config/examples/` against it, returning non-zero exit codes on failure.
- **Acceptance Criteria**:
  *   Create `scripts/validate-schemas.sh` using a lightweight command-line validator (e.g., `ajv-cli` via `npx` or `jsonschema` via Python).
  *   Script must scan and validate all config, snapshot, and metrics example files.
  *   Script must return `0` on validation success, and output detailed error paths on validation failure.
- **Dependencies**: ISSUE-001
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: test`, `scope: ci-cd`, `phase: 0`
- **Suggested Assignee**: Shared
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: Script executes successfully on local shell, validates example folders, and is committed to the repository.

---

## ISSUE-003: Pre-commit Linting and Formatting Check Integration
- **Description**: Configure pre-commit checks or npm scripts at the root level to run linters, formatters, and schema validations before any commit is processed.
- **Objective**: Automate code standards verification, ensuring no unformatted or lint-failing code is pushed.
- **Technical Background**: Utilizes git hooks or simple runner configurations (e.g. `husky` + `lint-staged` or a root python/node wrapper runner) to verify ruff, black, mypy, eslint, and prettier settings.
- **Acceptance Criteria**:
  *   Create a script or runner configuration (e.g., in package.json or python pre-commit-config.yaml) to trigger static checks.
  *   Hook must run `ruff check` on python files, `eslint` and `prettier` check on frontend files, and `validate-schemas.sh` on schemas.
  *   Bypassable only with `--no-verify`.
- **Dependencies**: ISSUE-001, ISSUE-002
- **Estimated Effort**: S
- **Priority**: Medium
- **Suggested Labels**: `type: chore`, `scope: ci-cd`, `phase: 0`
- **Suggested Assignee**: Both
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: A git hook prevents committing if a styling or linting rule is violated, reporting errors clearly.

---

## ISSUE-004: Repository Architecture Document Updates
- **Description**: Update the repository architecture specification at `docs/architecture/01-repository-architecture.md` with final directory references, stack configurations, and anti-patterns.
- **Objective**: Keep repository bootstrap documentation up-to-date with monorepo directory owners and ownership guidelines.
- **Technical Background**: Documentation is managed under a Doc-as-Code philosophy. This task updates the core documentation files with finalized stack choices.
- **Acceptance Criteria**:
  *   Verify the directory structure section in `docs/architecture/01-repository-architecture.md` matches the actual repository tree.
  *   Update technology stack table (Python 3.11+, React 18+, Vite, Tailwind CSS, FastAPI, HTML5 Canvas).
- **Dependencies**: ISSUE-001
- **Estimated Effort**: XS
- **Priority**: High
- **Suggested Labels**: `type: documentation`, `scope: docs`, `phase: 0`
- **Suggested Assignee**: Both
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: MD file is complete, reviewed by both developers, and committed.

---

## ISSUE-005: Communication Contract Documentation and API Design Spec Sync
- **Description**: Synchronize the communication contract specification file (`docs/architecture/08-communication-contract.md`) with the final FastAPI endpoints and WebSocket message schemas.
- **Objective**: Clarify endpoint parameters, method verbs, and message envelopes for both frontend and backend developers.
- **Technical Background**: Represents the interface agreement between frontend client and backend server.
- **Acceptance Criteria**:
  *   Specify endpoint details for POST `/api/v1/simulations`, GET `/api/v1/simulations/{id}`, POST `/api/v1/simulations/{id}/control`, and GET `/api/v1/simulations/{id}/metrics`.
  *   Document WebSocket payload envelopes (`type` fields like `"snapshot"`, `"status_change"`, `"error"`).
- **Dependencies**: ISSUE-001
- **Estimated Effort**: S
- **Priority**: Critical
- **Suggested Labels**: `type: documentation`, `scope: docs`, `phase: 0`
- **Suggested Assignee**: Shared
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: Communication contract documentation matches the final schemas and API layer endpoints.

---

## ISSUE-006: Metric Formulas Reference Sheet Sync
- **Description**: Review and align `docs/architecture/07-metric-contract.md` with the mathematical definitions of the 10 performance metrics.
- **Objective**: Avoid semantic discrepancies regarding wait times, stops, speed indexes, and fairness variables.
- **Technical Background**: This document defines LaTeX-based equations for wait thresholds, Jain's fairness index, rolling throughput rates, and travel reliability statistics.
- **Acceptance Criteria**:
  *   Verify all 10 formulas are mathematically complete.
  *   Define concrete units for all formulas (seconds, meters, vehicles, indices).
  *   Detail warmup handling criteria (excluding pre-warmup ticks from metrics).
- **Dependencies**: ISSUE-001
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: documentation`, `scope: docs`, `phase: 0`
- **Suggested Assignee**: Both
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: Equations and formulas are accepted as the implementation blueprint.

---

## ISSUE-007: Backend Ruff, MyPy, and Pytest Configurations setup
- **Description**: Configure static analysis toolchains for the Python backend including Ruff, MyPy, and Pytest configs.
- **Objective**: Set up type validation and formatting rules inside `backend/pyproject.toml`.
- **Technical Background**: Python lacks compilation-level type checking. MyPy strict mode and Ruff linting rules (like Pyflakes, Ruff-specific, and Isort equivalents) must be configured.
- **Acceptance Criteria**:
  *   Create or edit `backend/pyproject.toml` containing configurations for `[tool.ruff]`, `[tool.mypy]`, and `[tool.pytest.ini_options]`.
  *   Configure MyPy to enforce strict mode (`strict = true`).
  *   Configure Ruff with line length `88` and select codes (E, F, I, N).
- **Dependencies**: ISSUE-001
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: chore`, `scope: backend`, `phase: 0`
- **Suggested Assignee**: Backend
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: CLI commands `ruff check .` and `mypy src/` execute without configuration errors.

---

## ISSUE-008: Frontend ESLint, Prettier, and TypeScript Configurations setup
- **Description**: Configure ESLint, Prettier, and TypeScript configurations in the React project workspace.
- **Objective**: Set up code formatting rules, TS strict compiler options, and CSS lint settings.
- **Technical Background**: Ensures type safety on the frontend. ESLint is configured for React hooks and import ordering, while Prettier handles formatting rules (tabWidth, semi, singleQuote).
- **Acceptance Criteria**:
  *   Verify `frontend/tsconfig.json` runs with `strict: true`.
  *   Verify `frontend/eslint.config.js` uses strict typescript-eslint rules.
  *   Verify `.prettierrc` is configured with standard spacing and quote preferences.
- **Dependencies**: ISSUE-001
- **Estimated Effort**: S
- **Priority**: High
- **Suggested Labels**: `type: chore`, `scope: frontend`, `phase: 0`
- **Suggested Assignee**: Frontend
- **Related Milestone**: `v0.1.0 — Architecture Complete`
- **Definition of Done**: Frontend linter and type-check scripts pass successfully with zero warnings.
