"""Cooperative vs non-cooperative experiments over a road graph (F19).

For each seed the network is simulated once (the non-cooperative baseline,
unchanged ``simulate_network``); each penetration rate and channel setting is
then evaluated on that run's vehicle traces with the behavioural model in
``behaviour.py`` (read its assumptions before reading a number). Because every
scenario shares the seed's baseline, the comparison is paired by seed and is
analysed with ``src.uncertainty.comparison``. The cooperative side is ``a``, so
a negative difference (delay, stops, fuel) is a benefit.
"""

from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Sequence

from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow
from src.uncertainty.comparison import compare_paired, verdict
from src.v2x.behaviour import (
    CO2_KG_PER_L,
    CRUISE_L_PER_S,
    IDLE_L_PER_S,
    STOP_EQUIV_IDLE_S,
    STOP_MIN_WAIT,
    BehaviourConfig,
    Hazard,
    Outcome,
    evaluate,
)
from src.v2x.channel import Channel, ChannelConfig
from src.v2x.traces import VehicleTrace, run_traced

METRICS: Sequence[str] = ("delaySeconds", "stops", "fuelLitres", "co2Kg")
DEFAULT_PENETRATIONS: Sequence[float] = (0.0, 0.25, 0.5, 0.75, 1.0)
ASSUMPTIONS: Sequence[str] = (
    "Baseline is the unmodified mesoscopic run; the cooperative outcome is an overlay on its vehicle traces, not a re-simulation.",
    "No second-order effects: queues, discharge rates and signal timing of other vehicles are unchanged by connected vehicles.",
    "Signals are fixed-time with equal phases and connected vehicles know the cycle; SPaT age costs lead time, not accuracy.",
    "GLOSA lets a vehicle absorb red time down to a minimum speed fraction; waiting behind a queue is not reduced; rolling slowly still counts as delay.",
    "Hazard detours are free-flow costed with the original remainder's waits; diverted traffic creates no congestion.",
    "Fuel and CO2 are relative proxies of excess over free flow, not calibrated emissions.",
)


@dataclass(frozen=True)
class SensitivitySpec:
    penetration: float = 1.0
    latencies_ms: Sequence[float] = (0.0, 100.0, 500.0, 2000.0, 5000.0)
    loss_probabilities: Sequence[float] = (0.0, 0.1, 0.3, 0.6, 0.9)


class _Seed:
    def __init__(self, seed: int, traces: List[VehicleTrace], result: Dict[str, Any]):
        self.seed = seed
        self.traces = traces
        self.result = result


def _paired(
    coop: Sequence[float], base: Sequence[float], method: str, confidence: float
) -> Optional[Dict[str, Any]]:
    if len(coop) < 2:
        return None
    cmp = compare_paired(coop, base, method=method, confidence=confidence, seed=0)
    out = cmp.to_dict()
    out["verdict"] = verdict(cmp, lower_is_better=True)
    return out


def _agg(outs: Sequence[Outcome]) -> Dict[str, float]:
    keys = outs[0].per_vehicle().keys() if outs else METRICS
    return {k: sum(o.per_vehicle()[k] for o in outs) / max(1, len(outs)) for k in keys}


def _summarise(
    coop: Sequence[Outcome], base: Sequence[Outcome], method: str, confidence: float
) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    cm, bm = _agg(coop), _agg(base)
    for m in METRICS:
        cv = [o.per_vehicle()[m] for o in coop]
        bv = [o.per_vehicle()[m] for o in base]
        change = cm[m] - bm[m]
        metrics[m] = {
            "baseline": bm[m],
            "cooperative": cm[m],
            "change": change,
            "changePct": (100.0 * change / bm[m]) if bm[m] else None,
            "paired": _paired(cv, bv, method, confidence),
        }
    comms_n = sum(o.spat_attempts + o.hazard_attempts for o in coop)
    delivered = sum(o.spat_delivered + o.hazard_delivered for o in coop)
    used = sum(o.spat_used + o.hazard_used for o in coop)
    age = sum(o.age_sum_s for o in coop)
    return {
        "metrics": metrics,
        "connectedVehicles": sum(o.connected for o in coop),
        "vehicles": sum(o.vehicles for o in coop),
        "stopsAvoided": sum(o.stops_avoided for o in coop),
        "reroutes": sum(o.reroutes for o in coop),
        "messageDeliveryRatio": delivered / comms_n if comms_n else None,
        "meanMessageAgeAtUseSeconds": age / used if used else None,
        "messagesAttempted": comms_n,
        "messagesDelivered": delivered,
        "messagesUsed": used,
    }


