"""The numeric metrics the collector emits match the shared key list.

``shared/metrics/collector-metric-keys.json`` is what the frontend's glossary
test checks against its metric catalog, so a metric added to the collector but
not to that list fails here, and one added to the list but not described in
the catalog fails there.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Set

from src.study.multiseed import default_study_config, seeded_run_config
from src.study.runner import SimTask, run_simulation_tasks

KEYS_FILE = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "metrics"
    / "collector-metric-keys.json"
)


def _numeric_keys(metrics: Dict[str, Any]) -> Set[str]:
    return {
        k
        for k, v in metrics.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def test_collector_numeric_keys_equal_the_shared_list() -> None:
    fixture = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    seen: Set[str] = set()
    for geometry in ("signal", "roundabout"):
        task = SimTask(
            config=seeded_run_config(default_study_config(40.0), 3, 40.0),
            geometry=geometry,
            duration=40.0,
            label="parity",
        )
        seen |= _numeric_keys(run_simulation_tasks([task])[0]["metrics"])
    listed = set(fixture["numeric"])
    assert seen - listed == set(), (
        "metrics emitted but missing from shared/metrics/collector-metric-keys.json: "
        f"{sorted(seen - listed)}"
    )
    assert listed - seen == set(), (
        "keys listed in shared/metrics/collector-metric-keys.json but not emitted: "
        f"{sorted(listed - seen)}"
    )


def test_every_exclusion_is_listed_and_explained() -> None:
    fixture = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    assert set(fixture["excluded"]) <= set(fixture["numeric"])
    assert all(len(reason) > 20 for reason in fixture["excluded"].values())
