import copy
import json
import logging
from typing import Any, Dict, Tuple

from src.core.config_models import DEFAULT_PHASE_SEQUENCE
from src.snapshot.lockstep import (
    LockstepOrchestrator,
    LockstepRun,
    resolve_shared_seed,
)

logger = logging.getLogger(__name__)


def signal_and_roundabout_configs(
    config: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The signal and roundabout engine configurations derived from one live
    scenario configuration (seed not yet applied). The signal keeps the
    scenario's signal control (fixed-time or adaptive); the roundabout keeps
    its entry control (conventional or metered)."""
    # Make deep copies of the configuration for both instances
    config_signal = json.loads(json.dumps(config))
    config_signal["geometry"] = config_signal.get("geometry", {})
    config_signal["geometry"]["intersectionType"] = "fixed_time_signal"

    config_roundabout = json.loads(json.dumps(config))
    config_roundabout["geometry"] = config_roundabout.get("geometry", {})
    config_roundabout["geometry"]["intersectionType"] = "roundabout"

    # ── Inject proper controller configs for each mode ──────────────
    # Signal controller needs signal timing parameters. When the source
    # config carries none (the live dashboard was set to "roundabout", so
    # its controller block holds ring parameters), the signal side gets the
    # canonical signal defaults: the paired NS/EW phaseSequence and
    # FixedTimeSignalController's own 30/5/4/2 s fallbacks.
    #
    # It used to get 15 s greens, a 3 s yellow and no phaseSequence — the
    # one-direction-at-a-time cycle — so the "same" signal in the dual
    # comparison ran a 100 s one-way cycle or a 72 s paired cycle
    # depending only on which geometry the dashboard happened to have
    # selected.
    signal_ctrl = config_signal.get("controller") or {}
    if not any(
        key in signal_ctrl
        for key in ("straightRightDuration", "greenDuration", "greenTime")
    ):
        # How the signal times its greens (V1.3) is not a timing value;
        # it is kept so an adaptive comparison stays adaptive.
        signal_ctrl = {
            "phaseSequence": list(DEFAULT_PHASE_SEQUENCE),
            **{
                key: signal_ctrl[key]
                for key in ("signalControl", "adaptive")
                if key in signal_ctrl
            },
        }
    config_signal["controller"] = signal_ctrl

    # Roundabout controller needs gap-acceptance / geometry parameters
    #
    # V1.4: the ring's design (radii, entry and circulating speed) is
    # carried over from the source config when it sets it. These used to
    # be replaced by fixed values whatever the scenario said, so a study
    # of a larger or faster roundabout silently ran the default one. A
    # config that does not set them gets exactly the old values.
    round_ctrl = config.get("roundaboutController", config.get("controller", {}))
    source_ctrl = config.get("controller") or {}

    def _ring_value(key: str, default: float) -> float:
        for section in (round_ctrl, source_ctrl):
            if isinstance(section, dict) and section.get(key) is not None:
                return float(section[key])
        return default

    config_roundabout["controller"] = {
        "innerRadius": _ring_value("innerRadius", 10.0),
        "outerRadius": _ring_value("outerRadius", 20.0),
        "circulatingLanes": 1,
        "criticalGap": float(round_ctrl.get("criticalGap", 4.0)),
        "followUpTime": float(round_ctrl.get("followUpTime", 2.5)),
        "entrySpeed": _ring_value("entrySpeed", 5.0),
        "circulatingSpeed": _ring_value("circulatingSpeed", 8.0),
    }
    if (config_roundabout.get("geometry") or {}).get(
        "circulatingLanes"
    ) is not None:
        # The ring lane count is set where V1.4 reads it; the reserved,
        # inert V1.0 field would only contradict it.
        del config_roundabout["controller"]["circulatingLanes"]

    # V3.0 W2 (H12): carry entryControl and entryMetering across when
    # configured, reading from roundaboutController falling back to
    # controller. An absent field leaves the section untouched.
    for key in ("entryControl", "entryMetering"):
        for section in (round_ctrl, source_ctrl):
            if isinstance(section, dict) and section.get(key) is not None:
                config_roundabout["controller"][key] = copy.deepcopy(
                    section[key]
                )
                break

    return config_signal, config_roundabout


class DualSimulationOrchestrator(LockstepOrchestrator):
    """Orchestrates two parallel simulations (Fixed-Time Signal and Roundabout) in lockstep with matching random seeds."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        config_signal, config_roundabout = signal_and_roundabout_configs(config)
        # Propagate random seed to align spawn sequences for fair comparison
        seed = resolve_shared_seed(self.config, "dual simulation")
        for derived in (config_signal, config_roundabout):
            derived.setdefault("simulation", {})["randomSeed"] = seed
        self.config_signal = config_signal
        self.config_roundabout = config_roundabout
        super().__init__(
            [
                ("signal", config_signal, "dual_signal"),
                ("roundabout", config_roundabout, "dual_roundabout"),
            ]
        )

    # The two runs under the names the live API, captures, reproduction and
    # studies have always read.
    @property
    def _signal(self) -> LockstepRun:
        return self.runs[0]

    @property
    def _roundabout(self) -> LockstepRun:
        return self.runs[1]

    @property
    def clock_signal(self) -> Any:
        return self._signal.clock

    @property
    def engine_signal(self) -> Any:
        return self._signal.engine

    @property
    def controller_signal(self) -> Any:
        return self._signal.controller

    @property
    def collector_signal(self) -> Any:
        return self._signal.collector

    @property
    def builder_signal(self) -> Any:
        return self._signal.builder

    @property
    def clock_roundabout(self) -> Any:
        return self._roundabout.clock

    @property
    def engine_roundabout(self) -> Any:
        return self._roundabout.engine

    @property
    def controller_roundabout(self) -> Any:
        return self._roundabout.controller

    @property
    def collector_roundabout(self) -> Any:
        return self._roundabout.collector

    @property
    def builder_roundabout(self) -> Any:
        return self._roundabout.builder

    def get_dual_snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self.clock_signal.get_tick_count(),
            "elapsed": round(self.clock_signal.get_elapsed_time(), 2),
            "signal": self.builder_signal.build(),
            "roundabout": self.builder_roundabout.build(),
        }
