"""Fit metrics between simulated and observed link flows (veh/h).

GEH = sqrt(2 (M - C)^2 / (M + C)) with M modelled and C counted hourly
volumes (0 when both are 0). RMSE is in veh/h. MAPE skips links whose
observed flow is below ``min_observed_vph`` (a tiny denominator would make a
meaningless huge percentage); the number skipped is reported. R^2 is
``1 - SS_res / SS_tot`` over links and is None when observed flow has no
variance (it can be negative for a model worse than the mean).

G-CAL default (see :class:`GCalCriteria`): GEH < 5 on at least 85 % of
links. That is the UK DMRB / TfL guidance for assignment models and is the
placeholder for the "agreed error" of gate G-CAL until the product owner
confirms a threshold (decision D1); pass a different :class:`GCalCriteria`
to change it. The thresholds applied are returned inside every result.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional

GEH_LIMIT = 5.0
GEH_FRACTION = 0.85
MIN_OBSERVED_VPH = 10.0


def geh(modelled: float, observed: float) -> float:
    total = modelled + observed
    if total <= 0:
        return 0.0
    return math.sqrt(2.0 * (modelled - observed) ** 2 / total)


@dataclass(frozen=True)
class GCalCriteria:
    """Pass rule for gate G-CAL.

    ``geh_limit`` / ``min_fraction``: at least ``min_fraction`` of links must
    have GEH below ``geh_limit``. Optional extras ``max_mape`` (percent) and
    ``max_rmse`` (veh/h) must also hold when given: this is the "agreed error
    threshold passed in".
    """

    geh_limit: float = GEH_LIMIT
    min_fraction: float = GEH_FRACTION
    max_mape: Optional[float] = None
    max_rmse: Optional[float] = None


def per_link_rows(
    simulated: Mapping[str, float],
    observed: Mapping[str, float],
    min_observed_vph: float = MIN_OBSERVED_VPH,
) -> List[Dict[str, Any]]:
    rows = []
    for link in sorted(observed):
        o, s = float(observed[link]), float(simulated.get(link, 0.0))
        resid = s - o
        rows.append(
            {
                "linkId": link,
                "observedVph": round(o, 3),
                "simulatedVph": round(s, 3),
                "residualVph": round(resid, 3),
                "geh": round(geh(s, o), 4),
                "percentError": (
                    round(100.0 * resid / o, 3) if o >= min_observed_vph else None
                ),
            }
        )
    return rows


def network_metrics(
    simulated: Mapping[str, float],
    observed: Mapping[str, float],
    min_observed_vph: float = MIN_OBSERVED_VPH,
) -> Dict[str, Any]:
    links = sorted(observed)
    n = len(links)
    if n == 0:
        return {
            "links": 0,
            "rmseVph": None,
            "mapePercent": None,
            "r2": None,
            "meanGeh": None,
            "gehUnderLimitFraction": None,
            "mapeLinks": 0,
            "mapeSkippedLinks": 0,
            "minObservedVph": min_observed_vph,
        }
    obs = [float(observed[k]) for k in links]
    sim = [float(simulated.get(k, 0.0)) for k in links]
    sse = sum((s - o) ** 2 for s, o in zip(sim, obs))
    rmse = math.sqrt(sse / n)
    pct = [abs(s - o) / o * 100.0 for s, o in zip(sim, obs) if o >= min_observed_vph]
    mean_obs = sum(obs) / n
    sst = sum((o - mean_obs) ** 2 for o in obs)
    gehs = [geh(s, o) for s, o in zip(sim, obs)]
    return {
        "links": n,
        "rmseVph": round(rmse, 4),
        "mapePercent": round(sum(pct) / len(pct), 4) if pct else None,
        "r2": round(1.0 - sse / sst, 6) if sst > 0 else None,
        "meanGeh": round(sum(gehs) / n, 4),
        "gehUnderLimitFraction": round(sum(1 for g in gehs if g < GEH_LIMIT) / n, 4),
        "mapeLinks": len(pct),
        "mapeSkippedLinks": n - len(pct),
        "minObservedVph": min_observed_vph,
    }


def g_cal_check(
    simulated: Mapping[str, float],
    observed: Mapping[str, float],
    criteria: GCalCriteria = GCalCriteria(),
    min_observed_vph: float = MIN_OBSERVED_VPH,
) -> Dict[str, Any]:
    """Gate G-CAL: does the simulated flow match the counts within criteria?"""
    n = len(observed)
    metrics = network_metrics(simulated, observed, min_observed_vph)
    reasons: List[str] = []
    if n == 0:
        return {
            "passed": False,
            "criteria": asdict(criteria),
            "linksChecked": 0,
            "linksPassingGeh": 0,
            "gehFraction": None,
            "reasons": ["No links with counts to check"],
        }
    passing = sum(
        1
        for k in observed
        if geh(float(simulated.get(k, 0.0)), float(observed[k])) < criteria.geh_limit
    )
    frac = passing / n
    ok = frac >= criteria.min_fraction
    if not ok:
        reasons.append(
            f"GEH < {criteria.geh_limit:g} on {frac * 100:.1f}% of links; "
            f"{criteria.min_fraction * 100:.0f}% required"
        )
    if criteria.max_mape is not None:
        mape = metrics["mapePercent"]
        if mape is None or mape > criteria.max_mape:
            ok = False
            reasons.append(f"MAPE {mape} exceeds the agreed {criteria.max_mape:g}%")
    if criteria.max_rmse is not None:
        if metrics["rmseVph"] > criteria.max_rmse:
            ok = False
            reasons.append(
                f"RMSE {metrics['rmseVph']} veh/h exceeds the agreed {criteria.max_rmse:g}"
            )
    return {
        "passed": ok,
        "criteria": asdict(criteria),
        "linksChecked": n,
        "linksPassingGeh": passing,
        "gehFraction": round(frac, 4),
        "reasons": reasons,
    }
