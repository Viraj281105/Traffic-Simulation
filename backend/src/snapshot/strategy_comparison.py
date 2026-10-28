"""The live comparison of any registered control strategies on one scenario.

The guided comparison lets a visitor pick which strategies to compare. Each
pick is a canonical strategy id from the registry (``src.strategies``); this
module derives that strategy's engine configuration from the live scenario
and runs every pick in lockstep on the same seed (``lockstep``).

A configuration is derived from the same signal or roundabout configuration
the signal-vs-roundabout pair uses (``dual_orchestrator``), then given the
one setting that distinguishes the strategy, and is checked against the
registry: the controller factory must resolve it to the strategy it was
built for, so a result can never be attributed to the wrong control.
"""

import copy
from typing import Any, Callable, Dict, List, Sequence

from src.snapshot.dual_orchestrator import signal_and_roundabout_configs
from src.snapshot.lockstep import LockstepOrchestrator, resolve_shared_seed
from src.strategies.registry import get_strategy_registry
from src.strategies.resolution import resolve_strategy

APPROACH_ORDER = ("north", "east", "south", "west")


def _approaches(config: Dict[str, Any]) -> List[str]:
    """The approaches the scenario has: its declared roads, or all four for
    the dashboard's symmetric four-arm junction."""
    declared = (config.get("roads") or {}).get("approaches")
    if isinstance(declared, list):
        names = {
            item.get("direction") for item in declared if isinstance(item, dict)
        }
        present = [a for a in APPROACH_ORDER if a in names]
        if present:
            return present
    return list(APPROACH_ORDER)


def default_entry_metering(approaches: Sequence[str]) -> Dict[str, Any]:
    """The metering plan a metered-entry roundabout runs when the scenario
    draws none: north-south then east-west entries, 20 s greens, with the
    registry's default 3 s yellow and 2 s all-red. It mirrors the plan the
    scenario builder starts a metered roundabout with
    (frontend scenarioModel.defaultEntryMetering)."""
    params = get_strategy_registry().get("metered_entry_roundabout").parameters
    ns = [a for a in ("north", "south") if a in approaches]
    ew = [a for a in ("east", "west") if a in approaches]
    phases = [{"entries": group, "green": 20.0} for group in (ns, ew) if group]
    if not phases:
        phases = [{"entries": list(approaches), "green": 20.0}]
    return {
        "phases": phases,
        "yellow": params["metering_yellow"].default_value,
        "allRed": params["metering_all_red"].default_value,
        "offset": 0.0,
        "spillbackGuard": {"enabled": False, "stoppedThreshold": 2, "maxHold": 10.0},
        "queueCap": {"enabled": False, "vehicles": 8},
    }


def _metering_plan(source: Dict[str, Any]) -> Any:
    for section in (source.get("roundaboutController"), source.get("controller")):
        if isinstance(section, dict) and section.get("entryMetering") is not None:
            return copy.deepcopy(section["entryMetering"])
    return None


def _fixed_time(signal: Dict[str, Any], _: Dict[str, Any]) -> None:
    signal["controller"].pop("signalControl", None)
    signal["controller"].pop("adaptive", None)


def _adaptive(signal: Dict[str, Any], _: Dict[str, Any]) -> None:
    # The scenario's adaptive settings when it has them; otherwise the
    # controller's own defaults.
    signal["controller"]["signalControl"] = "adaptive"


def _conventional(roundabout: Dict[str, Any], _: Dict[str, Any]) -> None:
    roundabout["controller"].pop("entryControl", None)
    roundabout["controller"].pop("entryMetering", None)


def _metered(roundabout: Dict[str, Any], source: Dict[str, Any]) -> None:
    roundabout["controller"]["entryControl"] = "metered_entry"
    roundabout["controller"]["entryMetering"] = _metering_plan(
        source
    ) or default_entry_metering(_approaches(source))


# How each live-comparable strategy is derived: which of the two base
# configurations it starts from, and the setting that makes it that strategy.
# A strategy is offered in the live comparison exactly when it is listed here.
_DERIVATIONS: Dict[str, tuple[str, Callable[[Dict[str, Any], Dict[str, Any]], None]]] = {
    "fixed_time_signal": ("signal", _fixed_time),
    "adaptive_signal": ("signal", _adaptive),
    "conventional_roundabout": ("roundabout", _conventional),
    "metered_entry_roundabout": ("roundabout", _metered),
}

LIVE_COMPARISON_STRATEGIES: tuple[str, ...] = tuple(_DERIVATIONS)
DEFAULT_COMPARISON_STRATEGIES: tuple[str, ...] = (
    "fixed_time_signal",
    "conventional_roundabout",
)


def canonical_comparison_strategies(requested: Any) -> List[str]:
    """Canonical, de-duplicated strategy ids in the order given, each one a
    registered strategy the live comparison can run. Raises ValueError
    otherwise (aliases such as ``adaptive`` are accepted and resolved)."""
    if not isinstance(requested, list) or not requested:
        raise ValueError("strategies must be a non-empty list of strategy ids")
    registry = get_strategy_registry()
    out: List[str] = []
    for item in requested:
        try:
            canonical = registry.resolve_id(item)
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"Unknown strategy {item!r}")
        if canonical not in _DERIVATIONS:
            raise ValueError(
                f"Strategy {canonical!r} is not available in the live comparison"
            )
        if canonical not in out:
            out.append(canonical)
    return out


def strategy_engine_config(config: Dict[str, Any], strategy_id: str) -> Dict[str, Any]:
    """The engine configuration that runs the live scenario *config* under
    *strategy_id* (canonical), verified against the registry."""
    base, apply = _DERIVATIONS[strategy_id]
    source = {k: v for k, v in config.items() if k != "comparison"}
    signal, roundabout = signal_and_roundabout_configs(source)
    derived = signal if base == "signal" else roundabout
    apply(derived, source)
    resolved = resolve_strategy(derived).id
    if resolved != strategy_id:
        raise ValueError(
            f"Derived configuration for {strategy_id!r} resolves to {resolved!r}"
        )
    return derived


class StrategyComparisonOrchestrator(LockstepOrchestrator):
    """Runs the chosen strategies on one scenario in lockstep, one run per
    strategy, all on the same seed and time step."""

    def __init__(self, config: Dict[str, Any], strategies: Sequence[str]) -> None:
        self.config = config
        self.strategies = canonical_comparison_strategies(list(strategies))
        seed = resolve_shared_seed(self.config, "strategy comparison")
        runs = []
        for strategy_id in self.strategies:
            derived = strategy_engine_config(config, strategy_id)
            derived.setdefault("simulation", {})["randomSeed"] = seed
            runs.append((strategy_id, derived, f"compare_{strategy_id}"))
        super().__init__(runs)

    def get_snapshot(self) -> Dict[str, Any]:
        lead = self.runs[0]
        return {
            "tick": lead.clock.get_tick_count(),
            "elapsed": round(lead.clock.get_elapsed_time(), 2),
            "runs": [
                {"strategy": run.key, "snapshot": run.builder.build()}
                for run in self.runs
            ],
        }
