"""Operational logging and metrics for the API process.

* ``logging_setup`` — structured (JSON) or plain logs, a request id on every
  line logged while a request is handled, and a filter that scrubs bearer
  tokens, personal access tokens and JWTs from any message.
* ``metrics`` — a small in-process registry of counters, gauges and
  histograms with fixed, low-cardinality labels, rendered in the Prometheus
  text format by ``GET /metrics``.
* ``middleware`` — the request id and per-request metrics and log line.

No dependency beyond the standard library; nothing here runs per simulation
tick. See docs/operations.md, "Logs and metrics".
"""
