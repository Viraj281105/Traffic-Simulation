# Observability, load and chaos runbook (F15, package 1D)

Companion to `docs/operations.md` ("Logs and metrics") and `docs/operations-platform.md`. This page
covers tracing, Prometheus/Grafana, SLOs, k6 load tests, chaos tests and the Redpanda replay.

Status words used throughout: **VERIFIED** = run in the dev environment with the result stated;
**WRITTEN** = authored carefully but not executed here (tool not installed, or needs a live stack).

## 1. What exists

| Piece | Where |
| --- | --- |
| Tracing helpers (OpenTelemetry, optional) | `backend/src/observability/tracing.py` |
| Run/API Prometheus metrics | `backend/src/observability/prom_metrics.py` |
| Scrape route `GET /metrics/prom` | `backend/src/observability/prom_router.py` |
| SLO data + evaluator | `deploy/observability/slo.json`, `backend/src/observability/slo.py` |
| Prometheus scrape + alerts | `deploy/observability/prometheus/` |
| Grafana dashboard + provisioning, local compose | `deploy/observability/grafana/`, `deploy/observability/docker-compose.yml` |
| k6 smoke / load / spike | `deploy/k6/` |
| Chaos scripts | `deploy/chaos/` |
| Redpanda compose, replay, Go consumer | `docker-compose.redpanda.yml`, `scripts/replay_to_redpanda.py`, `services/consumer-go/` |

`GET /metrics` (existing, `observability/router.py`) already owns that path, so the richer set is
served at **`GET /metrics/prom`**. It returns the new run/API metrics plus everything `/metrics`
serves. Both use the same access rule: `Authorization: Bearer $METRICS_TOKEN` when the variable is
set, otherwise loopback clients only.

### Active Mounting in `backend/src/main.py`

Mounted and active in production:

```python
from src.observability import prom_router
app.include_router(prom_router.router)
```

### Instrumenting code

```python
from src.observability.prom_metrics import METRICS
from src.observability.tracing import run_span, request_span, setup_tracing

setup_tracing("urbanflow-backend")        # once at startup; no-op without the SDK

with METRICS.track_run("network"), run_span("network", run_id=rid):
    engine.run()                           # counts started/completed, records duration

METRICS.set_queue_depth(n)                 # from the job registry
with METRICS.track_request("POST", "/api/v2/network-metrics/simulate"), \
     request_span("POST", "/api/v2/network-metrics/simulate"):
    ...                                    # only if you are not using the existing middleware
```

The existing `ObservabilityMiddleware` already records `urbanflow_http_request_duration_seconds`
and `urbanflow_http_requests_total`; the API SLOs use those, so no extra request instrumentation is
needed. `urbanflow_runs_*`, `urbanflow_run_duration_seconds` and `urbanflow_queue_depth` stay at
zero/empty until the run launch points call `METRICS.track_run(...)` / `set_queue_depth(...)`
(not wired yet: that touches files outside this package).

Optional packages (not in `requirements*.txt`; everything works without them):

```
pip install prometheus-client opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
pip install kafka-python        # only for scripts/replay_to_redpanda.py without --dry-run
```

Tracing environment: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`, `OTEL_SERVICE_NAME`,
`OTEL_TRACES_CONSOLE=1` to print spans.

## 2. SLOs

Defined once in `deploy/observability/slo.json` (28-day window). The evaluator, Prometheus alerts,
Grafana panels and k6 thresholds all use these numbers; change the JSON, then update
`prometheus/alerts.yml` (thresholds are written out there) and the panel titles.

| ID | Objective | Metric |
| --- | --- | --- |
| `api_latency_p95` | p95 <= 2.5 s | `urbanflow_http_request_duration_seconds` |
| `network_simulate_p95` | p95 <= 10 s for `/api/v2/network-metrics/simulate` | same, `route` label |
| `api_availability` | >= 99.5 % of requests not 5xx | `urbanflow_http_requests_total` |
| `job_success_rate` | >= 98 % completed (cancelled excluded) | `urbanflow_jobs_total` |
| `job_duration_p95` | p95 <= 300 s | `urbanflow_job_duration_seconds` |
| `run_success_rate` | >= 99 % completed (cancelled excluded) | `urbanflow_runs_completed_total` |
| `run_duration_p95` | p95 <= 120 s | `urbanflow_run_duration_seconds` |

An SLO with no data reports `no_data`, not a violation.

Check a running backend (exit code 1 if any SLO is violated):

```bash
cd backend
METRICS_TOKEN=devtoken .venv/Scripts/python -m src.observability.slo http://127.0.0.1:8000/metrics/prom
# or from a saved scrape
.venv/Scripts/python -m src.observability.slo scrape.txt
```

## 3. Prometheus and Grafana (WRITTEN)

```bash
# from the repo root; the token file must match the backend's METRICS_TOKEN
printf '%s' "$METRICS_TOKEN" > deploy/observability/prometheus/metrics_token   # NOT git-ignored: never commit this file
export GRAFANA_ADMIN_PASSWORD=choose-one
docker compose -f docker-compose.yml -f deploy/observability/docker-compose.yml up -d prometheus grafana
```

Prometheus: http://127.0.0.1:9090 (Status > Targets should show `urbanflow-backend` up).
Grafana: http://127.0.0.1:3000, dashboard "UrbanFlow SLOs" (provisioned). Validate rules with
`promtool check rules deploy/observability/prometheus/alerts.yml` and
`promtool check config deploy/observability/prometheus/prometheus.yml`.

Do not commit `metrics_token`.

## 4. k6 load tests (WRITTEN)

k6 is not installed in the dev environment. Install from https://grafana.com/docs/k6/, then:

```bash
export BASE_URL=http://127.0.0.1:8000
export AUTH_TOKEN=<bearer token for the v2 routes>      # the simulate route requires auth
k6 run deploy/k6/smoke.js      # 1 VU, 30 s
k6 run deploy/k6/load.js       # ramp to 10 VUs, hold 5 min
k6 run deploy/k6/spike.js      # 2 -> 50 VUs, then recovery
```

Each script calls `/health` and `POST /api/v2/network-metrics/simulate` (2x2 grid, 120 s; `load.js`
also runs the 3x3 / 600 s SLO-sized call in 10 % of iterations). Thresholds are read from
`slo.json`: failure rate < 0.5 %, health p95 < 2.5 s, simulate p95 < 10 s. `spike.js` allows 2x the
latency and 5x the error rate. Failing thresholds make k6 exit non-zero, so the scripts can gate a
scheduled CI job (no workflow was added here).

## 5. Chaos tests

All state-changing actions are dry runs unless `--execute` is passed.

```bash
python deploy/chaos/chaos.py kill-backend                     # prints the plan only
python deploy/chaos/chaos.py kill-backend --execute --down-seconds 20
python deploy/chaos/chaos.py latency-proxy --listen 9000 --target 127.0.0.1:8000 \
       --delay-ms 400 --jitter-ms 100 --seconds 60 --execute    # then k6 with BASE_URL=http://127.0.0.1:9000
