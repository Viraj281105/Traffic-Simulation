"""Cross-field rules for the V1.4 lane, approach and roundabout configuration.

Every rule here says *why* a configuration cannot be simulated and what would
be valid instead. Nothing is adjusted: a configuration either passes as given
or is rejected with these messages (see config_validation, which collects
them with the rest of the contract's cross-field rules).
"""

from __future__ import annotations

import math
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    TypeGuard,
    Union,
)

from src.core.enums import Direction, TurnIntent
from src.roads.junction_geometry import (
    DESIGN_TURNING_RADIUS,
    DESIGN_VEHICLE_NAMES,
    configured_arms,
    geometry_errors,
    present_arms,
    resolve_junction_geometry,
    roundabout_geometry_errors,
    uturn_lanes_needed,
    uturn_radius,
)
from src.roads.lane_config import (
    CIRCULATING_LANE_SIDE_CLEARANCE,
    CORE_TURNS,
    MAX_CIRCULATING_LANES,
    MIN_CIRCULATING_LANE_WIDTH,
    TURN_ORDER,
    default_policy_turns,
    default_roundabout_lane_use,
    default_signal_lane_use,
    designated_ring_lanes,
    parse_turns,
    ring_lane_for,
    target_direction,
)
from src.roads.network import lane_counts, resolve_lanes_per_approach

# A roundabout entry may have at most this many more lanes than the ring. The
# surplus lanes merge onto the innermost ring lane, one vehicle at a time; a
# wider approach would need a flare or an upstream lane drop, which the model
# does not have.
MAX_MERGING_ENTRY_LANES: int = 1

_PLURAL = {
    "car": "cars",
    "suv": "SUVs",
    "bus": "buses",
    "truck": "trucks",
    "motorcycle": "motorcycles",
}

# Same tolerance as the contract's other sum-to-one rules.
_SUM_TOLERANCE: float = 0.01

_NAMES = {d.value: d for d in Direction}


