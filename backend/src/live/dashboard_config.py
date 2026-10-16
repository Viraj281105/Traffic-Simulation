"""What a dashboard scenario means: the live default configuration and the
compilation of the dashboard's flat scenario payload into an engine config.

The single definition of a dashboard scenario: the live session
(/api/simulation/config) runs it, the reliability check
(/api/v1/study/validate/monte-carlo with ``scenario``) repeats it over other
seeds, and a suite batch (/api/suites/{id}/batch) sweeps its demand. Invalid
payloads raise HTTPException(400) — the message is part of the dashboard's
contract, so it is decided here once rather than translated at each caller.
"""

import copy
import random
from typing import Any, Dict

import jsonschema
from fastapi import HTTPException

from src.api.validation import valid_scenario_or_400
from src.core.config_validation import semantic_config_errors
from src.core.limits import demand_vehicle_limit
from src.core.scenario import JUNCTION_STRATEGY, compile_live_comparison, parse_scenario
from src.core.schema import CONFIG_SCHEMA

DEFAULT_CONFIG: Dict[str, Any] = {
    "simulation": {
        "timeStep": 0.1,
        "duration": 600,
        "warmupTime": 30.0,
    },
    "geometry": {
        "intersectionType": "fixed_time_signal",
        "intersectionCenter": {"x": 0.0, "y": 0.0},
        "boundingRadius": 15.0,
    },
    "controller": {
        # Matches the canonical greenTime=30/yellowTime=4/allRedTime=2
        # defaults (docs/architecture/06-scenario-configuration-contract.md,
        # ControllerSection, CONFIG_SCHEMA) — see
        # FixedTimeSignalController.__init__ for the same reconciliation.
        "straightRightDuration": 30.0,
        "leftDuration": 5.0,
        "yellowDuration": 4.0,
        "allRedDuration": 2.0,
        # Matches ControllerSection.phaseSequence's default_factory exactly.
        # Without this, FixedTimeSignalController falls back to its original
        # one-direction-at-a-time cycle (see _build_phase_sequence) — the
        # live dashboard previously got that less realistic default even
        # though the paired NS/EW-green model was already the documented,
        # schema-declared default everywhere else. This does not change
        # FixedTimeSignalController itself, and existing tests that
        # construct it directly with no phaseSequence key still see the
        # original one-direction-at-a-time fallback unchanged.
        "phaseSequence": [
            "ns_green",
            "ns_yellow",
            "all_red",
            "ew_green",
            "ew_yellow",
            "all_red",
        ],
    },
    "vehicleGeneration": {
        "stopSpeedThreshold": 0.1,
        "waitSpeedThreshold": 0.5,
        # Acceleration, braking and desired speed are the engine defaults
        # (IDM a = 2.0, b = 3.0 m/s^2; desired speed from roads.speedLimit),
        # i.e. the same vehicles as the calibrated capacity study.
    },
}

VALID_INTERSECTION_TYPES: list[str] = CONFIG_SCHEMA["properties"]["geometry"][
    "properties"
]["intersectionType"]["enum"]


def generate_random_seed() -> int:
    """The single authority for auto-generating a live-dashboard random
    seed, used wherever the dashboard needs a fresh seed because the
    current one isn't user-defined (initial config, restarting a
    completed live/dual run, resetting the dual comparison).

    Was previously duplicated at each call site as a bare
    `random.randint(1, 10000000)`, pulling from the shared global `random`
    module. Matches the fix already applied in VehicleSpawner and
    DualSimulationOrchestrator for the same reason: never touch the
    shared global module's state for a simulation-scoped seed — use a
    private, independently OS-seeded Random instance instead.
    """
    return random.Random().randint(1, 10_000_000)


def live_config_errors(config: Dict[str, Any]) -> list[str]:
    """Schema bounds plus cross-field rules for a compiled live-dashboard config.

    The live config carries one shape the versioned schema does not accept —
    a per-direction ``lanesPerApproach`` object (see §2.4 of the scenario
    contract) — so each direction's lane count is checked as if it were the
    scalar the schema expects. Everything else is validated as-is.
    """
    lanes = config.get("roads", {}).get("lanesPerApproach")
    per_direction = lanes if isinstance(lanes, dict) else {"all": lanes}
    for direction, count in per_direction.items():
        candidate = copy.deepcopy(config)
        candidate["roads"]["lanesPerApproach"] = count
        try:
            jsonschema.validate(instance=candidate, schema=CONFIG_SCHEMA)
        except jsonschema.ValidationError as err:
            where = "/".join(str(p) for p in err.absolute_path)
            if where == "roads/lanesPerApproach" and direction != "all":
                where = f"lanes{direction.capitalize()}"
            return [f"{where}: {err.message}" if where else err.message]
    # warmupTime is not a dashboard input — it is always DEFAULT_CONFIG's
    # 30 s — so a short dashboard run must not be rejected for it (the same
    # "explicit warmupTime only" rule the versioned API applies).
    user_supplied = copy.deepcopy(config)
    user_supplied.get("simulation", {}).pop("warmupTime", None)
    return semantic_config_errors(user_supplied)


