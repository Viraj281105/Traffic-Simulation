"""Make the scripts/ and airflow/dags/ modules importable before test modules load."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
for sub in ("scripts", "airflow/dags"):
    path = str(REPO / sub)
    if path not in sys.path:
        sys.path.insert(0, path)
