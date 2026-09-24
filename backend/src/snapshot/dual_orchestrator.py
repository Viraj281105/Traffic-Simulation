import json
import logging
import random
import threading
import time
from typing import Any, Dict, Optional

from src.controllers.factory import build_tick_callback, create_controller
from src.core.clock import Clock
from src.core.config_models import DEFAULT_PHASE_SEQUENCE
from src.core.engine import SimulationEngine
from src.core.enums import SimulationStatus
from src.metrics.collector import MetricCollector
from src.snapshot.builder import SnapshotBuilder

logger = logging.getLogger(__name__)


class DualSimulationOrchestrator:
    """Orchestrates two parallel simulations (Fixed-Time Signal and Roundabout) in lockstep with matching random seeds."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

        # Make deep copies of the configuration for both instances
        self.config_signal = json.loads(json.dumps(config))
        self.config_signal["geometry"] = self.config_signal.get("geometry", {})
        self.config_signal["geometry"]["intersectionType"] = "fixed_time_signal"

        self.config_roundabout = json.loads(json.dumps(config))
        self.config_roundabout["geometry"] = self.config_roundabout.get("geometry", {})
        self.config_roundabout["geometry"]["intersectionType"] = "roundabout"

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
        signal_ctrl = self.config_signal.get("controller") or {}
        if not any(
            key in signal_ctrl
            for key in ("straightRightDuration", "greenDuration", "greenTime")
        ):
            signal_ctrl = {"phaseSequence": list(DEFAULT_PHASE_SEQUENCE)}
        self.config_signal["controller"] = signal_ctrl

        # Roundabout controller needs gap-acceptance / geometry parameters
        round_ctrl = config.get("roundaboutController", config.get("controller", {}))
        self.config_roundabout["controller"] = {
            "innerRadius": 10.0,
            "outerRadius": 20.0,
            "circulatingLanes": 1,
            "criticalGap": float(round_ctrl.get("criticalGap", 4.0)),
            "followUpTime": float(round_ctrl.get("followUpTime", 2.5)),
            "entrySpeed": 5.0,
            "circulatingSpeed": 8.0,
        }

        # Propagate random seed to align spawn sequences for fair comparison
        seed = config.get("simulation", {}).get("randomSeed")
        if seed is None:
            # Never fall back to the shared global `random` module (see
            # vehicles/spawner.py for the same fix and rationale). Use a
            # private, independently OS-seeded instance instead, and log
            # the fallback so it is never silent.
            seed = random.Random().randint(1, 10_000_000)
            logger.warning(
                "No simulation.randomSeed configured for dual simulation; "
                "generated seed=%d for this comparison run. Pass "
                "randomSeed explicitly for reproducible comparisons.",
                seed,
            )
            if "simulation" not in self.config:
                self.config["simulation"] = {}
            self.config["simulation"]["randomSeed"] = seed

        if "simulation" not in self.config_signal:
            self.config_signal["simulation"] = {}
        if "simulation" not in self.config_roundabout:
            self.config_roundabout["simulation"] = {}
        self.config_signal["simulation"]["randomSeed"] = seed
        self.config_roundabout["simulation"]["randomSeed"] = seed

        # Both engines step with the configured time step. This used to be a
        # hard-coded 0.1 s, so the sweep and Monte-Carlo dashboards' Δt
        # choice (0.05 / 0.1 / 0.2 s, shown next to their results) was
        # silently ignored, and a reproduction of a run recorded at another
        # time step could not honour it either.
        time_step = float(config.get("simulation", {}).get("timeStep", 0.1))

        # ── Build Signal Simulation ─────────────────────────────────────
        self.clock_signal = Clock(time_step=time_step)
        duration = config.get("simulation", {}).get("duration", 300)
        self.engine_signal = SimulationEngine(
            self.clock_signal, duration=duration, config=self.config_signal
        )
        self.controller_signal = create_controller(
            self.config_signal, self.engine_signal.network
        )

        # CRITICAL: Assign controller to engine so engine.step() calls
        # controller.update() BEFORE vehicle physics (zero-latency response)
        self.engine_signal.controller = self.controller_signal

        self.collector_signal = MetricCollector(self.config_signal)
        self.builder_signal = SnapshotBuilder(
            "dual_signal",
            "dual_cfg",
            self.engine_signal,
            self.collector_signal,
            self.controller_signal,
        )

        self.engine_signal.register_tick_callback(
            build_tick_callback(
                self.controller_signal,
                self.clock_signal,
                self.engine_signal,
                self.collector_signal,
            )
        )

        # ── Build Roundabout Simulation ─────────────────────────────────
        self.clock_roundabout = Clock(time_step=time_step)
        self.engine_roundabout = SimulationEngine(
            self.clock_roundabout, duration=duration, config=self.config_roundabout
        )
        self.controller_roundabout = create_controller(
            self.config_roundabout, self.engine_roundabout.network
        )

        # CRITICAL: Assign controller to engine so engine.step() calls
        # controller.update() BEFORE vehicle physics (zero-latency yield response)
        self.engine_roundabout.controller = self.controller_roundabout

        self.collector_roundabout = MetricCollector(self.config_roundabout)
        self.builder_roundabout = SnapshotBuilder(
            "dual_roundabout",
            "dual_cfg",
            self.engine_roundabout,
            self.collector_roundabout,
            self.controller_roundabout,
        )

        self.engine_roundabout.register_tick_callback(
            build_tick_callback(
                self.controller_roundabout,
                self.clock_roundabout,
                self.engine_roundabout,
                self.collector_roundabout,
            )
        )

        # ── Thread synchronization primitives for lockstep execution ────
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self.engine_signal.status == SimulationStatus.RUNNING:
                return
            if self.engine_signal.status == SimulationStatus.PAUSED:
                self.resume()
                return

            self.engine_signal._transition_to(SimulationStatus.RUNNING)
            self.engine_roundabout._transition_to(SimulationStatus.RUNNING)
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if (
                    self.engine_signal.status != SimulationStatus.RUNNING
                    or self.engine_roundabout.status != SimulationStatus.RUNNING
                ):
                    break

            start_time = time.time()

            try:
                self.step()
            except Exception:
                logger.exception("Error in dual simulation step")
                with self._lock:
                    self.engine_signal._transition_to(SimulationStatus.ERROR)
                    self.engine_roundabout._transition_to(SimulationStatus.ERROR)
                break

            with self._lock:
                sig_status: Any = self.engine_signal.status
                round_status: Any = self.engine_roundabout.status
                if (
                    sig_status == SimulationStatus.COMPLETED
                    and round_status == SimulationStatus.COMPLETED
                ):
                    break

            elapsed = time.time() - start_time
            sleep_time = max(0.0, self.clock_signal.time_step - elapsed)
            time.sleep(sleep_time)

    def resume(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            if self.engine_signal.status != SimulationStatus.PAUSED:
                return
            thread_to_join = self._thread

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

        with self._lock:
            if self.engine_signal.status == SimulationStatus.PAUSED:
                self.engine_signal._transition_to(SimulationStatus.RUNNING)
                self.engine_roundabout._transition_to(SimulationStatus.RUNNING)
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()

    def pause(self) -> None:
        with self._lock:
            if self.engine_signal.status == SimulationStatus.RUNNING:
                self._stop_event.set()
                self.engine_signal._transition_to(SimulationStatus.PAUSED)
                self.engine_roundabout._transition_to(SimulationStatus.PAUSED)

    def stop(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            self._stop_event.set()
            thread_to_join = self._thread
            self.engine_signal._transition_to(SimulationStatus.COMPLETED)
            self.engine_roundabout._transition_to(SimulationStatus.COMPLETED)

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

    def reset(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            self._stop_event.set()
            thread_to_join = self._thread

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

        with self._lock:
            self.engine_signal.reset()
            self.engine_roundabout.reset()

    def step(self) -> None:
        self.engine_signal.step()
        self.engine_roundabout.step()

    def get_status(self) -> str:
        if (
            self.engine_signal.status == SimulationStatus.ERROR
            or self.engine_roundabout.status == SimulationStatus.ERROR
        ):
            return "error"
        if (
            self.engine_signal.status == SimulationStatus.COMPLETED
            and self.engine_roundabout.status == SimulationStatus.COMPLETED
        ):
            return "completed"
        return str(self.engine_signal.status.value).lower()

    def get_dual_snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self.clock_signal.get_tick_count(),
            "elapsed": round(self.clock_signal.get_elapsed_time(), 2),
            "signal": self.builder_signal.build(),
            "roundabout": self.builder_roundabout.build(),
        }
