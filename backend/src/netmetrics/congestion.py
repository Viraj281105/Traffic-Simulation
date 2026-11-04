"""Congestion propagation analysis (F5, W42): per-link occupancy and queue
series, spillback events, and the order and speed at which congestion spreads
between links. The result is plain JSON, shaped for a links x time heatmap.

A link is *congested* when its occupancy ratio (vehicles / storage) stays at
or above ``threshold`` for ``min_hold_seconds``; its onset is the start of that
run. *Spillback* is a run of steps in which the link's head vehicle is ready
but the next link is full."""

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.netmetrics.metrics import _r, steps_per_bucket
from src.netmetrics.recorder import Recorder, bucketize, run_recorded
from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow

CONGESTION_FORMAT = "urbanflow-congestion"


def _runs(mask: np.ndarray, min_len: int) -> List[Tuple[int, int]]:
    """(start, end exclusive) of runs of True of at least ``min_len``."""
    if not mask.any():
        return []
    padded = np.concatenate(([False], mask, [False])).astype(np.int8)
    edge = np.diff(padded)
    starts, ends = np.flatnonzero(edge == 1), np.flatnonzero(edge == -1)
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e - s >= min_len]


def _onsets(ratio: np.ndarray, threshold: float, hold: int) -> np.ndarray:
    """First step at which each link starts a run of ``hold`` steps at or
    above ``threshold``; -1 when it never does."""
    above = (ratio >= threshold).astype(np.int32)
    csum = np.vstack(
        [np.zeros((1, above.shape[1]), dtype=np.int32), np.cumsum(above, axis=0)]
    )
    if above.shape[0] < hold:
        return np.full(above.shape[1], -1, dtype=np.int64)
    ok = (csum[hold:] - csum[:-hold]) == hold  # ok[i]: steps i .. i+hold-1 all above
    first = ok.argmax(axis=0)
    return np.where(ok.any(axis=0), first, -1).astype(np.int64)


