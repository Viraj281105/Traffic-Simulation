# Automation & Development Scripts

This directory contains the headless study runner, schema validation, Cognito provisioning and optional GitHub project-management utilities. None are required to run the API or frontend.

---

## Directory Organization & Scripts Index

```
scripts/
├── assign_issues.py              # Automation to assign GitHub Issues to developers
├── push_everything_to_github.py # Git orchestration helper to sync commits/branches
├── run_full_study.py             # Headless validated study: volume sweep + Monte Carlo → CSV/JSON report
├── setup_cognito.py              # One-off Cognito user-pool provisioning (needs boto3 + AWS credentials)
├── set_milestone_deadlines.py    # GitHub Milestone timeline configuration runner
├── setup_github.py               # Creates GitHub labels, milestones, and issues
├── validate-schemas.sh           # Bash wrapper for CI/CD schema validation
├── validate_schemas.py           # Core validation script using JSON Schema engine
└── README.md                     # This documentation file
```

---

## Detailed Script Specifications

### 0. Validated Study Runner

#### [`run_full_study.py`](./run_full_study.py)

Runs the full comparative study directly against the simulation engine — no API server needed: a volume sweep (signal vs roundabout, same seed per tier) and a Monte Carlo validation (Student-t intervals, Welch's t-test, Cohen's d), then writes a report. Runs are also persisted to the database at `DB_PATH`.

```bash
python scripts/run_full_study.py --help
python scripts/run_full_study.py
python scripts/run_full_study.py --sweep-duration 240 --validation-duration 240 --num-seeds 5 --time-step 0.1 --rates 0.1,0.2,0.3 --output-csv study_report.csv --output-json study_report.json
```

Defaults: 240 s per run (30 s warm-up excluded), 5 seeds, Δt 0.1 s, rates = 20–160 % of the one-lane reference capacity. See [docs/research/reproducibility.md](../docs/research/reproducibility.md).

#### [`setup_cognito.py`](./setup_cognito.py)

Creates the Cognito user pool used for optional sign-in. Run once from a machine with AWS credentials (`pip install boto3`). It makes remote changes in your AWS account — review it first.

---

### 1. Schema Validation Suite

Ensures data integrity for configuration and snapshot contracts across Backend/Frontend borders.

#### Core Validator: [`validate_schemas.py`](./validate_schemas.py)

Checks that every JSON file in `shared/schemas/` is valid JSON and contains a `$schema` field. It does not validate example payloads and does not require the `jsonschema` package.

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

Creates the repository's configured GitHub labels, milestones, and issue definitions. Review the script before running it because it makes remote changes.

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

Assigns configured GitHub issues to the users defined by the script.

- **Execution**:
  ```bash
  python scripts/assign_issues.py
  ```

#### Milestone Deadlines: [`set_milestone_deadlines.py`](./set_milestone_deadlines.py)

Configures start and target dates for project milestones on GitHub.

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
