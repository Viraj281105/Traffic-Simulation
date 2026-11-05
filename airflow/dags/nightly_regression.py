"""Nightly regression DAG (F3).

Runs the backend test suite (slow tests included) and a short multi-seed study
by calling the same commands a developer runs by hand. A failing task fails
the DAG run, which is the pass/fail report.

Importable without Airflow: ``dag`` is then None and the helpers still work.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import json

import nightly_history as history
import urbanflow_common as common

# (check id, display name): what each night's history entry holds, in order.
CHECKS = (
    ("backend_suite", "Backend test suite"),
    ("multiseed_smoke", "Multi-seed smoke study"),
)


def run_backend_suite(ds: str = "manual") -> None:
    def suite() -> None:
        common.run(common.nightly_pytest_command(slow=True))

    history.checked(common.RESULTS_DIR, ds, "backend_suite", CHECKS[0][1], suite)


def run_multiseed_smoke(ds: str = "manual") -> None:
    out = common.RESULTS_DIR / "nightly" / f"{ds}-multiseed.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    def study() -> dict:
        common.run(common.multiseed_command("signal", 5, 60.0, out))
        mean = json.loads(out.read_text(encoding="utf-8"))["summary"]["delay"]["mean"]
        return {"metric": "mean_delay_s", "actual": mean, "unit": "s"}

    history.checked(common.RESULTS_DIR, ds, "multiseed_smoke", CHECKS[1][1], study)


def record_history(ds: str = "manual") -> None:
    history.record_night(common.RESULTS_DIR, ds, CHECKS, common.REPO_ROOT)


dag = None

if common.AIRFLOW_AVAILABLE:
    from airflow import DAG
    from airflow.operators.python import PythonOperator

    with DAG(
        dag_id="urbanflow_nightly_regression",
        description="Backend test suite and multi-seed study, nightly",
        schedule="17 2 * * *",
        start_date=datetime(2026, 11, 1),
        catchup=False,
        max_active_runs=1,
        default_args={"retries": 1, "retry_delay": timedelta(minutes=10)},
        tags=["urbanflow", "regression"],
    ) as dag:
        suite = PythonOperator(
            task_id="backend_suite",
            python_callable=run_backend_suite,
            op_kwargs={"ds": "{{ ds }}"},
            execution_timeout=timedelta(hours=2),
        )
        study = PythonOperator(
            task_id="multiseed_smoke",
            python_callable=run_multiseed_smoke,
            op_kwargs={"ds": "{{ ds }}"},
            execution_timeout=timedelta(minutes=30),
        )
        record = PythonOperator(
            task_id="record_history",
            python_callable=record_history,
            op_kwargs={"ds": "{{ ds }}"},
            trigger_rule="all_done",
        )
        suite >> study >> record
