"""Prediction-versus-observation scoring: MAE, MAPE, bias, lag, alerts."""

from typing import Any, Dict, List, Optional, Sequence, Tuple

LAG_SEARCH_WINDOWS = 3


def series_metrics(
    predicted: Sequence[float], observed: Sequence[float]
) -> Dict[str, Any]:
    """MAE, bias (mean predicted minus observed) and MAPE (percent, over the
    points where the observation is above zero; None when there are none)."""
    n = len(predicted)
    if n == 0:
        return {"n": 0, "mae": None, "mape": None, "bias": None}
    errors = [p - o for p, o in zip(predicted, observed)]
    pct = [abs(p - o) / o * 100.0 for p, o in zip(predicted, observed) if o > 0]
    return {
        "n": n,
        "mae": round(sum(abs(e) for e in errors) / n, 6),
        "mape": round(sum(pct) / len(pct), 6) if pct else None,
        "bias": round(sum(errors) / n, 6),
    }


def best_lag(predicted: Sequence[float], observed: Sequence[float]) -> int:
    """Shift s in [-3, 3] (windows) minimising the MAE between predicted[k]
    and observed[k + s]. A positive s means the observations reach the
    prediction's level s windows later (the twin runs early); a negative s
    means the twin runs late. Ties go to the smaller shift, so a twin that is
    in step reports 0."""
    best, best_mae = 0, None
    for s in sorted(range(-LAG_SEARCH_WINDOWS, LAG_SEARCH_WINDOWS + 1), key=abs):
        pairs = [
            (predicted[k], observed[k + s])
            for k in range(len(predicted))
            if 0 <= k + s < len(observed)
        ]
        if len(pairs) < 2:
            continue
        mae = sum(abs(p - o) for p, o in pairs) / len(pairs)
        if best_mae is None or mae < best_mae - 1e-12:
            best, best_mae = s, mae
    return best


def compare(
    predicted: Dict[int, Dict[str, float]],
    observed: Dict[int, Dict[str, float]],
    interval: float,
    alert_threshold_pct: float = 25.0,
) -> Dict[str, Any]:
    """Score ``predicted[window][link]`` against ``observed[window][link]``.

    Only (window, link) pairs with an observation are scored. The network
    series is the per-window total over the observed links. An alert is raised
    for every window whose network error exceeds ``alert_threshold_pct`` and
    for the overall network MAPE."""
    per_link_pairs: Dict[str, List[Tuple[float, float]]] = {}
    windows: List[int] = []
    net_pred: List[float] = []
    net_obs: List[float] = []
    for w in sorted(observed):
        if w not in predicted:
            continue
        links = sorted(k for k in observed[w] if k in predicted[w])
        if not links:
            continue
        windows.append(w)
        net_pred.append(sum(predicted[w][k] for k in links))
        net_obs.append(sum(observed[w][k] for k in links))
        for k in links:
            per_link_pairs.setdefault(k, []).append((predicted[w][k], observed[w][k]))

    per_link = {
        k: series_metrics([p for p, _ in pairs], [o for _, o in pairs])
        for k, pairs in sorted(per_link_pairs.items())
    }
    network = series_metrics(net_pred, net_obs)
    lag = best_lag(net_pred, net_obs)
    network["lagWindows"] = lag
    network["lagSeconds"] = lag * interval

    series: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []
    for w, p, o in zip(windows, net_pred, net_obs):
        err_pct: Optional[float] = abs(p - o) / o * 100.0 if o > 0 else None
        series.append(
            {
                "window": w,
                "predicted": p,
                "observed": o,
                "error": p - o,
                "errorPct": None if err_pct is None else round(err_pct, 6),
            }
        )
        if err_pct is not None and err_pct > alert_threshold_pct:
            alerts.append(
                {
                    "window": w,
                    "kind": "window",
                    "errorPct": round(err_pct, 6),
                    "thresholdPct": alert_threshold_pct,
                }
            )
    if network["mape"] is not None and network["mape"] > alert_threshold_pct:
        alerts.append(
            {
                "window": None,
                "kind": "overall",
                "errorPct": network["mape"],
                "thresholdPct": alert_threshold_pct,
            }
        )
    return {
        "network": network,
        "perLink": per_link,
        "series": series,
        "alertThresholdPct": alert_threshold_pct,
        "alert": bool(alerts),
        "alerts": alerts,
    }
