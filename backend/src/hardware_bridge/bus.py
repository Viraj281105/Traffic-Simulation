"""Topic-string message bus for hardware traffic (``urbanflow/hw/<device>/...``).

The v2x ``MessageBus`` is keyed by V2X message kind and typed to V2X models, so
it cannot carry hardware JSON; this is the same seam for raw JSON topics. The
in-process bus reuses the v2x :class:`Channel` (latency, loss) on a simulated
clock; :class:`MqttHwBus` wraps an MQTT client (paho is imported lazily by
``src.v2x.mqtt_bus``; a fake client can be injected, so tests need no broker).
"""

import heapq
import itertools
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from src.v2x.channel import Channel

DEVICE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

Handler = Callable[[str, str, float], None]  # (topic, payload, rx_time)


def device_topic(device: str, leaf: str) -> str:
    """``urbanflow/hw/<device>/<leaf>`` with ``leaf`` in command/status."""
    if not DEVICE_RE.match(device):
        raise ValueError("device must match [A-Za-z0-9_-]{1,32}")
    if leaf not in ("command", "status"):
        raise ValueError("leaf must be command or status")
    return f"urbanflow/hw/{device}/{leaf}"


class HwBus(Protocol):
    def publish(self, topic: str, payload: str, *, now: float = 0.0) -> None: ...

    def subscribe(self, topic: str, handler: Handler) -> None: ...

    def close(self) -> None: ...


@dataclass
class DirStats:
    sent: int = 0
    lost: int = 0
    delivered: int = 0


class InProcessHwBus:
    """Deterministic simulated bus: ``down`` channel for command topics, ``up``
    channel for status topics. Delivery is queued at ``now + latency``."""

    def __init__(self, down: Channel, up: Channel) -> None:
        self._down, self._up = down, up
        self.now = 0.0
        self.down_stats, self.up_stats = DirStats(), DirStats()
        self._subs: Dict[str, List[Handler]] = {}
        self._queue: List[Tuple[float, int, str, str, Handler]] = []
        self._seq = itertools.count()

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subs.setdefault(topic, []).append(handler)

    def publish(self, topic: str, payload: str, *, now: float = 0.0) -> None:
        if now < self.now:
            raise ValueError("cannot publish in the past of the bus clock")
        up = topic.endswith("/status")
        chan, stats = (self._up, self.up_stats) if up else (self._down, self.down_stats)
        for handler in self._subs.get(topic, []):
            stats.sent += 1
            tx = chan.transmit(0.0)
            if not tx.delivered:
                stats.lost += 1
                continue
            due = now + tx.latency_s
            heapq.heappush(self._queue, (due, next(self._seq), topic, payload, handler))

    def advance_to(self, t: float) -> int:
        n = 0
        while self._queue and self._queue[0][0] <= t:
            due, _, topic, payload, handler = heapq.heappop(self._queue)
            self.now = max(self.now, due)
            stats = self.up_stats if topic.endswith("/status") else self.down_stats
            stats.delivered += 1
            handler(topic, payload, due)
            n += 1
        self.now = max(self.now, t)
        return n

    def close(self) -> None:
        self._subs.clear()
        self._queue.clear()


class MqttHwBus:
    """MQTT-backed bus. Nothing connects until :meth:`connect`. ``client`` may
    be injected; otherwise paho-mqtt is imported lazily (not a pinned dep)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: str = "urbanflow-hw",
        client: Optional[Any] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if client is None:
            from src.v2x.mqtt_bus import _default_client

            client = _default_client(client_id)
        self.host, self.port = host, port
        self._client = client
        self._clock = clock
        self._handlers: Dict[str, List[Handler]] = {}
        self._client.on_message = self._on_message

    def connect(self, keepalive: int = 30) -> None:
        self._client.connect(self.host, self.port, keepalive)
        self._client.loop_start()

    def publish(self, topic: str, payload: str, *, now: float = 0.0) -> None:
        self._client.publish(topic, payload, qos=0)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)
        self._client.subscribe(topic, qos=0)

    def _on_message(self, _client: Any, _userdata: Any, msg: Any) -> None:
        raw = msg.payload
        payload = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        rx = self._clock()
        for handler in self._handlers.get(msg.topic, []):
            handler(msg.topic, payload, rx)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
