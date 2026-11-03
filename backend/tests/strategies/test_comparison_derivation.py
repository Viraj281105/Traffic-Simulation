"""Every live-comparable strategy derives from any valid scenario config (F-49).

``strategy_engine_config`` builds one strategy's engine config from a source
config and checks that the registry resolves it to that strategy. A strategy
named in the source (``scenario.strategy`` from ``compile_scenario``, or a
root/controller ``strategy``) used to override the derivation: from a compiled
fixed-time scenario the adaptive run raised a compatibility error, and from an
adaptive one the fixed-time run resolved to adaptive.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.controllers.factory import create_controller
from src.core.clock import Clock
from src.engine.simulation_engine import SimulationEngine
from src.scenario.documents import (
    compile_live_comparison,
    compile_scenario,
    parse_scenario,
)
from src.snapshot.strategy_comparison import (
    LIVE_COMPARISON_STRATEGIES,
    strategy_engine_config,
)
from src.strategies.resolution import resolve_strategy


def _document(junction: str) -> Any:
    approach = {
        "lanes": 1,
        "length": 150.0,
        "vehiclesPerHour": 300,
        "turning": {"left": 0.25, "straight": 0.5, "right": 0.25},
    }
    parsed, errors = parse_scenario(
        {
            "format": "urbanflow-scenario",
            "version": 1,
            "name": "derivation",
            "junction": {"type": junction},
            "approaches": {
                d: dict(approach) for d in ("north", "south", "east", "west")
            },
            "simulation": {"duration": 60.0, "warmup": 5.0, "seed": 9},
        }
    )
    assert parsed is not None, errors
    return parsed


SOURCES = {
    "compiled fixed_time": lambda: compile_scenario(
        _document("fixed_time_signal"), "fixed_time"
    ),
    "compiled adaptive": lambda: compile_scenario(
        _document("adaptive_signal"), "adaptive"
    ),
    "compiled roundabout": lambda: compile_scenario(
        _document("roundabout"), "roundabout"
    ),
    "live comparison": lambda: compile_live_comparison(
        _document("fixed_time_signal"), "fixed_time", "fixed_time_signal"
    ),
}


@pytest.mark.parametrize("source_name", list(SOURCES))
@pytest.mark.parametrize("strategy_id", LIVE_COMPARISON_STRATEGIES)
def test_every_strategy_derives_from_every_source(
    source_name: str, strategy_id: str
) -> None:
    source: Dict[str, Any] = SOURCES[source_name]()
    before = repr(source)

    derived = strategy_engine_config(source, strategy_id)

    assert resolve_strategy(derived).id == strategy_id
    engine = SimulationEngine(Clock(time_step=0.1), duration=60.0, config=derived)
    controller = create_controller(derived, engine.network)
    assert controller is not None
    # The caller's config is not modified.
    assert repr(source) == before


def test_a_declared_strategy_anywhere_does_not_override_the_derivation() -> None:
    source = compile_scenario(_document("fixed_time_signal"), "fixed_time")
    source["strategy"] = "fixed_time_signal"
    source["controller"]["strategy"] = "fixed_time"

    derived = strategy_engine_config(source, "adaptive_signal")

    assert resolve_strategy(derived).id == "adaptive_signal"
