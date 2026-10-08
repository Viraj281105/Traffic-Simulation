"""Junction execution abstraction and the network-level result contract.

The engine runs one junction. ``JunctionExecutor`` is the seam a network run
goes through: V1.9 ships the composition logic (topological order, one-way
inflow hand-over) and the result structure; a concrete executor that wraps
the engine plugs in behind the protocol without changing either.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol

from src.networks.models import EXECUTION_MODEL

RESULT_FORMAT = "urbanflow-network-result"
RESULT_VERSION = 1
LANE_CAPACITY_VPH = 1800.0  # saturation flow used for edge utilisation

# Metric keys a junction run must offer for network aggregation (the names in
# docs/research/metrics-reference.md); absent keys are treated as unavailable.
NODE_METRIC_KEYS = (
    "averageDelay",
    "throughput",
    "averageQueueLength",
    "maxQueueLength",
    "vehicleLimitReached",
)


@dataclass(frozen=True)
class JunctionRunInput:
    node_id: str
    scenario: Optional[Dict[str, Any]]
    inflow_by_arm: Dict[str, float]
    turning_by_arm: Dict[str, Dict[str, float]]
    seed: int


@dataclass
class JunctionRunResult:
    metrics: Dict[str, Any]
    # Measured departures (veh/h) by exit arm, handed to the downstream edge.
    departures_by_arm: Dict[str, float] = field(default_factory=dict)


class JunctionExecutor(Protocol):
    def run(self, request: JunctionRunInput) -> JunctionRunResult: ...


def execute_network(
    plan: Mapping[str, Any],
    scenarios: Mapping[str, Dict[str, Any]],
    executor: JunctionExecutor,
    seed: int = 1,
) -> Dict[str, JunctionRunResult]:
    """Run the junctions of ``plan`` in order, one-way coupled: an arm fed by
    an upstream junction receives that junction's departures on the
    connecting arm; an arm fed by a gate receives the route-implied demand."""
    results: Dict[str, JunctionRunResult] = {}
    inflows: Dict[str, Dict[str, float]] = {}
    for node in plan["nodes"]:
        if node["kind"] != "junction":
            continue
        inflow: Dict[str, float] = {}
        for arm, link in node["upstream"].items():
            upstream = results.get(link["fromNode"])
            if link["fromKind"] == "junction" and upstream is not None:
                inflow[arm] = upstream.departures_by_arm.get(link["fromArm"], 0.0)
            else:
                inflow[arm] = node["inflowByArm"].get(arm, 0.0)
        inflows[node["id"]] = inflow
        results[node["id"]] = executor.run(
            JunctionRunInput(
                node_id=node["id"],
                scenario=scenarios.get(node["id"]),
                inflow_by_arm=inflow,
                turning_by_arm=node["turningByArm"],
                seed=seed,
            )
        )
    return results


def _node_delay(result: Optional[JunctionRunResult]) -> Optional[float]:
    if result is None:
        return None
    value = result.metrics.get("averageDelay")
    return float(value) if isinstance(value, (int, float)) else None


def build_network_result(
    plan: Mapping[str, Any],
    results: Optional[Mapping[str, JunctionRunResult]] = None,
) -> Dict[str, Any]:
    """The ``urbanflow-network-result`` structure. With ``results=None`` it is
    the empty (``not_executed``) contract: same keys, null values, so a client
    can build against it before any run exists."""
    results = results or {}
    executed = bool(results)
    per_node: Dict[str, Any] = {}
    for node in plan["nodes"]:
        if node["kind"] != "junction":
            continue
        run = results.get(node["id"])
        per_node[node["id"]] = {
            "metrics": (
                {k: run.metrics.get(k) for k in NODE_METRIC_KEYS} if run else None
            ),
            "inflowByArm": node["inflowByArm"],
            "departuresByArm": run.departures_by_arm if run else None,
            "fingerprint": node.get("scenarioFingerprint"),
        }

    per_edge = {
        e["id"]: {
            "flowVph": e["demandVph"],
            "freeFlowSeconds": e["freeFlowSeconds"],
            "estimatedSeconds": e["freeFlowSeconds"],
            "utilisation": round(e["demandVph"] / (LANE_CAPACITY_VPH * e["lanes"]), 4),
        }
        for e in plan["edges"]
    }

    per_route: Dict[str, Any] = {}
    route_times: List[float] = []
    for route in plan["routes"]:
        delays: Dict[str, Optional[float]] = {}
        for p in route["passages"]:
            delays[p["node"]] = (
                _node_delay(results.get(p["node"])) if executed else None
            )
        known = [d for d in delays.values() if d is not None]
        travel = (
            round(route["freeFlowSeconds"] + sum(known), 3)
            if executed and len(known) == len(delays)
            else None
        )
        if travel is not None:
            route_times.append(travel)
        total = sum(known)
        per_route[route["id"]] = {
            "demandVph": route["demandVph"],
            "estimatedTravelSeconds": travel,
            "delayShare": {
                n: (round(d / total, 4) if d is not None and total > 0 else None)
                for n, d in delays.items()
            },
        }

    throughput = sum(r.metrics.get("throughput") or 0 for r in results.values())
    delay_hours = sum(
        (_node_delay(r) or 0.0) * (r.metrics.get("throughput") or 0) / 3600.0
        for r in results.values()
    )
    network_level = {
        "totalThroughput": throughput if executed else None,
        "vehicleHoursDelay": round(delay_hours, 4) if executed else None,
        "meanDelayPerVehicle": (
            round(delay_hours * 3600.0 / throughput, 3)
            if executed and throughput
            else None
        ),
        "meanRouteTravelTime": (
            round(sum(route_times) / len(route_times), 3) if route_times else None
        ),
        "vehicleLimitReached": (
            any(bool(r.metrics.get("vehicleLimitReached")) for r in results.values())
            if executed
            else None
        ),
    }
    return {
        "format": RESULT_FORMAT,
        "version": RESULT_VERSION,
        "status": "executed" if executed else "not_executed",
        "network": {
            "fingerprint": plan["fingerprint"],
            "nodeCount": len(plan["nodes"]),
            "edgeCount": len(plan["edges"]),
            "executionModel": EXECUTION_MODEL,
        },
        "network_level": network_level,
        "perNode": per_node,
        "perEdge": per_edge,
        "perRoute": per_route,
        "metricDefinitions": {
            "totalThroughput": "sum of junction throughputs (a vehicle is "
            "counted once per junction it crosses)",
            "vehicleHoursDelay": "sum over junctions of averageDelay x "
            "throughput, in hours",
            "meanDelayPerVehicle": "vehicleHoursDelay per junction passage, seconds",
            "meanRouteTravelTime": "mean over routes of free-flow edge time "
            "plus junction delay, seconds",
            "utilisation": f"edge flow / ({LANE_CAPACITY_VPH:g} veh/h x lanes)",
        },
        "limitations": list(plan["limitations"]),
    }
