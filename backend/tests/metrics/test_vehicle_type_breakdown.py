"""V1.1 per-vehicle-class metric breakdown."""

from types import SimpleNamespace

from src.metrics.definitions.vehicle_mix import calculate_vehicle_type_breakdown


def test_breakdown_reconciles_with_the_aggregate() -> None:
    exited = [
        SimpleNamespace(vehicle_type="car"),
        SimpleNamespace(vehicle_type="car"),
        SimpleNamespace(vehicle_type="bus"),
        SimpleNamespace(),  # legacy/mock vehicle without a class: a car
    ]
    delays = [10.0, 20.0, 40.0, 30.0]
    active = [SimpleNamespace(vehicle_type="truck")]
    out = calculate_vehicle_type_breakdown(exited, delays, active)  # type: ignore[arg-type]
    assert out["car"] == {"exited": 3, "share": 0.75, "averageDelay": 20.0, "active": 0}
    assert out["bus"] == {"exited": 1, "share": 0.25, "averageDelay": 40.0, "active": 0}
    assert out["truck"] == {"exited": 0, "share": 0.0, "averageDelay": 0.0, "active": 1}
    total = sum(e["exited"] * e["averageDelay"] for e in out.values())
    assert total / sum(e["exited"] for e in out.values()) == sum(delays) / len(delays)


def test_empty_run() -> None:
    assert calculate_vehicle_type_breakdown([], [], []) == {}
