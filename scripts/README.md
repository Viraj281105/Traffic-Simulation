# Automation, Benchmark & Engineering Tooling (`scripts/`)

This directory houses automated study runners, network calibration pipelines, reinforcement learning evaluation scripts, deployment helpers, contract validators, and engineering tools.

None of these scripts are required for the standard web server runtime. All scripts that import the simulation engine add `backend/` to `sys.path` automatically and should be executed from the repository root using the backend virtual environment:

```bash
# Activate backend virtual environment from repository root
.venv\Scripts\activate          # Windows PowerShell / CMD
# source backend/.venv/bin/activate # macOS / Linux
```

---

## Complete Scripts Inventory

```
scripts/
├── run_full_study.py                   # Headless study runner: volume sweep + Monte Carlo validation to CSV/JSON
├── v2_demo.py                          # Automated V2.0 decision-support demonstration script
├── v3_demo.py                          # Automated V3.0 Robustness Lab demonstration script (--offline support)
├── build_fallback_pack.py              # Compiles and verifies presentation fallback asset packs
├── reproducibility_audit.py            # Master reproducibility audit: multi-seed, 12-junction, and calibration
│
├── calibrate_network.py                # Command-line network calibration against turning counts (GEH/RMSE/MAPE)
├── bench_network.py                    # Multi-junction network execution benchmark (12-junction grid)
├── benchmark_signalised_roundabout.py  # Runtime and memory benchmark: metered vs. conventional roundabout
├── w2_baseline_study.py                # V3.0 W2 signalised-roundabout baseline study runner
├── w2_safety_matrix.py                 # V3.0 W2 signalised-roundabout safety matrix evidence generator
├── roundabout_lane_experiment.py       # Third-lane capacity experiment generator
├── sampler_condition_table.py          # Prints Robustness Lab uncertainty condition samples
│
├── rl_train.py                         # Single-junction Gymnasium RL policy training runner
├── rl_evaluate.py                      # Single-junction RL policy evaluation against classical baselines
├── rl_network_evaluate.py              # Multi-junction network RL evaluation runner with paired CIs
├── produce_rl_comparison.py            # Generates RL vs. baseline comparison JSON result fixtures
├── produce_loadtest_summary.py         # Parses k6 performance metrics and outputs loadtest summary JSON
├── produce_sensitivity.py              # Generates multi-factor Sobol sensitivity analysis result fixtures
├── produce_paired_seeds.py             # Generates paired common-random-number seeds for studies
├── produce_common.py                   # Common utilities for insight fixture producers
│
├── replay_to_redpanda.py               # Replays simulation snapshot telemetry into Redpanda/Kafka topics
├── generate_ts_client.py               # Generates type-safe TypeScript API client from OpenAPI snapshot
├── export_strategy_schema.py           # Exports shared JSON schema for layered strategy descriptors
├── validate_schemas.py                 # Validates root shared JSON Schema files (config, snapshot, vehicle_state)
├── validate-schemas.sh                 # Unix shell wrapper for validate_schemas.py
│
├── setup_cognito.py                    # Provisions Amazon Cognito User Pool and App Clients (AWS Boto3)
├── deploy-ec2.sh                       # Single-instance EC2 deployment automation script
├── run-remote-deploy.sh                # SSH remote deployment runner polling deploy-ec2.sh
│
├── record_landing_scene.py             # Records vehicle trajectory frames for landing page canvas hero
├── landing_perf.mjs                    # Landing page performance, FPS, and memory probe
├── landing_canvas_diff.mjs             # Compares landing page canvas rendering snapshots
├── check_bundle_budgets.mjs            # Production frontend asset bundle size budget validator
└── repo_inventory.py                   # Audits repository files and updates inventory documentation
```

---

## Key Script Usage Guides

### 1. Master Reproducibility Audit (`reproducibility_audit.py`)
Executes three core verification workloads twice under identical seeds, strips non-deterministic timestamps, and asserts exact canonical JSON identity:
- Multi-seed signal study (2 seeds, 20 s)
- 12-junction network metrics (seed 7, 120 s)
- Synthetic ground-truth network calibration

```bash
# Run quick verification pass
python scripts/reproducibility_audit.py --quick

# Run full-duration verification pass
python scripts/reproducibility_audit.py
```

### 2. Network Calibration Tool (`calibrate_network.py`)
Calibrates simulated link flows and turning counts against observed count CSV datasets:
```bash
python scripts/calibrate_network.py \
  --network-file backend/tests/networks/fixtures/twelve_junction.json \
  --counts-file backend/tests/calibration/fixtures/synthetic_counts.csv \
  --output-report calibration_report.json
```

### 3. Headless Comparative Study Runner (`run_full_study.py`)
Runs volume sweeps and Monte Carlo statistical significance testing directly against the physics engine:
```bash
python scripts/run_full_study.py \
  --sweep-duration 240 \
  --validation-duration 240 \
  --num-seeds 5 \
  --output-csv study_report.csv \
  --output-json study_report.json
```

### 4. Multi-Junction Reinforcement Learning Evaluator (`rl_network_evaluate.py`)
Evaluates trained PPO/DQN policies on the 12-junction arterial grid against Fixed-Time and Max-Pressure baselines:
```bash
python scripts/rl_network_evaluate.py \
  --model-path backend/src/rl/models/ppo_network.pt \
  --episodes 10 \
  --output rl_comparison.json
```

### 5. TypeScript Client SDK Generator (`generate_ts_client.py`)
Parses `shared/schemas/v3/openapi.v3.snapshot.json` and generates type-safe TypeScript interfaces and service methods:
```bash
python scripts/generate_ts_client.py
```

### 6. Schema Validator (`validate_schemas.py`)
Checks that all shared JSON Schema documents are valid and formatted correctly:
```bash
python scripts/validate_schemas.py
```
