"""Emergency pre-emption and transit priority wrapped around a fixed-time plan.

:class:`PriorityController` wraps the junction's own
:class:`~src.controllers.fixed_time_signal.FixedTimeSignalController`; it is
installed as ``engine.controller`` and delegates to the wrapped controller on
every tick in which it has nothing to do. It also injects the scheduled
emergency and transit vehicles (before the engine's physics step) and runs the
bus-stop dwell (after it, as a tick callback), so one object carries a run's
whole priority behaviour and the engine itself is not modified.

Pre-emption (emergency vehicles)
--------------------------------
States: ``normal`` -> ``clearing`` -> ``hold`` -> ``recovering`` -> ``normal``.

1. *Detection.* A vehicle with ``priority`` set that is on an incoming lane
   within ``detection_distance_m`` of its stop line, or will reach it within
   ``detection_time_s``, requests the green phase that releases its movement.
   One request is served at a time, the nearest first.
2. *Clearing.* If that green is showing, go straight to ``hold``. If another
   green is showing it runs until it has been green for ``min_green_s`` (the
   safety minimum; it is never cut earlier) and is then ended by jumping to the
   plan's own clearance phases for that green, so the plan's full yellow and
   all-red durations are always served. If the plan is already in yellow or
   all-red it runs on; the green it would have entered next is replaced by the
   requested one. A green is never replaced by a conflicting green directly.
3. *Hold.* The requested green stays on (the plan clock is frozen) until no
   detected emergency vehicle for it remains on the approach, or
   ``max_hold_s`` has passed, whichever is first.
4. *Recovery.* The hold ends through the plan's clearance phases, and the plan
   resumes at the green that was interrupted (so no movement is skipped for a
   cycle) or, if none was interrupted, at the next green after the held one.
   The interrupted green starts afresh (its remaining time is not credited).
   For ``min_recovery_s`` afterwards no new pre-emption starts, so a stream of
   vehicles cannot lock cross traffic out indefinitely. Cross traffic
   therefore loses at most one truncated green, the hold, and one clearance.

Transit priority (buses)
------------------------
Only in ``normal`` state (emergency vehicles take precedence), only for a bus
within ``detection_distance_m`` of the stop line that is behind schedule
(``lateness_threshold_s``), and each action at most once per phase and at
least ``min_spacing_s`` apart:

* *Green extension*: if the bus's green would end before it clears and
  holding it up to ``max_extension_s`` would let it through, the plan clock is
  frozen for as long as needed within that bound.
* *Early green*: if the bus's green is the next in the plan and the bus
  would otherwise arrive to a red, the green showing is shortened by up to
  ``max_early_green_s``, never below ``min_green_s`` in total.

Plan clearances are never shortened by either action.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.controllers.base import BaseController
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.core.enums import Direction, SimulationStatus, TurnIntent, VehicleState
from src.priority.models import (
    EmergencySpec,
    PreemptionConfig,
    TransitLineSpec,
    TransitPriorityConfig,
    YieldConfig,
)
from src.priority.phases import PhaseDriver
from src.priority.vehicles import (
    EMERGENCY_KINDS,
    LANE_PREFIX,
    EmergencyVehicle,
    TransitVehicle,
    VehicleBase,
    find_entry,
    route_free_flow_time,
)
from src.priority.yielding import YieldManager
from src.vehicles.vehicle_types import DEFAULT_PROFILES, VehicleParams

NORMAL = "normal"
CLEARING_MIN_GREEN = "clearing_min_green"
CLEARING = "clearing"
HOLD = "hold"
RECOVERING = "recovering"

#: Deceleration (fraction of the bus's comfortable one) used to stop at a bus stop.
_STOP_DECEL_FRACTION = 0.8
_STOP_TOLERANCE_M = 0.5
_BUS_SPEED_FACTOR = 0.825  # midpoint of the bus class's desired-speed range


def _approach_of(vehicle: Any) -> str:
    return str(vehicle.approach)


class _Pending:
    __slots__ = ("time", "kind", "payload")

    def __init__(self, time: float, kind: str, payload: Any) -> None:
        self.time = time
        self.kind = kind
        self.payload = payload


class PriorityController(BaseController):
    def __init__(
        self,
        base: FixedTimeSignalController,
        engine: Any,
        *,
        speed_limit: float,
        emergencies: Sequence[EmergencySpec] = (),
        transit_lines: Sequence[TransitLineSpec] = (),
        preemption: Optional[PreemptionConfig] = None,
        yielding: Optional[YieldConfig] = None,
        transit: Optional[TransitPriorityConfig] = None,
        wait_speed_threshold: float = 0.5,
        schedule_padding_s: float = 10.0,
    ) -> None:
        self.schedule_padding_s = schedule_padding_s
        self.driver = PhaseDriver(base)
        self.base = base
        self.engine = engine
        self.speed_limit = speed_limit
        self.emergencies = list(emergencies)
        self.transit_lines = list(transit_lines)
        self.preemption = preemption
        self.transit = transit
        self.wait_speed_threshold = wait_speed_threshold
        self.yield_manager: Optional[YieldManager] = (
            YieldManager(yielding, speed_limit)
            if yielding is not None and yielding.enabled
            else None
        )
        self._reset_state()

    # -- BaseController ---------------------------------------------------

    def reset(self) -> None:
        self.base.reset()
        if self.yield_manager is not None:
            self.yield_manager.reset()
        self._reset_state()

    def _reset_state(self) -> None:
        self.state = NORMAL
        self._goal: Optional[int] = None
        self._served_ids: set[str] = set()
        self._resume: Optional[int] = None
        self._hold_started = 0.0
        self._hold_total = 0.0
        self._lockout = 0.0
        self._reason = "plan"
        self._last_idx = self.driver.index
        self._phase_started = 0.0
        self._green_since: Optional[float] = 0.0 if self.driver.is_green() else None
        self.phase_log: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.preemption_count = 0
        self.entry_waits: Dict[str, float] = {}
        self.injected: List[Any] = []
        self._pending: List[_Pending] = self._schedule()
        self._tsp_key: Tuple[int, int] = (-1, -1)
        self._tsp_extended = 0.0
        self._tsp_cut_key: Tuple[int, int] = (-1, -1)
        self._tsp_last_action = -1e9
        self.tsp_extension_total = 0.0
        self.tsp_early_green_total = 0.0
        self.tsp_actions = 0
        self.tsp_late_requests = 0

    def _schedule(self) -> List[_Pending]:
        pending: List[_Pending] = []
        for i, spec in enumerate(self.emergencies):
            pending.append(_Pending(spec.time_s, "emergency", (i, spec)))
        for line in self.transit_lines:
            for k in range(line.count):
                pending.append(
                    _Pending(
                        line.first_departure_s + k * line.headway_s,
                        "transit",
                        (k, line),
                    )
                )
        pending.sort(key=lambda p: (p.time, p.kind))
        return pending

    def get_state(self) -> Dict[str, Any]:
        state = self.base.get_state()
        state["priority"] = {
            "state": self.state,
            "preemptions": self.preemption_count,
            "holdSeconds": round(self._hold_total, 2),
        }
        return state

    def signals_state(self) -> Dict[Direction, str]:
        out: Dict[Direction, str] = {}
        for sig in self.base.get_state().get("signals", []):
            out[Direction(str(sig["direction"]).lower())] = sig["color"]
        return out

    # -- per tick ---------------------------------------------------------

    @property
    def _now(self) -> float:
        return float(self.engine.clock.get_elapsed_time())

    def update(self, delta_time: float, active_vehicles: List[Any]) -> None:
        now = self._now
        if self.state == NORMAL:
            self._reason = "plan"
        self._inject(now)
        emergencies = [
            v
            for v in self.engine.pool.active_vehicles
            if isinstance(v, EmergencyVehicle) and v.state != VehicleState.EXITED
        ]
        for ev in emergencies:
            if ev.stop_line_time is None and ev.lane is not None:
                if not ev.lane.lane_id.startswith(LANE_PREFIX[ev.approach]):
                    ev.stop_line_time = now
        for v in self.engine.pool.active_vehicles:
            if (
                isinstance(v, TransitVehicle)
                and v.stop_line_time is None
                and v.lane is not None
                and not v.lane.lane_id.startswith(LANE_PREFIX[v.approach])
            ):
                v.stop_line_time = now
        if self.yield_manager is not None:
            self.yield_manager.update(emergencies, self.engine.pool.active_vehicles)

        handled = False
        if self.preemption is not None and self.preemption.enabled:
            handled = self._preemption_step(delta_time, now, emergencies)
        if not handled and self.state == NORMAL:
            handled = self._transit_step(delta_time, now)
        if not handled:
            self.base.update(delta_time, active_vehicles)
        self._after_step(now)

    # -- injection --------------------------------------------------------

    def _inject(self, now: float) -> None:
        if not self._pending or self._pending[0].time > now + 1e-9:
            return
        still: List[_Pending] = []
        for item in self._pending:
            if item.time > now + 1e-9:
                still.append(item)
                continue
            vehicle = (
                self._place_emergency(item, now)
                if item.kind == "emergency"
                else self._place_transit(item, now)
            )
            if vehicle is None:
                still.append(item)
            else:
                self.engine.pool.add_vehicle(vehicle)
                self.injected.append(vehicle)
                self.entry_waits[vehicle.vehicle_id] = now - item.time
        self._pending = still

    def _place_emergency(
        self, item: _Pending, now: float
    ) -> Optional[EmergencyVehicle]:
        index, spec = item.payload
        kind = EMERGENCY_KINDS[spec.kind]
        params = kind.params(self.speed_limit)
        desired = params.desired_speed_range[0]
        direction = Direction(spec.approach)
        entry = find_entry(
            self.engine.network,
            direction,
            spec.turn,
            spec.lane,
            kind.length,
            kind.minimum_gap,
            kind.comfort_deceleration,
            desired,
        )
        if entry is None:
            return None
        lane_index, speed = entry
        turn = TurnIntent(spec.turn)
        route = self.engine.network.generate_route(direction, lane_index, turn)
        base = VehicleBase(
            vehicle_id=f"ev_{index}",
            length=kind.length,
            width=kind.width,
            desired_speed=desired,
            route=route,
            start_position=kind.length / 2.0,
            initial_speed=speed,
            turn_intent=turn,
            spawn_time=now,
            wait_speed_threshold=self.wait_speed_threshold,
            params=params,
        )
        ev = EmergencyVehicle(
            base,
            kind=spec.kind,
            approach=spec.approach,
            turn_name=spec.turn,
            scheduled_time=spec.time_s,
        )
        ev.free_flow_time = route_free_flow_time(ev)
        return ev

    def _place_transit(self, item: _Pending, now: float) -> Optional[TransitVehicle]:
        trip, line = item.payload
        profile = DEFAULT_PROFILES["bus"]
        desired = self.speed_limit * _BUS_SPEED_FACTOR
        params = VehicleParams(profile, (desired, desired))
        length = sum(profile.length) / 2.0
        direction = Direction(line.approach)
        entry = find_entry(
            self.engine.network,
            direction,
            line.turn,
            None,
            length,
            profile.minimum_gap,
            profile.comfort_deceleration,
            desired,
        )
        if entry is None:
            return None
        lane_index, speed = entry
        turn = TurnIntent(line.turn)
        route = self.engine.network.generate_route(direction, lane_index, turn)
        lane_length = route[0].length
        stop_position = (
            line.stop_position_m
            if line.stop_position_m is not None
            else max(length, lane_length - 60.0)
        )
        stop_position = min(max(stop_position, length), lane_length - 10.0)
        base = VehicleBase(
            vehicle_id=f"bus_{line.line_id}_{trip}",
            length=length,
            width=sum(profile.width) / 2.0,
            desired_speed=desired,
            route=route,
            start_position=length / 2.0,
            initial_speed=speed,
            turn_intent=turn,
            spawn_time=now,
            wait_speed_threshold=self.wait_speed_threshold,
            params=params,
        )
        bus = TransitVehicle(
            base,
            line_id=line.line_id,
            trip_index=trip,
            approach=line.approach,
            turn_name=line.turn,
            dwell_s=line.dwell_s,
            stop_position=stop_position,
        )
        bus.free_flow_to_stop = max(0.0, lane_length - length / 2.0) / desired
        bus.planned_arrival = (
            now + bus.free_flow_to_stop + line.dwell_s + self.schedule_padding_s
        )
        if line.dwell_s <= 0.0:
            bus.dwell_state = "done"
        return bus

    # -- phase bookkeeping ------------------------------------------------

    def _after_step(self, now: float) -> None:
        d = self.driver
        idx = d.index
        if idx == self._last_idx:
            return
        prev, cur = d.phases[self._last_idx], d.phases[idx]
        self.phase_log.append(
            {
                "time": round(now, 3),
                "from": prev.name,
                "to": cur.name,
                "fromColor": prev.color,
                "toColor": cur.color,
                "fromDirections": [x.value for x in prev.directions],
                "toDirections": [x.value for x in cur.directions],
                "phaseSeconds": round(now - self._phase_started, 3),
                "greenAge": (
                    round(now - self._green_since, 3)
                    if self._green_since is not None
                    else None
                ),
                "reason": self._reason,
            }
        )
        if cur.color == "green":
            if not (prev.color == "green" and prev.directions == cur.directions):
                self._green_since = now
        else:
            self._green_since = None
        self._phase_started = now
        self._last_idx = idx

    def _green_age(self, now: float) -> float:
        return 0.0 if self._green_since is None else now - self._green_since

    # -- pre-emption ------------------------------------------------------

    @staticmethod
    def _on_approach(ev: EmergencyVehicle) -> bool:
        return (
            ev.state != VehicleState.EXITED
            and ev.lane is not None
            and ev.lane.lane_id.startswith(LANE_PREFIX[ev.approach])
        )

    def _detected(self, ev: EmergencyVehicle) -> bool:
        cfg = self.preemption
        if cfg is None or not self._on_approach(ev) or ev.lane is None:
            return False
        dist = max(0.0, ev.lane.length - ev.position)
        if cfg.detection_distance_m is not None and dist <= cfg.detection_distance_m:
            return True
        return (
            cfg.detection_time_s is not None
            and ev.speed > 0.5
            and dist / ev.speed <= cfg.detection_time_s
        )

    def _request(
        self, emergencies: Sequence[EmergencyVehicle]
    ) -> Optional[Tuple[EmergencyVehicle, int]]:
        best: Optional[Tuple[float, EmergencyVehicle, int]] = None
        for ev in emergencies:
            if not self._detected(ev) or ev.lane is None:
                continue
            target = self.driver.find_green(
                Direction(ev.approach), TurnIntent(ev.turn_name)
            )
            if target is None:
                continue
            dist = ev.lane.length - ev.position
            if best is None or dist < best[0]:
                best = (dist, ev, target)
        return None if best is None else (best[1], best[2])

    def _log_event(self, now: float, kind: str, **fields: Any) -> None:
        self.events.append({"time": round(now, 3), "type": kind, **fields})

    def _select_toward(self, old: int, goal: Optional[int]) -> int:
        n = len(self.driver.phases)
        nxt = (old + 1) % n
        if (
            goal is not None
            and self.driver.phases[nxt].color == "green"
            and nxt != goal
        ):
            return goal
        return nxt

    def _preemption_step(
        self, dt: float, now: float, emergencies: Sequence[EmergencyVehicle]
    ) -> bool:
        cfg = self.preemption
        assert cfg is not None
        d = self.driver
        if self.state == NORMAL:
            if self._lockout > 0.0:
                self._lockout = max(0.0, self._lockout - dt)
                return False
            request = self._request(emergencies)
            if request is None:
                return False
            ev, target = request
            self._begin(now, ev, target)
            if self.state == NORMAL:
                return False

        if self.state in (CLEARING_MIN_GREEN, CLEARING, HOLD):
            for ev in emergencies:
                if self._detected(ev):
                    self._served_ids.add(ev.vehicle_id)

        if self.state == CLEARING_MIN_GREEN:
            if not d.is_green():
                self.state = CLEARING
            elif self._green_age(now) >= cfg.min_green_s:
                clearance = d.clearance_start(d.index)
                if clearance is None:
                    self._abort(now, "the plan has no clearance after this green")
                    return False
                self._reason = "preempt-clearance"
                d.jump(clearance)
                self.state = CLEARING
                return True
            else:
                self._reason = "plan"
                d.advance(dt)
                return True

        if self.state == CLEARING:
            goal = self._goal
            self._reason = "preempt-clearance"
            d.advance(dt, lambda old: self._select_toward(old, goal))
            if d.index == goal:
                self._enter_hold(now)
            return True

        if self.state == HOLD:
            goal = self._goal
            assert goal is not None
            self.base._apply_signals()
            waiting = [
                ev
                for ev in emergencies
                if ev.vehicle_id in self._served_ids
                and self._on_approach(ev)
                and d.serves(goal, Direction(ev.approach), TurnIntent(ev.turn_name))
            ]
            held = now - self._hold_started
            # The green is shown for at least the safety minimum even if the
            # vehicle has already passed (max_hold_s >= min_green_s, validated).
            cleared = not waiting and self._green_age(now) >= cfg.min_green_s
            if cleared or held >= cfg.max_hold_s:
                self._release(now, timed_out=bool(waiting))
            return True

        if self.state == RECOVERING:
            resume = self._resume
            self._reason = "preempt-recovery"
            d.advance(dt, lambda old: self._select_toward(old, resume))
            if d.is_green():
                self.state = NORMAL
                self._lockout = cfg.min_recovery_s
                self._reason = "plan"
                self._log_event(now, "restored", phase=d.phase.name)
            return True
        return False

    def _begin(self, now: float, ev: EmergencyVehicle, target: int) -> None:
        d = self.driver
        self.preemption_count += 1
        interrupted = d.index if d.is_green() else d.next_green(d.index)
        target_dirs = d.phases[target].directions
        resume = interrupted
        if resume is None or d.phases[resume].directions == target_dirs:
            resume = d.next_green(target, exclude=target_dirs)
        self._resume = resume
        self._goal = target
        self._served_ids = {ev.vehicle_id}
        self._log_event(
            now,
            "preempt_start",
            vehicle=ev.vehicle_id,
            target=d.phases[target].name,
            interrupted=d.phases[d.index].name,
            distance=round(max(0.0, ev.lane.length - ev.position), 2)
            if ev.lane is not None
            else None,
        )
        if d.index == target:
            self._enter_hold(now)
        elif d.is_green():
            self.state = CLEARING_MIN_GREEN
        else:
            self.state = CLEARING

    def _enter_hold(self, now: float) -> None:
        self.state = HOLD
        self._hold_started = now
        self._reason = "preempt-hold"
        self._log_event(now, "hold_start", phase=self.driver.phase.name)

    def _release(self, now: float, timed_out: bool) -> None:
        d = self.driver
        goal = self._goal
        assert goal is not None
        held = now - self._hold_started
        self._hold_total += held
        self._log_event(now, "hold_end", heldSeconds=round(held, 2), timedOut=timed_out)
        clearance = d.clearance_start(goal)
        self._reason = "preempt-recovery"
        if clearance is None:
            self.state = NORMAL
            self._lockout = self.preemption.min_recovery_s if self.preemption else 0.0
            return
        d.jump(clearance)
        self.state = RECOVERING

    def _abort(self, now: float, why: str) -> None:
        self.state = NORMAL
        self._lockout = self.preemption.min_recovery_s if self.preemption else 0.0
        self._log_event(now, "aborted", reason=why)

    # -- transit priority -------------------------------------------------

    def _remaining_dwell(self, bus: TransitVehicle, now: float) -> float:
        if bus.dwell_state == "dwelling":
            return max(0.0, bus.dwell_s - (now - bus.dwell_started))
        if bus.dwell_state == "approach":
            return bus.dwell_s
        return 0.0

    def _bus_eta(self, bus: TransitVehicle, now: float) -> float:
        assert bus.lane is not None
        dist = max(0.0, bus.lane.length - bus.position)
        speed = max(bus.speed, 0.6 * bus.desired_speed)
        return self._remaining_dwell(bus, now) + dist / speed

    def _lateness(self, bus: TransitVehicle, now: float) -> float:
        assert bus.lane is not None
        dist = max(0.0, bus.lane.length - bus.position)
        predicted = now + dist / bus.desired_speed + self._remaining_dwell(bus, now)
        return predicted - bus.planned_arrival

    def _transit_step(self, dt: float, now: float) -> bool:
        cfg = self.transit
        if cfg is None or not cfg.enabled:
            return False
        d = self.driver
        candidates: List[Tuple[float, TransitVehicle]] = []
        for v in self.engine.pool.active_vehicles:
            if not isinstance(v, TransitVehicle) or v.lane is None:
                continue
            if v.state == VehicleState.EXITED:
                continue
            if not v.lane.lane_id.startswith(LANE_PREFIX[v.approach]):
                continue
            dist = v.lane.length - v.position
            if dist > cfg.detection_distance_m:
                continue
            if cfg.conditional and self._lateness(v, now) < cfg.lateness_threshold_s:
                continue
            candidates.append((dist, v))
        if not candidates:
            return False
        candidates.sort(key=lambda c: (c[0], c[1].vehicle_id))
        bus = candidates[0][1]
        direction, turn = Direction(bus.approach), TurnIntent(bus.turn_name)
        key = (d.index, self.base.cycle_number)
        if key != self._tsp_key:
            self._tsp_key = key
            self._tsp_extended = 0.0
        eta = self._bus_eta(bus, now)
        spaced = now - self._tsp_last_action >= cfg.min_spacing_s

        if d.serves(d.index, direction, turn):
            left = cfg.max_extension_s - self._tsp_extended
            if (
                d.remaining < eta + 1.0
                and eta <= d.remaining + left
                and left > 0.0
                and (self._tsp_extended > 0.0 or spaced)
            ):
                self._tsp_extended += dt
                self.tsp_extension_total += dt
                bus.priority_extension_s += dt
                if self._tsp_extended <= dt + 1e-9:
                    self.tsp_actions += 1
                self._tsp_last_action = now
                self._reason = "transit-extension"
                self.base._apply_signals()
                return True
            return False

        if not d.is_green() or self._tsp_cut_key == key or not spaced:
            return False
        target = d.find_green(direction, turn)
        if (
            target is None
            or d.next_green(d.index, exclude=d.phase.directions) != target
        ):
            return False
        wait = d.remaining + sum(
            p.duration for p in self._phases_between(d.index, target)
        )
        if wait <= eta:
            return False
        keep = max(0.0, cfg.min_green_s - d.elapsed)
        cut = min(cfg.max_early_green_s, d.remaining - keep, wait - eta)
        if cut < 0.5:
            return False
        d.skip_ahead(cut)
        self._tsp_cut_key = key
        self._tsp_last_action = now
        self.tsp_early_green_total += cut
        self.tsp_actions += 1
        bus.priority_early_green = True
        self._reason = "transit-early-green"
        return False

    def _phases_between(self, start: int, end: int) -> List[Any]:
        n = len(self.driver.phases)
        out = []
        idx = (start + 1) % n
        while idx != end:
            out.append(self.driver.phases[idx])
            idx = (idx + 1) % n
        return out

    # -- bus stops (tick callback, after the engine's physics step) -------

    def after_physics(self) -> None:
        now = self._now
        for v in self.engine.pool.active_vehicles:
            if (
                not isinstance(v, TransitVehicle)
                or v.lane is None
                or v.dwell_state == "done"
            ):
                continue
            if v.dwell_state == "approach":
                if not v.lane.lane_id.startswith(LANE_PREFIX[v.approach]):
                    v.dwell_state = "done"
                    continue
                dist = v.stop_position - v.position
                decel = _STOP_DECEL_FRACTION * v.comfort_deceleration
                if dist <= _STOP_TOLERANCE_M:
                    v.position = min(v.position, v.stop_position)
                    v.speed = 0.0
                    v.acceleration = 0.0
                    v.dwell_state = "dwelling"
                    v.dwell_started = now
                    v.hold_position = v.position
                    continue
                cap = (2.0 * decel * dist) ** 0.5
                if v.speed > cap:
                    v.speed = cap
            elif v.dwell_state == "dwelling":
                v.position = v.hold_position
                v.speed = 0.0
                v.acceleration = 0.0
                if now - v.dwell_started >= v.dwell_s - 1e-9:
                    v.dwell_state = "done"
                    v.dwell_total = now - v.dwell_started

    # -- results ----------------------------------------------------------

    def finalize(self) -> None:
        """Undo temporary vehicle changes (yielding) before the run is measured."""
        if self.yield_manager is not None:
            self.yield_manager.restore_all()

    def summary(self) -> Dict[str, Any]:
        return {
            "preemptionEnabled": bool(self.preemption and self.preemption.enabled),
            "preemptions": self.preemption_count,
            "holdSeconds": round(self._hold_total, 2),
            "transitPriorityEnabled": bool(self.transit and self.transit.enabled),
            "transitActions": self.tsp_actions,
            "transitExtensionSeconds": round(self.tsp_extension_total, 2),
            "transitEarlyGreenSeconds": round(self.tsp_early_green_total, 2),
            "vehiclesYielded": (
                len(self.yield_manager.yielded_ids)
                if self.yield_manager is not None
                else 0
            ),
            "events": list(self.events),
        }


def is_complete(engine: Any) -> bool:
    return bool(engine.status == SimulationStatus.COMPLETED)
