# ADR-022: Observability and Service-Level Objectives

## Status

**Accepted / Implemented** (V4.4 / W44, feature F15; mounted in `backend/src/main.py` and validated via `tests/observability/`). In-cluster deployment artifacts remain `WRITTEN` per honesty conventions.

## Date

2026-11-05

## Context

Until V4.1 the backend had a JSON log format and a plain `/metrics` route (`observability/router.py`). With a network simulator, background jobs, a Go consumer and a cluster deployment, the team needs to see latency, errors, queue depth and run outcomes, to state targets, and to test that the service degrades cleanly. The environment where this was built has no Prometheus, Grafana, k6, Go or Docker stack running, so the design must work and be testable without them.

## Decision

1. **Tracing** uses OpenTelemetry through thin helpers (`observability/tracing.py`: `setup_tracing`, `run_span`, `request_span`). They are no-ops when the SDK is not installed, and export over OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. The SDK is an optional dependency, not in `requirements*.txt`.
2. **Metrics** are Prometheus-format, served at `GET /metrics/prom` (`prom_router.py`) because `GET /metrics` is already taken. The route returns the new run and API metrics plus everything `/metrics` serves, under the same rule: `Authorization: Bearer $METRICS_TOKEN` when set, otherwise loopback clients only. A built-in text-format backend is used when `prometheus_client` is absent, so the endpoint and its tests do not depend on the package.
3. **HTTP metrics** reuse the existing `ObservabilityMiddleware` (`urbanflow_http_request_duration_seconds`, `urbanflow_http_requests_total`). Run metrics (`urbanflow_runs_*`, `urbanflow_run_duration_seconds`, `urbanflow_queue_depth`) are recorded through `METRICS.track_run` and `set_queue_depth`.
4. **SLOs are data**, defined once in `deploy/observability/slo.json` over a 28-day window: API p95 latency <= 2.5 s; network-simulate p95 <= 10 s; availability >= 99.5 % non-5xx; job success >= 98 %; job p95 duration <= 300 s; run success >= 99 %; run p95 duration <= 120 s. Cancelled work is excluded from success rates. An evaluator and CLI (`observability/slo.py`) read a scrape or a URL and exit non-zero on a violation; an SLO with no data reports `no_data`, never a violation.
5. **Prometheus alerts, the Grafana dashboard and k6 thresholds** repeat the SLO numbers. The alert thresholds are written out by hand in `prometheus/alerts.yml`, so a change to `slo.json` must be mirrored there (a drift risk, see consequences).
6. **Load and chaos**: k6 smoke, load and spike scripts (`deploy/k6/`) read thresholds from `slo.json`. Chaos scripts (`deploy/chaos/chaos.py`) are dry runs unless `--execute` is passed. A resilience test in the normal suite refuses database connections and checks that health, compute routes and metrics keep answering and that DB routes fail cleanly and are counted as 5xx.
7. **Event stream**: observations replay to Redpanda (`scripts/replay_to_redpanda.py`, topic `urbanflow.observations`, keyed by `link_id`); a Go consumer aggregates per link and counts malformed messages without blocking the partition.
8. **Honesty rule**: every piece is labelled VERIFIED or WRITTEN in `docs/operations-observability.md` section 7. Nothing is called "live" until it has run against a real stack and the result is recorded in that file's Findings section.

## Consequences

* The backend can be observed and tested locally with no extra packages; the optional SDKs add export, not behaviour.
* As of this ADR, Prometheus, Grafana, k6, the chaos scripts against a live container, Redpanda and the Go consumer are WRITTEN and have not been run. The run counters are not yet wired to the launch points, so the run SLOs read `no_data`.
* SLO numbers live in two places (JSON and alert rules). A test or generator that keeps them in sync is a follow-up.
* The targets are engineering choices for a small service, not contractual commitments, and were set before any load measurement. They should be revisited after the first k6 run.

## Open points

1. Are the SLO targets acceptable, or should they be set after a measured baseline?
2. Which environment runs the observability stack first (local compose, kind, or the EC2 host)?
3. Should the run counters be wired before the stack is first run (recommended: yes)?
