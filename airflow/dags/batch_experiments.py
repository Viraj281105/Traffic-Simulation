"""Batch experiments DAG (F3).

Triggered manually. Runs a multi-seed study per geometry (in parallel tasks)
and then the existing full-study CLI, writing results under
``URBANFLOW_RESULTS_DIR``. Trigger conf (all optional):
``{"num_seeds": 10, "duration": 120, "base_seed": 42}``.

Importable without Airflow: ``dag`` is then None and the helpers still work.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import urbanflow_common as common

GEOMETRIES = ("signal", "roundabout")


def _params(conf: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    conf = conf or {}
    return {
        "num_seeds": int(conf.get("num_seeds", 5)),
        "duration": float(conf.get("duration", 60.0)),
        "base_seed": conf.get("base_seed"),
    }


def run_geometry(geometry: str, run_id: str = "manual", dag_run: Any = None) -> None:
    p = _params(getattr(dag_run, "conf", None))
    out = common.RESULTS_DIR / "batch" / run_id / f"multiseed-{geometry}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    seed = None if p["base_seed"] is None else int(p["base_seed"])
    common.run(common.multiseed_command(geometry, p["num_seeds"], p["duration"], out, seed))


def run_full_study(run_id: str = "manual", dag_run: Any = None) -> None:
    p = _params(getattr(dag_run, "conf", None))
    base = common.RESULTS_DIR / "batch" / run_id
    base.mkdir(parents=True, exist_ok=True)
    common.run(
        common.full_study_command(base / "study_report.csv", base / "study_summary.json", p["num_seeds"])
    )


dag = None

if common.AIRFLOW_AVAILABLE:
    from airflow import DAG
    from airflow.operators.python import PythonOperator

    with DAG(
        dag_id="urbanflow_batch_experiments",
        description="Multi-seed studies per geometry, then the full study CLI",
        schedule=None,
        start_date=datetime(2026, 11, 1),
        catchup=False,
        max_active_runs=1,
        default_args={"retries": 0},
        tags=["urbanflow", "experiments"],
    ) as dag:
        per_geometry = [
            PythonOperator(
                task_id=f"multiseed_{g}",
                python_callable=run_geometry,
                # dag_run is injected by Airflow from the task context.
                op_kwargs={"geometry": g, "run_id": "{{ run_id }}"},
                execution_timeout=timedelta(hours=1),
            )
            for g in GEOMETRIES
        ]
        full = PythonOperator(
            task_id="full_study",
            python_callable=run_full_study,
            op_kwargs={"run_id": "{{ run_id }}"},
            execution_timeout=timedelta(hours=2),
        )
        per_geometry >> full
