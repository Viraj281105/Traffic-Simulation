"""A comparison frame shows every run at the same tick (F-51).

The lockstep loop steps the runs one after another while holding the
orchestrator's lock; each snapshot builder holds only its own engine's lock.
The live WebSocket streams build frames on a worker thread, so a frame built
between two runs' steps showed the first run one tick ahead of the second.

These tests pause the stepping thread exactly there (after the first run has
stepped, before the next) and ask for a frame from another thread.
"""

from __future__ import annotations

import copy
import threading
from typing import Any, Callable, Dict, List

from src.live.dashboard_config import DEFAULT_CONFIG
from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.snapshot.lockstep import LockstepOrchestrator
from src.snapshot.strategy_comparison import StrategyComparisonOrchestrator


def _config() -> Dict[str, Any]:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.setdefault("simulation", {})["randomSeed"] = 3
    return config


def _frame_taken_mid_step(
    orch: LockstepOrchestrator, take: Callable[[], Dict[str, Any]]
) -> Dict[str, Any]:
    """Step every run once, as the loop does, while another thread asks for
    a frame right after the first run has stepped."""
    first = orch.runs[0].engine
    real_step = first.step
    frames: List[Dict[str, Any]] = []
    started = threading.Event()

    def ask() -> None:
        started.set()
        frames.append(take())

    asker = threading.Thread(target=ask)

    def step_then_ask() -> None:
        real_step()
        asker.start()
        started.wait(timeout=5.0)
        # Long enough for an unguarded frame to be built right here.
        asker.join(timeout=1.0)

    first.step = step_then_ask  # type: ignore[method-assign]
    try:
        with orch.snapshot_lock():
            orch.step()
    finally:
        first.step = real_step  # type: ignore[method-assign]
    asker.join(timeout=10.0)
    assert frames, "the frame was never built"
    return frames[0]


def test_a_dual_frame_shows_both_runs_at_one_tick() -> None:
    orch = DualSimulationOrchestrator(_config())
    for _ in range(5):
        orch.step()

    frame = _frame_taken_mid_step(orch, orch.get_dual_snapshot)

    assert frame["signal"]["tick"] == frame["roundabout"]["tick"] == frame["tick"]
    assert frame["tick"] == 6


def test_a_strategy_comparison_frame_shows_every_run_at_one_tick() -> None:
    orch = StrategyComparisonOrchestrator(
        _config(),
        ["fixed_time_signal", "adaptive_signal", "conventional_roundabout"],
    )
    for _ in range(5):
        orch.step()

    frame = _frame_taken_mid_step(orch, orch.get_snapshot)

    ticks = {run["snapshot"]["tick"] for run in frame["runs"]}
    assert ticks == {frame["tick"]} == {6}
