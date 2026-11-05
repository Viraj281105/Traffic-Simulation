"""Message bus abstraction and the in-process deterministic implementation.

:class:`MessageBus` is the seam (like ``ObservationSource`` in ``src.twin``):
the simulator publishes and subscribes through it and does not care whether
delivery is simulated (:class:`InProcessBus`) or real (``MqttBus`` in
``mqtt_bus.py``, which imports paho lazily).

:class:`InProcessBus` runs on a simulated clock. ``publish`` draws the channel
for each matching subscriber and queues the delivery at ``now + latency``;
``advance_to(t)`` hands out everything due by ``t`` in (delivery time,
publication order), so ordering is reproducible. No threads, no wall clock.
"""

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from src.v2x.channel import Channel
from src.v2x.messages import (
    BasicSafetyMessage,
    HazardWarning,
    SignalPhaseAndTiming,
    topic_for,
)

AnyMessage = BasicSafetyMessage | SignalPhaseAndTiming | HazardWarning
Position = Tuple[float, float]


@dataclass(frozen=True)
class Envelope:
    topic: str
    message: AnyMessage
    sent_at: float
    delivered_at: float
    receiver: str

    @property
    def age(self) -> float:
        return self.delivered_at - self.sent_at


Handler = Callable[[Envelope], None]


@runtime_checkable
class MessageBus(Protocol):
    def publish(
        self,
        kind: str,
        node: str,
        message: AnyMessage,
        *,
        now: float = 0.0,
        origin: Optional[Position] = None,
    ) -> None: ...

    def subscribe(
        self,
        receiver: str,
        kind: str,
        node: str = "+",
        *,
        handler: Handler,
        position: Optional[Position] = None,
    ) -> None: ...

    def close(self) -> None: ...


@dataclass
class _Sub:
    receiver: str
    kind: str
    node: str
    handler: Handler
    position: Optional[Position]


@dataclass
class BusStats:
    published: int = 0
    attempted: int = 0
    delivered: int = 0
    lost: int = 0
    out_of_range: int = 0
    by_receiver: Dict[str, int] = field(default_factory=dict)

    @property
    def delivery_ratio(self) -> Optional[float]:
        return self.delivered / self.attempted if self.attempted else None


class InProcessBus:
    """Deterministic simulated bus. ``node`` in a subscription is an exact node
    id or ``"+"`` for any. A subscriber with no ``position`` is treated as at
    distance 0 (infrastructure listening to everything in range)."""

    def __init__(self, channel: Channel) -> None:
        self.channel = channel
        self.now = 0.0
        self.stats = BusStats()
        self._subs: List[_Sub] = []
        self._queue: List[Tuple[float, int, Envelope, Handler]] = []
        self._seq = itertools.count()

    def subscribe(
        self,
        receiver: str,
        kind: str,
        node: str = "+",
        *,
        handler: Handler,
        position: Optional[Position] = None,
    ) -> None:
        topic_for(kind, "x" if node == "+" else node)  # validates kind and node
        self._subs.append(_Sub(receiver, kind, node, handler, position))

    def publish(
        self,
        kind: str,
        node: str,
        message: AnyMessage,
        *,
        now: float = 0.0,
        origin: Optional[Position] = None,
    ) -> None:
        topic = topic_for(kind, node)
        if now < self.now:
            raise ValueError("cannot publish in the past of the bus clock")
        self.stats.published += 1
        for sub in self._subs:  # subscription order: deterministic draws
            if sub.kind != kind or sub.node not in ("+", node):
                continue
            distance = 0.0
            if origin is not None and sub.position is not None:
                distance = (
                    (origin[0] - sub.position[0]) ** 2
                    + (origin[1] - sub.position[1]) ** 2
                ) ** 0.5
            self.stats.attempted += 1
            tx = self.channel.transmit(distance)
            if not tx.delivered:
                if tx.reason == "lost":
                    self.stats.lost += 1
                else:
                    self.stats.out_of_range += 1
                continue
            due = now + tx.latency_s
            env = Envelope(topic, message, now, due, sub.receiver)
            heapq.heappush(self._queue, (due, next(self._seq), env, sub.handler))

    def advance_to(self, t: float) -> int:
        """Deliver every message due at or before ``t``; returns the count."""
        if t < self.now:
            raise ValueError("the bus clock does not run backwards")
        n = 0
        while self._queue and self._queue[0][0] <= t:
            due, _, env, handler = heapq.heappop(self._queue)
            self.now = max(self.now, due)
            self.stats.delivered += 1
            self.stats.by_receiver[env.receiver] = (
                self.stats.by_receiver.get(env.receiver, 0) + 1
            )
            handler(env)
            n += 1
        self.now = max(self.now, t)
        return n

    def pending(self) -> int:
        return len(self._queue)

    def close(self) -> None:
        self._subs.clear()
        self._queue.clear()
