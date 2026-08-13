import threading
import time
from typing import Any, Callable, Dict, List, Optional

from src.core.clock import Clock
from src.core.enums import SimulationStatus
from src.roads.network import RoadNetwork
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.pool import VehiclePool
from src.vehicles.spawner import VehicleSpawner


class SimulationEngine:
    """Orchestrates the entire discrete-time traffic simulation lifecycle and execution loop."""

    def __init__(
        self, clock: Clock, duration: float, config: Optional[Dict[str, Any]] = None
    ) -> None:
        if duration <= 0:
            raise ValueError("duration must be greater than zero")

        self.clock: Clock = clock
        self.duration: float = duration
        self.config: Dict[str, Any] = config if config is not None else {}

        self.status: SimulationStatus = SimulationStatus.INITIALIZED

        self._tick_callbacks: List[Callable[[], None]] = []
        self._status_callbacks: List[Callable[[SimulationStatus], None]] = []

        # Setup subsystems if config is provided
        self.network: RoadNetwork = RoadNetwork()
        self.pool: VehiclePool = VehiclePool()
        self.spawner: Optional[VehicleSpawner] = None
        self.idm: Optional[IntelligentDriverModel] = None

        if self.config:
            # Setup default network
            road_cfg = self.config.get("roads", {})
            self.network.setup_default_intersection(
                approach_length=road_cfg.get("approachLength", 200.0),
                lane_width=road_cfg.get("laneWidth", 3.5),
                lanes_per_approach=road_cfg.get("lanesPerApproach", 2),
            )
            self.spawner = VehicleSpawner(self.config, self.network)

            veh_gen = self.config.get("vehicleGeneration", {})
            self.idm = IntelligentDriverModel(
                max_acceleration=veh_gen.get("maxAcceleration", 2.0),
                comfort_deceleration=veh_gen.get("comfortDeceleration", 3.0),
                desired_time_headway=veh_gen.get("desiredTimeHeadway", 1.5),
                minimum_gap=veh_gen.get("minimumGap", 2.0),
                idm_delta=veh_gen.get("idmDelta", 4.0),
            )

        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()

    def register_tick_callback(self, callback: Callable[[], None]) -> None:
        self._tick_callbacks.append(callback)

    def register_status_callback(
        self, callback: Callable[[SimulationStatus], None]
    ) -> None:
        self._status_callbacks.append(callback)

    def _transition_to(self, new_status: SimulationStatus) -> None:
        self.status = new_status
        for cb in self._status_callbacks:
            cb(new_status)

    def start(self) -> None:
        with self._lock:
            if self.status != SimulationStatus.INITIALIZED:
                raise RuntimeError("Cannot start simulation")

            self._transition_to(SimulationStatus.RUNNING)
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                status = self.status
                if status != SimulationStatus.RUNNING:
                    break

            start_time = time.time()

            try:
                self.step()
            except Exception:
                with self._lock:
                    self._transition_to(SimulationStatus.ERROR)
                break

            with self._lock:
                status = self.status
                if status == SimulationStatus.COMPLETED:
                    break

            elapsed = time.time() - start_time
            sleep_time = max(0.0, self.clock.time_step - elapsed)
            time.sleep(sleep_time)

    def pause(self) -> None:
        with self._lock:
            if self.status == SimulationStatus.RUNNING:
                self._transition_to(SimulationStatus.PAUSED)
                self._stop_event.set()

    def resume(self) -> None:
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            if self.status != SimulationStatus.PAUSED:
                return
            thread_to_join = self._thread

        if (
            thread_to_join is not None
            and thread_to_join is not threading.current_thread()
        ):
            thread_to_join.join()

        with self._lock:
            if self.status == SimulationStatus.PAUSED:
                self._transition_to(SimulationStatus.RUNNING)
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self.status in (SimulationStatus.RUNNING, SimulationStatus.PAUSED):
                self._stop_event.set()
                self._transition_to(SimulationStatus.COMPLETED)

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
            self.clock.reset()
            if self.spawner is not None:
                self.spawner.reset()
            self.pool.active_vehicles.clear()
            self.pool.exited_vehicles.clear()
            self._transition_to(SimulationStatus.INITIALIZED)

    def step(self) -> None:
        if self.status == SimulationStatus.COMPLETED:
            raise RuntimeError("Cannot step simulation in 'completed' status")

        self.clock.tick()

        # Generate new arrivals
        if self.spawner is not None:
            new_vehs = self.spawner.step(self.clock.time_step)
            for v in new_vehs:
                self.pool.add_vehicle(v)

        # Update spatial states of all vehicles
        self.pool.update(self.clock.time_step, self)

        # Run registered tick callbacks
        for cb in self._tick_callbacks:
            cb()

        # Stop conditions check
        if self.clock.get_elapsed_time() >= self.duration:
            self._transition_to(SimulationStatus.COMPLETED)
