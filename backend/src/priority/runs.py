"""Building, running and measuring one single-junction simulation with priority.

A run is the existing :class:`~src.engine.simulation_engine.SimulationEngine`
with the junction's own signal controller wrapped in a
:class:`~src.priority.controller.PriorityController` (installed as
``engine.controller``). It is stepped synchronously, no thread, so a run is a
pure function of its inputs and seed.

Delay definition used throughout: **time lost** = time in the network minus the
time the distance driven would take at the vehicle's desired speed (minus bus
dwell, which is scheduled, not lost). It is measured for every vehicle that
entered the network, exited or not, so two runs of one seed are comparable even
when pre-emption changes how many vehicles have left by the end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.controllers.factory import create_controller
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.clock import Clock
from src.core.enums import SimulationStatus, VehicleState
from src.core.speed_thresholds import resolve_speed_threshold
from src.engine.simulation_engine import SimulationEngine
from src.priority.controller import PriorityController
from src.priority.models import (
    EmergencySpec,
    PreemptionConfig,
    ScenarioSpec,
    TransitLineSpec,
    TransitPriorityConfig,
    YieldConfig,
)
from src.priority.vehicles import EmergencyVehicle, TransitVehicle, distance_driven
from src.vehicles.speed_profile import resolve_speed_limit
from src.vehicles.vehicle import Vehicle

PAIRED_PLAN: Tuple[str, ...] = (
    "ns_green",
    "ns_yellow",
    "all_red",
    "ew_green",
    "ew_yellow",
    "all_red",
)


def build_config(
    spec: ScenarioSpec, seed: int, with_buses: bool = False
) -> Dict[str, Any]:
    """The scenario configuration of a run. Background traffic is the engine's
    own (Poisson arrivals, equal split, 20/60/20 turns); only the seed varies."""
    config: Dict[str, Any] = {
        "simulation": {
            "duration": spec.duration_s,
            "timeStep": spec.time_step_s,
            "randomSeed": seed,
        },
        "geometry": {"intersectionType": "fixed_time_signal"},
        "roads": {
            "approachLength": spec.approach_length_m,
            "laneWidth": 3.5,
            "lanesPerApproach": spec.lanes_per_approach,
            "speedLimit": spec.speed_limit_mps,
        },
        "traffic": {
            "arrivalRate": spec.arrival_rate,
            "arrivalDistribution": "poisson",
            "totalVehicles": 100_000,
            "directionalSplit": {
                "north": 0.25,
                "south": 0.25,
                "east": 0.25,
                "west": 0.25,
            },
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
        },
        "controller": {
            "straightRightDuration": spec.green_s,
            "yellowDuration": spec.yellow_s,
            "allRedDuration": spec.all_red_s,
            "phaseSequence": list(PAIRED_PLAN),
        },
    }
    if with_buses:
        # Gives the junction the layout for 12 m buses (a mixed population);
        # these background buses are ordinary traffic, not scheduled lines.
        config["vehicleGeneration"] = {"vehicleMix": {"car": 0.97, "bus": 0.03}}
    return config


@dataclass
class PriorityRun:
    spec: ScenarioSpec
    seed: int
    config: Dict[str, Any]
    engine: SimulationEngine
    controller: PriorityController
    preemption: Optional[PreemptionConfig]
    transit: Optional[TransitPriorityConfig]


def build_run(
    spec: ScenarioSpec,
    seed: int,
    *,
    emergencies: Sequence[EmergencySpec] = (),
    transit_lines: Sequence[TransitLineSpec] = (),
    preemption: Optional[PreemptionConfig] = None,
    yielding: Optional[YieldConfig] = None,
    transit: Optional[TransitPriorityConfig] = None,
    schedule_padding_s: float = 10.0,
) -> PriorityRun:
    spec.validate()
    for item in emergencies:
        from src.priority.vehicles import EMERGENCY_KINDS

        item.validate(dict(EMERGENCY_KINDS), spec.duration_s)
    for line in transit_lines:
        line.validate(spec.duration_s)
    if preemption is not None:
        preemption.validate()
    if yielding is not None:
        yielding.validate()
    if transit is not None:
        transit.validate()

    config = build_config(spec, seed, with_buses=bool(transit_lines))
    clock = Clock(time_step=spec.time_step_s)
    engine = SimulationEngine(clock, duration=spec.duration_s, config=config)
    base = create_controller(config, engine.network)
    if not isinstance(base, FixedTimeSignalController):
        raise ValueError("priority needs a fixed-time signal plan")
    controller = PriorityController(
        base,
        engine,
        speed_limit=resolve_speed_limit(config),
        emergencies=emergencies,
        transit_lines=transit_lines,
        preemption=preemption,
        yielding=yielding,
        transit=transit,
        wait_speed_threshold=resolve_speed_threshold(config, "waitSpeedThreshold", 0.5),
        schedule_padding_s=schedule_padding_s,
    )
    engine.controller = controller
    engine.register_tick_callback(controller.after_physics)
    return PriorityRun(spec, seed, config, engine, controller, preemption, transit)


def execute(run: PriorityRun) -> Dict[str, Any]:
    """Step the run to its end and return its measurements."""
    engine = run.engine
    while engine.status != SimulationStatus.COMPLETED:
        engine.step()
    run.controller.finalize()
    return collect_metrics(run)


# -- measurement ---------------------------------------------------------


def _dwell_so_far(vehicle: Vehicle, now: float) -> float:
    if isinstance(vehicle, TransitVehicle):
        if vehicle.dwell_state == "dwelling":
            return now - vehicle.dwell_started
        return vehicle.dwell_total
    return 0.0


def time_lost(vehicle: Vehicle, now: float) -> float:
    """Seconds lost to the network since the vehicle entered it."""
    end = vehicle.exit_time if vehicle.exit_time is not None else now
    elapsed = end - vehicle.spawn_time
    free_flow = distance_driven(vehicle) / vehicle.desired_speed
    return max(0.0, elapsed - free_flow - _dwell_so_far(vehicle, now))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _emergency_record(ev: EmergencyVehicle, now: float) -> Dict[str, Any]:
    completed = ev.exit_time is not None
    end = ev.exit_time if ev.exit_time is not None else now
    travel = end - ev.spawn_time
    stop_line = (
        None
        if ev.stop_line_time is None
        else round(ev.stop_line_time - ev.spawn_time, 3)
    )
    junction = (
        round(end - ev.stop_line_time, 3) if ev.stop_line_time is not None else None
    )
    return {
        "id": ev.vehicle_id,
        "kind": ev.kind,
        "approach": ev.approach,
        "turn": ev.turn_name,
        "scheduledTime": ev.scheduled_time,
        "placedTime": round(ev.spawn_time, 3),
        "completed": completed,
        "travelTime": round(travel, 3),
        "freeFlowTime": round(ev.free_flow_time, 3),
        "delay": round(travel - ev.free_flow_time, 3),
        "waitTime": round(ev.wait_time, 3),
        "timeToStopLine": stop_line,
        "junctionTime": junction,
    }


def collect_metrics(run: PriorityRun) -> Dict[str, Any]:
    engine, ctrl, spec = run.engine, run.controller, run.spec
    pool = engine.pool
    now = float(engine.clock.get_elapsed_time())
    everyone: List[Vehicle] = list(pool.exited_vehicles) + list(pool.active_vehicles)
    ids = [v.vehicle_id for v in everyone]
    spawner = engine.spawner
    spawned = (spawner.spawned_count if spawner is not None else 0) + len(ctrl.injected)

    emergencies = [v for v in everyone if isinstance(v, EmergencyVehicle)]
    unplaced_emergencies = len(ctrl.emergencies) - len(emergencies)
    others = [v for v in everyone if not isinstance(v, EmergencyVehicle)]
    lost = {v.vehicle_id: time_lost(v, now) for v in others}
    exited_others = [v for v in others if v.state == VehicleState.EXITED]

    metrics: Dict[str, Any] = {
        "seed": run.seed,
        "durationSeconds": spec.duration_s,
        "emergency": [_emergency_record(ev, now) for ev in emergencies],
        "emergencyNotPlaced": unplaced_emergencies,
        "vehicles": {
            "spawned": spawned,
            "exited": len(pool.exited_vehicles),
            "active": len(pool.active_vehicles),
            "duplicateIds": len(ids) - len(set(ids)),
            "conserved": len(everyone) == spawned and len(ids) == len(set(ids)),
        },
        "collisions": pool.collision_count,
        "nonEmergency": {
            "count": len(others),
            "exited": len(exited_others),
            "meanTimeLost": round(_mean(list(lost.values())), 4),
            "meanTimeLostExited": round(
                _mean([lost[v.vehicle_id] for v in exited_others]), 4
            ),
        },
        "signal": ctrl.summary(),
        "phaseLogEntries": len(ctrl.phase_log),
    }
    metrics["transit"] = _transit_metrics(run, everyone, lost, now)
    return metrics


def _occupancy(vehicle: Vehicle, spec: ScenarioSpec) -> float:
    if isinstance(vehicle, TransitVehicle) or vehicle.vehicle_type == "bus":
        return spec.bus_occupancy
    return spec.car_occupancy


def _transit_metrics(
    run: PriorityRun, everyone: List[Vehicle], lost: Dict[str, float], now: float
) -> Dict[str, Any]:
    spec = run.spec
    buses = [v for v in everyone if isinstance(v, TransitVehicle)]
    non_ev = [v for v in everyone if not isinstance(v, EmergencyVehicle)]
    trips: List[Dict[str, Any]] = []
    for bus in buses:
        crossed = bus.stop_line_time is not None
        trips.append(
            {
                "id": bus.vehicle_id,
                "line": bus.line_id,
                "trip": bus.trip_index,
                "placedTime": round(bus.spawn_time, 3),
                "crossedStopLine": crossed,
                "scheduleLateness": (
                    round(bus.stop_line_time - bus.planned_arrival, 3)
                    if bus.stop_line_time is not None
                    else None
                ),
                "timeLost": round(lost[bus.vehicle_id], 3),
                "dwell": round(_dwell_so_far(bus, now), 3),
                "extensionSeconds": round(bus.priority_extension_s, 3),
                "earlyGreen": bus.priority_early_green,
            }
        )
    people = sum(_occupancy(v, spec) for v in non_ev)
    person_delay = sum(_occupancy(v, spec) * lost[v.vehicle_id] for v in non_ev)
    line_ids = {v.vehicle_id for v in buses}
    rest = [v for v in non_ev if v.vehicle_id not in line_ids]
    crossed_lateness = [
        t["scheduleLateness"] for t in trips if t["scheduleLateness"] is not None
    ]
    return {
        "trips": trips,
        "busesCrossed": len(crossed_lateness),
        "meanScheduleLateness": round(_mean(crossed_lateness), 4),
        "meanBusTimeLost": round(_mean([lost[v.vehicle_id] for v in buses]), 4),
        "people": round(people, 2),
        "personDelayTotal": round(person_delay, 2),
        "personDelayPerPerson": round(person_delay / people, 4) if people else 0.0,
        "vehicleDelayMean": round(_mean([lost[v.vehicle_id] for v in non_ev]), 4),
        "otherVehicleDelayMean": round(_mean([lost[v.vehicle_id] for v in rest]), 4),
    }
