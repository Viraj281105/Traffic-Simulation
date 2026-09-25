from typing import Any, Dict, Optional


def calculate_master_efficiency_score(metrics: Dict[str, Any]) -> Optional[float]:
    """Calculates a fixed-weight composite (0.0 to 100.0) from operational metrics.

    WHAT IT IS VALID FOR: comparing runs of the SAME geometry on the SAME
    scenario (e.g. two signal timing plans at one demand level), as a single
    number summarising five measures with fixed weights.

    WHAT IT IS NOT VALID FOR: ranking a signal against a roundabout.
    - ``idleOpportunityLoss`` is signal-only: it is structurally 0.0 for a
      roundabout, so the roundabout always receives the full 10 points of that
      term whatever it does.
    - The throughput term is normalised against a fixed 120 veh/min ceiling, so
      at ordinary demand it mostly reflects how much traffic arrived.
    The API keeps returning it for same-geometry use; the frontend never puts
    it side by side across geometries.

    Returns ``None`` when no vehicle has exited after warm-up: every input
    then holds a best-case placeholder (0 wait, 0 stops, fairness 1.0), which
    would otherwise score high before anything has been measured.

    Formula weights:
    - Throughput Rate (higher is better): weight = 30.0
    - Average Wait Time (lower is better): weight = -25.0
    - Average Stops per vehicle (lower is better): weight = -15.0
    - Directional Fairness Index (higher is better): weight = 20.0
    - Idle Capacity Loss (lower is better): weight = -10.0
    """
    if not metrics.get("throughput"):
        return None
    throughput_rate = float(metrics.get("throughputRate", 0.0))
    avg_wait = float(metrics.get("averageWaitTime", 0.0))
    avg_stops = float(metrics.get("averageStopsPerVehicle", 0.0))
    dfi = float(metrics.get("directionalFairnessIndex", 1.0))
    idle_loss = float(metrics.get("idleOpportunityLoss", 0.0))

    # Normalization mappings to prevent runaway bounds
    # throughputRate is always reported in vehicles/minute (see
    # docs/architecture/07-metric-contract.md section 2.2), so it is always
    # converted to vehicles/sec before normalizing against a high limit of
    # 2.0 vehicles/sec (120 veh/min).
    tp_per_sec = throughput_rate / 60.0
    tp_norm = min(1.0, tp_per_sec / 2.0)

    # Average wait time: normalized (1.0 at 0s, 0.0 at 60s or more wait)
    wait_norm = max(0.0, 1.0 - (avg_wait / 60.0))

    # Stops per vehicle: normalized (1.0 at 0 stops, 0.0 at 5 stops or more)
    stops_norm = max(0.0, 1.0 - (avg_stops / 5.0))

    # Fairness: directly 0.0 to 1.0
    fairness_norm = max(0.0, min(1.0, dfi))

    # Idle loss: normalized (1.0 at 0% idle loss, 0.0 at 100% idle loss)
    idle_norm = max(0.0, 1.0 - idle_loss)

    # Calculate weighted score (maximum possible sum of weights is 100.0)
    score = (
        (tp_norm * 30.0)
        + (wait_norm * 25.0)
        + (stops_norm * 15.0)
        + (fairness_norm * 20.0)
        + (idle_norm * 10.0)
    )

    return round(score, 1)
