"""V1.9 network foundation: model, validation, fingerprint, compile, API.
Pure data tests: nothing here runs a simulation."""

import copy
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.networks.compile import compile_network, derive_node_scenarios
from src.networks.execution import (
    JunctionRunInput,
    JunctionRunResult,
    build_network_result,
    execute_network,
)
from src.networks.models import NetworkDocument, network_fingerprint, serialize_network
from src.networks.validate import movement_between, parse_network, validate_network

client = TestClient(app)


def _arm(vph: float = 300, lanes: int = 1) -> Dict[str, Any]:
    return {
        "lanes": lanes,
        "vehiclesPerHour": vph,
        "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
    }


def _scenario(name: str = "J") -> Dict[str, Any]:
    return {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": name,
        "junction": {"type": "fixed_time_signal"},
        "approaches": {d: _arm() for d in ("north", "south", "east", "west")},
        "simulation": {"duration": 60, "warmup": 10, "seed": 1},
    }


def _network() -> Dict[str, Any]:
    """O1 -> J1 -> J2 -> D1, west to east, plus a side exit from J1 south."""
    return {
        "format": "urbanflow-network",
        "version": 1,
        "name": "Corridor",
        "nodes": [
            {"id": "J1", "kind": "junction", "scenario": _scenario("a")},
            {"id": "J2", "kind": "junction", "scenario": _scenario("b")},
            {"id": "O1", "kind": "origin"},
            {"id": "D1", "kind": "destination"},
            {"id": "D2", "kind": "destination"},
        ],
        "edges": [
            {
                "id": "E1",
                "from": {"node": "O1"},
                "to": {"node": "J1", "arm": "west"},
                "lengthMeters": 150,
                "lanes": 1,
                "speedLimit": 15,
            },
            {
                "id": "E2",
                "from": {"node": "J1", "arm": "east"},
                "to": {"node": "J2", "arm": "west"},
                "lengthMeters": 450,
                "lanes": 2,
                "speedLimit": 15,
                "laneMetadata": [
                    {"index": 1, "movements": ["left", "straight"]},
                    {"index": 2, "movements": ["straight", "right"], "width": 3.5},
                ],
            },
            {
                "id": "E3",
                "from": {"node": "J2", "arm": "east"},
                "to": {"node": "D1"},
                "lengthMeters": 150,
                "lanes": 1,
            },
            {
                "id": "E4",
                "from": {"node": "J1", "arm": "south"},
                "to": {"node": "D2"},
                "lengthMeters": 150,
                "lanes": 1,
            },
        ],
        "routes": [
            {
                "id": "R1",
                "origin": "O1",
                "destination": "D1",
                "path": ["E1", "E2", "E3"],
            },
            {"id": "R2", "origin": "O1", "destination": "D2", "path": ["E1", "E4"]},
        ],
        "demand": [
            {"routeId": "R1", "vehiclesPerHour": 600, "vehicleMix": {"car": 1.0}},
            {"routeId": "R2", "vehiclesPerHour": 200},
        ],
        "simulation": {"duration": 120, "warmup": 20, "seed": 3},
    }


def _errors(payload: Dict[str, Any]) -> List[str]:
    return validate_network(payload)["errors"]


def _mutated(fn: Any) -> Dict[str, Any]:
    net = _network()
    fn(net)
    return net


def test_valid_network() -> None:
    result = validate_network(_network())
    assert result["valid"], result["errors"]
    assert len(result["fingerprint"]) == 16


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda n: n["edges"][0]["to"].update(node="NOPE"), "unknown node 'NOPE'"),
        (lambda n: n["edges"][1]["from"].pop("arm"), "needs an arm"),
        (
            lambda n: n["nodes"].append({"id": "J1", "kind": "origin"}),
            "Duplicate node id",
        ),
        (lambda n: n["routes"][0].update(path=["E1", "E9"]), "unknown edge 'E9'"),
        (
            lambda n: n["demand"].append({"routeId": "R9", "vehiclesPerHour": 1}),
            "unknown route 'R9'",
        ),
        (lambda n: n["nodes"][2].update(scenario=_scenario()), "gate has no scenario"),
        (lambda n: n["nodes"][0].update(scenario=None), "needs a scenario"),
        (
            lambda n: n["nodes"][0].update(junctionType="roundabout"),
            "does not match its scenario",
        ),
    ],
)
def test_invalid_references(mutate: Any, needle: str) -> None:
    assert any(needle in e for e in _errors(_mutated(mutate))), needle


