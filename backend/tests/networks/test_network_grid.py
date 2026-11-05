"""Grid scenarios and the 12-junction network (F5, W41/W44): shape, vehicle
conservation over seeds, determinism, and a regression pin for the
behaviour-preserving speed-up of ``simulate_network``."""

import pytest

from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.networks.graph import validate_graph
from src.networks.grid import (
    build_grid,
    build_three_by_three,
    build_twelve_junction_network,
    grid_flows,
    twelve_junction_flows,
)
from src.networks.network_sim import Flow, _capacity, simulate_network


def test_three_by_three_shape() -> None:
    g = build_three_by_three()
    junctions = [n for n in g.nodes if n.kind == "junction"]
    gates = [n for n in g.nodes if n.kind == "gate"]
    assert len(junctions) == 9 and len(gates) == 12
    assert all(n.control == "signal" for n in junctions)
    # 3 rows x 4 segments + 3 cols x 4 segments, two directions each
    assert len(g.links) == 48
    check = validate_graph(g)
    assert check["valid"] and check["warnings"] == []
    lanes = {k.id: k.lanes for k in g.links}
    assert lanes["J10>J11"] == 2 and lanes["J00>J01"] == 1  # middle row is the arterial


def test_twelve_junction_network_shape_and_geo() -> None:
    g = build_twelve_junction_network()
    assert sum(1 for n in g.nodes if n.kind == "junction") == 12
    assert validate_graph(g)["valid"]
    assert all(n.lat is not None and n.lon is not None for n in g.nodes)
    j00, j03 = g.node_map()["J00"], g.node_map()["J03"]
    assert j03.lon > j00.lon and j03.lat == j00.lat  # east is increasing longitude


def test_grid_bounds_and_node_naming() -> None:
    with pytest.raises(ValueError):
        build_grid(0, 3)
    with pytest.raises(ValueError):
        build_grid(3, 3, spacing=5)
    g = build_grid(2, 5, 200.0)
    assert {"J04", "J14", "GW0", "GE1", "GN4", "GS0"} <= set(g.node_map())
    assert g.node_map()["J14"].x == 800.0 and g.node_map()["J14"].y == -200.0


def test_default_flows_are_routable() -> None:
    g = build_three_by_three()
    res = simulate_network(g, grid_flows(3, 3), duration=30, seed=1)
    assert res["unroutable"] == []
    assert len(res["routes"]) == len(grid_flows(3, 3))


@pytest.mark.parametrize("seed", [1, 2, 3, 5, 8, 13])
@pytest.mark.parametrize("vph", [150.0, 600.0, 1800.0])
def test_grid_conserves_vehicles_over_seeds(seed: int, vph: float) -> None:
    g = build_three_by_three()
    res = simulate_network(g, grid_flows(3, 3, vph), duration=300, seed=seed)
    assert res["conserved"]
    assert res["entered"] == res["completed"] + res["active"]
    assert res["generated"] == res["entered"] + res["blockedAtEntry"]
    links = g.link_map()
    for lid, stat in res["perLink"].items():
        assert 0 <= stat["occupancy"] <= stat["peakOccupancy"] <= _capacity(links[lid])
    # every vehicle that completed was passed by exactly one destination node
    gate_passes = sum(
        res["perNode"][n.id]["passed"] for n in g.nodes if n.kind == "gate"
    )
    assert gate_passes == res["completed"]


def test_grid_is_deterministic_and_seed_sensitive() -> None:
    g = build_three_by_three()
    a = simulate_network(g, grid_flows(3, 3), duration=300, seed=4)
    assert a == simulate_network(g, grid_flows(3, 3), duration=300, seed=4)
    assert a != simulate_network(g, grid_flows(3, 3), duration=300, seed=5)


def test_twelve_junction_end_to_end() -> None:
    g = build_twelve_junction_network()
    res = simulate_network(g, twelve_junction_flows(500), duration=600, seed=9)
    assert res["conserved"] and res["unroutable"] == []
    assert res["completed"] > 400
    # vehicles really crossed all four columns of junctions
    for jid in ("J00", "J03", "J10", "J13", "J20", "J23"):
        assert res["perNode"][jid]["passed"] > 0
    assert res == simulate_network(g, twelve_junction_flows(500), duration=600, seed=9)


# Pinned from the engine before the hot-loop optimisation: the speed-up must not
# change any result (same rng draws, same arithmetic order).
@pytest.mark.parametrize(
    "build,flows,duration,seed,expected",
    [
        (build_two_junction_corridor, corridor_flows, 600, 7, (274, 224, 0)),
        (build_three_by_three, lambda: grid_flows(3, 3, 400), 900, 3, (930, 821, 0)),
        (
            build_twelve_junction_network,
            lambda: twelve_junction_flows(500),
            900,
            5,
            (1321, 1102, 0),
        ),
        (
            build_twelve_junction_network,
            lambda: twelve_junction_flows(1200),
            900,
            5,
            (2750, 2162, 404),
        ),
    ],
)
def test_optimised_engine_results_are_unchanged(
    build, flows, duration, seed, expected
) -> None:
    res = simulate_network(build(), flows(), duration=duration, seed=seed)
    assert (res["entered"], res["completed"], res["blockedAtEntry"]) == expected


def test_overloaded_single_flow_pin() -> None:
    res = simulate_network(
        build_two_junction_corridor(), [Flow("W", "E", 7200)], duration=300, seed=1
    )
    assert (res["entered"], res["completed"], res["blockedAtEntry"]) == (212, 103, 88)
