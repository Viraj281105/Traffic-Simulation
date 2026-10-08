"""Portable scenario documents (V1.4).

A scenario document describes *the junction and its traffic* — approaches,
lanes, lane use, demand, turning, vehicle mix, timing and roundabout design,
duration, warm-up and seed — independently of how the junction is controlled.
It is compiled into an ordinary engine configuration (the scenario
configuration contract, ``shared/schemas/config.schema.json``) once per
control strategy:

    compile_scenario(document, "fixed_time")   -> engine config
    compile_scenario(document, "adaptive")     -> engine config
    compile_scenario(document, "roundabout")   -> engine config

Every strategy is compiled from the same document, so geometry, lanes,
traffic, vehicle mix, duration and seed are identical by construction and only
the control section differs — the property a controlled comparison needs.
The comparison paths before V1.4 rebuilt each strategy's config by hand (the
dual orchestrator replaced the roundabout's radii and speeds with fixed
values whatever the scenario said).

The document is JSON, versioned (``format`` / ``version``), validated
strictly (unknown fields are rejected, not ignored), and never normalised: a
vehicle mix that totals 95 % is reported, not rescaled.

V1.5 (real-world junctions) adds optional fields only: an approach may be
``null`` (a three-arm junction), and may give its ``bearing``, its own
``laneWidth``, U-turn lane arrows and a ``uturn`` turning share. A document
that sets none of them is unchanged — it compiles to the same configuration
and keeps the same fingerprint — so the format stays version 1. A server
older than V1.5 rejects the new fields by name rather than ignoring them.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.core.config_models import DEFAULT_PHASE_SEQUENCE
from src.core.enums import Direction, TurnIntent
from src.core.limits import demand_vehicle_limit

SCENARIO_FORMAT = "urbanflow-scenario"
SCENARIO_VERSION = 1

Strategy = Literal["fixed_time", "adaptive", "roundabout"]
STRATEGIES: Tuple[str, ...] = ("fixed_time", "adaptive", "roundabout")
STRATEGY_TITLES = {
    "fixed_time": "Fixed-time signal",
    "adaptive": "Adaptive signal",
    "roundabout": "Roundabout",
}
# The junction type a document names, as a strategy.
JUNCTION_STRATEGY = {
    "fixed_time_signal": "fixed_time",
    "adaptive_signal": "adaptive",
    "roundabout": "roundabout",
}

Movement = Literal["uturn", "left", "straight", "right"]

# V1.5 fields left out of a document's fingerprint while unset, so every
# earlier document keeps the fingerprint it always had.
_V15_OPTIONAL_APPROACH_FIELDS = ("bearing", "laneWidth")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Turning(_Strict):
    left: float = Field(..., ge=0, le=1)
    straight: float = Field(..., ge=0, le=1)
    right: float = Field(..., ge=0, le=1)
    # V1.5: the share making a U-turn (omitted: none).
    uturn: Optional[float] = Field(None, ge=0, le=1)


class Mix(_Strict):
    car: float = Field(0.0, ge=0, le=1)
    suv: float = Field(0.0, ge=0, le=1)
    bus: float = Field(0.0, ge=0, le=1)
    truck: float = Field(0.0, ge=0, le=1)
    motorcycle: float = Field(0.0, ge=0, le=1)


class ApproachSpec(_Strict):
    """One arm: its incoming lanes and the traffic arriving on it."""

    lanes: int = Field(..., ge=1, le=4)
    length: float = Field(200.0, gt=50, le=1000)
    # Movements each lane allows at a SIGNAL (the lane arrows), lane 1 (next
    # to the centre line) first. Omitted: the default lane-use policy.
    laneUse: Optional[List[List[Movement]]] = None
    # The same for the ROUNDABOUT's entry lane markings. They are part of
    # each junction's design, not of the road: where a two-lane ring meets a
    # one-lane road, only the outer ring lane leads into it, so a left turn
    # into that road must start from the right-hand entry lane — the
    # opposite of what signal arrows require. Omitted: derived from the ring
    # assignment (roads/lane_config.default_roundabout_lane_use).
    roundaboutLaneUse: Optional[List[List[Movement]]] = None
    vehiclesPerHour: float = Field(..., ge=0, le=7200)
    turning: Turning = Field(
        default_factory=lambda: Turning(left=0.2, straight=0.6, right=0.2, uturn=None)
    )
    # This approach's own vehicle mix; omitted: the scenario's.
    vehicleMix: Optional[Mix] = None
    # V1.5: compass bearing (degrees clockwise from north) of the arm from
    # the junction outwards, and the arm's own lane width. Omitted: the
    # slot's own bearing and roads.laneWidth (roads/junction_geometry.py).
    bearing: Optional[float] = Field(None, ge=0, lt=360)
    laneWidth: Optional[float] = Field(None, gt=2.5, le=5.0)


class Approaches(_Strict):
    # V1.5: null for a slot with no arm (a three-arm junction).
    north: Optional[ApproachSpec]
    south: Optional[ApproachSpec]
    east: Optional[ApproachSpec]
    west: Optional[ApproachSpec]

    def present(self) -> Dict[Direction, ApproachSpec]:
        """The arms that exist, in compass-enum order."""
        found: Dict[Direction, ApproachSpec] = {}
        for d in Direction:
            arm = getattr(self, d.value)
            if arm is not None:
                found[d] = arm
        return found


class RoadSpec(_Strict):
    laneWidth: float = Field(3.5, gt=2.5, le=5.0)
    speedLimit: float = Field(13.89, gt=0, le=30.0)
    laneChanging: bool = True


class VehicleSpec(_Strict):
    # Omitted: the calibrated passenger-car population.
    mix: Optional[Mix] = None
    # Per-class parameter overrides (vehicleGeneration.vehicleTypes).
    types: Optional[Dict[str, Dict[str, Any]]] = None


class AdaptiveSpec(_Strict):
    minGreen: float = Field(10.0, ge=5, le=60)
    maxGreen: float = Field(50.0, ge=10, le=180)
    extensionStep: float = Field(2.5, ge=0.5, le=10)
    detectionDistance: float = Field(30.0, ge=5, le=200)
    demandThreshold: int = Field(1, ge=1, le=20)


class SignalSpec(_Strict):
    greenTime: float = Field(30.0, gt=5, le=120)
    nsGreenTime: Optional[float] = Field(None, gt=5, le=120)
    ewGreenTime: Optional[float] = Field(None, gt=5, le=120)
    yellowTime: float = Field(4.0, gt=2, le=8)
    allRedTime: float = Field(2.0, ge=0, le=5)
    adaptive: AdaptiveSpec = Field(
        default_factory=lambda: AdaptiveSpec.model_validate({})
    )


class RoundaboutSpec(_Strict):
    # Omitted: as many as the widest approach.
    circulatingLanes: Optional[int] = Field(None, ge=1, le=3)
    innerRadius: float = Field(10.0, gt=5, le=50)
    outerRadius: float = Field(20.0, gt=5, le=80)
    criticalGap: float = Field(4.0, gt=0, le=10)
    followUpTime: float = Field(2.5, gt=0, le=10)
    entrySpeed: float = Field(5.0, gt=0, le=15)
    circulatingSpeed: float = Field(8.0, gt=0, le=15)


class SimulationSpec(_Strict):
    duration: float = Field(300.0, ge=1, le=3600)
    warmup: float = Field(30.0, ge=0)
    seed: int = Field(42, ge=0)
    arrivalPattern: Literal["poisson", "uniform"] = "poisson"
    timeStep: float = Field(0.1, gt=0, le=1.0)


class JunctionSpec(_Strict):
    type: Literal["fixed_time_signal", "adaptive_signal", "roundabout"]


class ScenarioDocument(_Strict):
    format: Literal["urbanflow-scenario"] = "urbanflow-scenario"
    version: Literal[1] = 1
    name: str = Field("Custom scenario", max_length=120)
    description: str = Field("", max_length=2000)
    # The preset it started from, if any — informational only.
    preset: Optional[str] = Field(None, max_length=64)
    junction: JunctionSpec
    approaches: Approaches
    roads: RoadSpec = Field(default_factory=lambda: RoadSpec.model_validate({}))
    vehicles: VehicleSpec = Field(
        default_factory=lambda: VehicleSpec.model_validate({})
    )
    signal: SignalSpec = Field(default_factory=lambda: SignalSpec.model_validate({}))
    roundabout: RoundaboutSpec = Field(
        default_factory=lambda: RoundaboutSpec.model_validate({})
    )
    simulation: SimulationSpec = Field(
        default_factory=lambda: SimulationSpec.model_validate({})
    )
    # Research use: extra engine sections merged into every compiled config
    # (vehicleGeneration IDM parameters, roads.laneChange, metrics), validated
    # with the rest of the compiled config.
    advanced: Optional[Dict[str, Any]] = None


def _mix_dict(mix: Optional[Mix]) -> Optional[Dict[str, float]]:
    if mix is None:
        return None
    return {k: v for k, v in mix.model_dump().items() if v > 0} or mix.model_dump()


def scenario_fingerprint(document: ScenarioDocument) -> str:
    """Short, stable hash of what a document simulates (name and description
    excluded), so two runs can be shown to share a scenario."""
    body = document.model_dump(exclude={"name", "description", "preset"})
    for arm in body["approaches"].values():
        if arm is None:
            continue
        for key in _V15_OPTIONAL_APPROACH_FIELDS:
            if arm.get(key) is None:
                arm.pop(key, None)
        if arm["turning"].get("uturn") is None:
            arm["turning"].pop("uturn", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def total_vehicles_per_hour(document: ScenarioDocument) -> float:
    return float(
        sum(arm.vehiclesPerHour for arm in document.approaches.present().values())
    )


def _turning_dict(turning: Turning) -> Dict[str, float]:
    found = turning.model_dump()
    if found.get("uturn") is None:
        found.pop("uturn", None)
    return found


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


def compile_scenario(document: ScenarioDocument, strategy: str) -> Dict[str, Any]:
    """The engine configuration that runs *document* under *strategy*.

    Raises ValueError for an unknown strategy or a document with no demand
    at all. Everything else is left to the engine contract's validation
    (``validate_scenario``), which reports it rather than adjusting it.
    """
    if strategy not in STRATEGIES:
        raise ValueError(
            f"Unknown strategy {strategy!r}; expected one of {list(STRATEGIES)}"
        )
    total_vph = total_vehicles_per_hour(document)
    if not total_vph > 0:
        raise ValueError(
            "No traffic: every approach has 0 vehicles per hour. Give at least "
            "one approach some demand"
        )
    arms = document.approaches.present()
    if len(arms) < 3:
        raise ValueError(_arm_count_message(arms))
    sim = document.simulation
    rate = total_vph / 3600.0

    road_items: List[Dict[str, Any]] = []
    traffic_items: List[Dict[str, Any]] = []
    for d, arm in arms.items():
        item: Dict[str, Any] = {
            "direction": d.value,
            "lanes": arm.lanes,
            "length": arm.length,
        }
        lane_use = arm.roundaboutLaneUse if strategy == "roundabout" else arm.laneUse
        if lane_use is not None:
            item["laneUse"] = [list(lane) for lane in lane_use]
        if arm.bearing is not None:
            item["bearing"] = arm.bearing
        if arm.laneWidth is not None:
            item["laneWidth"] = arm.laneWidth
        road_items.append(item)
        t_item: Dict[str, Any] = {
            "direction": d.value,
            "turnProbabilities": _turning_dict(arm.turning),
        }
        if arm.vehicleMix is not None:
            t_item["vehicleMix"] = _mix_dict(arm.vehicleMix)
        traffic_items.append(t_item)

    config: Dict[str, Any] = {
        "simulation": {
            "duration": sim.duration,
            "timeStep": sim.timeStep,
            "warmupTime": sim.warmup,
            "randomSeed": sim.seed,
        },
        "geometry": {
            "intersectionType": (
                "roundabout" if strategy == "roundabout" else "fixed_time_signal"
            ),
            "intersectionCenter": {"x": 0.0, "y": 0.0},
        },
        "roads": {
            "approachLength": max(arm.length for arm in arms.values()),
            "laneWidth": document.roads.laneWidth,
            "speedLimit": document.roads.speedLimit,
            "lanesPerApproach": max(arm.lanes for arm in arms.values()),
            "approaches": road_items,
            "laneChange": {"enabled": document.roads.laneChanging},
        },
        "traffic": {
            "arrivalRate": rate,
            "arrivalDistribution": sim.arrivalPattern,
            "totalVehicles": demand_vehicle_limit(rate, sim.duration),
            "directionalSplit": {
                d.value: (arms[d].vehiclesPerHour / total_vph if d in arms else 0.0)
                for d in Direction
            },
            # The scenario-wide share is unused (every approach sets its own)
            # but kept valid for readers that expect it.
            "turnProbabilities": {"left": 0.2, "straight": 0.6, "right": 0.2},
            "approaches": traffic_items,
        },
        "vehicleGeneration": {},
    }
    if len(arms) < len(Direction):
        # V1.5: only the slots that have an arm.
        config["geometry"]["arms"] = [d.value for d in arms]
    mix = _mix_dict(document.vehicles.mix)
    if mix is not None:
        config["vehicleGeneration"]["vehicleMix"] = mix
    if document.vehicles.types:
        config["vehicleGeneration"]["vehicleTypes"] = copy.deepcopy(
            document.vehicles.types
        )

    if strategy == "roundabout":
        rb = document.roundabout
        config["controller"] = {
            "innerRadius": rb.innerRadius,
            "outerRadius": rb.outerRadius,
            "criticalGap": rb.criticalGap,
            "followUpTime": rb.followUpTime,
            "entrySpeed": rb.entrySpeed,
            "circulatingSpeed": rb.circulatingSpeed,
        }
        if rb.circulatingLanes is not None:
            config["geometry"]["circulatingLanes"] = rb.circulatingLanes
    else:
        sig = document.signal
        ctrl: Dict[str, Any] = {
            "straightRightDuration": sig.greenTime,
            "yellowDuration": sig.yellowTime,
            "allRedDuration": sig.allRedTime,
            "phaseSequence": list(DEFAULT_PHASE_SEQUENCE),
        }
        if sig.nsGreenTime is not None:
            ctrl["nsGreenDuration"] = sig.nsGreenTime
        if sig.ewGreenTime is not None:
            ctrl["ewGreenDuration"] = sig.ewGreenTime
        if strategy == "adaptive":
            ctrl["signalControl"] = "adaptive"
            ctrl["adaptive"] = sig.adaptive.model_dump()
        config["controller"] = ctrl

    if document.advanced:
        _deep_merge(config, document.advanced)

    config["scenario"] = {
        "format": SCENARIO_FORMAT,
        "version": SCENARIO_VERSION,
        "name": document.name,
        "fingerprint": scenario_fingerprint(document),
        "strategy": strategy,
    }
    return config


def compile_live_comparison(
    document: ScenarioDocument, signal_strategy: str, intersection_type: str
) -> Dict[str, Any]:
    """The live dashboard config for a scenario's side-by-side comparison.

    The live comparison (DualSimulationOrchestrator) derives its signal and
    roundabout engines from one config, so that config carries the signal
    strategy's own controller section plus the roundabout's design under
    ``roundaboutController`` (the key the dashboard already uses) and the
    ring lane count in ``geometry``. Both engines therefore run exactly
    what compile_scenario gives for their strategy.
    """
    if signal_strategy not in ("fixed_time", "adaptive"):
        raise ValueError("signal_strategy must be 'fixed_time' or 'adaptive'")
    config = compile_scenario(document, signal_strategy)
    rb = compile_scenario(document, "roundabout")
    config["roundaboutController"] = dict(rb["controller"])
    if "circulatingLanes" in rb["geometry"]:
        config["geometry"]["circulatingLanes"] = rb["geometry"]["circulatingLanes"]
    config["geometry"]["intersectionType"] = intersection_type
    if intersection_type == "roundabout":
        # A single roundabout view: the ring's settings drive it; the signal
        # timing stays alongside (a roundabout ignores it), but not the
        # adaptive switch, which is only valid on a signal.
        signal = {
            k: v
            for k, v in config["controller"].items()
            if k not in ("signalControl", "adaptive")
        }
        config["controller"] = {**signal, **rb["controller"]}
    config["scenario"]["strategy"] = f"{signal_strategy}+roundabout"
    return config


def parse_scenario(payload: Any) -> Tuple[Optional[ScenarioDocument], List[str]]:
    """Parse a document, returning it or every structural error found."""
    if not isinstance(payload, dict):
        return None, ["A scenario must be a JSON object"]
    body = payload.get("scenario", payload) if "junction" not in payload else payload
    if not isinstance(body, dict):
        return None, ["A scenario must be a JSON object"]
    fmt = body.get("format", SCENARIO_FORMAT)
    if fmt != SCENARIO_FORMAT:
        return None, [
            f"Not an UrbanFlow scenario: format is {fmt!r}, expected "
            f"{SCENARIO_FORMAT!r}"
        ]
    version = body.get("version", SCENARIO_VERSION)
    if version != SCENARIO_VERSION:
        return None, [
            f"Scenario version {version!r} is not supported by this server, "
            f"which reads version {SCENARIO_VERSION}"
        ]
    try:
        return ScenarioDocument.model_validate(body), []
    except ValidationError as err:
        return None, [_pydantic_message(dict(e)) for e in err.errors()]


def _pydantic_message(error: Dict[str, Any]) -> str:
    where = ".".join(str(part) for part in error.get("loc", ()))
    msg = str(error.get("msg", "invalid value"))
    if error.get("type") == "extra_forbidden":
        msg = "is not a scenario field (check the spelling)"
    return f"{where}: {msg}" if where else msg


def _arm_count_message(arms: Dict[Direction, ApproachSpec]) -> str:
    names = ", ".join(d.value for d in arms) or "none"
    return (
        f"approaches: {len(arms)} arm(s) given ({names}); a junction needs 3 or 4 "
        "arms. Two arms are a bend in one road, not a junction: give a three-arm "
        "(T or Y) or a four-arm junction"
    )


def _scenario_level_checks(document: ScenarioDocument) -> List[str]:
    errors: List[str] = []
    if len(document.approaches.present()) < 3:
        return [_arm_count_message(document.approaches.present())]
    if document.simulation.warmup >= document.simulation.duration:
        errors.append(
            f"simulation.warmup ({document.simulation.warmup:g} s) must be shorter "
            f"than simulation.duration ({document.simulation.duration:g} s), or "
            "nothing would be measured"
        )
    if not total_vehicles_per_hour(document) > 0:
        errors.append(
            "No traffic: every approach has 0 vehicles per hour. Give at least one "
            "approach some demand"
        )
    elif total_vehicles_per_hour(document) / 3600.0 > 10.0:
        errors.append(
            f"Total demand {total_vehicles_per_hour(document):,.0f} veh/h is above "
            "the 36,000 veh/h the engine accepts"
        )
    return errors


def scenario_warnings(document: ScenarioDocument, strategies: List[str]) -> List[str]:
    """Things a valid scenario's results should be read in the light of."""
    warnings: List[str] = []
    arms = document.approaches.present()
    lanes = {arm.lanes for arm in arms.values()}
    if lanes != {1}:
        warnings.append(
            "More than one lane on some approach: results are exploratory; the "
            "calibrated comparison is one lane per approach."
        )
    mixes = [document.vehicles.mix] + [arm.vehicleMix for arm in arms.values()]
    if any(
        m is not None and (m.suv + m.bus + m.truck + m.motorcycle) > 0 for m in mixes
    ):
        warnings.append(
            "Mixed vehicle classes: class parameters are model inputs, not "
            "calibrated values; results are exploratory."
        )
    if len(arms) < len(Direction) or any(
        arm.bearing is not None or arm.laneWidth is not None for arm in arms.values()
    ):
        warnings.append(
            "Real-world geometry (a three-arm junction, skewed arms or "
            "per-approach lane widths): the geometry is modelled, but the "
            "calibrated comparison is the four-arm right-angled junction, so "
            "results are exploratory."
        )
    if any((arm.turning.uturn or 0) > 0 for arm in arms.values()):
        warnings.append(
            "U-turns: their paths and yielding are modelled but not calibrated "
            "against observed U-turn behaviour; results are exploratory."
        )
    for d, arm in arms.items():
        per_lane = arm.vehiclesPerHour / arm.lanes
        if per_lane > 1800:
            warnings.append(
                f"The {d.value} approach offers {per_lane:,.0f} veh/h per lane, "
                "above what a lane can discharge (about 1,800 veh/h); expect queues "
                "to grow for the whole run."
            )
    return warnings


