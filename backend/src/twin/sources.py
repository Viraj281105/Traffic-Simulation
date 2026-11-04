"""Observation sources: where the twin gets its data.

:class:`ObservationSource` is the seam. :class:`ReplaySource` plays back a
recording (CSV or JSON lines). :class:`StubLiveSource` marks where a real
feed plugs in once decision D3 (the feed source) is made; it makes no
network calls.
"""

import csv
import io
import json
from typing import (
    Callable,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from src.twin.models import Observation


@runtime_checkable
class ObservationSource(Protocol):
    def poll(self, until: float) -> List[Observation]:
        """Observations not yet delivered whose timestamp is below ``until``,
        ordered by (timestamp, link id)."""
        ...

    def close(self) -> None: ...


def parse_csv(text: str) -> List[Observation]:
    """Columns ``link_id,timestamp,count[,mean_speed]`` with a header row."""
    out: List[Observation] = []
    for row in csv.DictReader(io.StringIO(text)):
        speed = (row.get("mean_speed") or "").strip()
        out.append(
            Observation(
                linkId=row["link_id"].strip(),
                timestamp=float(row["timestamp"]),
                count=int(row["count"]),
                meanSpeed=float(speed) if speed else None,
            )
        )
    return out


def parse_jsonl(text: str) -> List[Observation]:
    """One JSON object per line, keyed linkId / timestamp / count / meanSpeed."""
    return [
        Observation.model_validate(json.loads(line))
        for line in text.splitlines()
        if line.strip()
    ]


class ReplaySource:
    """Plays a recording back in timestamp order.

    Pacing is deterministic: :meth:`schedule` maps every observation to a wall
    offset ``(timestamp - start) / speedup`` without touching the clock, and
    :meth:`paced` walks it through an injectable ``sleep`` so tests never
    wait. A ``speedup`` of 60 plays a minute of recording per second."""

    def __init__(
        self, observations: Sequence[Observation], speedup: float = 1.0
    ) -> None:
        if speedup <= 0:
            raise ValueError("speedup must be positive")
        self._items = sorted(observations, key=lambda o: (o.timestamp, o.link_id))
        self.speedup = speedup
        self._next = 0

    @classmethod
    def from_csv(cls, text: str, speedup: float = 1.0) -> "ReplaySource":
        return cls(parse_csv(text), speedup)

    @classmethod
    def from_jsonl(cls, text: str, speedup: float = 1.0) -> "ReplaySource":
        return cls(parse_jsonl(text), speedup)

    @property
    def start(self) -> float:
        return self._items[0].timestamp if self._items else 0.0

    def poll(self, until: float) -> List[Observation]:
        out: List[Observation] = []
        while (
            self._next < len(self._items) and self._items[self._next].timestamp < until
        ):
            out.append(self._items[self._next])
            self._next += 1
        return out

    def schedule(self) -> List[Tuple[float, Observation]]:
        """``[(wall_offset_seconds, observation)]`` for the whole recording."""
        return [((o.timestamp - self.start) / self.speedup, o) for o in self._items]

    def paced(
        self, interval: float, sleep: Callable[[float], None] = lambda s: None
    ) -> Iterator[List[Observation]]:
        """One batch per ``interval`` of recording time, calling
        ``sleep(interval / speedup)`` before each (a no-op by default)."""
        if interval <= 0:
            raise ValueError("interval must be positive")
        t = self.start
        while self._next < len(self._items):
            sleep(interval / self.speedup)
            t += interval
            yield self.poll(t)

    def close(self) -> None:
        self._next = len(self._items)


class StubLiveSource:
    """Where a real feed plugs in (decision D3 pending; W51 owns the adapter).

    A real implementation connects to the feed in its constructor or a
    ``start`` method, buffers decoded messages as :class:`Observation` values
    (feed timestamps mapped to seconds, one count per link per interval), and
    has ``poll`` return and drain the buffer. This stub never connects: it only
    holds what is pushed into it, which also makes it usable in tests."""

    def __init__(self, endpoint: Optional[str] = None) -> None:
        self.endpoint = endpoint  # unused: no network access here
        self._buffer: List[Observation] = []

    def push(self, observation: Observation) -> None:
        self._buffer.append(observation)

    def poll(self, until: float) -> List[Observation]:
        ready = sorted(
            (o for o in self._buffer if o.timestamp < until),
            key=lambda o: (o.timestamp, o.link_id),
        )
        self._buffer = [o for o in self._buffer if o.timestamp >= until]
        return ready

    def close(self) -> None:
        self._buffer = []
