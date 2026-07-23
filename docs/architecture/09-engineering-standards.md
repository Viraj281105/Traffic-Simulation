# Deliverable 9 — Engineering Standards

> **Document Version:** 0.1.0
> **Last Updated:** 2026-07-23
> **Status:** Phase 0 — Architecture Specification
> **Owner:** Both Developers

---

## 1. Naming Conventions

### 1.1 Folder Naming

| Context | Convention | Example |
|---------|-----------|---------|
| All directories | `lowercase-kebab-case` or `lowercase_snake_case` (pick one per layer) | — |
| Backend (Python) | `snake_case` | `vehicle_models/`, `traffic_signal/` |
| Frontend (TypeScript/React) | `kebab-case` for non-component dirs, `PascalCase` for component dirs (if grouped by component) | `services/`, `hooks/` |
| Shared | `kebab-case` | `snapshot/`, `config/` |
| Documentation | `kebab-case` | `architecture/`, `api-reference/` |

### 1.2 File Naming

| Context | Convention | Example |
|---------|-----------|---------|
| Python modules | `snake_case.py` | `idm_physics.py`, `metric_calculator.py` |
| Python test files | `test_<module>.py` | `test_idm_physics.py` |
| TypeScript modules | `camelCase.ts` | `snapshotParser.ts`, `apiClient.ts` |
| React components | `PascalCase.tsx` | `MetricCard.tsx`, `SimulationCanvas.tsx` |
| CSS files | `kebab-case.css` | `variables.css`, `chart-styles.css` |
| JSON schemas | `kebab-case.schema.json` | `snapshot.schema.json` |
| Markdown docs | `kebab-case.md` or `##-title.md` (numbered) | `01-repository-architecture.md` |
| Configuration files | `kebab-case` | `.eslintrc.json`, `vite.config.ts` |

### 1.3 Class and Interface Naming

| Context | Convention | Example |
|---------|-----------|---------|
| Python classes | `PascalCase` | `VehicleSpawner`, `MetricCollector` |
| Python abstract base classes | `PascalCase` with "Base" or "Abstract" prefix | `BaseController`, `AbstractMetric` |
| TypeScript interfaces | `PascalCase` (no "I" prefix) | `Snapshot`, `VehicleState`, `MetricResult` |
| TypeScript types | `PascalCase` | `ControllerType`, `Direction` |
| React components | `PascalCase` | `MetricCard`, `PlaybackControls` |

### 1.4 Function and Method Naming

| Context | Convention | Example |
|---------|-----------|---------|
| Python functions | `snake_case` | `calculate_wait_time()`, `emit_snapshot()` |
| Python private methods | `_snake_case` (single underscore) | `_validate_config()` |
| TypeScript functions | `camelCase` | `parseSnapshot()`, `formatMetricValue()` |
| React hooks | `useCamelCase` | `useWebSocket()`, `useSimulation()` |
| Event handlers (React) | `handleCamelCase` | `handlePause()`, `handleSpeedChange()` |

### 1.5 Variable and Constant Naming

| Context | Convention | Example |
|---------|-----------|---------|
| Python variables | `snake_case` | `current_tick`, `vehicle_count` |
| Python constants | `UPPER_SNAKE_CASE` | `MAX_VEHICLES`, `DEFAULT_TIME_STEP` |
| TypeScript variables | `camelCase` | `currentTick`, `vehicleCount` |
| TypeScript constants | `UPPER_SNAKE_CASE` | `MAX_VEHICLES`, `DEFAULT_TIME_STEP` |
| Environment variables | `UPPER_SNAKE_CASE` | `API_PORT`, `LOG_LEVEL` |

### 1.6 Enum Naming

| Context | Convention | Example |
|---------|-----------|---------|
| Python enums | `PascalCase` class, `UPPER_SNAKE_CASE` values | `class SimulationStatus(Enum): RUNNING = "running"` |
| TypeScript enums | `PascalCase` name, `PascalCase` values | `enum SimulationStatus { Running = "running" }` |
| JSON values | `snake_case` strings | `"fixed_time_signal"`, `"running"` |

---

## 2. Code Organization

### 2.1 Import Ordering