def _section(config: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = config.get(key)
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> TypeGuard[Union[int, float]]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _turn_list(turns: FrozenSet[TurnIntent]) -> str:
    return "/".join(t.value for t in sorted(turns, key=TURN_ORDER.__getitem__))


def _demanded_turns(
    traffic: Mapping[str, Any], direction: str
) -> Optional[FrozenSet[TurnIntent]]:
    """Movements that will actually arrive on an approach: those with a
    positive turning share. None when turning is unset (the spawner then
    draws random shares, all positive)."""
    probabilities: Any = None
    for item in traffic.get("approaches") or []:
        if (
            isinstance(item, Mapping)
            and str(item.get("direction", "")).lower() == direction
            and isinstance(item.get("turnProbabilities"), Mapping)
        ):
            probabilities = item["turnProbabilities"]
    if probabilities is None:
        probabilities = traffic.get("turnProbabilities")
    if not isinstance(probabilities, Mapping):
        return None
    return frozenset(
        t
        for t in TurnIntent
        if _number(probabilities.get(t.value)) and float(probabilities[t.value]) > 0
    )


def _approach_items(
    section: Mapping[str, Any], path: str, errors: List[str]
) -> Dict[str, Mapping[str, Any]]:
    """{direction: item} for an approaches[] list, reporting duplicates."""
    found: Dict[str, Mapping[str, Any]] = {}
    for item in section.get("approaches") or []:
        if not isinstance(item, Mapping):
            continue
        direction = str(item.get("direction", "")).lower()
        if direction not in _NAMES:
            continue  # the schema reports unknown directions
        if direction in found:
            errors.append(
                f"{path} lists the {direction} approach more than once; give "
                "each approach one entry"
            )
            continue
        found[direction] = item
    return found


def resolved_lane_use(
    config: Mapping[str, Any],
) -> Optional[Dict[Direction, List[FrozenSet[TurnIntent]]]]:
    """Lane use per approach as the engine will apply it, or None if the
    roads section cannot be read (the schema reports that)."""
    roads = _section(config, "roads")
    try:
        counts = {
            _NAMES[k]: v
            for k, v in lane_counts(resolve_lanes_per_approach(roads)).items()
        }
    except (TypeError, ValueError):
        return None
    present = present_arms(config)
    for d in Direction:
        if d not in present:
            counts[d] = 0
    is_roundabout = _section(config, "geometry").get("intersectionType") == "roundabout"
    rings = circulating_lanes_of(config, counts)
    result: Dict[Direction, List[FrozenSet[TurnIntent]]] = {}
    configured: Dict[Direction, List[FrozenSet[TurnIntent]]] = {}
    for item in roads.get("approaches") or []:
        if not isinstance(item, Mapping) or not isinstance(item.get("laneUse"), list):
            continue
        direction = _NAMES.get(str(item.get("direction", "")).lower())
        lanes = [parse_turns(x) for x in item["laneUse"]]
        if direction is not None and all(lane is not None for lane in lanes):
            configured[direction] = [lane for lane in lanes if lane is not None]
    for d in present:
        if d in configured:
            result[d] = configured[d]
        elif is_roundabout:
            result[d] = default_roundabout_lane_use(d, counts, rings)
        elif len(present) < len(Direction):
            result[d] = default_signal_lane_use(d, counts)
        else:
            result[d] = [default_policy_turns(i, counts[d]) for i in range(counts[d])]
    return result


def circulating_lanes_of(
    config: Mapping[str, Any], counts: Mapping[Direction, int]
) -> int:
    value = _section(config, "geometry").get("circulatingLanes")
    if _number(value):
        return int(value)
    widest = max(counts.values()) if counts else 1
    return min(widest, MAX_CIRCULATING_LANES)


def lane_configuration_errors(config: Mapping[str, Any]) -> List[str]:
    """Every V1.4 lane / approach / roundabout rule the config violates."""
    errors: List[str] = []
    roads = _section(config, "roads")
    traffic = _section(config, "traffic")
    geometry = _section(config, "geometry")
    is_roundabout = geometry.get("intersectionType") == "roundabout"

    road_items = _approach_items(roads, "roads.approaches", errors)
    traffic_items = _approach_items(traffic, "traffic.approaches", errors)

    try:
        counts = {
            _NAMES[k]: v
            for k, v in lane_counts(resolve_lanes_per_approach(roads)).items()
        }
    except (TypeError, ValueError):
        return errors

    # -- arms that exist (V1.5) ----------------------------------------------
    present = present_arms(config)
    errors.extend(_arm_errors(config, present, road_items, traffic_items))
    if len(present) < 3:
        return errors
    for d in Direction:
        if d not in present:
            counts[d] = 0
    road_items = {k: v for k, v in road_items.items() if _NAMES[k] in present}
    traffic_items = {k: v for k, v in traffic_items.items() if _NAMES[k] in present}

    # -- per-approach turning ------------------------------------------------
    for direction, item in traffic_items.items():
        probabilities = item.get("turnProbabilities")
        if isinstance(probabilities, Mapping):
            # A U-turn share (V1.5) is optional and counts as 0 when unset.
            parts = [probabilities.get(t.value) for t in CORE_TURNS] + [
                probabilities.get(TurnIntent.UTURN.value, 0)
            ]
            if all(_number(p) for p in parts):
                total = sum(float(p) for p in parts if p is not None)
                if abs(total - 1.0) > _SUM_TOLERANCE:
                    errors.append(
                        f"traffic.approaches[{direction}].turnProbabilities must "
                        f"sum to 1.0 (±{_SUM_TOLERANCE}); got {total:g}"
                    )

    # -- approach length -----------------------------------------------------
    for direction, item in road_items.items():
        length = item.get("length")
        if length is not None and _number(length) and not 50 < float(length) <= 1000:
            errors.append(
                f"roads.approaches[{direction}].length ({float(length):g} m) must "
                "be more than 50 m and at most 1000 m"
            )

    # -- lane use shape --------------------------------------------------------
    configured: Dict[Direction, List[FrozenSet[TurnIntent]]] = {}
    for direction, item in road_items.items():
        raw = item.get("laneUse")
        if raw is None:
            continue
        d = _NAMES[direction]
        label = f"roads.approaches[{direction}].laneUse"
        if not isinstance(raw, list):
            errors.append(f"{label} must be a list with one entry per lane")
            continue
        if len(raw) != counts[d]:
            errors.append(
                f"{label} describes {len(raw)} lane(s) but the {direction} approach "
                f"has {counts[d]}; give exactly one movement list per lane, lane 1 "
                "next to the centre line first"
            )
            continue
        lanes: List[FrozenSet[TurnIntent]] = []
        for i, entry in enumerate(raw):
            turns = parse_turns(entry)
            if turns is None:
                errors.append(
                    f"{label} lane {i + 1}: movements must be some of "
                    "'uturn', 'left', 'straight', 'right'"
                )
                break
            if not turns:
                errors.append(
                    f"{label} lane {i + 1} allows no movement; every lane must "
                    "allow at least one of U-turn, left, straight, right"
                )
                break
            lanes.append(turns)
        else:
            configured[d] = lanes

    # -- roundabout geometry -------------------------------------------------
    rings = circulating_lanes_of(config, counts)
    raw_rings = geometry.get("circulatingLanes")
    if raw_rings is not None:
        if not _number(raw_rings) or float(raw_rings) != int(raw_rings):
            errors.append("geometry.circulatingLanes must be a whole number")
            return errors
        if int(raw_rings) < 1:
            errors.append("geometry.circulatingLanes must be at least 1")
            return errors
        if int(raw_rings) > MAX_CIRCULATING_LANES:
            errors.append(
                f"{int(raw_rings)} circulating lanes are not supported yet: with "
                "more than two, a middle lane would carry traffic past an exit "
                "that the inner lane leaves by, and that weave has not been "
                "validated as collision-free. Use 1 or 2 circulating lanes "
                "(approaches may still have 3 lanes; two of them then merge "
                "onto the inner ring lane)"
            )
            return errors
        legacy = _section(config, "controller").get("circulatingLanes")
        if _number(legacy) and int(legacy) != int(raw_rings):
            errors.append(
                f"controller.circulatingLanes ({int(legacy)}) disagrees with "
                f"geometry.circulatingLanes ({int(raw_rings)}); "
                "controller.circulatingLanes is the reserved V1.0 field and has "
                "no effect — remove it and set geometry.circulatingLanes"
            )
    if is_roundabout:
        errors.extend(_ring_errors(config, counts, rings))

    # -- geometry (V1.5) ------------------------------------------------------
    geometry_problems = _junction_geometry_errors(config, is_roundabout)
    if geometry_problems:
        errors.extend(geometry_problems)
        return errors

    # -- movements every lane can serve, and every demand served ------------
    use = resolved_lane_use(config)
    if use is None:
        return errors
    for d in present:
        lanes = configured.get(d, use[d])
        road_item = road_items.get(d.value)
        if (
            road_item is not None
            and road_item.get("laneUse") is not None
            and d not in configured
        ):
            continue  # its lane use is malformed, already reported above
        demanded = _demanded_turns(traffic, d.value)
        needed = demanded if demanded is not None else frozenset(CORE_TURNS)
        if demanded is None and len(present) < len(Direction):
            # Random turning (no shares set) at a three-arm junction would
            # send traffic into the missing arm.
            errors.append(
                f"The {d.value} approach has no turning shares, so drivers would "
                "be sent every way, including into the missing arm; set its "
                "turning shares"
            )
            continue
        movement_problems = _movement_errors(d, lanes, needed, counts, present)
        if movement_problems:
            errors.extend(movement_problems)
            continue
        offered = frozenset().union(*lanes) if lanes else frozenset()
        missing = needed - offered
        if missing:
            errors.append(
                f"The {d.value} approach has traffic turning "
                f"{_turn_list(frozenset(missing))} but no lane allows it; allow "
                "it in a lane or set its turning share to 0"
            )
        if is_roundabout:
            errors.extend(_roundabout_lane_errors(d, lanes, counts, rings))
        else:
            if d in configured:
                errors.extend(_signal_lane_errors(d, lanes, counts, configured))
            if any(TurnIntent.UTURN in lane for lane in lanes):
                errors.extend(_signal_uturn_errors(config, d, lanes))
    return errors


def _arm_errors(
    config: Mapping[str, Any],
    present: Sequence[Direction],
    road_items: Mapping[str, Mapping[str, Any]],
    traffic_items: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    """V1.5: which arms exist, and that nothing describes one that does not."""
    from src.roads.junction_geometry import arm_count_errors

    if configured_arms(config) is None:
        return []
    errors = arm_count_errors(present)
    if errors:
        return errors
    missing = [d for d in Direction if d not in present]
    names = ", ".join(d.value for d in missing)
    for direction in road_items:
        if _NAMES[direction] in missing:
            errors.append(
                f"roads.approaches describes the {direction} approach, but "
                f"geometry.arms has no {direction} arm; remove that entry or add "
                f"{direction} to geometry.arms"
            )
    for direction in traffic_items:
        if _NAMES[direction] in missing:
            errors.append(
                f"traffic.approaches describes the {direction} approach, but "
                f"geometry.arms has no {direction} arm; remove that entry or add "
                f"{direction} to geometry.arms"
            )
    traffic = _section(config, "traffic")
    split = traffic.get("directionalSplit")
    if not isinstance(split, Mapping):
        errors.append(
            f"A junction without a {names} arm needs traffic.directionalSplit with "
            f"a share of 0 for {names}: without one the spawner would invent "
            "random shares for all four slots"
        )
    else:
        for d in missing:
            share = split.get(d.value)
            if _number(share) and float(share) > 0:
                errors.append(
                    f"traffic.directionalSplit gives the {d.value} slot "
                    f"{float(share):g} of the traffic, but there is no {d.value} "
                    "arm; set it to 0"
                )
    return errors


def _junction_geometry_errors(
    config: Mapping[str, Any], is_roundabout: bool
) -> List[str]:
    """V1.5: bearings, arm separation, storage and roundabout mouths."""
    from src.roads.network import SIGNAL_STOP_LINE_SETBACK
    from src.vehicles.vehicle_types import design_vehicle_allowance

    try:
        geometry = resolve_junction_geometry(config)
    except (TypeError, ValueError):
        return []
    errors = geometry_errors(
        geometry,
        is_roundabout,
        SIGNAL_STOP_LINE_SETBACK + max(0.0, design_vehicle_allowance(config)),
    )
    if not errors and is_roundabout:
        outer = _section(config, "controller").get("outerRadius", 20.0)
        if _number(outer):
            errors.extend(roundabout_geometry_errors(geometry, float(outer)))
    return errors


def _movement_errors(
    d: Direction,
    lanes: List[FrozenSet[TurnIntent]],
    needed: FrozenSet[TurnIntent],
    counts: Mapping[Direction, int],
    present: Sequence[Direction],
) -> List[str]:
    """V1.5: no lane may carry, and no traffic may make, a movement into a slot
    without an arm; every lane needs a movement it can make."""
    errors: List[str] = []
    if len(present) == len(Direction):
        return errors
    possible = frozenset(t for t in TurnIntent if counts[target_direction(d, t)] > 0)
    possible_names = _turn_list(frozenset(possible & frozenset(CORE_TURNS)))
    for i, turns in enumerate(lanes):
        impossible = turns - possible
        if impossible:
            exits = ", ".join(
                target_direction(d, t).value
                for t in sorted(impossible, key=TURN_ORDER.__getitem__)
            )
            errors.append(
                f"The {d.value} approach's lane {i + 1} allows "
                f"{_turn_list(frozenset(impossible))}, which would leave by the "
                f"{exits} slot, where this junction has no arm. From {d.value} a "
                f"vehicle can go {possible_names} (or U-turn where allowed)"
            )
        elif not turns:
            errors.append(
                f"The {d.value} approach's lane {i + 1} has no movement under the "
                "default lane use once movements into the missing arm are removed; "
                f"give the {d.value} approach explicit lane arrows (it can go "
                f"{possible_names})"
            )
    wanted = needed - possible
    if wanted:
        errors.append(
            f"The {d.value} approach has traffic turning "
            f"{_turn_list(frozenset(wanted))}, into a slot this junction has no "
            f"arm in; set that turning share to 0 (from {d.value} a vehicle can "
            f"go {possible_names})"
        )
    if not (possible & frozenset(CORE_TURNS)):
        errors.append(
            f"The {d.value} approach has no legal movement: no other arm can be "
            "reached from it"
        )
    return errors


def _approach_classes(config: Mapping[str, Any], d: Direction) -> List[str]:
    """Vehicle classes that arrive on an approach."""
    from src.vehicles.vehicle_types import approach_vehicle_mixes, configured_mix

    mix = approach_vehicle_mixes(config).get(d.value) or configured_mix(config)
    if not mix:
        return ["car"]
    return [k for k, v in mix.items() if v > 0]


def _signal_uturn_errors(
    config: Mapping[str, Any], d: Direction, lanes: List[FrozenSet[TurnIntent]]
) -> List[str]:
    """V1.5: a signalised U-turn starts from lane 1 only, and the half circle
    it drives must be one every vehicle class on the approach can turn."""
    errors: List[str] = []
    uturn_lanes = [i for i, lane in enumerate(lanes) if TurnIntent.UTURN in lane]
    if uturn_lanes != [0]:
        errors.append(
            f"The {d.value} approach allows a U-turn from lane(s) "
            f"{', '.join(str(i + 1) for i in uturn_lanes)}: a U-turn crosses every "
            "lane to its left, so at a signal it may only start from lane 1 (next "
            "to the centre line). Allow it in lane 1 only"
        )
        return errors
    try:
        arm = resolve_junction_geometry(config).arms[d]
    except (KeyError, TypeError, ValueError):
        return errors
    radius = uturn_radius(arm, 0)
    classes = _approach_classes(config, d)
    need_cls = max(classes, key=lambda c: DESIGN_TURNING_RADIUS.get(c, 6.4))
    need = DESIGN_TURNING_RADIUS.get(need_cls, 6.4)
    if radius + 1e-9 < need:
        lanes_needed = uturn_lanes_needed(need, arm.lane_width)
        width_needed = 2.0 * need / arm.lanes
        options = [f"at least {lanes_needed} lanes each way at {arm.lane_width:g} m"]
        if width_needed <= 5.0:
            options.append(f"lanes at least {width_needed:.2f} m wide")
        errors.append(
            f"A U-turn from the {d.value} approach is not physically possible here: "
            f"turning from lane 1 into the kerb-side exit lane gives a "
            f"{radius:.2f} m radius ({arm.lanes} lane(s) of {arm.lane_width:g} m "
            f"each way), but a {DESIGN_VEHICLE_NAMES.get(need_cls, need_cls)} "
            f"needs at least {need:g} m (design turning radius). Valid options: "
            + ", or ".join(options)
            + (
                f"; a vehicle mix without {_PLURAL.get(need_cls, need_cls)}"
                if need > min(DESIGN_TURNING_RADIUS.values())
                else ""
            )
            + "; or no U-turn at this signal (a roundabout serves U-turns on its "
            "ring)"
        )
    return errors


def _ring_errors(
    config: Mapping[str, Any], counts: Mapping[Direction, int], rings: int
) -> List[str]:
    errors: List[str] = []
    ctrl = _section(config, "controller")
    inner = ctrl.get("innerRadius", 10.0)
    outer = ctrl.get("outerRadius", 20.0)
    if _number(inner) and _number(outer) and float(outer) > float(inner):
        width = (float(outer) - float(inner)) / rings
        needed = max(
            MIN_CIRCULATING_LANE_WIDTH,
            _widest_vehicle(config) + 2 * (CIRCULATING_LANE_SIDE_CLEARANCE),
        )
        if width + 1e-9 < needed:
            errors.append(
                f"The ring is too narrow for {rings} circulating lane(s): each would "
                f"be {width:.2f} m wide but needs at least {needed:.2f} m (the widest "
                f"vehicle plus {CIRCULATING_LANE_SIDE_CLEARANCE:g} m each side, and "
                f"never under {MIN_CIRCULATING_LANE_WIDTH:g} m). Increase "
                f"controller.outerRadius to at least "
                f"{float(inner) + rings * needed:.1f} m or use fewer circulating lanes"
            )
    for d in Direction:
        if counts[d] - rings > MAX_MERGING_ENTRY_LANES:
            errors.append(
                f"The {d.value} approach has {counts[d]} lanes but the ring has "
                f"{rings}: at most {rings + MAX_MERGING_ENTRY_LANES} entry lanes can "
                "feed it (the extra lane merges at the give-way line). Add "
                "circulating lanes or reduce the approach's lanes"
            )
    return errors


def _widest_vehicle(config: Mapping[str, Any]) -> float:
    # Imported here: vehicle_types pulls in the IDM and speed profile.
    from src.vehicles.vehicle_types import (
        DEFAULT_PROFILES,
        VEHICLE_CLASSES,
        approach_vehicle_mixes,
        configured_mix,
    )

    classes: Set[str] = set()
    for mix in [configured_mix(config) or {}] + list(
        approach_vehicle_mixes(config).values()
    ):
        classes.update(k for k, v in mix.items() if v > 0)
    widths = [2.2]
    veh_gen = _section(config, "vehicleGeneration")
    width_range = veh_gen.get("vehicleWidth")
    if isinstance(width_range, Mapping) and _number(width_range.get("max")):
        widths.append(float(width_range["max"]))
    types = veh_gen.get("vehicleTypes") if isinstance(veh_gen, Mapping) else None
    for cls in classes & set(VEHICLE_CLASSES):
        widths.append(DEFAULT_PROFILES[cls].width[1])
        override = (types or {}).get(cls) if isinstance(types, Mapping) else None
        if isinstance(override, Mapping) and isinstance(override.get("width"), Mapping):
            w = override["width"].get("max")
            if _number(w):
                widths.append(float(w))
    return max(widths)


def _roundabout_lane_errors(
    d: Direction,
    lanes: List[FrozenSet[TurnIntent]],
    counts: Mapping[Direction, int],
    rings: int,
) -> List[str]:
    errors: List[str] = []
    for i, turns in enumerate(lanes):
        for turn in sorted(turns, key=TURN_ORDER.__getitem__):
            exit_arm = target_direction(d, turn)
            ring = ring_lane_for(i, counts[d], rings, counts[exit_arm], turn)
            if ring is None:
                outer = designated_ring_lanes(rings, turn) == frozenset({rings - 1})
                where = (
                    "a right turn uses the outer circulating lane, which only the "
                    "right-hand entry lane feeds"
                    if outer
                    else f"a {'U-turn' if turn == TurnIntent.UTURN else 'left turn'} "
                    "uses the inner circulating lane, which the right-hand entry "
                    "lane does not feed"
                )
                errors.append(
                    f"At the roundabout, {d.value} lane {i + 1} cannot turn "
                    f"{turn.value}: on a {rings}-lane ring {where}. Allow it from "
                    "another lane, or leave the roundabout lane markings automatic"
                )
    return errors


def _signal_lane_errors(
    d: Direction,
    lanes: List[FrozenSet[TurnIntent]],
    counts: Mapping[Direction, int],
    configured: Mapping[Direction, List[FrozenSet[TurnIntent]]],
) -> List[str]:
    # Imported here to keep this module importable from lane_config users.
    from src.roads.lane_config import lane_use_order_errors

    errors = lane_use_order_errors(f"The {d.value} approach's", lanes)
    for turn in (TurnIntent.LEFT, TurnIntent.RIGHT):
        turning = sum(1 for lane in lanes if turn in lane)
        exit_arm = target_direction(d, turn)
        if counts[exit_arm] <= 0:
            continue  # no arm there: reported as an impossible movement
        if turning > counts[exit_arm]:
            errors.append(
                f"The {d.value} approach has {turning} lanes turning {turn.value} "
                f"but the {exit_arm.value} road it turns into has only "
                f"{counts[exit_arm]} lane(s); each turning lane needs its own "
                "receiving lane"
            )
    return errors