def test_null_arm_and_shared_port_are_rejected() -> None:
    def three_arm(net: Dict[str, Any]) -> None:
        net["nodes"][0]["scenario"]["approaches"]["south"] = None
        net["nodes"][0]["scenario"]["approaches"]["north"]["turning"] = {
            "left": 0,
            "straight": 0.5,
            "right": 0.5,
        }

    errors = _errors(_mutated(three_arm))
    assert any("arm 'south' does not exist" in e for e in errors)

    def shared(net: Dict[str, Any]) -> None:
        net["edges"].append(
            {
                "id": "E5",
                "from": {"node": "O1"},
                "to": {"node": "J1", "arm": "west"},
                "lengthMeters": 50,
                "lanes": 1,
            }
        )

    assert any(
        "already has an edge that enters" in e for e in _errors(_mutated(shared))
    )


def test_disconnected_network_is_rejected() -> None:
    net = _network()
    net["nodes"].append({"id": "O9", "kind": "origin"})
    errors = _errors(net)
    assert any("disconnected" in e and "O9" in e for e in errors)


def test_cycle_is_rejected() -> None:
    net = _network()
    net["nodes"].append({"id": "J3", "kind": "junction", "scenario": _scenario()})
    # J2 north -> J3 south and J3 east -> J1 east would close a loop.
    net["edges"] += [
        {
            "id": "E5",
            "from": {"node": "J2", "arm": "north"},
            "to": {"node": "J3", "arm": "south"},
            "lengthMeters": 200,
            "lanes": 1,
        },
        {
            "id": "E6",
            "from": {"node": "J3", "arm": "west"},
            "to": {"node": "J1", "arm": "north"},
            "lengthMeters": 200,
            "lanes": 1,
        },
    ]
    assert any("cycle" in e for e in _errors(net))


def test_route_validation() -> None:
    assert movement_between("west", "east") == "straight"
    assert movement_between("west", "north") == "left"
    assert movement_between("west", "south") == "right"
    assert movement_between("west", "west") == "uturn"

    broken = _mutated(lambda n: n["routes"][0].update(path=["E1", "E3"]))
    assert any("not connected" in e for e in _errors(broken))

    wrong_end = _mutated(lambda n: n["routes"][0].update(destination="D2"))
    assert any("last edge" in e for e in _errors(wrong_end))

    wrong_start = _mutated(lambda n: n["routes"][0].update(origin="J1"))
    assert any("first edge" in e for e in _errors(wrong_start))


def test_demand_validation() -> None:
    dup = _mutated(
        lambda n: n["demand"].append({"routeId": "R1", "vehiclesPerHour": 5})
    )
    assert any("More than one demand" in e for e in _errors(dup))

    bad_class = _mutated(lambda n: n["demand"][0].update(vehicleMix={"tank": 1.0}))
    assert any("unknown vehicle class" in e for e in _errors(bad_class))

    over = _mutated(lambda n: n["demand"][0].update(vehiclesPerHour=7200))
    over["demand"][1]["vehiclesPerHour"] = 1000
    assert any("above the 7200" in e for e in _errors(over))

    short_mix = _network()
    short_mix["demand"][0]["vehicleMix"] = {"car": 0.9}
    result = validate_network(short_mix)
    assert result["valid"]
    assert any("sums to 0.9" in w for w in result["warnings"])

    negative = parse_network(
        _mutated(lambda n: n["demand"][0].update(vehiclesPerHour=-1))
    )
    assert negative[0] is None


def test_lane_metadata() -> None:
    doc, _ = parse_network(_network())
    assert doc is not None
    plan = compile_network(doc)
    e2 = next(e for e in plan["edges"] if e["id"] == "E2")
    assert [m["index"] for m in e2["laneMetadata"]] == [1, 2]
    assert e2["laneMetadata"][1]["width"] == 3.5

    too_many = _mutated(lambda n: n["edges"][1]["laneMetadata"].append({"index": 3}))
    assert any("exceeds its 2 lane" in e for e in _errors(too_many))
    dup = _mutated(lambda n: n["edges"][1]["laneMetadata"].append({"index": 1}))
    assert any("duplicate lane index" in e for e in _errors(dup))


def test_fingerprint_is_deterministic_and_order_independent() -> None:
    a = _network()
    b = copy.deepcopy(a)
    for key in ("nodes", "edges", "routes", "demand"):
        b[key].reverse()
    b["name"] = "renamed"
    fa, fb = validate_network(a)["fingerprint"], validate_network(b)["fingerprint"]
    assert fa == fb == validate_network(copy.deepcopy(a))["fingerprint"]

    c = _network()
    c["edges"][1]["lengthMeters"] = 451
    assert validate_network(c)["fingerprint"] != fa
    d = _network()
    d["nodes"][0]["scenario"]["approaches"]["east"]["vehiclesPerHour"] = 301
    assert validate_network(d)["fingerprint"] != fa


