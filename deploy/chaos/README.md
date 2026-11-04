# Chaos scripts

`chaos.py` (stdlib only) kills/restarts the backend container, adds latency through a TCP proxy,
and probes `/health`. Everything that changes state is a dry run unless `--execute` is passed.
Usage and the expected results are in `docs/operations-observability.md`. WRITTEN, not run against
a live stack.
