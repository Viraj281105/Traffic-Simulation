"""Network-wide metrics for a ``urbanflow-graph`` run (F5, W41).

Everything is in-model: the mesoscopic engine of ``src.networks`` is not
calibrated, so these are comparisons between scenarios, not predictions.
"""

from typing import Any, Dict, List

import numpy as np

from src.netmetrics.recorder import Recorder, bucketize, run_recorded
from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow

METRICS_FORMAT = "urbanflow-network-metrics"


def steps_per_bucket(bucket_seconds: float, dt: float) -> int:
    return max(1, int(round(bucket_seconds / dt)))


def _r(x: float, nd: int = 4) -> float:
    return round(float(x), nd)


def compute_metrics(
    graph: RoadGraph,
    result: Dict[str, Any],
    rec: Recorder,
    bucket_seconds: float = 30.0,
    per_link_diagram: bool = False,
) -> Dict[str, Any]:
    """Metrics from a finished recorded run. JSON-serialisable."""
    dt, duration = rec.dt, result["duration"]
    spb = steps_per_bucket(bucket_seconds, dt)
    ids = rec.link_ids
    links = graph.link_map()
    nodes = graph.node_map()
    length = np.array([links[k].length for k in ids])
    lanes = np.array([links[k].lanes for k in ids], dtype=np.float64)
    lane_m = length * lanes  # lane-metres of storage per link

    occ = rec.occ.astype(np.float64)
    que = rec.queue.astype(np.float64)
    passed_step = np.diff(rec.cum, axis=0, prepend=0).astype(np.float64)
    mean_occ = occ.mean(axis=0)
    mean_que = que.mean(axis=0)
    blocked_steps = (rec.blocked >= 0).sum(axis=0)

    per_link: Dict[str, Any] = {}
    for j, lid in enumerate(ids):
        passed = int(rec.cum[-1, j])
        per_link[lid] = {
            "passed": passed,
            "flowVph": _r(passed / duration * 3600.0, 2),
            "capacity": int(rec.capacity[j]),
            "meanOccupancy": _r(mean_occ[j]),
            "peakOccupancy": int(rec.occ[:, j].max()),
            "meanOccupancyRatio": _r(mean_occ[j] / rec.capacity[j]),
            "meanQueue": _r(mean_que[j]),
            "peakQueue": int(rec.queue[:, j].max()),
            "densityVehPerKmLane": _r(mean_occ[j] / lane_m[j] * 1000.0, 3),
            "blockedSeconds": _r(blocked_steps[j] * dt, 2),
        }

    incoming = graph.incoming()
    col = rec.index
    per_node: Dict[str, Any] = {}
    for nid in sorted(nodes):
        cols = [col[k.id] for k in incoming[nid]]
        passed = int(result["perNode"][nid]["passed"])
        entry: Dict[str, Any] = {
            "kind": nodes[nid].kind,
            "passed": passed,
            "throughputVph": _r(passed / duration * 3600.0, 2),
        }
        if cols:
            tot_occ, tot_que = occ[:, cols].sum(axis=1), que[:, cols].sum(axis=1)
            entry.update(
                {
                    "meanOccupancy": _r(tot_occ.mean()),
                    "peakOccupancy": int(tot_occ.max()),
                    "meanQueue": _r(tot_que.mean()),
                    "peakQueue": int(tot_que.max()),
                }
            )
        else:
            entry.update(
                {
                    "meanOccupancy": 0.0,
                    "peakOccupancy": 0,
                    "meanQueue": 0.0,
                    "peakQueue": 0,
                }
            )
        per_node[nid] = entry

    # Time series per bucket.
    exit_cols = [j for j, k in enumerate(ids) if nodes[links[k].to].kind == "gate"]
    occ_b = bucketize(occ.sum(axis=1), spb)
    que_b = bucketize(que.sum(axis=1), spb)
    exit_b = (
        bucketize(passed_step[:, exit_cols].sum(axis=1), spb, "sum")
        if exit_cols
        else np.zeros_like(occ_b)
    )
    # Fundamental diagram: lane-length weighted density (veh/km/lane) and flow
    # (veh/h/lane) over the whole network, one point per bucket.
    tot_lane_m = float(lane_m.sum())
    dens_b = bucketize(occ.sum(axis=1), spb) / tot_lane_m * 1000.0
    pass_b = bucketize(passed_step * length, spb, "sum").sum(axis=1)
    bucket_len = np.diff(np.append(np.arange(0, rec.steps, spb), rec.steps)) * dt
    flow_b = pass_b / (tot_lane_m * bucket_len) * 3600.0
    starts = (np.arange(len(occ_b)) * spb * dt).tolist()
    series = [
        {
            "tStart": _r(starts[b], 2),
            "vehiclesInNetwork": _r(occ_b[b], 2),
            "queuedVehicles": _r(que_b[b], 2),
            "exitedVehicles": int(exit_b[b]),
        }
        for b in range(len(occ_b))
    ]
    points = [
        {
            "tStart": _r(starts[b], 2),
            "densityVehPerKmLane": _r(dens_b[b], 3),
            "flowVehPerHourLane": _r(flow_b[b], 2),
        }
        for b in range(len(dens_b))
    ]
    peak = max(points, key=lambda p: p["flowVehPerHourLane"]) if points else None
    diagram: Dict[str, Any] = {
        "bucketSeconds": _r(spb * dt, 2),
        "points": points,
        "peakFlow": (
            {
                "flowVehPerHourLane": peak["flowVehPerHourLane"],
                "densityVehPerKmLane": peak["densityVehPerKmLane"],
            }
            if peak
            else None
        ),
    }
    if per_link_diagram:
        occ_lb = bucketize(occ, spb)
        pas_lb = bucketize(passed_step, spb, "sum")
        diagram["perLink"] = {
            lid: [
                {
                    "densityVehPerKmLane": _r(occ_lb[b, j] / lane_m[j] * 1000.0, 3),
                    "flowVehPerHourLane": _r(
                        pas_lb[b, j] / lanes[j] / bucket_len[b] * 3600.0, 2
                    ),
                }
                for b in range(occ_lb.shape[0])
            ]
            for j, lid in enumerate(ids)
        }

    completed = result["completed"]
    total_delay = result["totalDelaySeconds"]
    return {
        "format": METRICS_FORMAT,
        "version": 1,
        "seed": result["seed"],
        "duration": duration,
        "bucketSeconds": _r(spb * dt, 2),
        "inModelOnly": True,
        "network": {
            "generated": result["generated"],
            "entered": result["entered"],
            "blockedAtEntry": result["blockedAtEntry"],
            "completed": completed,
            "active": result["active"],
            "conserved": result["conserved"],
            "throughputVph": _r(completed / duration * 3600.0, 2),
            "totalDelaySeconds": total_delay,
            "totalDelayHours": _r(total_delay / 3600.0, 4),
            "meanDelaySeconds": result["meanDelaySeconds"],
            "meanTravelSeconds": result["meanTravelSeconds"],
            "totalTravelSeconds": result["totalTravelSeconds"],
            "meanVehiclesInNetwork": _r(occ.sum(axis=1).mean(), 2),
            "meanQueuedVehicles": _r(que.sum(axis=1).mean(), 2),
            "blockedLinkSeconds": _r(float(blocked_steps.sum()) * dt, 2),
            "unroutable": result["unroutable"],
        },
        "perLink": per_link,
        "perNode": per_node,
        "series": series,
        "fundamentalDiagram": diagram,
        "notes": [
            "Delay counts vehicles that completed their trip; vehicles still in the network at the end are not included.",
            "Mesoscopic, uncalibrated model: compare scenarios, do not read these as predictions.",
        ],
    }


def network_metrics(
    graph: RoadGraph,
    flows: List[Flow],
    duration: float = 600.0,
    seed: int = 1,
    dt: float = 1.0,
    bucket_seconds: float = 30.0,
    per_link_diagram: bool = False,
) -> Dict[str, Any]:
    """Run the network and return its network-wide metrics."""
    result, rec = run_recorded(graph, flows, duration, seed, dt)
    return compute_metrics(graph, result, rec, bucket_seconds, per_link_diagram)
