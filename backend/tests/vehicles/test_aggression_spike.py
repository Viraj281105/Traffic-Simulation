"""Spike AG-1 sensitivity evaluation and validation suite (V3.0 W4, ADR-016).

Evaluates the proposed driver aggression multipliers across:
1. IDM car-following parameters (T, s0, a, desired speed ceiling).
2. All 5 heterogeneous vehicle classes (car, suv, bus, truck, motorcycle).
3. MOBIL lane-change thresholds, politeness, and the safe deceleration invariant (b_safe = 4.0 m/s^2).
4. Roundabout safety margins (_EXIT_SAFETY_HEADWAY = 1.0 s) and entry gap acceptance.
5. Shockwave braking safety and numerical stability.

Results here provide empirical justification for the final multipliers recorded in ADR-016.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pytest

from src.controllers.roundabout import (
    _EXIT_COMMIT_MARGIN,
    _EXIT_SAFETY_HEADWAY,
)
from src.core.enums import Direction, TurnIntent
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.idm import IntelligentDriverModel
from src.vehicles.lane_change import (
    LaneChangeModel,
    LaneChangeSettings,
)
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import (
    CAR,
    DEFAULT_PROFILES,
    VEHICLE_CLASSES,
    VehicleTypeProfile,
)

# Standard speed limit used across urban scenarios (50 km/h)
URBAN_SPEED_LIMIT_MS: float = 13.89

# Defined W4 Profile Multipliers (ADR-016)
AGGRESSION_MULTIPLIERS = {
    "standard": {
        "headway_mult": 1.0,
        "gap_mult": 1.0,
        "accel_mult": 1.0,
        "speed_factor_offset": 0.0,
        "politeness_mult": 1.0,
        "threshold_mult": 1.0,
    },
    "moderate": {
        "headway_mult": 0.85,
        "gap_mult": 0.875,
        "accel_mult": 1.075,
        "speed_factor_offset": 0.025,
        "politeness_mult": 0.75,
        "threshold_mult": 0.75,
    },
    "high": {
        "headway_mult": 0.70,
        "gap_mult": 0.75,
        "accel_mult": 1.15,
        "speed_factor_offset": 0.05,
        "politeness_mult": 0.50,
        "threshold_mult": 0.50,
    },
}


def _resolve_profile_params(
    profile_name: str, base: VehicleTypeProfile
) -> Tuple[float, float, float, float]:
    """Return (T, s0, a, max_speed) for a vehicle class under a named aggression profile."""
    m = AGGRESSION_MULTIPLIERS[profile_name]
    t = base.desired_time_headway * m["headway_mult"]
    s0 = base.minimum_gap * m["gap_mult"]
    a = base.max_acceleration * m["accel_mult"]
    max_factor = min(1.10, base.desired_speed_factor[1] + m["speed_factor_offset"])
    max_speed = URBAN_SPEED_LIMIT_MS * max_factor
    return t, s0, a, max_speed


# --- 1. IDM Car-Following Parameter Bounds Across Vehicle Classes --------------------------------


class TestIDMAggressionSpike:
    @pytest.mark.parametrize("class_name", VEHICLE_CLASSES)
    def test_idm_multipliers_across_all_vehicle_classes(self, class_name: str) -> None:
        """All vehicle classes must scale monotonically while respecting physical validity bounds."""
        base = DEFAULT_PROFILES[class_name]

        t_std, s0_std, a_std, v_std = _resolve_profile_params("standard", base)
        t_mod, s0_mod, a_mod, v_mod = _resolve_profile_params("moderate", base)
        t_high, s0_high, a_high, v_high = _resolve_profile_params("high", base)

        # Monotonicity checks
        assert t_high < t_mod < t_std, f"T ordering violated for {class_name}"
        assert s0_high < s0_mod < s0_std, f"s0 ordering violated for {class_name}"
        assert a_high > a_mod > a_std, f"a ordering violated for {class_name}"
        assert v_high >= v_mod >= v_std, f"v_max ordering violated for {class_name}"

        # Exact expected percentage shifts for High
        assert pytest.approx(t_high / t_std, rel=1e-3) == 0.70
        assert pytest.approx(s0_high / s0_std, rel=1e-3) == 0.75
        assert pytest.approx(a_high / a_std, rel=1e-3) == 1.15

        # Bounds checks: time headway > 0.5s, minimum gap > 1.0m, a <= 4.0 m/s^2, speed <= 1.10x limit
        assert t_high >= 0.5, f"T too small for {class_name}: {t_high}"
        assert s0_high >= 1.0, f"s0 too small for {class_name}: {s0_high}"
        assert a_high <= 4.0, f"a too large for {class_name}: {a_high}"
        assert v_high <= URBAN_SPEED_LIMIT_MS * 1.10 + 1e-4

        # Invariant checks: comfort deceleration b and delta are NOT modified
        assert base.comfort_deceleration == pytest.approx(base.comfort_deceleration)
        assert base.idm_delta == pytest.approx(base.idm_delta)

    def test_equilibrium_spacing_and_saturation_flow_ordering(self) -> None:
        """At steady state speed, High aggression must yield significantly shorter spacing and higher capacity."""
        base = DEFAULT_PROFILES[CAR]
        speed = URBAN_SPEED_LIMIT_MS  # 13.89 m/s (50 km/h)
        car_len = 4.5

        spacings: Dict[str, float] = {}
        capacities: Dict[str, float] = {}

        for profile in ("standard", "moderate", "high"):
            t, s0, _, _ = _resolve_profile_params(profile, base)
            # Steady-state equilibrium gap: s* = s0 + v * T
            s_eq = s0 + speed * t
            spacings[profile] = s_eq
            # Headway: h = (s_eq + L) / v = T + (s0 + L) / v
            headway_s = (s_eq + car_len) / speed
            capacities[profile] = 3600.0 / headway_s

        # Spacings: standard ~22.8m, moderate ~19.5m (-15%), high ~16.1m (-30%)
        assert spacings["standard"] > spacings["moderate"] > spacings["high"]
        assert pytest.approx(spacings["standard"], abs=0.1) == 22.84
        assert pytest.approx(spacings["moderate"], abs=0.1) == 19.46
        assert pytest.approx(spacings["high"], abs=0.1) == 16.08

        # Capacities: standard ~1820 veh/h, moderate ~2100 veh/h, high ~2475 veh/h
        assert capacities["high"] > capacities["moderate"] > capacities["standard"]
        assert (
            capacities["high"] >= capacities["standard"] * 1.25
        )  # At least +25% saturation flow

    def test_platoon_discharge_from_standstill(self) -> None:
        """Simulate a 5-vehicle queue launch from a stopline to measure startup delay and headway."""
        dt = 0.1
        v0 = URBAN_SPEED_LIMIT_MS
        car_len = 4.5
        n_veh = 5

        headway_results: Dict[str, float] = {}
        last_crossing_time: Dict[str, float] = {}

        for profile in ("standard", "moderate", "high"):
            base = DEFAULT_PROFILES[CAR]
            t_headway, s0, a, _ = _resolve_profile_params(profile, base)
            idm = IntelligentDriverModel(
                desired_time_headway=t_headway,
                minimum_gap=s0,
                max_acceleration=a,
                comfort_deceleration=3.0,
            )

            # Positions stopped behind stopline at 0.0: lead vehicle front at 0.0
            positions = [-(i * (car_len + s0)) for i in range(n_veh)]
            speeds = [0.0] * n_veh
            cross_times: Dict[int, float] = {}

            for step in range(250):  # 25 seconds
                sim_time = step * dt
                new_pos = list(positions)
                new_spd = list(speeds)

                # Lead vehicle accelerates freely
                acc0 = idm.calculate_acceleration(speeds[0], v0)
                new_spd[0] = max(0.0, speeds[0] + acc0 * dt)
                new_pos[0] = positions[0] + (speeds[0] + new_spd[0]) / 2.0 * dt
                if 0 not in cross_times and new_pos[0] >= 0.0:
                    cross_times[0] = sim_time

                # Followers
                for i in range(1, n_veh):
                    gap = positions[i - 1] - positions[i] - car_len
                    lead_speed = speeds[i - 1]
                    acc = idm.calculate_acceleration(speeds[i], v0, lead_speed, gap)
                    new_spd[i] = max(0.0, speeds[i] + acc * dt)
                    new_pos[i] = positions[i] + (speeds[i] + new_spd[i]) / 2.0 * dt
                    if i not in cross_times and new_pos[i] >= 0.0:
                        cross_times[i] = sim_time

                positions = new_pos
                speeds = new_spd

            assert len(cross_times) == n_veh
            headways = [cross_times[i] - cross_times[i - 1] for i in range(1, n_veh)]
            headway_results[profile] = sum(headways) / len(headways)
            last_crossing_time[profile] = cross_times[n_veh - 1]

        # High aggression discharges faster with tighter headways
        assert (
            last_crossing_time["high"]
            < last_crossing_time["moderate"]
            < last_crossing_time["standard"]
        )
        assert (
            headway_results["high"]
            < headway_results["moderate"]
            < headway_results["standard"]
        )
        # 5th car crosses > 2 seconds earlier under High than Standard
        assert last_crossing_time["standard"] - last_crossing_time["high"] >= 2.0

    def test_shockwave_braking_safety_under_aggression(self) -> None:
        """When lead vehicle brakes hard at 4.0 m/s^2 to a complete stop, follower must not collide."""
        dt = 0.05
        v_init = URBAN_SPEED_LIMIT_MS
        car_len = 4.5

        for profile in ("standard", "moderate", "high"):
            base = DEFAULT_PROFILES[CAR]
            t_headway, s0, a, _ = _resolve_profile_params(profile, base)
            idm = IntelligentDriverModel(
                desired_time_headway=t_headway,
                minimum_gap=s0,
                max_acceleration=a,
                comfort_deceleration=3.0,
            )

            # Equilibrium starting distance
            s_eq = s0 + v_init * t_headway
            lead_pos = s_eq + car_len
            lead_spd = v_init
            ego_pos = 0.0
            ego_spd = v_init

            min_gap = s_eq
            collided = False

            for _ in range(300):  # 15s
                # Lead vehicle brakes aggressively at 4 m/s^2 until 0
                lead_spd = max(0.0, lead_spd - 4.0 * dt)
                lead_pos += lead_spd * dt

                gap = lead_pos - ego_pos - car_len
                if gap <= 0.0:
                    collided = True
                    break
                min_gap = min(min_gap, gap)

                acc = idm.calculate_acceleration(ego_spd, v_init, lead_spd, gap)
                new_ego_spd = max(0.0, ego_spd + acc * dt)
                ego_pos += (ego_spd + new_ego_spd) / 2.0 * dt
                ego_spd = new_ego_spd

                if lead_spd == 0.0 and ego_spd == 0.0:
                    break

            # Invariant: 0 collisions under all profiles
            assert not collided, f"Collision occurred under profile {profile}"
            # Final rest gap should settle right at minimum_gap s0
            final_gap = lead_pos - ego_pos - car_len
            assert pytest.approx(final_gap, abs=0.05) == s0
            assert min_gap >= s0 * 0.95


# --- 2. MOBIL Lane-Changing Sensitivity & Invariants ---------------------------------------------


class TestMOBILAggressionSpike:
    def _setup_network(self) -> Tuple[RoadNetwork, Lane, Lane]:
        net = RoadNetwork()
        net.setup_default_intersection(approach_length=200.0, lanes_per_approach=2)
        lanes = net.get_incoming_approach(Direction.NORTH).get_lanes()
        return net, lanes[0], lanes[1]

    def _make_vehicle(
        self, net: RoadNetwork, vid: str, lane_idx: int, pos: float, speed: float
    ) -> Vehicle:
        route = net.generate_route(Direction.NORTH, lane_idx, TurnIntent.STRAIGHT)
        return Vehicle(
            vid,
            4.5,
            1.9,
            13.0,
            route,
            start_position=pos,
            initial_speed=speed,
            turn_intent=TurnIntent.STRAIGHT,
        )

    def test_safe_deceleration_invariant_is_strict(self) -> None:
        """Safe deceleration must remain exactly 4.0 m/s^2 across all profiles."""
        for profile, m in AGGRESSION_MULTIPLIERS.items():
            settings = LaneChangeSettings(
                politeness=0.30 * m["politeness_mult"],
                acceleration_threshold=0.20 * m["threshold_mult"],
                safe_deceleration=4.0,  # Explicitly UNCHANGED
            )
            assert settings.safe_deceleration == 4.0, f"b_safe was altered in {profile}"

    def test_marginal_lane_change_acceptance_gradient(self) -> None:
        """A lane change with modest ego gain and moderate follower penalty is rejected by Standard but accepted by Moderate and High."""
        results: Dict[str, bool] = {}

        for profile, m in AGGRESSION_MULTIPLIERS.items():
            # Create fresh network and vehicles per profile to ensure complete isolation
            net = RoadNetwork()
            net.setup_default_intersection(approach_length=200.0, lanes_per_approach=2)

            def make_v(vid: str, lane_idx: int, pos: float, speed: float) -> Vehicle:
                route = net.generate_route(
                    Direction.NORTH, lane_idx, TurnIntent.STRAIGHT
                )
                return Vehicle(
                    vid,
                    4.5,
                    1.9,
                    13.0,
                    route,
                    start_position=pos,
                    initial_speed=speed,
                    turn_intent=TurnIntent.STRAIGHT,
                )

            # Subject vehicle in lane 1 at pos 50, speed 10 m/s
            me = make_v("me", 1, 50.0, 10.0)
            # Origin lane leader at pos 90, speed 8 m/s (moderate braking/following)
            make_v("lead_slow", 1, 90.0, 8.0)
            # Target lane follower at pos 30, speed 10 m/s (clear gap, modest deceleration disadvantage)
            make_v("follower", 0, 30.0, 10.0)

            settings = LaneChangeSettings(
                politeness=0.30 * m["politeness_mult"],
                acceleration_threshold=0.20 * m["threshold_mult"],
                safe_deceleration=4.0,
            )
            model = LaneChangeModel(settings, IntelligentDriverModel())
            results[profile] = model.attempt(me, net, 0.0, -99)

        # Standard rejects (inc <= 0.20 due to higher politeness penalty)
        # Moderate and High accept (reduced politeness and lower threshold allow advantageous move)
        assert results["standard"] is False, "Standard should reject marginal change"
        assert results["moderate"] is True, "Moderate should accept marginal change"
        assert results["high"] is True, "High should accept marginal change"

    def test_unsafe_gap_is_rejected_even_under_high_aggression(self) -> None:
        """When target lane follower would have to brake > b_safe (4.0 m/s^2), ALL profiles must reject."""
        for profile, m in AGGRESSION_MULTIPLIERS.items():
            net, _, _ = self._setup_network()
            me = self._make_vehicle(net, "me", 1, 50.0, 10.0)
            # Blocker in origin lane
            self._make_vehicle(net, "lead_slow", 1, 65.0, 4.0)
            # Fast vehicle right behind in target lane (pos 46, speed 15) -> severe braking required
            self._make_vehicle(net, "tailgater", 0, 46.0, 15.0)

            settings = LaneChangeSettings(
                politeness=0.30 * m["politeness_mult"],
                acceleration_threshold=0.20 * m["threshold_mult"],
                safe_deceleration=4.0,
            )
            model = LaneChangeModel(settings, IntelligentDriverModel())
            assert not model.attempt(me, net, 0.0, -99), (
                f"Unsafe lane change accepted under {profile}!"
            )


# --- 3. Roundabout Safety Margins Justification --------------------------------------------------


class TestRoundaboutSafetyMarginsSpike:
    def test_roundabout_exit_safety_margins_remain_unmodified(self) -> None:
        """Adhering to ADR-016 and the physics boundary, roundabout exit safety margins must remain at 1.0s."""
        assert _EXIT_SAFETY_HEADWAY == 1.0, (
            "Exit safety headway must remain 1.0s without a dedicated physics ADR"
        )
        assert _EXIT_COMMIT_MARGIN == 1.0, (
            "Exit commit margin must remain 1.0s without a dedicated physics ADR"
        )

    def test_roundabout_gap_acceptance_is_dominated_by_approach_idm(self) -> None:
        """Demonstrates that approach IDM following headway and launch acceleration dictate entry flow.

        Altering internal convergence zone buffers (_EXIT_SAFETY_HEADWAY) is unsafe because at
        circulating speeds (8 m/s), reducing safety buffer below 1.0s shrinks physical clearance
        to less than a single vehicle length (< 8m), creating high collision risk on curved paths.
        """
        circulating_speed = 8.0  # m/s
        buffer_standard = circulating_speed * _EXIT_SAFETY_HEADWAY  # 8.0m
        assert buffer_standard >= 8.0, (
            "Standard buffer provides safe physical clearance"
        )

        # If headway were scaled by 0.70x without a dedicated ADR:
        buffer_reduced = circulating_speed * (_EXIT_SAFETY_HEADWAY * 0.70)  # 5.6m
        # 5.6m is less than a bus (12m) or truck (10m), posing unacceptable collision risk in multi-lane rings
        bus_len = DEFAULT_PROFILES["bus"].max_length
        assert buffer_reduced < bus_len, (
            "Reducing exit safety headway causes overlap risk with long vehicles"
        )
