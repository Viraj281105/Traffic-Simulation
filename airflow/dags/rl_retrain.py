"""Network RL retraining DAG (F18).

Weekly: train a candidate policy on the network, evaluate it and the current
production model on the same held-out seeds, and promote the candidate only if
it is better. Each task runs ``python -m src.rl.retrain <stage>`` from
``backend/`` (needs ``backend/requirements-rl.txt`` on the worker). Trigger conf
(all optional): ``{"timesteps": 50000, "seed": 3, "eval_seeds": 20,
"rows": 3, "cols": 3}``.

Importable without Airflow: ``dag`` is then None and the helpers still work.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import re

import urbanflow_common as common

STAGES = ("train", "evaluate", "promote")
REGISTRY_DIR = common.RESULTS_DIR / "rl" / "registry"


def _params(conf: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    conf = conf or {}
    return {
        "timesteps": int(conf.get("timesteps", 20000)),
        "seed": int(conf.get("seed", 0)),
        "eval_seeds": int(conf.get("eval_seeds", 10)),
        "rows": int(conf.get("rows", 2)),
        "cols": int(conf.get("cols", 2)),
    }


def work_dir(run_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id) or "manual"
    return common.RESULTS_DIR / "rl" / "retrain" / safe


def retrain_command(
    stage: str, run_id: str = "manual", params: Optional[Dict[str, Any]] = None
) -> List[str]:
    """The ``src.rl.retrain`` invocation for one stage."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    p = _params(params)
    return [
        common.PYTHON, "-m", "src.rl.retrain", stage,
        "--work-dir", str(work_dir(run_id)),
        "--registry-dir", str(REGISTRY_DIR),
        "--timesteps", str(p["timesteps"]),
        "--seed", str(p["seed"]),
        "--seeds", str(p["eval_seeds"]),
        "--rows", str(p["rows"]),
        "--cols", str(p["cols"]),
    ]


def run_stage(stage: str, run_id: str = "manual", dag_run: Any = None) -> None:
    params = _params(getattr(dag_run, "conf", None))
    work_dir(run_id).mkdir(parents=True, exist_ok=True)
    common.run(retrain_command(stage, run_id, params))


def run_train(run_id: str = "manual", dag_run: Any = None) -> None:
    run_stage("train", run_id, dag_run)


def run_evaluate(run_id: str = "manual", dag_run: Any = None) -> None:
    run_stage("evaluate", run_id, dag_run)


def run_promote(run_id: str = "manual", dag_run: Any = None) -> None:
    run_stage("promote", run_id, dag_run)


dag = None

if common.AIRFLOW_AVAILABLE:
    from airflow import DAG
    from airflow.operators.python import PythonOperator

    with DAG(
        dag_id="urbanflow_rl_retrain",
        description="Train, evaluate and conditionally promote the network RL policy",
        schedule="0 3 * * 0",
        start_date=datetime(2026, 11, 1),
        catchup=False,
        max_active_runs=1,
        default_args={"retries": 0, "retry_delay": timedelta(minutes=10)},
        tags=["urbanflow", "rl"],
    ) as dag:
        train = PythonOperator(
            task_id="train",
            python_callable=run_train,
            op_kwargs={"run_id": "{{ run_id }}"},
            execution_timeout=timedelta(hours=6),
        )
        evaluate = PythonOperator(
            task_id="evaluate",
            python_callable=run_evaluate,
            op_kwargs={"run_id": "{{ run_id }}"},
            execution_timeout=timedelta(hours=1),
        )
        promote = PythonOperator(
            task_id="promote",
            python_callable=run_promote,
            op_kwargs={"run_id": "{{ run_id }}"},
            execution_timeout=timedelta(minutes=10),
        )
        train >> evaluate >> promote