def validate_scenario(
    payload: Any, strategies: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Validate a document for every strategy it will be run with.

    Returns {valid, errors, warnings, strategies, byStrategy, fingerprint,
    scenario}. An error that holds for every strategy is listed once; one
    specific to a strategy is prefixed with its name, so "this cannot be
    compared as a roundabout because ..." is visible as such.
    """
    # Imported here: config_validation imports the controllers.
    import jsonschema

    from src.core.config_validation import semantic_config_errors
    from src.core.schema import CONFIG_SCHEMA

    document, errors = parse_scenario(payload)
    if document is None:
        return {
            "valid": False,
            "errors": errors,
            "warnings": [],
            "strategies": strategies or [],
            "byStrategy": {},
        }
    wanted = list(strategies or [JUNCTION_STRATEGY[document.junction.type]])
    unknown = [s for s in wanted if s not in STRATEGIES]
    if unknown:
        return {
            "valid": False,
            "errors": [
                f"Unknown strategies {unknown}; expected some of {list(STRATEGIES)}"
            ],
            "warnings": [],
            "strategies": wanted,
            "byStrategy": {},
        }
    errors = _scenario_level_checks(document)
    by_strategy: Dict[str, List[str]] = {}
    if not errors:
        for strategy in wanted:
            config = compile_scenario(document, strategy)
            found: List[str] = []
            try:
                jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)
            except jsonschema.ValidationError as err:
                where = "/".join(str(p) for p in err.absolute_path)
                found.append(f"{where}: {err.message}" if where else err.message)
            found.extend(semantic_config_errors(config))
            by_strategy[strategy] = found
        shared = [
            e
            for e in by_strategy[wanted[0]]
            if all(e in by_strategy[s] for s in wanted)
        ]
        errors.extend(shared)
        for strategy in wanted:
            errors.extend(
                f"{STRATEGY_TITLES[strategy]}: {e}"
                for e in by_strategy[strategy]
                if e not in shared
            )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": scenario_warnings(document, wanted) if not errors else [],
        "strategies": wanted,
        "byStrategy": by_strategy,
        "design": (
            {s: resolved_design(compile_scenario(document, s)) for s in wanted}
            if not errors
            else {}
        ),
        "fingerprint": scenario_fingerprint(document),
        "scenario": document.model_dump(),
    }


def resolved_design(config: Dict[str, Any]) -> Dict[str, Any]:
    """What the engine will build for a compiled config: each approach's lane
    use (lane 1 first) and, for a roundabout, its ring lane count and the
    ring lane and exit lane every permitted movement uses."""
    from src.core.lane_validation import circulating_lanes_of, resolved_lane_use
    from src.roads.junction_geometry import (
        present_arms,
        resolve_junction_geometry,
        signal_stop_distances,
    )
    from src.roads.lane_config import (
        TURN_ORDER,
        ring_exit_lane,
        ring_lane_for,
        target_direction,
    )
    from src.roads.network import (
        ROUNDABOUT_ENTRY_SETBACK,
        SIGNAL_STOP_LINE_SETBACK,
        lane_counts,
        resolve_lanes_per_approach,
    )
    from src.vehicles.vehicle_types import design_vehicle_allowance

    use = resolved_lane_use(config) or {}
    present = present_arms(config)
    counts = {
        Direction(k): (v if Direction(k) in present else 0)
        for k, v in lane_counts(
            resolve_lanes_per_approach(config.get("roads") or {})
        ).items()
    }
    # V1.5: the geometry the network lays out — each arm's bearing, lane
    # width and the distance from the centre to its stop / give-way line.
    geometry = resolve_junction_geometry(config)
    is_roundabout = (config.get("geometry") or {}).get(
        "intersectionType"
    ) == "roundabout"
    if is_roundabout:
        outer = float((config.get("controller") or {}).get("outerRadius", 20.0))
        stops = {d: outer + ROUNDABOUT_ENTRY_SETBACK for d in geometry.arms}
    else:
        stops = signal_stop_distances(
            geometry,
            SIGNAL_STOP_LINE_SETBACK + max(0.0, design_vehicle_allowance(config)),
        )
    design: Dict[str, Any] = {
        "geometry": {
            d.value: {
                "bearing": arm.bearing,
                "lanes": arm.lanes,
                "laneWidth": arm.lane_width,
                "length": arm.length,
                "stopLineDistance": round(stops[d], 3),
            }
            for d, arm in geometry.arms.items()
        },
        "laneUse": {
            d.value: [
                sorted((t.value for t in lane), key=lambda n: TURN_ORDER[TurnIntent(n)])
                for lane in lanes
            ]
            for d, lanes in use.items()
        },
    }
    if (config.get("geometry") or {}).get("intersectionType") == "roundabout":
        rings = circulating_lanes_of(config, counts)
        assignment: Dict[str, List[Dict[str, Any]]] = {}
        for d, lanes in use.items():
            rows: List[Dict[str, Any]] = []
            for i, turns in enumerate(lanes):
                for turn in sorted(turns, key=TURN_ORDER.__getitem__):
                    exit_arm = target_direction(d, turn)
                    ring = ring_lane_for(i, counts[d], rings, counts[exit_arm], turn)
                    rows.append(
                        {
                            "lane": i + 1,
                            "movement": turn.value,
                            "exitTo": exit_arm.value,
                            "ringLane": None if ring is None else ring + 1,
                            "exitLane": None
                            if ring is None
                            else ring_exit_lane(ring, rings, counts[exit_arm]) + 1,
                        }
                    )
            assignment[d.value] = rows
        design["circulatingLanes"] = rings
        design["ringAssignment"] = assignment
    return design


__all__ = [
    "JUNCTION_STRATEGY",
    "SCENARIO_FORMAT",
    "SCENARIO_VERSION",
    "STRATEGIES",
    "STRATEGY_TITLES",
    "ScenarioDocument",
    "compile_live_comparison",
    "compile_scenario",
    "parse_scenario",
    "scenario_fingerprint",
    "scenario_warnings",
    "total_vehicles_per_hour",
    "validate_scenario",
]
