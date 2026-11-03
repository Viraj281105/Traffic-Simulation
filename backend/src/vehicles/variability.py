"""Opt-in driver heterogeneity and demand variability (ADR-020, V3.1 W31).

Two independent models, both **off unless enabled** in ``traffic``:

``driverHeterogeneity``
    Each spawned vehicle draws persistent multipliers for desired time
    headway, maximum acceleration and comfortable deceleration, uniform on
    ``[1 - spread, 1 + spread]``.
``demandVariability``
    ``arrivalRate`` is multiplied by a seeded factor, one per run or one per
    ``intervalSeconds`` block.

Each model draws from its **own** ``random.Random``, seeded by hashing the
simulation seed with the model's name. Neither touches the engine's main
stream, so enabling one cannot shift any draw the engine already makes, and
the two cannot shift each other. The spreads are assumed ranges, not
calibrated values (ADR-020).
"""

from __future__ import annotations

import copy
import hashlib
import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.vehicles.idm import IntelligentDriverModel

MAX_DRIVER_SPREAD = 0.5
MAX_DEMAND_SPREAD = 0.8
MIN_INTERVAL_SECONDS = 30.0
MAX_INTERVAL_SECONDS = 3600.0

DRIVER_STREAM = "driver-heterogeneity"
DEMAND_STREAM = "demand-variability"


def variability_stream(seed: int, name: str) -> random.Random:
    """A private generator for one model, derived from the simulation seed."""
    digest = hashlib.sha256(f"urbanflow-{name}-v1:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _number(block: Mapping[str, Any], key: str, low: float, high: float) -> float:
    value = block.get(key, 0.0)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{key} must be a finite number")
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low:g} and {high:g}")
    return float(value)


def _block(traffic: Mapping[str, Any], key: str) -> Optional[Mapping[str, Any]]:
    block = traffic.get(key)
    if block is None:
        return None
    if not isinstance(block, dict):
        raise ValueError(f"traffic.{key} must be an object")
    enabled = block.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError(f"traffic.{key}.enabled must be true or false")
    return block if enabled else None


@dataclass(frozen=True)
class DriverHeterogeneity:
    headway_spread: float
    acceleration_spread: float
    deceleration_spread: float

    @property
    def active(self) -> bool:
        return (
            self.headway_spread > 0
            or self.acceleration_spread > 0
            or self.deceleration_spread > 0
        )


@dataclass(frozen=True)
class DemandVariability:
    spread: float
    interval_seconds: Optional[float]


def parse_driver_heterogeneity(
    traffic: Mapping[str, Any],
) -> Optional[DriverHeterogeneity]:
    """The enabled model's parameters, or None when it is off. Raises
    ValueError (naming the field) for an invalid enabled block."""
    block = _block(traffic, "driverHeterogeneity")
    if block is None:
        return None
    try:
        model = DriverHeterogeneity(
            _number(block, "headwaySpread", 0.0, MAX_DRIVER_SPREAD),
            _number(block, "accelerationSpread", 0.0, MAX_DRIVER_SPREAD),
            _number(block, "decelerationSpread", 0.0, MAX_DRIVER_SPREAD),
        )
    except ValueError as err:
        raise ValueError(f"traffic.driverHeterogeneity: {err}") from None
    return model if model.active else None


def parse_demand_variability(
    traffic: Mapping[str, Any],
) -> Optional[DemandVariability]:
    block = _block(traffic, "demandVariability")
    if block is None:
        return None
    try:
        spread = _number(block, "spread", 0.0, MAX_DEMAND_SPREAD)
        interval: Optional[float] = None
        if block.get("intervalSeconds") is not None:
            interval = _number(
                block, "intervalSeconds", MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS
            )
    except ValueError as err:
        raise ValueError(f"traffic.demandVariability: {err}") from None
    return DemandVariability(spread, interval) if spread > 0 else None


def validate_variability(config: Mapping[str, Any]) -> List[str]:
    """Every problem in the two blocks of a configuration (empty when valid)."""
    traffic = config.get("traffic")
    if not isinstance(traffic, dict):
        return []
    problems: List[str] = []
    for parse in (parse_driver_heterogeneity, parse_demand_variability):
        try:
            parse(traffic)
        except ValueError as err:
            problems.append(str(err))
    return problems


class DriverDraws:
    """Per-vehicle multipliers, in spawn order, from the model's own stream."""

    def __init__(self, model: DriverHeterogeneity, seed: int) -> None:
        self.model = model
        self._rng = variability_stream(seed, DRIVER_STREAM)

    def next_factors(self) -> Tuple[float, float, float]:
        m, r = self.model, self._rng
        # Always three draws, so a zero spread on one trait does not change
        # the draws of the others.
        h, a, b = r.random(), r.random(), r.random()
        return (
            1.0 + m.headway_spread * (2.0 * h - 1.0),
            1.0 + m.acceleration_spread * (2.0 * a - 1.0),
            1.0 + m.deceleration_spread * (2.0 * b - 1.0),
        )


class DemandFactors:
    """The arrival-rate multiplier in force at a simulated time."""

    def __init__(self, model: DemandVariability, seed: int) -> None:
        self.model = model
        self._rng = variability_stream(seed, DEMAND_STREAM)
        self._blocks: List[float] = []

    def _draw(self) -> float:
        return 1.0 + self.model.spread * (2.0 * self._rng.random() - 1.0)

    def factor_at(self, elapsed: float) -> float:
        interval = self.model.interval_seconds
        index = 0 if interval is None else int(max(0.0, elapsed) // interval)
        while len(self._blocks) <= index:
            self._blocks.append(self._draw())
        return self._blocks[index]


def scaled_idm(
    base: IntelligentDriverModel, factors: Tuple[float, float, float]
) -> IntelligentDriverModel:
    """A copy of ``base`` with headway, acceleration and deceleration scaled.

    A copy (not a rebuild) so a subclass such as the stochastic IDM keeps its
    type and its random stream; everything not scaled is shared unchanged.
    """
    headway, acceleration, deceleration = factors
    model = copy.copy(base)
    model._desired_time_headway = base._desired_time_headway * headway
    model._max_acceleration = base._max_acceleration * acceleration
    model._comfort_deceleration = base._comfort_deceleration * deceleration
    return model


def describe(config: Mapping[str, Any]) -> Dict[str, bool]:
    """Which models a configuration turns on (for results and logs)."""
    traffic = config.get("traffic") or {}
    return {
        "driverHeterogeneity": parse_driver_heterogeneity(traffic) is not None,
        "demandVariability": parse_demand_variability(traffic) is not None,
    }
