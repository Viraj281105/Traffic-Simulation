"""Scenario-suite batch experiments (V1.7).

One base engine configuration is run over a list of arrival rates, each rate
over ``num_seeds`` consecutive seeds starting at 42, and every completed run
is stored and attached to the suite. The caller (``POST
/api/suites/{id}/batch``) validates the configuration and bounds the
workload; this module only runs and records it.
"""

import copy
import logging
import uuid
from typing import Any, Dict, List, Optional

from src.core.provenance import build_run_provenance
from src.database.dao import RunMetricsDAO, ScenarioSuiteDAO, SimulationRunDAO
from src.database.db import get_db_connection
from src.study.runner import Progress, SimTask, run_simulation_tasks

logger = logging.getLogger(__name__)

# The first seed of every batch; seed i of a batch is FIRST_SEED + i.
FIRST_SEED = 42


def batch_tasks(
    suite_id: str,
    base_config: Dict[str, Any],
    arrival_rates: List[float],
    num_seeds: int,
) -> List[SimTask]:
    """One simulation per (arrival rate, seed), in that nesting order."""
    intersection_type = str(
        (base_config.get("geometry") or {}).get("intersectionType", "")
    )
    geometry = "roundabout" if intersection_type == "roundabout" else "signal"
    tasks = []
    for rate in arrival_rates:
        for seed in range(FIRST_SEED, FIRST_SEED + num_seeds):
            cfg = copy.deepcopy(base_config)
            cfg.setdefault("traffic", {})["arrivalRate"] = rate
            cfg.setdefault("simulation", {})["randomSeed"] = seed
            tasks.append(
                SimTask(
                    config=cfg,
                    geometry=geometry,
                    duration=cfg["simulation"].get("duration", 300),
                    label=f"batch_{suite_id[:8]}_{rate}_{seed}",
                )
            )
    return tasks


def run_suite_batch_experiment(
    suite_id: str,
    base_config: Dict[str, Any],
    arrival_rates: List[float],
    num_seeds: int,
    progress: Optional[Progress] = None,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the sweep and attach its runs to the suite. ``owner_id`` is stored
    on every run: a private suite's results must be as private as the suite,
    and an unowned run is public in the run history (src/access.py)."""
    progress = progress or Progress()
    tasks = batch_tasks(suite_id, base_config, arrival_rates, num_seeds)
    results = run_simulation_tasks(tasks, progress)

    run_ids = []
    with get_db_connection() as conn:
        for res in results:
            if not res.get("metrics"):
                continue

            run_id = f"run_{uuid.uuid4().hex[:8]}"
            run_ids.append(run_id)
            config = res["config"]
            metrics = res["metrics"]

            SimulationRunDAO.save(
                conn,
                run_id,
                "completed",
                res["elapsed"],
                intersection_type=config["geometry"]["intersectionType"],
                random_seed=config["simulation"]["randomSeed"],
                arrival_rate=config["traffic"].get("arrivalRate", 0.0),
                duration=res["engineDuration"],
                batch_id=suite_id,
                user_id=owner_id,
                config=config,
                summary_metrics=metrics,
                # Recorded like every other study run (see volume_sweep.py):
                # these used to be stored with no provenance, so a batch run's
                # reproducibility report could not name its commit or timing.
                provenance=build_run_provenance(
                    config_source="engine",
                    run_mode="single",
                    time_step=res["timeStep"],
                    duration=res["engineDuration"],
                    warmup_time=res["warmupTime"],
                ),
                commit=False,
            )
            # The run's own tick count, not elapsed / 0.1: a batch run at
            # another time step was filed under the wrong tick.
            RunMetricsDAO.save(conn, run_id, res["steps"], metrics, commit=False)

        ScenarioSuiteDAO.add_runs(conn, suite_id, run_ids)
        conn.commit()

    return {"suite_id": suite_id, "run_ids": run_ids}
