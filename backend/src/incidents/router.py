"""``/api/v2/incidents``: incidents, closures, weather, event surges and
resilience scores on the network engine (F13). Stateless: nothing is stored.

Register in ``main.py`` (same dependencies as the other network routers)::

    from src.incidents.router import router as incidents_router
    app.include_router(
        incidents_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )
"""

from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.incidents.catalogue import (
    NetworkSpec,
    build_network,
    catalogue,
    preset_by_id,
)
from src.incidents.engine import STRATEGIES, run_disruption
from src.incidents.model import Scenario, validate_scenario
from src.incidents.resilience import MAX_SEEDS, evaluate_resilience, run_metrics
from src.networks.graph import RoadGraph, parse_graph, validate_graph
from src.networks.network_sim import Flow

router = APIRouter(prefix="/api/v2/incidents", tags=["incidents"])

MAX_NODES = 400
MAX_WORK = 20_000_000  # nodes x simulated seconds x runs

Strategy = Literal["fixed_time", "max_pressure"]


class FlowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str
    destination: str
    vehiclesPerHour: float = Field(..., ge=0, le=7200)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A catalogue scenario id fills network, scenario and duration unless the
    # request gives them itself.
    preset: Optional[str] = None
    # Give `graph` (with `flows`) or a `network`; with neither, a corridor runs.
    graph: Optional[Dict[str, Any]] = None
    flows: Optional[List[FlowIn]] = None
    network: Optional[NetworkSpec] = None
    scenario: Optional[Scenario] = None
    duration: Optional[float] = Field(None, gt=0, le=3600)
    bucketSeconds: float = Field(30.0, ge=5, le=300)


class SimulateRequest(_Base):
    seed: int = 1
    strategy: Strategy = "fixed_time"
    compareBaseline: bool = True


def _default_strategies() -> List[Strategy]:
    return ["fixed_time", "max_pressure"]


class ResilienceRequest(_Base):
    strategies: List[Strategy] = Field(default_factory=_default_strategies)
    seeds: List[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    toleranceRelative: float = Field(0.10, ge=0, le=2)
    toleranceAbsoluteSeconds: float = Field(3.0, ge=0, le=300)
    holdBuckets: int = Field(3, ge=1, le=20)
    includeSeries: bool = False


def _resolve(req: _Base, runs: int) -> Tuple[RoadGraph, List[Flow], Scenario, float]:
    preset: Dict[str, Any] = {}
    if req.preset is not None:
        found = preset_by_id(req.preset)
        if found is None:
            raise HTTPException(422, detail=[f"unknown preset {req.preset!r}"])
        preset = found
    scenario = req.scenario
    if scenario is None:
        scenario = Scenario.model_validate(preset.get("scenario", {}))
    duration = req.duration or float(preset.get("duration", 900.0))
    if req.graph is not None:
        graph, errors = parse_graph(req.graph)
        if graph is None:
            raise HTTPException(422, detail=errors)
        check = validate_graph(graph)
        if check["errors"]:
            raise HTTPException(422, detail=check["errors"])
        if not req.flows:
            raise HTTPException(422, detail=["flows are required with a custom graph"])
        flows = [Flow(f.origin, f.destination, f.vehiclesPerHour) for f in req.flows]
    else:
        spec = req.network or NetworkSpec.model_validate(
            preset.get("network", {"kind": "corridor"})
        )
        graph, flows = build_network(spec)
        if req.flows:
            flows = [
                Flow(f.origin, f.destination, f.vehiclesPerHour) for f in req.flows
            ]
    if len(graph.nodes) > MAX_NODES:
        raise HTTPException(422, detail=[f"At most {MAX_NODES} nodes are allowed"])
    ids = {n.id for n in graph.nodes}
    problems = [
        f"Flow refers to unknown node {e!r}"
        for e in sorted({e for f in flows for e in (f.origin, f.destination)})
        if e not in ids
    ]
    problems += validate_scenario(graph, flows, scenario)
    if problems:
        raise HTTPException(422, detail=problems)
    if len(graph.nodes) * duration * runs > MAX_WORK:
        raise HTTPException(
            422, detail=["The request is too large; shorten the run or use fewer seeds"]
        )
    return graph, flows, scenario, duration


def _describe(graph: RoadGraph, flows: List[Flow]) -> Dict[str, Any]:
    return {
        "name": graph.name,
        "nodes": len(graph.nodes),
        "links": len(graph.links),
        "flows": [
            {
                "origin": f.origin,
                "destination": f.destination,
                "vehiclesPerHour": f.vehicles_per_hour,
            }
            for f in flows
        ],
    }


@router.get("/catalogue")
def get_catalogue() -> Dict[str, Any]:
    """Disruption types, weather factors, strategies, the resilience score
    formula and ready-made scenarios (the Stress Lab extension for F13)."""
    return catalogue()


@router.post("/simulate")
def simulate(req: SimulateRequest) -> Dict[str, Any]:
    """Run one disruption scenario with one signal strategy and one seed.

    Returns ``run`` (counters, ``series`` delay curve, ``segments``,
    ``reroutedVehicles``, ``conserved``) and, with ``compareBaseline``, the
    same run without the disruption (``baseline``) plus ``metrics`` (recovery
    time, peak delay, throughput loss, area under the delay curve, score) when
    the disruption ends early enough to measure recovery."""
    graph, flows, scenario, duration = _resolve(req, 2 if req.compareBaseline else 1)
    kw: Dict[str, Any] = dict(
        duration=duration,
        seed=req.seed,
        strategy=req.strategy,
        bucket_seconds=req.bucketSeconds,
    )
    out: Dict[str, Any] = {
        "network": _describe(graph, flows),
        "scenario": scenario.model_dump(),
        "duration": duration,
        "inModelOnly": True,
        "run": run_disruption(graph, flows, scenario, **kw),
    }
    if req.compareBaseline:
        base = run_disruption(graph, flows, Scenario(reroute=scenario.reroute), **kw)
        out["baseline"] = base
        end = scenario.disruption_end()
        metrics: Optional[Dict[str, Any]] = None
        if end is not None and end < duration - 2 * req.bucketSeconds:
            metrics = run_metrics(base, out["run"], end, duration)
        out["metrics"] = metrics
    return out


@router.post("/resilience")
def resilience(req: ResilienceRequest) -> Dict[str, Any]:
    """Recovery time, peak delay, throughput loss, area under the delay curve
    and a resilience score in [0, 1] with a bootstrap interval, per signal
    strategy, over ``seeds``. See ``resilience.py`` for the formula."""
    if not req.seeds or len(req.seeds) > MAX_SEEDS:
        raise HTTPException(422, detail=[f"give between 1 and {MAX_SEEDS} seeds"])
    strategies: List[str] = list(dict.fromkeys(req.strategies)) or list(STRATEGIES)
    graph, flows, scenario, duration = _resolve(
        req, 2 * len(req.seeds) * len(strategies)
    )
    try:
        result = evaluate_resilience(
            graph,
            flows,
            scenario,
            strategies=strategies,
            seeds=req.seeds,
            duration=duration,
            bucket_seconds=req.bucketSeconds,
            tolerance_rel=req.toleranceRelative,
            tolerance_abs=req.toleranceAbsoluteSeconds,
            hold_buckets=req.holdBuckets,
            include_series=req.includeSeries,
        )
    except ValueError as err:
        raise HTTPException(422, detail=[str(err)])
    result["network"] = _describe(graph, flows)
    result["scenario"] = scenario.model_dump()
    return result
