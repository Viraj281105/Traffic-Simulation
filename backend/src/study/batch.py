import copy
import logging
import uuid
from typing import Any, Dict, Optional

from src.database.dao import RunMetricsDAO, ScenarioSuiteDAO, SimulationRunDAO
from src.database.db import get_db_connection
from src.study.runner import Progress, SimTask, run_simulation_tasks

logger = logging.getLogger(__name__)


def run_suite_batch_experiment(
    suite_id: str,
    base_config: Dict[str, Any],
    sweep_parameters: Dict[str, list[float]],
    num_seeds: int,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    progress = progress or Progress()

    # Generate all variations
    # For now, just handling one sweep parameter, e.g. arrivalRate
    param_keys = list(sweep_parameters.keys())

    variations = []
    if param_keys:
        k = param_keys[0]
        for val in sweep_parameters[k]:
            for seed in range(42, 42 + num_seeds):
                variations.append((k, val, seed))

    tasks = []
    for k, val, seed in variations:
        cfg = copy.deepcopy(base_config)
        cfg["traffic"][k] = val
        cfg["simulation"]["randomSeed"] = seed
        intersection_type = cfg.get("geometry", {}).get("intersectionType", "signal")
        geometry = (
            "roundabout" if "roundabout" in intersection_type.lower() else "signal"
        )
        task_id = f"batch_{suite_id[:8]}_{val}_{seed}"

        # Build SimTask
        task = SimTask(
            config=cfg,
            geometry=geometry,
            duration=cfg["simulation"].get("duration", 300),
            label=task_id,
        )
        tasks.append(task)

    results = run_simulation_tasks(tasks, progress)

    run_ids = []
    with get_db_connection() as conn:
        for task, res in zip(tasks, results):
            if not res.get("metrics"):
                continue

            run_id = f"run_{uuid.uuid4().hex[:8]}"
            run_ids.append(run_id)

            sig_metrics = res["metrics"]

            SimulationRunDAO.save(
                conn,
                run_id,
                "completed",
                res["elapsed"],
                intersection_type=res["config"]["geometry"]["intersectionType"],
                random_seed=res["config"]["simulation"]["randomSeed"],
                arrival_rate=res["config"]["traffic"].get("arrivalRate", 0.0),
                duration=res["config"]["simulation"].get("duration", 300),
                batch_id=suite_id,
                config=res["config"],
                summary_metrics=sig_metrics,
                provenance={},
                commit=False,
            )
            RunMetricsDAO.save(
                conn, run_id, int(res["elapsed"] / 0.1), sig_metrics, commit=False
            )

        ScenarioSuiteDAO.add_runs(conn, suite_id, run_ids)
        conn.commit()

    return {"suite_id": suite_id, "run_ids": run_ids}