def test_serialization_round_trip() -> None:
    doc, _ = parse_network(_network())
    assert doc is not None
    wire = serialize_network(doc)
    assert [n["id"] for n in wire["nodes"]] == ["D1", "D2", "J1", "J2", "O1"]
    again, errors = parse_network(wire)
    assert again is not None, errors
    assert serialize_network(again) == wire
    assert network_fingerprint(again) == network_fingerprint(doc)
    assert isinstance(again, NetworkDocument)


def test_compile_plan_and_node_scenarios() -> None:
    doc, _ = parse_network(_network())
    assert doc is not None
    plan = compile_network(doc)
    assert plan["executionModel"] == "one-way-coupled-sequential"
    assert plan["order"].index("J1") < plan["order"].index("J2")
    j1 = next(n for n in plan["nodes"] if n["id"] == "J1")
    assert j1["inflowByArm"] == {"west": 800.0}
    assert j1["turningByArm"]["west"] == {"right": 0.25, "straight": 0.75}
    j2 = next(n for n in plan["nodes"] if n["id"] == "J2")
    assert j2["upstream"]["west"]["fromNode"] == "J1"
    r1 = next(r for r in plan["routes"] if r["id"] == "R1")
    assert r1["freeFlowSeconds"] == pytest.approx(
        150 / 15 + 450 / 15 + 150 / 13.89, abs=0.01
    )
    scenarios, errors = derive_node_scenarios(doc)
    assert not errors
    west = scenarios["J1"]["approaches"]["west"]
    assert west["vehiclesPerHour"] == 800.0 and west["turning"]["left"] == 0.0
    # the network's own document is untouched
    assert doc.nodes[0].scenario.approaches.west.vehiclesPerHour == 300  # type: ignore[union-attr]


def test_execution_abstraction_and_result_structure() -> None:
    doc, _ = parse_network(_network())
    assert doc is not None
    plan = compile_network(doc)
    empty = build_network_result(plan)
    assert empty["status"] == "not_executed"
    assert empty["network_level"]["totalThroughput"] is None
    assert set(empty["perEdge"]) == {"E1", "E2", "E3", "E4"}

    class Fake:
        calls: List[JunctionRunInput] = []

        def run(self, request: JunctionRunInput) -> JunctionRunResult:
            self.calls.append(request)
            total = sum(request.inflow_by_arm.values())
            return JunctionRunResult(
                {
                    "averageDelay": 10.0,
                    "throughput": total,
                    "vehicleLimitReached": False,
                },
                {"east": total * 0.75, "south": total * 0.25},
            )

    fake = Fake()
    results = execute_network(plan, {}, fake)
    assert [c.node_id for c in fake.calls] == ["J1", "J2"]
    assert fake.calls[1].inflow_by_arm == {"west": 600.0}  # J1 east departures
    out = build_network_result(plan, results)
    assert out["status"] == "executed"
    assert out["perRoute"]["R1"]["estimatedTravelSeconds"] == pytest.approx(
        plan["routes"][0]["freeFlowSeconds"] + 20.0, abs=0.01
    )
    assert out["network_level"]["vehicleLimitReached"] is False


def test_api_endpoints() -> None:
    body = {"network": _network()}
    v = client.post("/api/v2/networks/validate", json=body).json()
    assert v["valid"], v["errors"]
    fp = client.post("/api/v2/networks/fingerprint", json=body).json()
    assert fp["fingerprint"] == v["fingerprint"] and fp["edgeCount"] == 4
    plan = client.post("/api/v2/networks/compile", json=body).json()
    assert plan["fingerprint"] == fp["fingerprint"]
    sc = client.post("/api/v2/networks/scenario", json=body).json()
    assert set(sc["scenarios"]) == {"J1", "J2"}
    res = client.post("/api/v2/networks/result-structure", json=body).json()
    assert res["format"] == "urbanflow-network-result"

    bad = _network()
    bad["routes"][0]["path"] = ["E1", "E3"]
    bad_body = {"network": bad}
    assert (
        client.post("/api/v2/networks/validate", json=bad_body).json()["valid"] is False
    )
    for path in ("compile", "fingerprint", "scenario", "result-structure"):
        assert client.post(f"/api/v2/networks/{path}", json=bad_body).status_code == 400
