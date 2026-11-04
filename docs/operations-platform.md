# Platform operations: cluster, Airflow, CI/CD, Go ingest

Covers F3 (Kubernetes, Airflow, CI/CD) and F1 (Go ingest). Application-level operations are in
`docs/operations.md`. Everything here runs without a cloud account.

## 1. Local cluster (kind + Helm)

See `deploy/README.md` for the commands. Summary:

| Item | Where |
|---|---|
| Chart | `deploy/helm/urbanflow` (subcharts `backend`, `frontend`, `ingest`) |
| kind config | `deploy/kind/kind-config.yaml` (UI at `http://127.0.0.1:8080`) |
| kind values | `deploy/helm/values-kind.yaml` |
| Smoke test | `deploy/scripts/smoke-test.sh` |

Operating notes:

- **One backend replica.** SQLite on a ReadWriteOnce volume; the Deployment uses `Recreate`. Scaling out needs a
  different store first (F7/F16), not just `replicas: 2`.
- **Service name `backend`** is baked into the nginx template (`frontend/templates/default.conf.template`).
- **Logs:** `kubectl logs deploy/backend` (JSON lines, `LOG_FORMAT=json`); `kubectl logs deploy/frontend`.
- **Health:** both pods expose `/health`; probes use it. `kubectl get pods` should show `1/1 Running`.
- **Secrets:** `backend.apiKey` / `frontend.apiKey` must match. Empty means auth disabled (same as compose).
- **Rollback:** `helm history urbanflow`, `helm rollback urbanflow <rev>`.

## 2. CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/k8s-deploy.yml` | push to `main` (deploy-related paths), PRs touching `deploy/`, manual | `helm lint` and `helm template`; builds both images; creates a kind cluster on the runner; `helm install --wait`; runs the smoke test; dumps pod logs on failure |
| `.github/workflows/nightly-regression.yml` | 02:17 UTC daily, manual | full backend suite including slow tests, plus a 5-seed study; uploads coverage and result JSON |
| `.github/workflows/ingest-go.yml` | changes under `services/ingest-go/` or `proto/` | generates protobuf code, `go vet`, `go test`, in-process benchmark, image build |

"Deploy" in CI means a throwaway kind cluster that proves the chart installs and answers; no persistent
environment exists. Existing workflows (`ci.yml`, `docker.yml`, `deploy.yml` for EC2) are unchanged.

## 3. Airflow

DAGs live in `airflow/dags/`, helper scripts in `airflow/scripts/`, tests in `airflow/tests/`.

| DAG | Schedule | Tasks |
|---|---|---|
| `urbanflow_nightly_regression` | 02:17 UTC | `backend_suite` (pytest, slow included) then `multiseed_smoke` (5 seeds, 60 s) |
| `urbanflow_batch_experiments` | manual | `multiseed_signal` and `multiseed_roundabout` in parallel, then `full_study` (`scripts/run_full_study.py`) |

Both call existing code as subprocesses (pytest, `airflow/scripts/run_multiseed.py` over
`src.study.multiseed.run_multi_seed`, `scripts/run_full_study.py`). A non-zero exit fails the task, so the
DAG run state is the pass/fail report. Trigger the batch DAG with
`{"num_seeds": 10, "duration": 120, "base_seed": 42}` as run configuration; all keys are optional.

Environment for workers:

| Variable | Default | Meaning |
|---|---|---|
| `URBANFLOW_REPO` | parent of `airflow/` | repository checkout on the worker |
| `URBANFLOW_PYTHON` | `sys.executable` | interpreter with `backend/requirements-dev.txt` installed |
| `URBANFLOW_RESULTS_DIR` | `airflow/results` | output JSON/CSV (git-ignored) |

Try it locally without installing Airflow into the project environment:

```bash
pip install "apache-airflow==2.10.*"   # in a separate virtualenv; follow Airflow's constraints file
export AIRFLOW__CORE__DAGS_FOLDER=$PWD/airflow/dags AIRFLOW__CORE__LOAD_EXAMPLES=False
airflow dags test urbanflow_nightly_regression 2026-11-01
```

DAG modules import without Airflow (the DAG object is then `None`); `python -m pytest airflow/tests` checks the
command construction in that mode. The DAGs target Airflow 2.x APIs (`PythonOperator`, `schedule=`).

## 4. Go ingest service (F1)

- Contract: `proto/ingest.proto` (`Ingest` service: `IngestBatch`, `IngestStream`, `RunSummary`, `Stats`).
  Idempotency key is `(run_id, seq)`.
- Service: `services/ingest-go` (`cmd/ingest-server`, `client/`, `cmd/ingest-bench`, `internal/store`).
- Generated code is not committed. `make -C services/ingest-go proto` needs `protoc` plus the two plugins
  listed in the Makefile; the Dockerfile and CI install them.
- Run: `go run ./cmd/ingest-server -addr :9090`. In the cluster: `--set ingest.enabled=true`.
- Benchmark: `make -C services/ingest-go bench` prints store micro-benchmarks and a JSON report
  (events/s, batch latency p50/p95/p99) for the Go path.

**Status.** The service is not yet in the backend's data path and there is no Python client or Python-path
benchmark; the F1 acceptance items "in the real data path", "contract tests from both languages" and
"Go vs Python comparison" are open. When the comparison is made, report it even if Go is not faster. Use the
same payload (batch of 500 events, two metrics each) on both sides.

## 5. Known gaps

