"""Bus model (headway, dwell at a stop) and conditional transit priority."""

from typing import Any, Dict, List

from src.core.enums import SimulationStatus
from src.priority.audit import audit_phase_log
from src.priority.models import ScenarioSpec, TransitLineSpec, TransitPriorityConfig
from src.priority.runs import build_run, execute
from src.priority.vehicles import TransitVehicle, distance_driven

LIGHT = ScenarioSpec(duration_s=120.0, arrival_rate=0.2)


def _line(**overrides: Any) -> TransitLineSpec:
    fields: Dict[str, Any] = {
        "line_id": "L1",
        "approach": "north",
        "turn": "straight",
        "headway_s": 40.0,
        "first_departure_s": 5.0,
        "count": 2,
        "dwell_s": 10.0,
    }
    fields.update(overrides)
    return TransitLineSpec(**fields)


def test_buses_depart_at_the_headway_and_are_long_vehicles() -> None:
    run = build_run(LIGHT, seed=2, transit_lines=[_line()])
    metrics = execute(run)
    buses = [v for v in run.controller.injected if isinstance(v, TransitVehicle)]
    assert [round(b.spawn_time, 1) for b in buses] == [5.0, 45.0]
    assert [b.vehicle_id for b in buses] == ["bus_L1_0", "bus_L1_1"]
    assert all(b.length > 10.0 and b.vehicle_type == "bus" for b in buses)
    assert metrics["vehicles"]["conserved"] is True
    assert len(metrics["transit"]["trips"]) == 2
    assert metrics["transit"]["busesCrossed"] >= 1


def test_a_bus_stands_still_at_its_stop_for_the_dwell() -> None:
    run = build_run(LIGHT, seed=2, transit_lines=[_line(count=1, dwell_s=10.0)])
    engine = run.engine
    stopped_at: List[float] = []
    positions: List[float] = []
    while engine.status != SimulationStatus.COMPLETED:
        engine.step()
        for v in run.controller.injected:
            assert isinstance(v, TransitVehicle)
            if v.dwell_state == "dwelling":
                stopped_at.append(engine.clock.get_elapsed_time())
                positions.append(v.position)
                assert v.speed == 0.0
    assert stopped_at, "the bus never stopped"
    assert max(positions) - min(positions) < 1e-9  # no creep while dwelling
    assert abs((stopped_at[-1] - stopped_at[0]) - 10.0) < 0.5
    bus = run.controller.injected[0]
    assert isinstance(bus, TransitVehicle)
    assert bus.dwell_state == "done" and abs(bus.dwell_total - 10.0) < 0.2
    # It stopped where the stop is, before the stop line.
    assert abs(positions[0] - bus.stop_position) < 0.6
    assert bus.stop_position < 200.0 - 10.0


def test_zero_dwell_means_no_stop() -> None:
    run = build_run(LIGHT, seed=2, transit_lines=[_line(count=1, dwell_s=0.0)])
    engine = run.engine
    while engine.status != SimulationStatus.COMPLETED:
        engine.step()
        for v in run.controller.injected:
            assert isinstance(v, TransitVehicle)
            assert v.dwell_state == "done"


def test_dwell_is_scheduled_so_it_is_not_counted_as_time_lost() -> None:
    run = build_run(
        LIGHT,
        seed=2,
        transit_lines=[_line(count=1, dwell_s=12.0)],
        transit=None,
        schedule_padding_s=30.0,
    )
    trip = execute(run)["transit"]["trips"][0]
    bus = run.controller.injected[0]
    assert isinstance(bus, TransitVehicle)
    end = (
        bus.exit_time
        if bus.exit_time is not None
        else run.engine.clock.get_elapsed_time()
    )
    assert trip["dwell"] >= 11.0
    # time lost = time in network - free-flow driving time - dwell
    expected = (
        end
        - bus.spawn_time
        - distance_driven(bus) / bus.desired_speed
        - bus.dwell_total
    )
    assert abs(trip["timeLost"] - max(0.0, expected)) < 0.01
    assert trip["timeLost"] <= (end - bus.spawn_time) - bus.dwell_total
    assert bus.planned_arrival == bus.spawn_time + bus.free_flow_to_stop + 12.0 + 30.0


def test_priority_is_conditional_on_lateness() -> None:
    """With an unreachable lateness threshold no bus is ever granted priority."""
    cfg = TransitPriorityConfig(lateness_threshold_s=290.0)
    spec = ScenarioSpec(duration_s=150.0, arrival_rate=0.6)
    run = build_run(
        spec, seed=3, transit_lines=[_line(count=3, headway_s=40.0)], transit=cfg
    )
    summary = execute(run)["signal"]
    assert summary["transitActions"] == 0
    assert summary["transitExtensionSeconds"] == 0.0
    assert summary["transitEarlyGreenSeconds"] == 0.0


def test_priority_is_bounded_and_never_breaks_clearance_or_minimum_green() -> None:
    cfg = TransitPriorityConfig(
        conditional=False, max_extension_s=6.0, max_early_green_s=6.0, min_spacing_s=0.0
    )
    spec = ScenarioSpec(duration_s=240.0, arrival_rate=0.6)
    line = _line(count=5, headway_s=45.0, first_departure_s=20.0, dwell_s=8.0)
    run = build_run(spec, seed=4, transit_lines=[line], transit=cfg)
    metrics = execute(run)
    audit = audit_phase_log(
        run.controller.phase_log,
        yellow_s=spec.yellow_s,
        all_red_s=spec.all_red_s,
        min_green_s=cfg.min_green_s,
        time_step_s=spec.time_step_s,
    )
    assert audit["ok"], audit["violations"]
    signal = metrics["signal"]
    assert signal["transitActions"] > 0, "unconditional priority should have acted"
    # Each action is capped; the totals therefore are capped per action.
    assert signal["transitExtensionSeconds"] <= 6.0 * signal["transitActions"] + 0.2
    assert signal["transitEarlyGreenSeconds"] <= 6.0 * signal["transitActions"] + 0.2
    assert metrics["collisions"] == 0
    assert metrics["vehicles"]["conserved"] is True


def test_person_and_vehicle_delay_are_reported_and_weighted_by_occupancy() -> None:
    run = build_run(LIGHT, seed=2, transit_lines=[_line(count=1)])
    t = execute(run)["transit"]
    assert t["people"] > 0 and t["personDelayTotal"] >= 0
    assert abs(t["personDelayPerPerson"] - t["personDelayTotal"] / t["people"]) < 1e-3
    assert t["vehicleDelayMean"] >= 0 and t["otherVehicleDelayMean"] >= 0
    # A bus counts for its passengers: more occupancy, more people.
    heavy = ScenarioSpec(duration_s=120.0, arrival_rate=0.2, bus_occupancy=100.0)
    run2 = build_run(heavy, seed=2, transit_lines=[_line(count=1)])
    assert execute(run2)["transit"]["people"] > t["people"]


def test_transit_runs_are_deterministic() -> None:
    cfg = TransitPriorityConfig(conditional=False)
    one = execute(build_run(LIGHT, 5, transit_lines=[_line()], transit=cfg))
    two = execute(build_run(LIGHT, 5, transit_lines=[_line()], transit=cfg))
    assert one == two
