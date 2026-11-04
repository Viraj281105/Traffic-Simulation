"""Calibrate a road-network graph against link counts (F11 / package 1B).

Tunes, with the mesoscopic network simulator (``src.networks.network_sim``):

* ``demand:<origin>-><destination>``: a multiplier on each OD flow's veh/h;
* ``speed:<group>``: a multiplier on the free-flow speed of a group of links
  (default one group ``all``; pass ``speed_groups`` for finer control).

Method: seeded, deterministic coordinate (pattern) search. Each sweep visits
the parameters in a seeded random order and tries ``p x (1 +/- step)``,
keeping the better move; a sweep with no gain halves ``step``. It stops when
``step`` falls under ``min_step``, the evaluation ``budget`` is spent, or the
objective reaches ``target_objective``. The simulator uses one fixed seed for
every evaluation (common random numbers), so the objective is a deterministic
function of the parameters. Objective: mean GEH^2 over links with counts
(+ optional ridge ``regularisation`` x sum(ln p)^2 towards the start).

Counts only constrain what the sensors see: parameters that no counted link
depends on cannot be identified and stay at their start value.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from src.calibration.network_counts import CountSet
from src.calibration.network_metrics import (
    MIN_OBSERVED_VPH,
    GCalCriteria,
    g_cal_check,
    geh,
    network_metrics,
    per_link_rows,
)
from src.networks.graph import RoadGraph, serialize_graph
from src.networks.network_sim import Flow, simulate_network

REPORT_FORMAT = "urbanflow-network-calibration"
REPORT_VERSION = 1

DEMAND_BOUNDS = (0.2, 3.0)
SPEED_BOUNDS = (0.5, 1.6)
MAX_BUDGET = 2000


class NetworkCalibrationError(ValueError):
    def __init__(self, errors: Sequence[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class SimSettings:
    duration: float = 600.0  # simulated seconds per evaluation
    seed: int = 1
    dt: float = 1.0
    signal_cycle: float = 60.0


@dataclass(frozen=True)
class FitOptions:
    budget: int = 200  # max simulator evaluations (incl. baseline and final)
    seed: int = 1  # optimiser seed (parameter visit order)
    initial_step: float = 0.25
    min_step: float = 0.01
    shrink: float = 0.5
    calibrate_demand: bool = True
    calibrate_speed: bool = True
    speed_groups: Optional[Mapping[str, Sequence[str]]] = None
    demand_bounds: Tuple[float, float] = DEMAND_BOUNDS
    speed_bounds: Tuple[float, float] = SPEED_BOUNDS
    min_observed_vph: float = MIN_OBSERVED_VPH
    regularisation: float = 0.0
    target_objective: float = 0.0  # stop early at or below this mean GEH^2
    criteria: GCalCriteria = field(default_factory=GCalCriteria)


def demand_name(f: Flow) -> str:
    return f"demand:{f.origin}->{f.destination}"


def default_parameters(
    graph: RoadGraph, flows: Sequence[Flow], options: FitOptions
) -> Dict[str, float]:
    params: Dict[str, float] = {}
    if options.calibrate_demand:
        for f in flows:
            params[demand_name(f)] = 1.0
    if options.calibrate_speed:
        for g in speed_groups(graph, options):
            params[f"speed:{g}"] = 1.0
    return params


def speed_groups(graph: RoadGraph, options: FitOptions) -> Dict[str, List[str]]:
    if options.speed_groups:
        return {g: sorted(v) for g, v in sorted(options.speed_groups.items())}
    return {"all": sorted(k.id for k in graph.links)}


def validate_inputs(
    graph: RoadGraph, flows: Sequence[Flow], counts: CountSet, options: FitOptions
) -> List[str]:
    errs: List[str] = list(counts.errors)
    if not counts.records and not errs:
        errs.append("No count records to calibrate against")
    if not flows:
        errs.append("At least one OD flow is needed")
    seen = set()
    nodes = graph.node_map()
    for f in flows:
        key = (f.origin, f.destination)
        if key in seen:
            errs.append(
                f"OD flow {f.origin}->{f.destination} appears twice; merge into one flow"
            )
        seen.add(key)
        if f.vehicles_per_hour < 0:
            errs.append(f"OD flow {f.origin}->{f.destination} has negative demand")
        for end in key:
            if end not in nodes:
                errs.append(
                    f"OD flow {f.origin}->{f.destination} uses unknown node {end!r}"
                )
    link_ids = set(graph.link_map())
    for g, ids in (options.speed_groups or {}).items():
        bad = [i for i in ids if i not in link_ids]
        if bad:
            errs.append(
                f"Speed group {g!r} lists unknown link(s): {', '.join(bad[:5])}"
            )
    if options.budget < 2:
        errs.append("The evaluation budget must be at least 2")
    if options.budget > MAX_BUDGET:
        errs.append(f"The evaluation budget is capped at {MAX_BUDGET}")
    if not (0 < options.min_step < options.initial_step < 1):
        errs.append("Steps must satisfy 0 < min_step < initial_step < 1")
    if not options.calibrate_demand and not options.calibrate_speed:
        errs.append("Nothing to calibrate: enable demand or speed")
    return errs


def apply_parameters(
    graph: RoadGraph,
    flows: Sequence[Flow],
    params: Mapping[str, float],
    options: FitOptions,
) -> Tuple[RoadGraph, List[Flow]]:
    new_flows = [
        Flow(
            f.origin,
            f.destination,
            f.vehicles_per_hour * params.get(demand_name(f), 1.0),
        )
        for f in flows
    ]
    factor: Dict[str, float] = {}
    for g, ids in speed_groups(graph, options).items():
        scale = params.get(f"speed:{g}", 1.0)
        for i in ids:
            factor[i] = scale
    new_links = [
        k.model_copy(update={"speed": k.speed * factor.get(k.id, 1.0)})
        for k in graph.links
    ]
    return graph.model_copy(update={"links": new_links}), new_flows


def simulate_link_flows(
    graph: RoadGraph,
    flows: Sequence[Flow],
    params: Mapping[str, float],
    options: FitOptions,
    sim: SimSettings,
) -> Dict[str, float]:
    g, f = apply_parameters(graph, flows, params, options)
    result = simulate_network(
        g,
        list(f),
        duration=sim.duration,
        seed=sim.seed,
        dt=sim.dt,
        signal_cycle=sim.signal_cycle,
    )
    return {
        k: v["passed"] * 3600.0 / sim.duration for k, v in result["perLink"].items()
    }


def objective(
    simulated: Mapping[str, float],
    observed: Mapping[str, float],
    params: Mapping[str, float],
    start: Mapping[str, float],
    regularisation: float,
) -> float:
    if not observed:
        return math.inf
    value = sum(geh(simulated.get(k, 0.0), o) ** 2 for k, o in observed.items()) / len(
        observed
    )
    if regularisation:
        value += regularisation * sum(
            math.log(params[k] / start[k]) ** 2 for k in params
        )
    return value


def _bounds(name: str, options: FitOptions) -> Tuple[float, float]:
    return options.demand_bounds if name.startswith("demand:") else options.speed_bounds


def _round_params(params: Mapping[str, float]) -> Dict[str, float]:
    return {k: round(v, 6) for k, v in sorted(params.items())}


def optimise(
    graph: RoadGraph,
    flows: Sequence[Flow],
    observed: Mapping[str, float],
    options: FitOptions,
    sim: SimSettings,
    start: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Run the search. Returns parameters, the objective trace and counters.
    ``start`` warm-starts from earlier parameters (missing names default to 1)."""
    names = default_parameters(graph, flows, options)
    begin = {
        k: min(
            max(float(start.get(k, 1.0)) if start else 1.0, _bounds(k, options)[0]),
            _bounds(k, options)[1],
        )
        for k in names
    }
    cache: Dict[Tuple[float, ...], Tuple[float, Dict[str, float]]] = {}
    evals = 0

    def evaluate(p: Mapping[str, float]) -> Tuple[float, Dict[str, float]]:
        nonlocal evals
        key = tuple(round(p[k], 9) for k in sorted(names))
        if key in cache:
            return cache[key]
        evals += 1
        sim_flows = simulate_link_flows(graph, flows, p, options, sim)
        out = (
            objective(sim_flows, observed, p, begin, options.regularisation),
            sim_flows,
        )
        cache[key] = out
        return out

    rng = random.Random(options.seed)
    current = dict(begin)
    best_obj, best_flows = evaluate(current)
    initial_obj = best_obj
    start_flows = best_flows
    trace = [
        {
            "evaluations": evals,
            "step": options.initial_step,
            "objective": round(best_obj, 6),
        }
    ]
    step = options.initial_step
    stop = "converged"
    sweeps = 0
    order = sorted(names)
    while True:
        if best_obj <= options.target_objective:
            stop = "target reached"
            break
        if step < options.min_step:
            stop = "converged"
            break
        sweeps += 1
        rng.shuffle(order)
        improved = False
        out_of_budget = False
        for name in order:
            lo, hi = _bounds(name, options)
            moves: List[Tuple[float]] = []
            for sign in (1.0, -1.0):
                cand = min(hi, max(lo, current[name] * (1.0 + sign * step)))
                if abs(cand - current[name]) > 1e-12 and cand not in [
                    m[0] for m in moves
                ]:
                    moves.append((cand,))
            best_move = None
            for (cand,) in moves:
                trial = dict(current)
                trial[name] = cand
                key = tuple(round(trial[k], 9) for k in sorted(names))
                if key not in cache and evals >= options.budget:
                    out_of_budget = True
                    break
                value, flows_out = evaluate(trial)
                if value < best_obj - 1e-12 and (
                    best_move is None or value < best_move[0]
                ):
                    best_move = (value, cand, flows_out)
            if best_move is not None:
                best_obj, current[name], best_flows = best_move
                improved = True
            if out_of_budget:
                break
        trace.append(
            {
                "evaluations": evals,
                "step": round(step, 6),
                "objective": round(best_obj, 6),
            }
        )
        if out_of_budget:
            stop = "budget exhausted"
            break
        if not improved:
            step *= options.shrink
    return {
        "parameters": current,
        "start": begin,
        "initialObjective": initial_obj,
        "objective": best_obj,
        "simulatedVph": best_flows,
        "startVph": start_flows,
        "evaluations": evals,
        "sweeps": sweeps,
        "stopReason": stop,
        "finalStep": step,
        "trace": trace,
    }