**Python (enforce with `isort`):**
```python
# 1. Standard library
import json
import os
from pathlib import Path

# 2. Third-party packages
from fastapi import FastAPI
import numpy as np

# 3. Local application imports
from src.core.engine import SimulationEngine
from src.vehicles.idm import IDMModel
```

**TypeScript (enforce with ESLint import plugin):**
```typescript
// 1. React and framework imports
import React, { useState, useEffect } from 'react';

// 2. Third-party libraries
import { Chart } from 'chart.js';

// 3. Local components and modules
import { MetricCard } from '../components/MetricCard';
import { useWebSocket } from '../hooks/useWebSocket';

// 4. Types (type-only imports)
import type { Snapshot, MetricResult } from '../types';

// 5. Styles
import './SimulationPage.css';
```

### 2.2 Module Exports

**Python:** Use `__init__.py` to define the public API of each module.

```python
# src/metrics/__init__.py
from .collector import MetricCollector
from .calculator import MetricCalculator
from .aggregator import MetricAggregator

__all__ = ["MetricCollector", "MetricCalculator", "MetricAggregator"]
```

**TypeScript:** Use `index.ts` barrel exports.

```typescript
// src/hooks/index.ts
export { useWebSocket } from './useWebSocket';
export { useSimulation } from './useSimulation';
export { useSnapshot } from './useSnapshot';
```

---

## 3. Documentation Standards

### 3.1 Python Docstrings

Use Google-style docstrings:

```python
def calculate_wait_time(vehicles: list[Vehicle], threshold: float = 0.5) -> float:
    """Calculate average wait time across all exited vehicles.

    Args:
        vehicles: List of vehicle objects to analyze.
        threshold: Speed threshold (m/s) below which a vehicle is "waiting".

    Returns:
        Average wait time in seconds. Returns 0.0 if no vehicles have exited.

    Raises:
        ValueError: If threshold is negative.
    """
```

### 3.2 TypeScript JSDoc

```typescript
/**
 * Parses a raw WebSocket message into a typed Snapshot object.
 *
 * @param rawMessage - The raw JSON string from the WebSocket
 * @returns Parsed and validated Snapshot object
 * @throws {SnapshotParseError} If the message is malformed
 */
function parseSnapshot(rawMessage: string): Snapshot {
```

### 3.3 Comment Standards

| Type | When to Use | Example |
|------|-------------|---------|
| `// TODO:` | Known incomplete work | `// TODO: Add support for adaptive controllers` |
| `// FIXME:` | Known bugs | `// FIXME: Race condition on concurrent snapshot emit` |
| `// NOTE:` | Non-obvious behavior | `// NOTE: IDM delta must be > 0 to avoid division by zero` |
| `// HACK:` | Temporary workarounds | `// HACK: Bypass validation for debugging` |

**Rules:**
- Comments explain **why**, not **what**
- Remove commented-out code before merging
- Keep comments up-to-date when code changes
- All public APIs must have documentation comments

---

## 4. Git Workflow

### 4.1 Branch Strategy

```
main                    ← Production-ready, protected
├── develop             ← Integration branch for next release
│   ├── feature/BE-*    ← Backend feature branches (Developer A)
│   ├── feature/FE-*    ← Frontend feature branches (Developer B)
│   ├── feature/SH-*    ← Shared contract changes (either developer)
│   └── fix/*           ← Bug fix branches
└── release/*           ← Release preparation branches
```

**Branch Naming Convention:**

| Pattern | Use Case | Example |
|---------|----------|---------|
| `feature/BE-<short-name>` | Backend feature | `feature/BE-idm-physics` |
| `feature/FE-<short-name>` | Frontend feature | `feature/FE-simulation-canvas` |
| `feature/SH-<short-name>` | Shared contract change | `feature/SH-snapshot-schema-v2` |
| `fix/<short-name>` | Bug fix | `fix/websocket-reconnection` |
| `docs/<short-name>` | Documentation only | `docs/update-metric-formulas` |
| `release/v<version>` | Release prep | `release/v1.0.0` |

### 4.2 Commit Message Convention

