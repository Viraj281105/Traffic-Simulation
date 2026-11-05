"""Result-screen adapters for ``/api/v3`` (comparison, sensitivity, run metrics, run diff, nightly
regression, report, RL comparison, network upload checks).

Each module here turns data that already exists (the experiment store, the Parquet run store, files written
by the scripts under ``URBANFLOW_RESULTS_DIR``) into the camelCase shapes the frontend's ``types.ts`` files
define (``frontend/src/CONTRACTS.md``). No statistic is computed in the browser and none is invented here:
intervals and p-values come from ``src.uncertainty.comparison``, delay and emissions from ``src.metrics``.
A value that cannot be computed is ``None`` (JSON ``null``); a result that is not there is "not available",
which the router answers with 404.

The file locations and formats are documented in ``docs/operations-platform.md`` ("Result files").
"""
