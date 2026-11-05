# UrbanFlow V4.6 claims register

Every claim the V4.6 release makes, the evidence behind it, and its status. Release context: [v4.6-beyond-one-junction.md](v4.6-beyond-one-junction.md). Status words: **VERIFIED** (run, test named), **WRITTEN** (authored, not run), **NEEDS-INPUT** (blocked on the owner), **NOT CLAIMED** (do not say it).

| # | Claim | Evidence | Status |
| --- | --- | --- | --- |
| C1 | A 12-junction signalised network simulates end to end with vehicles conserved | `backend/tests/networks/test_network_grid.py`, `backend/tests/netmetrics/test_netmetrics.py` | VERIFIED |
| C2 | The 12-junction network is a real city network | none; it is a generated 3 x 4 grid | NOT CLAIMED |
| C3 | Network-wide delay, throughput, queue and spillback metrics are computed | `backend/src/netmetrics/metrics.py`, `test_netmetrics.py` | VERIFIED |
| C4 | Congestion spread between junctions is measured | `backend/src/netmetrics/congestion.py`, `test_netmetrics.py` | VERIFIED |
| C5 | The calibration pipeline recovers known parameters from synthetic counts and reports GEH, RMSE, MAPE and a G-CAL verdict | `backend/tests/calibration/test_network_calibration.py` | VERIFIED (synthetic only) |
| C6 | The model is calibrated to real traffic counts | no real dataset used (D1) | NEEDS-INPUT |
| C7 | Calibration reports are reproducible from their inputs (manifest hash) | `scripts/reproducibility_audit.py`, `test_network_calibration.py` | VERIFIED |
| C8 | RL machinery (environment, baselines, paired evaluation, registry, retraining stages) works at smoke budgets | `backend/tests/rl/` | VERIFIED |
| C9 | A trained RL policy beats fixed-time or max-pressure on the network | no long-budget result exists | NOT CLAIMED |
| C10 | The Airflow retraining DAG runs | `airflow/dags/rl_retrain.py`, never executed in Airflow | WRITTEN |
| C11 | Run and API Prometheus metrics are served at `/metrics/prom` with the same access rule as `/metrics` | `backend/tests/observability/test_prom_slo.py` | VERIFIED (built-in backend) |
| C12 | SLOs are defined in one file and can be evaluated against a scrape | `deploy/observability/slo.json`, `test_prom_slo.py` | VERIFIED |
| C13 | The service meets its SLOs | no load or soak run; run counters not wired | NOT CLAIMED |
| C14 | Prometheus alerts, Grafana dashboard and compose are provisioned and working | `deploy/observability/`; JSON parses only | WRITTEN |
| C15 | Dashboards and SLOs are live | nothing deployed | NOT CLAIMED |
| C16 | k6 load tests pass their thresholds | `deploy/k6/`, k6 not installed | WRITTEN |
| C17 | Chaos scripts plan and probe correctly in dry-run mode | `backend/tests/observability/test_chaos_script.py` | VERIFIED |
| C18 | The service survives a backend kill or added latency | `deploy/chaos/`, never executed live | WRITTEN |
| C19 | With the database down the app keeps answering health and compute routes and returns clean 5xx for DB routes | `backend/tests/observability/test_resilience.py` | VERIFIED |
| C20 | Observations can be replayed to Redpanda and consumed by a Go service | replay dry run tested; broker and Go never run | WRITTEN |
| C21 | A digital twin compares predictions with recorded observations and supports what-if | `backend/tests/twin/test_twin.py` (recorded fixtures) | VERIFIED |
| C22 | The twin follows live traffic | no live feed (D3) | NOT CLAIMED |
| C23 | Frontend screens for network, map, congestion, calibration, RL, twin and load tests exist and are built against fixtures | `frontend/src/{netpage,mapview,congestion,calibration,netrl,twinview,loadtest}/`; `npx vitest run` (716 tests), tsc, eslint, prettier and `npm run build` pass; never run against a live backend or in a browser | VERIFIED (fixtures only) |
| C24 | The system deploys to Kubernetes through CI | `deploy/helm/`, `deploy/kind/`, `.github/workflows/k8s-deploy.yml`, never run on a cluster | WRITTEN |
| C25 | The Go ingest service handles the data path | `services/ingest-go/`, Go not installed here | WRITTEN |
| C26 | Fixed-seed runs repeat bit for bit within one process (study, network metrics, calibration) | `python scripts/reproducibility_audit.py`; `backend/tests/audit/test_reproducibility_audit.py` | VERIFIED |
| C27 | Results are identical across machines, Python versions or commits | not tested | NOT CLAIMED |
| C28 | Any real-world performance, safety or emissions outcome | simulator results under stated assumptions only | NOT CLAIMED |
| C29 | G-REL2 is met | see the gate table: first two criteria met on synthetic data only, last two incomplete | NOT CLAIMED |
