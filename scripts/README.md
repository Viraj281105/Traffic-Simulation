# Automation & Development Scripts

This directory holds study runners, evidence generators, deployment and provisioning tools, schema validation and engineering tooling. None are required to run the API or frontend. Python scripts that import the engine add `backend/` to `sys.path` themselves; run them from the repository root with the backend virtual environment.

---

## Directory Organization & Scripts Index

```
scripts/
├── run_full_study.py                   # Headless validated study: volume sweep + Monte Carlo → CSV/JSON report
├── v2_demo.py                          # End-to-end V2.0 demo against a running backend
├── v3_demo.py                          # V3.0 Robustness Lab demo; --offline verifies a saved pack
├── build_fallback_pack.py              # Preview fallback pack (planning studies + checksums); --verify checks one
├── w2_baseline_study.py                # V3.0 W2 metered-roundabout baseline study → docs/research/examples/
├── w2_safety_matrix.py                 # V3.0 W2 signalised-roundabout safety matrix evidence
├── benchmark_signalised_roundabout.py  # Runtime/memory of metered vs conventional roundabout
├── roundabout_lane_experiment.py       # Third-lane capacity experiment (V2.0 release gate)
├── sampler_condition_table.py          # Prints the Robustness Lab's sampled conditions (no simulation)
├── record_landing_scene.py             # Records engine runs for the landing page (frontend/src/landing/data/)
├── export_strategy_schema.py           # Regenerates shared/schemas/v3/strategy-descriptor.schema.json
├── validate_schemas.py                 # Checks the hand-written shared/schemas/*.json (CI)
├── validate-schemas.sh                 # Shell wrapper for validate_schemas.py
├── setup_cognito.py                    # One-off Cognito user-pool provisioning (needs boto3 + AWS credentials)
├── deploy-ec2.sh                       # Runs on EC2: fetch, build and restart the stack (deploy.yml)
├── run-remote-deploy.sh                # Runs in CI: launches deploy-ec2.sh detached over SSH and polls it
├── landing_perf.mjs                    # Landing-page performance probe (docs/engineering/PERFORMANCE_BASELINE.md)
├── check_bundle_budgets.mjs            # Production bundle-size budgets (CI; docs/engineering/PERFORMANCE_BUDGETS.md)
├── repo_inventory.py                   # Generates/checks docs/engineering/REPOSITORY_INVENTORY.md
└── README.md                           # This file
```

The repository root's `src/__init__.py` extends the `src` package to `backend/src`, so scripts run from the root can `import src....`.

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

Checks that top-level JSON Schema files in `shared/schemas/*.json` (`config.schema.json`, `snapshot.schema.json`, `vehicle_state.json`) are valid JSON and contain a root `$schema` field. It does not recurse into subdirectories (`v2/`, `v3/`), which are validated by dedicated backend contract test suites (`test_contract.py`). It does not validate sample payloads and requires only Python standard libraries (`json`, `pathlib`).

- **Requirements**: Python 3.11+ standard library (`json`, `pathlib`; no external dependencies required)
- **Execution**:
  ```bash
  python scripts/validate_schemas.py
  ```

#### CI/CD Entry Point: [`validate-schemas.sh`](./validate-schemas.sh)

A Unix shell wrapper that finds `python3` or `python` and runs `validate_schemas.py`; it installs nothing.

- **Execution**:
  ```bash
  chmod +x scripts/validate-schemas.sh
  ./scripts/validate-schemas.sh
  ```

---

---

### 2. GitHub Project Automation

Removed in the 2026-10-29 refactor: `setup_github.py`, `assign_issues.py` and `set_milestone_deadlines.py` created the V1 issues from `docs/issues/`, which was deleted in `d17cf2d`; they are in git history if needed.