- None of the cluster, Airflow or Go pieces had been run when this was written on a machine without kind,
  Helm, Go or Airflow; first runs in CI or on a fully equipped machine may need small fixes (see the
  verification notes in the hand-off).
- No ingress, TLS or persistent cluster environment; kind only.
- Airflow itself (scheduler, metadata DB, deployment) is not provisioned by this repository.

## Result files (read by `/api/v3` result screens)

`src/insights` serves the result screens from files under `URBANFLOW_RESULTS_DIR` (default `airflow/results`).
A missing or unreadable file is "not available yet" (404); nothing is invented. Formats are described at the top
of each module in `backend/src/insights/`.

| File | Format | Served by |
| --- | --- | --- |
| `runs/<run id>/manifest.json`, `metrics.parquet` | Parquet run store, one row per vehicle trip | `GET /runs/{id}/metrics`, `GET /runs/compare` |
| `experiments/<id>/paired.json` | `urbanflow-paired-seeds`: per-seed values per alternative | `/experiments/{id}/comparison`, `/report` |
| `experiments/<id>/sensitivity.json` | `urbanflow-sensitivity`: a `sobol_lite` result | `/experiments/{id}/sensitivity`, `/report` |
| `nightly/history.json` | `urbanflow-nightly-history` | `GET /regression/nightly` |
| `rl/<id>.json` | `urbanflow-rl-comparison`, wrapping `urbanflow-rl-eval` documents | `GET /rl/comparisons/{id}` |

`POST /networks/import/preview` asks an Overpass server named by `URBANFLOW_OVERPASS_URL` (https); without it the
route answers 503.

## Producing result files

The scripts below write the files in the table above. Run them from the repository root with the backend
interpreter (`backend/.venv/Scripts/python` on Windows, `backend/.venv/bin/python` elsewhere). Each writes under
`URBANFLOW_RESULTS_DIR` (default `airflow/results`) unless `--results-dir` is given, replaces its file atomically
and prints the path. Ids are letters, digits, `-` and `_`. An invalid argument exits with status 2 and writes
nothing. The experiment id must be the id of a finished experiment for the endpoints to serve its files.

**Paired seeds** (`/experiments/{id}/comparison`, `/report`). Each `--alt ID=GEOMETRY` is run through
`run_multi_seed` over the same seeds; `--override ID=JSON` is merged into that alternative's config.

```bash
backend/.venv/Scripts/python scripts/produce_paired_seeds.py --experiment-id demo \
  --alt fixed=signal --alt adaptive=signal \
  --override 'adaptive={"controller":{"signalControl":"adaptive"}}' \
  --label fixed="Fixed time" --label adaptive="Adaptive" \
  --baseline fixed --num-seeds 10 --duration 120 --base-seed 42 --save-runs
```

`--save-runs` also stores each alternative as run `demo-fixed`, `demo-adaptive` in the Parquet run store and sets
`metricsRunId` to the baseline's. Those rows are per-seed summaries, so `/runs/{id}/metrics` returns null (not
zero) for trip-based values until per-trip rows are stored.

**Sensitivity** (`/experiments/{id}/sensitivity`, `/report`). Cost is `samples x (inputs + 2) x num-seeds`
simulations. Inputs: `arrivalRate` (veh/s), `greenTime` (s), `speedLimit` (m/s), `approachLength` (m),
`lanesPerApproach`. Small `--samples` give noisy indices; the endpoint clips and says so.

```bash
backend/.venv/Scripts/python scripts/produce_sensitivity.py --experiment-id demo \
  --input arrivalRate=0.1:0.5 --input greenTime=15:60 \
  --metric mean_delay_s --samples 32 --num-seeds 3 --duration 60 --seed 7
```

**Nightly history** (`/regression/nightly`). Written by the `urbanflow_nightly_regression` DAG: each task records
a check (`nightly/parts/<ds>/`), and a final `record_history` task (runs even when an earlier task failed) appends
the night to `nightly/history.json` through `airflow/dags/nightly_history.py`. A rerun of the same date replaces
that night; the newest 365 are kept; a skipped check means an earlier task failed. Locally, with no Airflow:
`cd airflow/dags` then call `nightly_history.record_night(results_dir, ds, checks, repo)` after `checked(...)`.

**RL against fixed-time** (`/rl/comparisons/{id}`). Evaluate each scenario with `scripts/rl_evaluate.py`, then wrap
the outputs (needs `backend/requirements-rl.txt` for the model). `--rl-policy` is the policy name inside the eval
files (`rl_dqn` or `rl_ppo`); the eval documents are copied in whole and the endpoint does the statistics.

```bash
backend/.venv/Scripts/python scripts/rl_evaluate.py --model rl_runs/dqn-s0-t20000/model.zip --algo dqn --vph 400 --seeds 20 --out low.json
backend/.venv/Scripts/python scripts/rl_evaluate.py --model rl_runs/dqn-s0-t20000/model.zip --algo dqn --vph 800 --seeds 20 --out high.json
backend/.venv/Scripts/python scripts/produce_rl_comparison.py --id dqn-four-way --junction "Four-way, one lane" \
  --scenario low="400 veh/h"=low.json --scenario high="800 veh/h"=high.json \
  --rl-policy rl_dqn --rl-label DQN --policy-id signal-control/3 --algorithm DQN --training-steps 20000 \
  --caveat "Trained and evaluated on one simulator."
```

Tests: `cd backend && .venv/Scripts/python -m pytest tests/producers --no-cov` and `python -m pytest airflow/tests`.
