"""Problem-independent NSGA-II pieces: constrained domination, non-dominated sorting, crowding distance,
binary tournament, and hypervolume (for tests and reporting). All objectives are minimised."""

from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple

Objectives = Tuple[float, ...]


def dominates(a: Objectives, b: Objectives) -> bool:
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def constrained_dominates(a: Optional[Objectives], b: Optional[Objectives]) -> bool:
    """``None`` is an infeasible point (hard constraint violated): any feasible point dominates it."""
    if a is None:
        return False
    if b is None:
        return True
    return dominates(a, b)


def non_dominated_sort(points: Sequence[Optional[Objectives]]) -> List[List[int]]:
    """Fronts of indexes, best first (Deb's fast non-dominated sort). Infeasible points form the last front."""
    n = len(points)
    dominated_by: List[List[int]] = [[] for _ in range(n)]
    counts = [0] * n
    fronts: List[List[int]] = [[]]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if constrained_dominates(points[i], points[j]):
                dominated_by[i].append(j)
            elif constrained_dominates(points[j], points[i]):
                counts[i] += 1
        if counts[i] == 0:
            fronts[0].append(i)
    k = 0
    while fronts[k]:
        nxt: List[int] = []
        for i in fronts[k]:
            for j in dominated_by[i]:
                counts[j] -= 1
                if counts[j] == 0:
                    nxt.append(j)
        k += 1
        fronts.append(sorted(nxt))
    return [sorted(f) for f in fronts if f]


def crowding_distance(
    points: Sequence[Objectives], front: Sequence[int]
) -> dict[int, float]:
    distance = {i: 0.0 for i in front}
    if len(front) <= 2:
        return {i: float("inf") for i in front}
    m = len(points[front[0]])
    for k in range(m):
        ordered = sorted(front, key=lambda i: (points[i][k], i))
        low, high = points[ordered[0]][k], points[ordered[-1]][k]
        distance[ordered[0]] = distance[ordered[-1]] = float("inf")
        span = high - low
        if span <= 0:
            continue
        for pos in range(1, len(ordered) - 1):
            distance[ordered[pos]] += (
                points[ordered[pos + 1]][k] - points[ordered[pos - 1]][k]
            ) / span
    return distance


def rank_and_crowding(
    points: Sequence[Optional[Objectives]],
) -> Tuple[List[int], List[float]]:
    """Per point: its front rank and crowding distance (infeasible points get the worst rank, 0 crowding)."""
    rank = [0] * len(points)
    crowd = [0.0] * len(points)
    for r, front in enumerate(non_dominated_sort(points)):
        feasible = [i for i in front if points[i] is not None]
        if feasible:
            dist = crowding_distance([p or () for p in points], feasible)
        else:
            dist = {}
        for i in front:
            rank[i] = r
            crowd[i] = dist.get(i, 0.0)
    return rank, crowd


def select_survivors(points: Sequence[Optional[Objectives]], size: int) -> List[int]:
    """The ``size`` best indexes: by front, then by crowding distance (ties by index, so deterministic)."""
    chosen: List[int] = []
    for front in non_dominated_sort(points):
        feasible = [i for i in front if points[i] is not None]
        others = [i for i in front if points[i] is None]
        if len(chosen) + len(front) <= size:
            chosen.extend(feasible + others)
            continue
        dist = (
            crowding_distance([p or () for p in points], feasible) if feasible else {}
        )
        ordered = sorted(feasible, key=lambda i: (-dist[i], i)) + others
        chosen.extend(ordered[: size - len(chosen)])
        break
    return chosen


def tournament(rng: random.Random, rank: Sequence[int], crowd: Sequence[float]) -> int:
    a, b = rng.randrange(len(rank)), rng.randrange(len(rank))
    if rank[a] != rank[b]:
        return a if rank[a] < rank[b] else b
    if crowd[a] != crowd[b]:
        return a if crowd[a] > crowd[b] else b
    return min(a, b)


def hypervolume_2d(
    points: Sequence[Objectives], reference: Tuple[float, float]
) -> float:
    """Area dominated by ``points`` (two minimised objectives) and bounded by ``reference``."""
    front = sorted(
        {(p[0], p[1]) for p in points if p[0] < reference[0] and p[1] < reference[1]}
    )
    area, best_y = 0.0, reference[1]
    for x, y in front:
        if y < best_y:
            area += (reference[0] - x) * (best_y - y)
            best_y = y
    return area