def compile_dashboard_scenario(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Live config for a scenario document (V1.4).

    The live comparison runs the scenario's signal (fixed-time or adaptive,
    as its junction type or ``signalControl`` says) beside its roundabout,
    so the document must be valid for both. Its own seed is used, so the
    live run reproduces exactly what the document describes.
    """
    raw = payload["scenario"]
    document, errors = parse_scenario(raw)
    if document is None:
        raise HTTPException(
            status_code=400, detail=f"Invalid scenario: {'; '.join(errors)}"
        )
    requested = payload.get("signalControl")
    if requested is not None and requested not in ("fixed_time", "adaptive"):
        raise HTTPException(
            status_code=400,
            detail="Invalid configuration: signalControl must be 'fixed_time' "
            "or 'adaptive'",
        )
    signal_strategy = requested or (
        "adaptive"
        if JUNCTION_STRATEGY[document.junction.type] == "adaptive"
        else "fixed_time"
    )
    intersection_type = payload.get("intersectionType", "fixed_time_signal")
    valid_scenario_or_400(raw, [signal_strategy, "roundabout"])
    return compile_live_comparison(document, signal_strategy, intersection_type)


def compile_dashboard_config(payload: Dict[str, Any], seed_val: int) -> Dict[str, Any]:
    """Compiles the dashboard's flat scenario payload into an engine config.

    Raises HTTPException(400) for a payload the simulator would reject.

    V1.4: a payload carrying ``scenario`` (a scenario document) is compiled
    from that document instead (see compile_dashboard_scenario).
    """
    if isinstance(payload.get("scenario"), dict):
        return compile_dashboard_scenario(payload)
    # Duration must fall within the same bounds the versioned API enforces
    # via SimulationSection.duration (ge=1, le=3600 — see config_models.py
    # and config.schema.json). This endpoint builds its config by hand
    # rather than through Pydantic/CONFIG_SCHEMA, so neither a malformed
    # value (-> uncaught ValueError -> raw 500) nor an out-of-range one was
    # previously rejected. Resolve and validate it up front, before it
    # (and any other malformed numeric field below) can reach that point.
    raw_duration = payload.get("duration", DEFAULT_CONFIG["simulation"]["duration"])
    try:
        duration_val = float(raw_duration)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid duration {raw_duration!r}: must be a number.",
        ) from exc
    if not (1.0 <= duration_val <= 3600.0):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid duration {duration_val}: must be between 1 and 3600 seconds."
            ),
        )

    # Optional asymmetric corridor greens (see FixedTimeSignalController.
    # _green_duration_for): when present, the NS or EW corridor uses its own
    # green instead of greenDuration/straightRightDuration. Same bounds as
    # ControllerSection.nsGreenDuration/ewGreenDuration (gt=5, le=120).
    # Omitted or null keeps the single shared green exactly as before.
    corridor_greens: Dict[str, float] = {}
    for corridor_key in ("nsGreenDuration", "ewGreenDuration"):
        raw_green = payload.get(corridor_key)
        if raw_green is None:
            continue
        try:
            green_val = float(raw_green)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid {corridor_key} {raw_green!r}: must be a number.",
            ) from exc
        if not (5.0 < green_val <= 120.0):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid {corridor_key} {green_val}: must be greater than 5 "
                    "and at most 120 seconds."
                ),
            )
        corridor_greens[corridor_key] = green_val

    # Compile the config dictionary based on user payload. The remaining
    # numeric fields are coerced directly from the raw payload (same as
    # duration above); wrap them the same way the versioned simulation
    # route does so malformed input is a 400, not a raw 500 that leaks past
    # the client-facing error envelope.
    try:
        config: Dict[str, Any] = {
            "simulation": {
                "timeStep": DEFAULT_CONFIG["simulation"]["timeStep"],
                "duration": duration_val,
                "warmupTime": DEFAULT_CONFIG["simulation"]["warmupTime"],
                "randomSeed": seed_val,
            },
            "geometry": {
                "intersectionType": payload.get(
                    "intersectionType", "fixed_time_signal"
                ),
                "intersectionCenter": {"x": 0.0, "y": 0.0},
                "boundingRadius": float(payload.get("intersectionSize", 15.0)),
            },
            "roads": {
                "approachLength": 200.0,
                "laneWidth": float(payload.get("laneWidth", 3.5)),
                "lanesPerApproach": {
                    "north": int(payload.get("lanesNorth", 2)),
                    "south": int(payload.get("lanesSouth", 2)),
                    "east": int(payload.get("lanesEast", 2)),
                    "west": int(payload.get("lanesWest", 2)),
                },
            },
            "traffic": {
                "arrivalRate": float(payload.get("arrivalRate", 0.5)),
                "arrivalDistribution": "poisson",
                # Sized to the scenario so the default 200-vehicle cap can
                # never silently truncate the demand asked for.
                "totalVehicles": demand_vehicle_limit(
                    float(payload.get("arrivalRate", 0.5)), duration_val
                ),
            },
            "controller": (
                {
                    "straightRightDuration": float(
                        payload.get(
                            "greenDuration",
                            DEFAULT_CONFIG["controller"]["straightRightDuration"],
                        )
                    ),
                    "leftDuration": float(
                        payload.get(
                            "leftDuration",
                            DEFAULT_CONFIG["controller"]["leftDuration"],
                        )
                    ),
                    "yellowDuration": float(
                        payload.get(
                            "yellowDuration",
                            DEFAULT_CONFIG["controller"]["yellowDuration"],
                        )
                    ),
                    "allRedDuration": float(
                        payload.get(
                            "allRedDuration",
                            DEFAULT_CONFIG["controller"]["allRedDuration"],
                        )
                    ),
                    # See DEFAULT_CONFIG's phaseSequence comment: without
                    # this, a dashboard config update would silently drop
                    # back to the less realistic one-direction-at-a-time
                    # cycle even though the initial (pre-update) dashboard
                    # state used the paired NS/EW-green model. The compact
                    # dashboard form has no phaseSequence field of its own
                    # to override this with.
                    "phaseSequence": copy.deepcopy(
                        DEFAULT_CONFIG["controller"]["phaseSequence"]
                    ),
                    **corridor_greens,
                }
                if payload.get("intersectionType", "fixed_time_signal")
                == "fixed_time_signal"
                else {
                    "innerRadius": 10.0,
                    "outerRadius": 20.0,
                    "circulatingLanes": 1,
                    "criticalGap": float(payload.get("criticalGap", 4.0)),
                    "followUpTime": float(payload.get("followUpTime", 2.5)),
                    "entrySpeed": 5.0,
                    "circulatingSpeed": 8.0,
                }
            ),
            "roundaboutController": {
                "criticalGap": float(payload.get("criticalGap", 4.0)),
                "followUpTime": float(payload.get("followUpTime", 2.5)),
            },
            "vehicleGeneration": copy.deepcopy(DEFAULT_CONFIG["vehicleGeneration"]),
        }
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid configuration: {exc}"
        ) from exc

    # V1.1: an optional vehicle-class mix ({class: share}). Omitted or null
    # keeps the calibrated single-car population exactly as before. Shares
    # are passed through as given; the schema bounds them and
    # semantic_config_errors checks they sum to 1, below.
    vehicle_mix = payload.get("vehicleMix")
    if vehicle_mix is not None:
        if not isinstance(vehicle_mix, dict):
            raise HTTPException(
                status_code=400,
                detail="Invalid configuration: vehicleMix must be an object of "
                "vehicle class shares",
            )
        config["vehicleGeneration"]["vehicleMix"] = dict(vehicle_mix)
    # V1.2: lane changing on multi-lane approaches (default on).
    lane_changing = payload.get("laneChanging")
    if lane_changing is not None:
        if not isinstance(lane_changing, bool):
            raise HTTPException(
                status_code=400,
                detail="Invalid configuration: laneChanging must be true or false",
            )
        config["roads"]["laneChange"] = {"enabled": lane_changing}
    # V1.3: how the signal times its greens. Omitted (or "fixed_time") keeps
    # the fixed timetable and the exact V1.2 config; "adaptive" runs the same
    # phase plan with greens ended by detected demand, tuned by the optional
    # "adaptive" object. Bounds and cross-field rules are checked below by
    # semantic_config_errors, like every other field.
    signal_control = payload.get("signalControl")
    adaptive_settings = payload.get("adaptive")
    if signal_control not in (None, "fixed_time", "adaptive"):
        raise HTTPException(
            status_code=400,
            detail="Invalid configuration: signalControl must be 'fixed_time' "
            "or 'adaptive'",
        )
    if adaptive_settings is not None and not isinstance(adaptive_settings, dict):
        raise HTTPException(
            status_code=400,
            detail="Invalid configuration: adaptive must be an object of "
            "adaptive signal settings",
        )
    if (
        signal_control == "adaptive"
        and config["geometry"]["intersectionType"] == "fixed_time_signal"
    ):
        config["controller"]["signalControl"] = "adaptive"
        if adaptive_settings:
            config["controller"]["adaptive"] = dict(adaptive_settings)

    # The coercions above only reject values that are not numbers at all.
    # Range checks were missing entirely, so lanesNorth=0 or -1, a negative or
    # NaN arrivalRate, a negative yellow/all-red or a negative critical gap
    # were all accepted and quietly simulated as something meaningless. Hold
    # the compiled config to the same schema bounds as the versioned API.
    errors = live_config_errors(config)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration: {'; '.join(errors)}",
        )
    return config
