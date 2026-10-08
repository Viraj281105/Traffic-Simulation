"""Represent one ``ScenarioDocument`` as a single-junction ``urbanflow-network``.

The junction becomes node ``J1``; every present arm gets an origin gate
feeding it and a destination gate leaving it; every non-zero turning share
becomes a route with demand ``arm.vehiclesPerHour x share``. Nothing is
simulated and the scenario is embedded unchanged, so the network's junction
has the scenario's own fingerprint.
"""

from typing import Any, Dict, List

from src.core.scenario import ScenarioDocument
from src.networks.models import NETWORK_FORMAT, NETWORK_VERSION
from src.networks.validate import movement_between

JUNCTION_ID = "J1"


def scenario_to_network(doc: ScenarioDocument) -> Dict[str, Any]:
    arms = {d.value: a for d, a in doc.approaches.present().items()}
    nodes: List[Dict[str, Any]] = [
        {
            "id": JUNCTION_ID,
            "kind": "junction",
            "scenario": doc.model_dump(mode="json"),
        }
    ]
    edges: List[Dict[str, Any]] = []
    for name, arm in arms.items():
        nodes.append({"id": f"O_{name}", "kind": "origin"})
        nodes.append({"id": f"D_{name}", "kind": "destination"})
        edges.append(
            {
                "id": f"IN_{name}",
                "from": {"node": f"O_{name}"},
                "to": {"node": JUNCTION_ID, "arm": name},
                "lengthMeters": arm.length,
                "lanes": arm.lanes,
            }
        )
        edges.append(
            {
                "id": f"OUT_{name}",
                "from": {"node": JUNCTION_ID, "arm": name},
                "to": {"node": f"D_{name}"},
                "lengthMeters": arm.length,
                "lanes": arm.lanes,
            }
        )

    routes: List[Dict[str, Any]] = []
    demand: List[Dict[str, Any]] = []
    for entry, arm in arms.items():
        shares = arm.turning.model_dump()
        for exit_arm in arms:
            move = movement_between(entry, exit_arm)
            share = shares.get(move) or 0.0
            if share <= 0:
                continue
            route_id = f"R_{entry}_{exit_arm}"
            routes.append(
                {
                    "id": route_id,
                    "origin": f"O_{entry}",
                    "destination": f"D_{exit_arm}",
                    "path": [f"IN_{entry}", f"OUT_{exit_arm}"],
                }
            )
            demand.append(
                {"routeId": route_id, "vehiclesPerHour": arm.vehiclesPerHour * share}
            )

    return {
        "format": NETWORK_FORMAT,
        "version": NETWORK_VERSION,
        "name": f"{doc.name} (single-junction network)",
        "nodes": nodes,
        "edges": edges,
        "routes": routes,
        "demand": demand,
        "simulation": {
            "duration": doc.simulation.duration,
            "warmup": doc.simulation.warmup,
            "seed": doc.simulation.seed,
        },
    }