python deploy/chaos/chaos.py probe --url http://127.0.0.1:8000/health --seconds 60
EXECUTE=1 sh deploy/chaos/worker-kill.sh                      # k6 load while the backend is killed
```

Expected: during `kill-backend` requests fail, then `/health` answers again within the
`--recovery-timeout` (default 120 s) and the script prints the recovery time. Record the numbers
and any fix or accepted risk in this file under "Findings" (none recorded yet; nothing has been run
against a live stack).

### Resilience test (VERIFIED)

`backend/tests/observability/test_resilience.py` runs the real app through `TestClient` with SQLite
refusing connections: `/health`, a pure-compute route and `/metrics` keep answering; a DB-backed
route returns a 5xx without a traceback, is counted in `urbanflow_http_requests_total{status="5xx"}`,
and answers normally once the database is back.

## 6. Redpanda replay and Go consumer (WRITTEN)

```bash
docker compose -f docker-compose.redpanda.yml up -d          # redpanda, topic, consumer
python scripts/replay_to_redpanda.py counts.csv --dry-run     # VERIFIED: prints messages
python scripts/replay_to_redpanda.py counts.csv --bootstrap localhost:19092 --rate 50
docker compose -f docker-compose.redpanda.yml logs -f consumer
```

CSV columns: `link_id`, `interval_start`, `count` (the network-calibration counts format), extra
columns are passed through. Messages go to topic `urbanflow.observations`, keyed by `link_id`:
`{"link_id":"L1","interval_start":"0","count":12.0,"sensor_id":"s1","seq":0}`. The consumer
aggregates per link, rejects malformed messages (counted, still committed so a bad message cannot
block a partition), and logs totals every `STATS_INTERVAL`.

Go tests (need Go 1.23): `cd services/consumer-go && go mod tidy && go vet ./... && go test ./...`.
`go.sum` is not committed; `go mod tidy` creates it and needs network access.

## 7. VERIFIED vs WRITTEN

| Item | Status | Evidence |
| --- | --- | --- |
| Tracing helpers are no-ops without OpenTelemetry | VERIFIED | `test_prom_slo.py` |
| OTLP export with the real SDK | WRITTEN | SDK not installed |
| Run/API metrics, builtin backend, `/metrics/prom` and auth | VERIFIED | `test_prom_slo.py` |
| Run/API metrics through `prometheus_client` | WRITTEN | package not installed; test skips |
| SLO file, evaluator, CLI | VERIFIED | `test_prom_slo.py` |
| Resilience with DB down | VERIFIED | `test_resilience.py` |
| Chaos script planning, dry run, probe logic | VERIFIED | `test_chaos_script.py` |
| Chaos against a live container, latency proxy | WRITTEN | needs Docker stack |
| Replay script parsing, throttling, dry run | VERIFIED | `test_replay_script.py` |
| Replay publish to a broker | WRITTEN | needs Redpanda and a Kafka client |
| Prometheus config/alerts, Grafana JSON, compose | WRITTEN | JSON parses; not loaded into the tools |
| k6 scripts | WRITTEN | k6 not installed |
| Go consumer, Dockerfile, Redpanda compose | WRITTEN | Go not installed here |
| Wiring `track_run` / `set_queue_depth` at run launch points | NOT DONE | outside this package |

## 8. Findings

None yet. Add rows here after the first load and chaos runs: date, test, result, action.