Use **Conventional Commits** (conventionalcommits.org):

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:**

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(BE): add IDM car-following model` |
| `fix` | Bug fix | `fix(FE): correct snapshot interpolation drift` |
| `docs` | Documentation | `docs(shared): update snapshot schema v1.1` |
| `refactor` | Code restructuring | `refactor(BE): extract metric registry` |
| `test` | Add or fix tests | `test(BE): add unit tests for wait time metric` |
| `chore` | Build, CI, dependencies | `chore: update Python dependencies` |
| `style` | Formatting only | `style(FE): fix ESLint warnings` |
| `perf` | Performance improvement | `perf(BE): optimize snapshot serialization` |

**Scopes:** `BE` (backend), `FE` (frontend), `shared`, `docs`, `ci`, `scripts`

**Rules:**
- Subject line: imperative mood, lowercase, no period, max 72 chars
- Body: explain **why**, not **what** (the diff shows what)
- Footer: reference issue numbers (`Closes #42`, `Refs #15`)

### 4.3 Pull Request Guidelines

**PR Title:** Same format as commit messages: `<type>(<scope>): <description>`

**PR Template:**

```markdown
## Summary
Brief description of what this PR does.

## Changes
- List of specific changes made

## Testing
- How this was tested
- [ ] Unit tests pass
- [ ] Integration tests pass (if applicable)

## Checklist
- [ ] Code follows engineering standards
- [ ] Documentation updated
- [ ] No breaking changes to shared contracts (or version bumped)
- [ ] Tests added for new functionality
```

**PR Rules:**
- Backend PRs: Reviewed by Developer A (self-review OK for small changes)
- Frontend PRs: Reviewed by Developer B (self-review OK for small changes)
- Shared PRs: **Both developers must review and approve**
- All PRs must pass CI checks before merging
- Squash merge is the default merge strategy

---

## 5. Issue Tracking

### 5.1 Issue Naming

**Format:** `[<SCOPE>] <Brief description>`

**Examples:**
- `[BE] Implement IDM car-following model`
- `[FE] Create simulation canvas component`
- `[Shared] Define snapshot schema v1.0`
- `[Bug] WebSocket disconnects after 60 seconds`
- `[Docs] Add API endpoint documentation`

### 5.2 Issue Labels

See [10-repository-bootstrap.md](./10-repository-bootstrap.md) for the complete label taxonomy.

---

## 6. Versioning

### 6.1 Project Versioning

Use **Semantic Versioning (SemVer)**:

```
MAJOR.MINOR.PATCH
```

| Component | When to Increment |
|-----------|-------------------|
| MAJOR | Breaking changes to shared contracts or public APIs |
| MINOR | New features, new optional fields in contracts |
| PATCH | Bug fixes, documentation improvements |

### 6.2 Version Locations

| File | Contains Version | Layer |
|------|-----------------|-------|
| `backend/pyproject.toml` | Backend package version | Backend |
| `frontend/package.json` | Frontend package version | Frontend |
| `shared/schemas/*.schema.json` | Schema versions | Shared |

All three versions should stay in sync for major and minor releases. Patch versions may diverge.

---

## 7. Code Quality Tools

### 7.1 Backend (Python)

| Tool | Purpose | Config File |
|------|---------|-------------|
| `ruff` | Linting + formatting | `pyproject.toml` (`[tool.ruff]`) |
| `mypy` | Static type checking | `pyproject.toml` (`[tool.mypy]`) |
| `pytest` | Test runner | `pyproject.toml` (`[tool.pytest]`) |
| `pytest-cov` | Coverage reporting | — |

### 7.2 Frontend (TypeScript/React)

| Tool | Purpose | Config File |
|------|---------|-------------|
| `eslint` | Linting | `eslint.config.js` |
| `prettier` | Code formatting | `.prettierrc` |
| `typescript` | Type checking | `tsconfig.json` |
| `vitest` | Test runner | `vite.config.ts` |

---

## 8. Cross-References

| Topic | Document |
|-------|----------|
| Repository structure | [01-repository-architecture.md](./01-repository-architecture.md) |
| Shared contract rules | [04-shared-contract-layer.md](./04-shared-contract-layer.md) |
| Repository bootstrap (labels, milestones) | [10-repository-bootstrap.md](./10-repository-bootstrap.md) |
