"""Wireless channel model: latency, packet loss and a range limit.

Deterministic given the seed. Every :meth:`Channel.transmit` call consumes the
same two random draws whatever the configuration, so two channels with the same
seed and call order stay coupled: raising the loss probability can only turn
deliveries into drops, and raising the latency can only delay them. That is
what makes "benefit shrinks as loss rises" a statement about the channel and
not about luck. :meth:`Channel.fork` derives an independent, reproducible
channel per key (e.g. per vehicle), so results do not depend on how many other
receivers there are.
"""

import math
import random
from dataclasses import dataclass
from typing import Literal, Optional

LatencyKind = Literal["constant", "uniform", "exponential"]
MAX_LATENCY_MS = 10_000.0
MAX_RANGE_M = 5_000.0


@dataclass(frozen=True)
class ChannelConfig:
    """Channel parameters.

    ``latency``: ``constant`` is ``latency_ms``; ``uniform`` is
    ``latency_ms +/- jitter_ms`` (floored at 0); ``exponential`` is
    ``latency_ms`` plus an exponential with mean ``jitter_ms``.
    ``loss_probability`` is independent per message and receiver.
    ``range_m`` is a hard cut-off (``None`` = unlimited)."""

    latency_kind: LatencyKind = "constant"
    latency_ms: float = 0.0
    jitter_ms: float = 0.0
    loss_probability: float = 0.0
    range_m: Optional[float] = None

    def __post_init__(self) -> None:
        if self.latency_kind not in ("constant", "uniform", "exponential"):
            raise ValueError("latency_kind must be constant, uniform or exponential")
        for name, v, hi in (
            ("latency_ms", self.latency_ms, MAX_LATENCY_MS),
            ("jitter_ms", self.jitter_ms, MAX_LATENCY_MS),
        ):
            if not (math.isfinite(v) and 0.0 <= v <= hi):
                raise ValueError(f"{name} must lie in [0, {hi:g}]")
        if not (
            math.isfinite(self.loss_probability) and 0.0 <= self.loss_probability <= 1.0
        ):
            raise ValueError("loss_probability must lie in [0, 1]")
        if self.range_m is not None and not (
            math.isfinite(self.range_m) and 0.0 < self.range_m <= MAX_RANGE_M
        ):
            raise ValueError(f"range_m must lie in (0, {MAX_RANGE_M:g}]")

    def to_dict(self) -> dict[str, object]:
        return {
            "latencyKind": self.latency_kind,
            "latencyMs": self.latency_ms,
            "jitterMs": self.jitter_ms,
            "lossProbability": self.loss_probability,
            "rangeM": self.range_m,
        }


@dataclass(frozen=True)
class Transmission:
    """Outcome of one transmission. ``latency_s`` is meaningful when delivered."""

    delivered: bool
    latency_s: float
    reason: Literal["ok", "lost", "out_of_range"]


class Channel:
    def __init__(self, config: ChannelConfig, seed: int = 0) -> None:
        self.config = config
        self.seed = seed
        self._rng = random.Random(f"v2x-channel:{seed}")

    def fork(self, key: int | str) -> "Channel":
        """An independent channel for ``key``, reproducible from (seed, key)."""
        return Channel(self.config, _derive(self.seed, key))

    def _latency_s(self, u: float) -> float:
        c = self.config
        if c.latency_kind == "constant":
            ms = c.latency_ms
        elif c.latency_kind == "uniform":
            ms = max(0.0, c.latency_ms + c.jitter_ms * (2.0 * u - 1.0))
        else:
            ms = c.latency_ms + (-math.log(1.0 - u) * c.jitter_ms)
        return ms / 1000.0

    def transmit(self, distance_m: float = 0.0) -> Transmission:
        u_loss = self._rng.random()
        u_lat = self._rng.random()
        c = self.config
        if c.range_m is not None and distance_m > c.range_m:
            return Transmission(False, 0.0, "out_of_range")
        if u_loss < c.loss_probability:
            return Transmission(False, 0.0, "lost")
        return Transmission(True, self._latency_s(u_lat), "ok")


def _derive(seed: int, key: int | str) -> int:
    """A stable 63-bit seed from (seed, key) via Python's seeded-string hashing
    (sha512 for ``str`` seeds, not affected by PYTHONHASHSEED)."""
    return random.Random(f"v2x-fork:{seed}:{key}").getrandbits(63)
