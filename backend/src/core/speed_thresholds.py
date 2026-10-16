"""Where a configuration sets the stop and wait speed thresholds.

Read by the spawner (vehicles) and the metric collector (metrics), so the
rule lives below both.
"""

from typing import Any, Dict


def resolve_speed_threshold(config: Dict[str, Any], key: str, default: float) -> float:
    """Read ``waitSpeedThreshold`` / ``stopSpeedThreshold`` from a config.

    The scenario contract, the JSON schema and the typed ``MetricsSection``
    all place these under ``metrics``; the runtime used to read them only from
    ``vehicleGeneration``, so a value set where the contract says to set it was
    silently ignored (and on the typed route, where ``VehicleGenerationSection``
    has no such fields, there was no way to set it at all). ``metrics`` now
    wins; ``vehicleGeneration`` is still honoured as the legacy location the
    dashboard and study presets use.
    """
    metrics_cfg = config.get("metrics") or {}
    if key in metrics_cfg and metrics_cfg[key] is not None:
        return float(metrics_cfg[key])
    veh_gen = config.get("vehicleGeneration") or {}
    return float(veh_gen.get(key, default))