def run_experiment(
    graph: RoadGraph,
    flows: Sequence[Flow],
    *,
    duration: float = 600.0,
    seeds: Sequence[int] = (1, 2, 3, 4, 5),
    penetrations: Sequence[float] = DEFAULT_PENETRATIONS,
    channel: ChannelConfig = ChannelConfig(),
    behaviour: BehaviourConfig = BehaviourConfig(),
    hazard: Optional[Hazard] = None,
    sensitivity: Optional[SensitivitySpec] = None,
    confidence: float = 0.95,
    method: str = "paired_t",
) -> Dict[str, Any]:
    """Run the experiment. ``seeds`` drives both the network run and the
    channel, so the result is a function of its arguments alone."""
    if hazard is not None and hazard.link_id not in graph.link_map():
        raise ValueError(f"hazard link {hazard.link_id!r} is not in the graph")
    runs: List[_Seed] = []
    for sd in seeds:
        result, traces = run_traced(graph, flows, duration, sd)
        runs.append(_Seed(sd, traces, result))

    def outcomes(p: float, cfg: ChannelConfig) -> List[Outcome]:
        return [
            evaluate(
                graph,
                r.traces,
                penetration=p,
                channel=Channel(cfg, r.seed),
                seed=r.seed,
                config=behaviour,
                hazard=hazard,
            )
            for r in runs
        ]

    base = outcomes(0.0, channel)
    sweep: List[Dict[str, Any]] = []
    for p in penetrations:
        coop = outcomes(p, channel) if p > 0 else base
        row = _summarise(coop, base, method, confidence)
        row["penetration"] = p
        sweep.append(row)

    out: Dict[str, Any] = {
        "format": "urbanflow-v2x-experiment",
        "version": 1,
        "baseline": {
            "perSeed": [
                {
                    "seed": r.seed,
                    "vehicles": b.vehicles,
                    "completedByNetwork": r.result["completed"],
                    **b.per_vehicle(),
                }
                for r, b in zip(runs, base)
            ],
            "mean": _agg(base),
        },
        "sweep": sweep,
        "provenance": {
            "seeds": list(seeds),
            "durationSeconds": duration,
            "penetrations": list(penetrations),
            "channel": channel.to_dict(),
            "behaviour": behaviour.to_dict(),
            "hazard": (
                None
                if hazard is None
                else {
                    "linkId": hazard.link_id,
                    "startSeconds": hazard.start_s,
                    "delaySeconds": hazard.delay_s,
                }
            ),
            "confidence": confidence,
            "method": method,
            "constants": {
                "stopMinWaitSeconds": STOP_MIN_WAIT,
                "idleLitresPerSecond": IDLE_L_PER_S,
                "standingStartIdleEquivalentSeconds": STOP_EQUIV_IDLE_S,
                "cruiseLitresPerSecond": CRUISE_L_PER_S,
                "co2KgPerLitre": CO2_KG_PER_L,
            },
            "assumptions": list(ASSUMPTIONS),
        },
    }
    if sensitivity is not None:
        out["sensitivity"] = _sensitivity(
            sensitivity, channel, outcomes, base, method, confidence
        )
    return out


def _sensitivity(
    spec: SensitivitySpec,
    channel: ChannelConfig,
    outcomes: Any,
    base: Sequence[Outcome],
    method: str,
    confidence: float,
) -> Dict[str, Any]:
    cells: List[Dict[str, Any]] = []
    for lat in spec.latencies_ms:
        for loss in spec.loss_probabilities:
            cfg = replace(channel, latency_ms=lat, loss_probability=loss)
            summ = _summarise(outcomes(spec.penetration, cfg), base, method, confidence)
            d, s = summ["metrics"]["delaySeconds"], summ["metrics"]["stops"]
            cells.append(
                {
                    "latencyMs": lat,
                    "lossProbability": loss,
                    "delayBenefitSeconds": -d["change"],
                    "delayBenefitPct": (
                        None if d["changePct"] is None else -d["changePct"]
                    ),
                    "stopsAvoidedPerVehicle": -s["change"],
                    "stopsReductionPct": (
                        None if s["changePct"] is None else -s["changePct"]
                    ),
                    "deliveryRatio": summ["messageDeliveryRatio"],
                    "meanAgeAtUseSeconds": summ["meanMessageAgeAtUseSeconds"],
                    "delayPaired": d["paired"],
                }
            )
    return {
        "penetration": spec.penetration,
        "latenciesMs": list(spec.latencies_ms),
        "lossProbabilities": list(spec.loss_probabilities),
        "note": "benefit = baseline minus cooperative (positive is better)",
        "cells": cells,
    }
