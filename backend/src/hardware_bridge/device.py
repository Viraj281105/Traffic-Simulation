"""Deterministic signal-head device simulator.

Subscribes to ``urbanflow/hw/<device>/command``, validates every message,
drives virtual lamps through the :class:`Interlock` and publishes status and
telemetry on ``urbanflow/hw/<device>/status``. No threads and no wall clock:
the caller feeds ``on_message`` and ``tick`` (or injects ``clock``).
"""

import json
import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.hardware_bridge.bus import HwBus, device_topic
from src.hardware_bridge.interlock import (
    APPROACHES,
    COMMAND_COLOURS,
    Heads,
    Interlock,
    InterlockConfig,
    conflicting_go,
)

MAX_PAYLOAD = 2048
MAX_LAMP_LOG = 5000


class CommandError(ValueError):
    pass


def parse_message(payload: str, device: str) -> Dict[str, Any]:
    """Validate a command/heartbeat payload; raise :class:`CommandError`."""
    if len(payload) > MAX_PAYLOAD:
        raise CommandError("payload too large")
    try:
        body = json.loads(payload)
    except ValueError as err:
        raise CommandError("not JSON") from err
    if not isinstance(body, dict) or body.get("v") != 1:
        raise CommandError("bad envelope")
    if body.get("device") != device:
        raise CommandError("wrong device")
    kind, seq, ts = body.get("type"), body.get("seq"), body.get("ts")
    if kind not in ("cmd", "hb"):
        raise CommandError("bad type")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
        raise CommandError("bad seq")
    if (
        not isinstance(ts, (int, float))
        or isinstance(ts, bool)
        or not math.isfinite(ts)
        or ts < 0
    ):
        raise CommandError("bad ts")
    if kind == "cmd":
        heads = body.get("heads")
        if (
            not isinstance(heads, dict)
            or set(heads) != set(APPROACHES)
            or any(c not in COMMAND_COLOURS for c in heads.values())
        ):
            raise CommandError("bad heads")
        if conflicting_go(heads):
            raise CommandError("conflicting command")
    return body


class SignalDevice:
    def __init__(
        self,
        device: str,
        bus: HwBus,
        config: Optional[InterlockConfig] = None,
        *,
        clock: Callable[[], float] = lambda: 0.0,
        status_interval: float = 1.0,
        late_threshold_s: float = 0.25,
    ) -> None:
        self.device, self.bus, self._clock = device, bus, clock
        self.status_topic = device_topic(device, "status")
        self.command_topic = device_topic(device, "command")
        t0 = clock()
        self.il = Interlock(config or InterlockConfig(), t0)
        self.status_interval, self.late_threshold_s = status_interval, late_threshold_s
        self.last_rx = t0
        self.last_seq = -1
        self.counters: Dict[str, int] = {
            "accepted": 0,
            "heartbeats": 0,
            "invalid": 0,
            "duplicates": 0,
            "reordered": 0,
            "late": 0,
        }
        self.rx_seqs: set[int] = set()
        self.one_way_s: List[float] = []  # command delivery delay (rx - ts)
        self.cmd_to_lamp_s: List[float] = []
        self.lamp_log: List[Tuple[float, Heads]] = [(t0, dict(self.il.heads))]
        self.lamp_log_truncated = False
        self._pending: List[Tuple[int, float]] = []
        self._status_seq = 0
        self._last_status = t0 - status_interval
        bus.subscribe(self.command_topic, self.on_message)

    @property
    def mode(self) -> str:
        return "failsafe" if self.il.failsafe else "normal"

    def _reject(self, now: float, why: str) -> None:
        self.counters["invalid"] += 1
        self.il.trip(now, why)
        self.il._log(now, "rejected", why)

    def on_message(self, topic: str, payload: str, rx_time: float) -> None:
        try:
            body = parse_message(payload, self.device)
        except CommandError as err:
            self._reject(rx_time, str(err))
            return
        seq = int(body["seq"])
        if seq <= self.last_seq:
            self.counters["duplicates" if seq == self.last_seq else "reordered"] += 1
            return
        self.last_seq, self.last_rx = seq, rx_time
        self.il.request_recovery()
        if body["type"] == "hb":
            self.counters["heartbeats"] += 1
            return
        ts = float(body["ts"])
        self.counters["accepted"] += 1
        self.rx_seqs.add(seq)
        self.one_way_s.append(rx_time - ts)
        if rx_time - ts > self.late_threshold_s:
            self.counters["late"] += 1
        self.il.set_desired(body["heads"])
        if body["heads"] != self.il.heads:
            self._pending.append((seq, ts))
        self._publish_status(rx_time, ack=(seq, ts))

    def tick(self, now: Optional[float] = None) -> None:
        t = self._clock() if now is None else now
        if not self.il.failsafe and t - self.last_rx > self.il.cfg.heartbeat_timeout:
            self.il.trip(t, "heartbeat_timeout")
        self.il.step(t)
        if self.il.heads != self.lamp_log[-1][1]:
            if len(self.lamp_log) < MAX_LAMP_LOG:
                self.lamp_log.append((t, dict(self.il.heads)))
            else:
                self.lamp_log_truncated = True
        if self._pending and self.il.heads == self.il.desired:
            self.cmd_to_lamp_s.extend(t - ts for _, ts in self._pending)
            self._pending.clear()
        if t - self._last_status >= self.status_interval - 1e-9:
            self._publish_status(t)

    def _publish_status(
        self, now: float, ack: Optional[Tuple[int, float]] = None
    ) -> None:
        self._last_status = now
        self._status_seq += 1
        body: Dict[str, Any] = {
            "v": 1,
            "device": self.device,
            "seq": self._status_seq,
            "ts": now,
            "mode": self.mode,
            "failsafeReason": self.il.reason or None,
            "heads": self.il.heads,
            "lastSeq": self.last_seq,
            "ackSeq": ack[0] if ack else None,
            "ackTs": ack[1] if ack else None,
            "counters": self.counters,
        }
        self.bus.publish(self.status_topic, json.dumps(body), now=now)