def _manifest(
    graph: RoadGraph,
    flows: Sequence[Flow],
    counts: CountSet,
    options: FitOptions,
    sim: SimSettings,
    start: Optional[Mapping[str, float]],
) -> Dict[str, Any]:
    inputs = {
        "graph": serialize_graph(graph),
        "flows": [[f.origin, f.destination, f.vehicles_per_hour] for f in flows],
        "countsSha256": counts.sha256,
        "countsRecords": len(counts.records),
        "countsIntervalSeconds": counts.interval_seconds,
        "options": {
            "budget": options.budget,
            "seed": options.seed,
            "initialStep": options.initial_step,
            "minStep": options.min_step,
            "shrink": options.shrink,
            "calibrateDemand": options.calibrate_demand,
            "calibrateSpeed": options.calibrate_speed,
            "speedGroups": speed_groups(graph, options)
            if options.calibrate_speed
            else None,
            "demandBounds": list(options.demand_bounds),
            "speedBounds": list(options.speed_bounds),
            "minObservedVph": options.min_observed_vph,
            "regularisation": options.regularisation,
            "targetObjective": options.target_objective,
            "criteria": options.criteria.__dict__,
        },
        "sim": sim.__dict__,
        "warmStart": _round_params(start) if start else None,
    }
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    return {
        "version": 1,
        "hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "graphSha256": hashlib.sha256(
            json.dumps(inputs["graph"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "note": "sha256 of the canonical JSON of every input; equal hash and code version give an equal report",
    }


def calibrate_network(
    graph: RoadGraph,
    flows: Sequence[Flow],
    counts: CountSet,
    options: FitOptions = FitOptions(),
    sim: SimSettings = SimSettings(),
    start: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Validate, optimise and return the calibration report (JSON-ready).

    Raises :class:`NetworkCalibrationError` with plain-language messages when
    the inputs are unusable. "Before" is the start point (all 1.0, or the
    warm start) so the report shows what the fit changed."""
    errors = validate_inputs(graph, flows, counts, options)
    if errors:
        raise NetworkCalibrationError(errors)
    observed = counts.link_flows_vph()
    link_ids = set(graph.link_map())
    observed = {k: v for k, v in observed.items() if k in link_ids}
    if not observed:
        raise NetworkCalibrationError(["No counted link exists in the network"])

    run = optimise(graph, flows, observed, options, sim, start)
    before_flows = run["startVph"]
    after_flows = run["simulatedVph"]
    before_rows = {
        r["linkId"]: r
        for r in per_link_rows(before_flows, observed, options.min_observed_vph)
    }
    after_rows = per_link_rows(after_flows, observed, options.min_observed_vph)
    per_link = []
    for row in after_rows:
        b = before_rows[row["linkId"]]
        per_link.append(
            {
                "linkId": row["linkId"],
                "observedVph": row["observedVph"],
                "before": {
                    k: b[k]
                    for k in ("simulatedVph", "residualVph", "geh", "percentError")
                },
                "after": {
                    k: row[k]
                    for k in ("simulatedVph", "residualVph", "geh", "percentError")
                },
            }
        )
    before = {
        "metrics": network_metrics(before_flows, observed, options.min_observed_vph),
        "gCal": g_cal_check(
            before_flows, observed, options.criteria, options.min_observed_vph
        ),
        "objective": round(run["initialObjective"], 6),
    }
    after = {
        "metrics": network_metrics(after_flows, observed, options.min_observed_vph),
        "gCal": g_cal_check(
            after_flows, observed, options.criteria, options.min_observed_vph
        ),
        "objective": round(run["objective"], 6),
    }
    names = sorted(run["parameters"])
    notes: List[str] = []
    if not after["gCal"]["passed"]:
        notes.append("G-CAL not met: " + "; ".join(after["gCal"]["reasons"]))
    if run["stopReason"] == "budget exhausted":
        notes.append("The evaluation budget ran out before the search converged")
    return {
        "format": REPORT_FORMAT,
        "version": REPORT_VERSION,
        "status": "PASS" if after["gCal"]["passed"] else "FAIL",
        "gate": "G-CAL",
        "before": before,
        "after": after,
        "parameters": {
            "fitted": _round_params(run["parameters"]),
            "start": _round_params(run["start"]),
            "bounds": {n: list(_bounds(n, options)) for n in names},
            "speedGroups": speed_groups(graph, options)
            if options.calibrate_speed
            else {},
            "fittedDemandVph": {
                f"{f.origin}->{f.destination}": round(
                    f.vehicles_per_hour * run["parameters"].get(demand_name(f), 1.0), 3
                )
                for f in flows
            },
        },
        "perLink": per_link,
        "optimiser": {
            "method": "coordinate-search",
            "seed": options.seed,
            "budget": options.budget,
            "evaluations": run["evaluations"],
            "sweeps": run["sweeps"],
            "stopReason": run["stopReason"],
            "finalStep": round(run["finalStep"], 6),
            "trace": run["trace"],
        },
        "simulation": dict(sim.__dict__),
        "provenance": {
            "counts": counts.provenance(),
            "network": {
                "name": graph.name,
                "source": graph.source,
                "nodes": len(graph.nodes),
                "links": len(graph.links),
            },
            "countedLinks": len(observed),
            "linksWithoutCounts": len(link_ids) - len(observed),
        },
        "thresholds": {
            "gCal": dict(options.criteria.__dict__),
            "minObservedVph": options.min_observed_vph,
            "gehNote": "GEH < 5 on >= 85% of links (UK DMRB/TfL guidance); placeholder for the agreed G-CAL error (D1)",
        },
        "manifest": _manifest(graph, flows, counts, options, sim, start),
        "notes": notes,
    }
