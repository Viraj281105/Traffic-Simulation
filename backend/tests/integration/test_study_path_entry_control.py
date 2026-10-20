"""The study path keeps a roundabout's entry control (V3.0 W2, hazard H12).

Every planner, Robustness Lab, batch, sweep, validation, calibration and
dual-reproduction run builds its roundabout through
``DualSimulationOrchestrator``, which **rebuilds** the roundabout's
``controller`` section from a fixed list of ring keys. Found 2026-10-19 while
building the golden-fingerprint study path: ``controller.entryControl`` and
``controller.entryMetering`` (docs/engineering/v3-w2-signalised-roundabout-plan.md
§5.1) are dropped there, so a metered alternative would silently run as a
conventional roundabout.

The two ``xfail(strict=True)`` tests record that defect: they fail today and
turn into errors the moment the carry-over exists (plan step S4), so the
marker has to be removed with the fix. The third pins what the orchestrator
builds for a config without the fields, which the fix must leave unchanged.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.study.runner import simulate_geometry
from tests.controllers.roundabout_golden import CORPUS, compile_case

# The shape the plan proposes (§5.1). Its content is irrelevant here: the
# orchestrator does not interpret it, it only has to pass it on.
_METERING: Dict[str, Any] = {
    "phases": [
        {"entries": ["north", "south"], "green": 20, "minGreen": 8, "maxGreen": 40},
        {"entries": ["east", "west"], "green": 20, "minGreen": 8, "maxGreen": 40},
    ],
    "yellow": 3.0,
    "allRed": 2.0,
}

_DROPPED = (
    "DualSimulationOrchestrator rebuilds the roundabout controller section "
    "and drops entryControl/entryMetering (hazard H12); fixed in plan step S4"
)


def _config(*, metered: bool) -> Dict[str, Any]:
    case = next(c for c in CORPUS if c["id"] == "study-path-two-ring-medium")
    config = copy.deepcopy(compile_case(case))
    config["simulation"]["duration"] = 2.0
    if metered:
        config["controller"]["entryControl"] = "metered_entry"
        config["controller"]["entryMetering"] = copy.deepcopy(_METERING)
    return config


def test_orchestrator_passes_entry_control_to_the_roundabout() -> None:
    orch = DualSimulationOrchestrator(_config(metered=True))
    controller = orch.config_roundabout["controller"]
    assert controller.get("entryControl") == "metered_entry"
    assert controller.get("entryMetering") == _METERING


def test_a_study_run_records_the_entry_control_it_ran_with() -> None:
    """What ``simulate_geometry`` stores as the run's own engine config."""
    ran = simulate_geometry(_config(metered=True), "roundabout", 2.0)["config"]
    assert ran["controller"].get("entryControl") == "metered_entry"


def test_without_entry_control_the_roundabout_section_is_unchanged() -> None:
    """Pinned 2026-10-19 (e43bfec): the fix may only add the two fields when
    they are given."""
    orch = DualSimulationOrchestrator(_config(metered=False))
    assert orch.config_roundabout["controller"] == {
        "innerRadius": 10.0,
        "outerRadius": 20.0,
        "criticalGap": 4.0,
        "followUpTime": 2.5,
        "entrySpeed": 5.0,
        "circulatingSpeed": 8.0,
    }
    assert "entryControl" not in orch.config_signal["controller"]