def analyse_congestion(
    graph: RoadGraph,
    result: Dict[str, Any],
    rec: Recorder,
    bucket_seconds: float = 30.0,
    threshold: float = 0.3,
    min_hold_seconds: float = 10.0,
    min_spillback_seconds: float = 5.0,
) -> Dict[str, Any]:
    dt = rec.dt
    ids = rec.link_ids
    links = graph.link_map()
    nodes = graph.node_map()
    spb = steps_per_bucket(bucket_seconds, dt)
    hold = max(1, int(math.ceil(min_hold_seconds / dt)))
    ratio = rec.occ / rec.capacity  # (steps, links)
    onset_step = _onsets(ratio, threshold, hold)
    congested = onset_step >= 0

    # --- spread front -------------------------------------------------
    mid = {
        k: (
            (nodes[links[k].from_].x + nodes[links[k].to].x) / 2.0,
            (nodes[links[k].from_].y + nodes[links[k].to].y) / 2.0,
        )
        for k in ids
    }
    onset_t = {
        k: (float(onset_step[j]) * dt if congested[j] else None)
        for j, k in enumerate(ids)
    }
    by_node: Dict[str, List[str]] = {}
    for k in ids:
        by_node.setdefault(links[k].from_, []).append(k)
        by_node.setdefault(links[k].to, []).append(k)
    order_ids = sorted(
        (k for k in ids if onset_t[k] is not None), key=lambda k: (onset_t[k], k)
    )
    rank = {k: i + 1 for i, k in enumerate(order_ids)}
    front: List[Dict[str, Any]] = []
    depth: Dict[str, int] = {}
    speeds: Dict[str, List[float]] = {"upstream": [], "downstream": [], "lateral": []}
    for k in order_ids:
        lk = links[k]
        cands = sorted(
            {
                o
                for n in (lk.from_, lk.to)
                for o in by_node[n]
                if o != k and onset_t[o] is not None and onset_t[o] < onset_t[k]  # type: ignore[operator]
            },
            key=lambda o: (-onset_t[o], o),  # type: ignore[operator]
        )
        entry: Dict[str, Any] = {
            "link": k,
            "rank": rank[k],
            "onsetSeconds": _r(onset_t[k], 2),  # type: ignore[arg-type]
            "parent": None,
            "direction": None,
            "hops": 0,
            "speedMps": None,
        }
        if cands:
            p = cands[0]
            pl = links[p]
            if pl.from_ == lk.to and pl.to == lk.from_:
                direction = "lateral"  # the opposite carriageway
            elif pl.from_ == lk.to:
                direction = (
                    "upstream"  # downstream link jammed first: queue grew backwards
                )
            elif pl.to == lk.from_:
                direction = "downstream"
            else:
                direction = "lateral"
            dist = math.hypot(mid[k][0] - mid[p][0], mid[k][1] - mid[p][1])
            dtime = onset_t[k] - onset_t[p]  # type: ignore[operator]
            speed = dist / dtime if dtime > 0 else None
            depth[k] = depth[p] + 1
            entry.update(
                {
                    "parent": p,
                    "direction": direction,
                    "hops": depth[k],
                    "speedMps": _r(speed, 3) if speed is not None else None,
                }
            )
            if speed is not None:
                speeds[direction].append(speed)
        else:
            depth[k] = 0
        front.append(entry)

    def _mean(v: List[float]) -> Optional[float]:
        return _r(sum(v) / len(v), 3) if v else None

    all_speeds = [s for v in speeds.values() for s in v]
    origin = order_ids[0] if order_ids else None
    spread = {
        "congestedLinks": len(order_ids),
        "totalLinks": len(ids),
        "origin": origin,
        "order": front,
        "durationSeconds": (
            _r(onset_t[order_ids[-1]] - onset_t[order_ids[0]], 2) if order_ids else 0.0  # type: ignore[operator]
        ),
        "maxHops": max(depth.values()) if depth else 0,
        "meanSpeedMps": _mean(all_speeds),
        "upstreamSpeedMps": _mean(speeds["upstream"]),
        "downstreamSpeedMps": _mean(speeds["downstream"]),
        "maxDistanceFromOriginMeters": (
            _r(
                max(
                    math.hypot(mid[k][0] - mid[origin][0], mid[k][1] - mid[origin][1])
                    for k in order_ids
                ),
                1,
            )
            if origin
            else 0.0
        ),
    }

    # --- spillback ----------------------------------------------------
    min_spill = max(1, int(math.ceil(min_spillback_seconds / dt)))
    events: List[Dict[str, Any]] = []
    for j, k in enumerate(ids):
        col = rec.blocked[:, j]
        for s, e in _runs(col >= 0, min_spill):
            seg = col[s:e]
            seg = seg[seg >= 0]
            blocker = int(np.bincount(seg).argmax())
            events.append(
                {
                    "link": k,
                    "blockedBy": ids[blocker],
                    "startSeconds": _r(s * dt, 2),
                    "endSeconds": _r(e * dt, 2),
                    "durationSeconds": _r((e - s) * dt, 2),
                    "peakOccupancyRatio": _r(ratio[s:e, j].max()),
                    "chainLength": 1,
                }
            )
    events.sort(key=lambda ev: (ev["startSeconds"], ev["link"]))
    # chainLength: how many links back the blockage reaches (the blocker is
    # itself blocked while this event runs). Guarded against gridlock cycles.
    by_link: Dict[str, List[Dict[str, Any]]] = {}
    for ev in events:
        by_link.setdefault(ev["link"], []).append(ev)

    def _chain(ev: Dict[str, Any], seen: Tuple[str, ...]) -> int:
        best = 1
        for o in by_link.get(ev["blockedBy"], []):
            if (
                o["link"] in seen
                or o["startSeconds"] >= ev["endSeconds"]
                or o["endSeconds"] <= ev["startSeconds"]
            ):
                continue
            best = max(best, 1 + _chain(o, seen + (o["link"],)))
        return best

    for ev in events:
        ev["chainLength"] = _chain(ev, (ev["link"],))
    spill_links = sorted({ev["link"] for ev in events})
    spillback = {
        "events": events,
        "summary": {
            "events": len(events),
            "linksAffected": len(spill_links),
            "links": spill_links,
            "totalBlockedSeconds": _r(sum(ev["durationSeconds"] for ev in events), 2),
            "longestSeconds": _r(
                max((ev["durationSeconds"] for ev in events), default=0.0), 2
            ),
            "maxChainLength": max((ev["chainLength"] for ev in events), default=0),
            "firstStartSeconds": events[0]["startSeconds"] if events else None,
        },
    }

    # --- heatmap (links x time buckets), rows in congestion order -------
    row_order = order_ids + sorted(k for k in ids if onset_t[k] is None)
    cols = [rec.index[k] for k in row_order]
    occ_b = bucketize(ratio, spb).T[cols]
    que_b = bucketize(rec.queue.astype(np.float64), spb).T[cols]
    blk_b = bucketize((rec.blocked >= 0).astype(np.float64), spb).T[cols]
    nb = occ_b.shape[1]
    heatmap = {
        "metric": "occupancyRatio",
        "bucketSeconds": _r(spb * dt, 2),
        "bucketStarts": [_r(b * spb * dt, 2) for b in range(nb)],
        "linkIds": row_order,
        "values": np.round(occ_b, 4).tolist(),
        "queue": np.round(que_b, 3).tolist(),
        "blockedFraction": np.round(blk_b, 4).tolist(),
    }
    link_rows = [
        {
            "id": k,
            "from": links[k].from_,
            "to": links[k].to,
            "name": links[k].name,
            "length": links[k].length,
            "lanes": links[k].lanes,
            "capacity": int(rec.capacity[rec.index[k]]),
            "onsetSeconds": (
                _r(onset, 2) if (onset := onset_t[k]) is not None else None
            ),
            "rank": rank.get(k),
            "peakOccupancyRatio": _r(float(ratio[:, rec.index[k]].max())),
        }
        for k in row_order
    ]
    return {
        "format": CONGESTION_FORMAT,
        "version": 1,
        "seed": result["seed"],
        "duration": result["duration"],
        "threshold": threshold,
        "minHoldSeconds": _r(hold * dt, 2),
        "inModelOnly": True,
        "run": {
            "generated": result["generated"],
            "entered": result["entered"],
            "completed": result["completed"],
            "active": result["active"],
            "blockedAtEntry": result["blockedAtEntry"],
            "conserved": result["conserved"],
        },
        "links": link_rows,
        "heatmap": heatmap,
        "spillback": spillback,
        "spread": spread,
    }


def congestion_analysis(
    graph: RoadGraph,
    flows: List[Flow],
    duration: float = 600.0,
    seed: int = 1,
    dt: float = 1.0,
    bucket_seconds: float = 30.0,
    threshold: float = 0.3,
    min_hold_seconds: float = 10.0,
    min_spillback_seconds: float = 5.0,
) -> Dict[str, Any]:
    """Run the network and analyse how congestion forms and spreads."""
    result, rec = run_recorded(graph, flows, duration, seed, dt)
    return analyse_congestion(
        graph,
        result,
        rec,
        bucket_seconds,
        threshold,
        min_hold_seconds,
        min_spillback_seconds,
    )
