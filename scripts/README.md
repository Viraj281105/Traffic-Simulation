# Automation & Development Scripts

This directory houses development utilities, database seed scripts, schema validators, and automation tools to streamline workspace setup, GitHub project management, and quality control.

---

## Directory Organization & Scripts Index

```
scripts/
├── assign_issues.py              # Automation to assign GitHub Issues to developers
├── push_everything_to_github.py # Git orchestration helper to sync commits/branches
├── set_milestone_deadlines.py    # GitHub Milestone timeline configuration runner
├── setup_github.py               # Repository bootsrapper (creates labels, milestones, issues)
├── validate-schemas.sh           # Bash wrapper for CI/CD schema validation
├── validate_schemas.py           # Core validation script using JSON Schema engine
└── README.md                     # This documentation file
```

---

## Detailed Script Specifications

### 1. Schema Validation Suite

Ensures data integrity for configuration and snapshot contracts across Backend/Frontend borders.

#### Core Validator: [`validate_schemas.py`](./validate_schemas.py)

Uses the `jsonschema` library to programmatically validate example payloads (e.g., config templates or engine output states) against schemas defined in the `shared/schemas/` directory.

- **Requirements**: `jsonschema`, `json`
- **Execution**:
  ```bash
  python scripts/validate_schemas.py
  ```

#### CI/CD Entry Point: [`validate-schemas.sh`](./validate-schemas.sh)

A Unix shell wrapper that checks if Python is available, installs temporary dependencies, and runs `validate_schemas.py`. Excellent for pre-commit hooks and GitHub Actions workflows.

- **Execution**:
  ```bash
  chmod +x scripts/validate-schemas.sh
  ./scripts/validate-schemas.sh
  ```

---

### 2. GitHub Project Automation

Automates project management overhead using the GitHub REST API.

#### Repository Bootstrap: [`setup_github.py`](./setup_github.py)

Automatically creates custom GitHub Issue Labels (with HSL colors), Milestones (timelines), and registers the full suite of 61 deconstructed engineering backlog issues under their corresponding categories.

- **Requirements**: `requests`
- **Environment Setup**:
  Requires a GitHub Personal Access Token (PAT) with repository scopes:
  ```bash
  set GITHUB_TOKEN=your_token_here
  set GITHUB_REPO=your_username/your_repo_name
  ```
- **Execution**:
  ```bash
  python scripts/setup_github.py
  ```

#### Issue Assigner: [`assign_issues.py`](./assign_issues.py)

Partitions backlog tasks programmatically by assigning the appropriate frontend tasks to Khushi Kashyap and simulation/physics tasks to Viraj Jadhao.

- **Execution**:
  ```bash
  python scripts/assign_issues.py
  ```

#### Milestone Deadlines: [`set_milestone_deadlines.py`](./set_milestone_deadlines.py)

Configures start and target dates for project Milestones (Phase 1, Phase 2, Phase 3, Phase 4) on GitHub to keep progress tracked against scheduled deadlines.

- **Execution**:
  ```bash
  python scripts/set_milestone_deadlines.py
  ```

---

### 3. Remote Git Sync Automation

#### Orchestrator: [`push_everything_to_github.py`](./push_everything_to_github.py)

A powerful wrapper that automates checking for local files, staging files, creating structured commits complying with conventional guidelines, creating local staging branches, resolving remote conflicts, and pushing everything cleanly to the upstream GitHub remote.

- **Execution**:
  ```bash
  python scripts/push_everything_to_github.py
  ```
