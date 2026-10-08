"""``/api/v2/networks``: stateless validate / compile / fingerprint endpoints.

Nothing is stored; every endpoint takes the network document and answers
from it, so the same document always gives the same answer.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.scenario import parse_scenario
from src.networks.compile import compile_network, derive_node_scenarios
from src.networks.execution import build_network_result
from src.networks.from_scenario import scenario_to_network
from src.networks.models import NetworkDocument, network_fingerprint
from src.networks.validate import parse_network, validate_network

router = APIRouter(prefix="/api/v2/networks", tags=["networks"])


class NetworkRequest(BaseModel):
    network: Dict[str, Any]


class ScenarioRequest(BaseModel):
    scenario: Dict[str, Any]


def _valid_network_or_400(raw: Dict[str, Any]) -> NetworkDocument:
    result = validate_network(raw)
    if not result["valid"]:
        raise HTTPException(
            status_code=400, detail=f"Invalid network: {'; '.join(result['errors'])}"
        )
    document, _ = parse_network(raw)
    assert document is not None
    return document


@router.post("/validate")
def validate_network_endpoint(payload: NetworkRequest) -> Dict[str, Any]:
    """Always 200: ``valid`` is false and ``errors`` says why when it is not."""
    return validate_network(payload.network)


@router.post("/compile")
def compile_network_endpoint(payload: NetworkRequest) -> Dict[str, Any]:
    """The execution plan: junction order, route-implied arm flows, edges."""
    return compile_network(_valid_network_or_400(payload.network))


@router.post("/fingerprint")
def network_fingerprint_endpoint(payload: NetworkRequest) -> Dict[str, Any]:
    """The network's stable fingerprint (list order and names do not matter)."""
    document = _valid_network_or_400(payload.network)
    return {
        "fingerprint": network_fingerprint(document),
        "nodeCount": len(document.nodes),
        "edgeCount": len(document.edges),
    }


@router.post("/scenario")
def network_scenarios_endpoint(payload: NetworkRequest) -> Dict[str, Any]:
    """Each inline junction's scenario with the route-implied volume and
    turning applied, ready for the single-junction scenario endpoints."""
    document = _valid_network_or_400(payload.network)
    scenarios, _ = derive_node_scenarios(document)
    return {
        "fingerprint": network_fingerprint(document),
        "scenarios": scenarios,
    }


@router.post("/result-structure")
def network_result_structure_endpoint(payload: NetworkRequest) -> Dict[str, Any]:
    """The ``urbanflow-network-result`` contract for this network, with
    ``status: not_executed`` (V1.9 does not run multi-junction simulations)."""
    document = _valid_network_or_400(payload.network)
    return build_network_result(compile_network(document))


@router.post("/from-scenario")
def network_from_scenario_endpoint(payload: ScenarioRequest) -> Dict[str, Any]:
    """The scenario represented as a single-junction ``urbanflow-network``
    (gates, entry/exit edges, one route per turning movement), with its
    validation and fingerprint. Nothing is simulated."""
    doc, errors = parse_scenario(payload.scenario)
    if doc is None:
        raise HTTPException(
            status_code=400, detail=f"Invalid scenario: {'; '.join(errors)}"
        )
    network = scenario_to_network(doc)
    check = validate_network(network)
    return {
        "network": network,
        "valid": check["valid"],
        "errors": check["errors"],
        "warnings": check["warnings"],
        "fingerprint": check.get("fingerprint"),
    }
