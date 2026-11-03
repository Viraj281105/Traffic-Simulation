"""Multi-seed runs with the opt-in variability models (ADR-020, W31 T4)."""

from __future__ import annotations

from typing import Any, Dict

from src.study.multiseed import default_study_config, run_multi_seed

BASE_SEED = 20261103
DURATION = 40.0
MODELS: Dict[str, Any] = {
    "driverHeterogeneity": {
        "enabled": True,
        "headwaySpread": 0.3,
        "accelerationSpread": 0.2,
        "decelerationSpread": 0.2,
    },
    "demandVariability": {"enabled": True, "spread": 0.4, "intervalSeconds": 60},
}


def _config(models: bool) -> Dict[str, Any]:
    cfg = default_study_config(DURATION)
    if models:
        cfg["traffic"].update(MODELS)
    return cfg


def _run(models: bool) -> Dict[str, Any]:
    return run_multi_seed(
        _config(models),
        geometry="signal",
        num_seeds=8,
        duration=DURATION,
        base_seed=BASE_SEED,
    )


def test_models_on_give_spread_and_repeat_exactly() -> None:
    first, second = _run(True), _run(True)
    assert first == second
    delay = first["summary"]["delay"]
    assert delay["n"] == 8 and delay["sd"] is not None and delay["sd"] > 0


def test_models_change_the_result_but_not_the_seeds() -> None:
    on, off = _run(True), _run(False)
    assert on["seeds"] == off["seeds"]
    assert on["seedRuns"] != off["seedRuns"]
    assert on["manifest"]["configHash"] != off["manifest"]["configHash"]
