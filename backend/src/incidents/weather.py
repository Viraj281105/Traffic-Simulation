"""Weather as multipliers on the network engine's driver and road parameters.

Three multipliers per weather kind, all applied network-wide while the weather
window is active:

* ``speed``      free-flow speed (a link is crossed in ``length / (speed * f)``);
* ``saturation`` saturation flow, i.e. the discharge rate per lane at a stop line;
* ``headway``    reaction / following-headway time. A longer headway means fewer
                 vehicles per second, so the discharge rate is divided by it.

The discharge rate is therefore scaled by ``saturation / headway`` (floored at
``MIN_DISCHARGE``). Friction and visibility have no variable of their own in the
mesoscopic engine: they act only through these three numbers (low friction
lengthens safe headways and lowers speed; low visibility does the same).

MODELLING ASSUMPTIONS, NOT MEASUREMENTS. The direction and rough size follow the
weather-adjustment literature that traffic engineers use, for example the FHWA
Road Weather Management Program summary "How Do Weather Events Impact Roads?",
Agarwal, Maze and Souleyrette (2005), "Impacts of weather on urban freeway
traffic flow characteristics and facility capacity", and the weather and
incident adjustment chapters of the Highway Capacity Manual (6th ed.). Those
sources report ranges (for example single-digit to low double-digit percent
speed and capacity losses in rain and fog, larger in snow and ice). The values
below are round numbers chosen inside such ranges, quoted from memory, not
fitted to data, not calibrated to any city and not re-checked against the
cited texts in this repository. Treat results as comparisons between
scenarios, never as predictions.

Severity is a number in [0, 1]. Each factor moves linearly from 1.0 (no effect)
at severity 0 to the "full" value below at severity 1, so a worse weather never
gives a better factor (monotone by construction).
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

WEATHER_KINDS: Tuple[str, ...] = ("rain", "fog", "snow", "ice")

# Bounds every factor is clamped into, so no input can stop the network outright.
MIN_SPEED_FACTOR = 0.3
MIN_SATURATION_FACTOR = 0.3
MAX_HEADWAY_FACTOR = 2.5
MIN_DISCHARGE = 0.15


@dataclass(frozen=True)
class WeatherFactors:
    speed: float = 1.0
    saturation: float = 1.0
    headway: float = 1.0

    @property
    def discharge(self) -> float:
        """Multiplier on the per-lane discharge rate (saturation / headway)."""
        return max(MIN_DISCHARGE, self.saturation / self.headway)


# kind -> (speed, saturation, headway) at severity 1. Assumptions, see module doc.
_AT_FULL_SEVERITY: Dict[str, Tuple[float, float, float]] = {
    "rain": (0.88, 0.90, 1.15),
    "fog": (0.85, 0.92, 1.25),
    "snow": (0.72, 0.80, 1.35),
    "ice": (0.55, 0.70, 1.70),
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def weather_factors(kind: str, severity: float) -> WeatherFactors:
    """Factors for one weather window. ``severity`` is clamped into [0, 1]."""
    if kind not in _AT_FULL_SEVERITY:
        raise ValueError(f"unknown weather kind {kind!r}; use one of {WEATHER_KINDS}")
    s = _clamp(float(severity), 0.0, 1.0)
    sp, sat, hw = _AT_FULL_SEVERITY[kind]
    return WeatherFactors(
        speed=_clamp(1.0 + (sp - 1.0) * s, MIN_SPEED_FACTOR, 1.0),
        saturation=_clamp(1.0 + (sat - 1.0) * s, MIN_SATURATION_FACTOR, 1.0),
        headway=_clamp(1.0 + (hw - 1.0) * s, 1.0, MAX_HEADWAY_FACTOR),
    )


def combine(factors: Iterable[WeatherFactors]) -> WeatherFactors:
    """Overlapping windows multiply (then are clamped to the same bounds)."""
    sp = sat = hw = 1.0
    for f in factors:
        sp *= f.speed
        sat *= f.saturation
        hw *= f.headway
    return WeatherFactors(
        speed=_clamp(sp, MIN_SPEED_FACTOR, 1.0),
        saturation=_clamp(sat, MIN_SATURATION_FACTOR, 1.0),
        headway=_clamp(hw, 1.0, MAX_HEADWAY_FACTOR),
    )


def weather_table() -> Dict[str, Dict[str, float]]:
    """The full-severity factors per kind, for the catalogue."""
    out: Dict[str, Dict[str, float]] = {}
    for kind in WEATHER_KINDS:
        f = weather_factors(kind, 1.0)
        out[kind] = {
            "speed": f.speed,
            "saturation": f.saturation,
            "headway": f.headway,
            "discharge": round(f.discharge, 4),
        }
    return out
