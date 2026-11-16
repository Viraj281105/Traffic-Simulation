"""Latency and loss measurement for a bridge <-> device run."""

import math
from typing import Dict, List, Optional, Sequence

from src.hardware_bridge.bridge import SignalBridge
from src.hardware_bridge.device import SignalDevice


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    """Nearest-rank percentile (``p`` in (0, 100]); None for no data."""
    if not values:
        return None
    s = sorted(values)
    rank = max(1, math.ceil(p / 100.0 * len(s)))
    return s[rank - 1]


def _stats_ms(values: List[float]) -> Dict[str, object]:
    def ms(v: Optional[float]) -> Optional[float]:
        return None if v is None else round(v * 1000.0, 3)

    return {
        "count": len(values),
        "p50Ms": ms(percentile(values, 50)),
        "p95Ms": ms(percentile(values, 95)),
        "p99Ms": ms(percentile(values, 99)),
        "maxMs": ms(max(values) if values else None),
    }


def summarise(bridge: SignalBridge, device: SignalDevice) -> Dict[str, object]:
    """Round-trip (command ts -> ack received by the bridge), one-way command
    delivery, and command-to-lamp (command ts -> lamps show the command) stats,
    plus dropped (sent but never received) and late (one-way above the device's
    threshold) command counts. Duplicates/reordered are device-side counts."""
    sent = bridge.commands_sent
    received = len(device.rx_seqs)
    return {
        "roundTrip": _stats_ms(bridge.rtt_s),
        "oneWay": _stats_ms(device.one_way_s),
        "commandToLamp": _stats_ms(device.cmd_to_lamp_s),
        "commandsSent": sent,
        "commandsReceived": received,
        "commandsDropped": max(0, sent - received),
        "commandsLate": device.counters["late"],
        "lateThresholdMs": device.late_threshold_s * 1000.0,
        "commandsReordered": device.counters["reordered"],
        "commandsDuplicate": device.counters["duplicates"],
        "commandsInvalid": device.counters["invalid"],
        "heartbeatsSent": bridge.heartbeats_sent,
    }
