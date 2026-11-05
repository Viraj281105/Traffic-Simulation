"""Job queue abstraction (F17, package 2E): a ``JobQueue`` protocol and an in-memory implementation.

The semantics mirror SQS standard queues, so the worker behaves the same on both:

* ``receive`` hides a message for ``visibility_timeout`` seconds and counts the delivery.
* ``ack`` deletes it; ``nack`` makes it visible again after a delay.
* A message not acked before its visibility timeout is delivered again (at-least-once).
* A message received more than ``max_receives`` times is moved to the dead-letter queue instead
  of being delivered (SQS redrive policy ``maxReceiveCount``).
* ``reject`` sends a message to the dead-letter queue at once (a poison message).

The in-memory queue also drops a second ``send`` with an idempotency key it has already seen,
which the SQS standard queue cannot do; the worker's run-store check covers that case there.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from .spec import JobMessage

DEFAULT_QUEUE_MAX_RECEIVES = 3
DEFAULT_VISIBILITY_TIMEOUT = 30.0


class QueueError(RuntimeError):
    """The queue backend could not complete an operation."""


class StaleReceiptError(QueueError):
    """The receipt handle is no longer current (the message timed out and was redelivered, or
    was already deleted)."""


@dataclass(frozen=True)
class Delivery:
    """One received message. ``body`` is the raw text: parsing is the worker's job, so a
    malformed message still reaches ``reject`` instead of being lost in the queue."""

    message_id: str
    receipt: str
    body: str
    receive_count: int


@dataclass(frozen=True)
class QueueStats:
    visible: int
    in_flight: int
    dead_letter: int

    def as_dict(self) -> Dict[str, int]:
        return {
            "visible": self.visible,
            "inFlight": self.in_flight,
            "deadLetter": self.dead_letter,
        }


class JobQueue(Protocol):
    def send(self, message: JobMessage) -> str:
        """Enqueue and return the queue's message id."""
        ...

    def receive(
        self,
        max_messages: int = 1,
        *,
        wait_seconds: float = 0,
        visibility_timeout: Optional[float] = None,
    ) -> List[Delivery]: ...

    def ack(self, delivery: Delivery) -> None: ...

    def nack(self, delivery: Delivery, delay_seconds: float = 0) -> None: ...

    def extend(self, delivery: Delivery, seconds: float) -> None: ...

    def reject(self, delivery: Delivery, reason: str) -> None: ...

    def stats(self) -> QueueStats: ...


@dataclass
class _Entry:
    message_id: str
    body: str
    receive_count: int = 0
    visible_at: float = 0.0
    receipt: Optional[str] = None


class InMemoryJobQueue:
    """Thread-safe in-process queue with an injectable clock (tests advance it by hand)."""

    def __init__(
        self,
        *,
        max_receives: int = DEFAULT_QUEUE_MAX_RECEIVES,
        visibility_timeout: float = DEFAULT_VISIBILITY_TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_receives < 1:
            raise ValueError("max_receives must be at least 1")
        self.max_receives = max_receives
        self.visibility_timeout = visibility_timeout
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: Dict[str, _Entry] = {}
        self._keys: Dict[str, str] = {}
        self._dead: List[Tuple[str, str]] = []

    def send(self, message: JobMessage) -> str:
        return self.send_raw(message.to_json(), message.idempotency_key)

    def send_raw(self, body: str, idempotency_key: Optional[str] = None) -> str:
        """Enqueue any text (tests use this to send a poison message)."""
        with self._lock:
            if idempotency_key is not None and idempotency_key in self._keys:
                return self._keys[idempotency_key]
            message_id = uuid.uuid4().hex
            self._entries[message_id] = _Entry(message_id, body)
            if idempotency_key is not None:
                self._keys[idempotency_key] = message_id
            return message_id

    def receive(
        self,
        max_messages: int = 1,
        *,
        wait_seconds: float = 0,
        visibility_timeout: Optional[float] = None,
    ) -> List[Delivery]:
        # ``wait_seconds`` is accepted for protocol parity; an in-memory queue never blocks.
        timeout = (
            self.visibility_timeout
            if visibility_timeout is None
            else visibility_timeout
        )
        now = self._clock()
        out: List[Delivery] = []
        with self._lock:
            for entry in list(self._entries.values()):
                if len(out) >= max_messages:
                    break
                if entry.visible_at > now:
                    continue
                if entry.receive_count + 1 > self.max_receives:
                    self._dead.append((entry.body, "max receives exceeded"))
                    del self._entries[entry.message_id]
                    continue
                entry.receive_count += 1
                entry.receipt = uuid.uuid4().hex
                entry.visible_at = now + timeout
                out.append(
                    Delivery(
                        entry.message_id, entry.receipt, entry.body, entry.receive_count
                    )
                )
        return out

    def _current(self, delivery: Delivery) -> _Entry:
        entry = self._entries.get(delivery.message_id)
        if entry is None or entry.receipt != delivery.receipt:
            raise StaleReceiptError(delivery.message_id)
        return entry

    def ack(self, delivery: Delivery) -> None:
        with self._lock:
            del self._entries[self._current(delivery).message_id]

    def nack(self, delivery: Delivery, delay_seconds: float = 0) -> None:
        with self._lock:
            entry = self._current(delivery)
            entry.visible_at = self._clock() + max(0.0, delay_seconds)
            entry.receipt = None

    def extend(self, delivery: Delivery, seconds: float) -> None:
        with self._lock:
            self._current(delivery).visible_at = self._clock() + max(0.0, seconds)

    def reject(self, delivery: Delivery, reason: str) -> None:
        with self._lock:
            entry = self._current(delivery)
            self._dead.append((entry.body, reason))
            del self._entries[entry.message_id]

    def stats(self) -> QueueStats:
        now = self._clock()
        with self._lock:
            hidden = sum(1 for e in self._entries.values() if e.visible_at > now)
            return QueueStats(
                visible=len(self._entries) - hidden,
                in_flight=hidden,
                dead_letter=len(self._dead),
            )

    def dead_letters(self) -> List[Tuple[str, str]]:
        """(body, reason) of every dead-lettered message."""
        with self._lock:
            return list(self._dead)
