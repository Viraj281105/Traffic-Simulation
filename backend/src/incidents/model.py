"""Disruption scenario: incidents, weather windows and demand surges.

All times are simulation seconds. A scenario is plain data (pydantic), so it
round-trips through the API and is reproducible from the run seed.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.incidents.weather import WEATHER_KINDS
from src.networks.graph import RoadGraph
from src.networks.network_sim import Flow

MAX_EVENTS = 20
# Default speed factor on the affected link: a crash slows the vehicles that
# still pass (rubbernecking, merging); a blocked lane or closure does not.
DEFAULT_SPEED_FACTOR = {"crash": 0.6, "blocked_lane": 1.0, "closure": 1.0}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Incident(_Strict):
    """A crash, a blocked lane or a full road closure on one or more links.

    * ``crash``        ``lanesBlocked`` lanes are lost and the remaining lanes
                       run at ``speedFactor`` (default 0.6) of free-flow speed.
    * ``blocked_lane`` ``lanesBlocked`` lanes are lost, speed unchanged.
    * ``closure``      the link is closed to new vehicles.

    If the lanes lost reach the link's lane count the link is fully blocked:
    nothing may enter it, and (crash / blocked lane) nothing leaves it either.
    A closure's ``policy`` says what happens to vehicles already on the link:
    ``drain`` lets them leave at the normal rate, ``hold`` keeps them there
    until the closure ends.
    """

    id: str = ""
    type: Literal["crash", "blocked_lane", "closure"]
    links: List[str] = Field(..., min_length=1, max_length=MAX_EVENTS)
    start: float = Field(..., ge=0, le=86400)
    duration: float = Field(..., gt=0, le=86400)
    lanesBlocked: int = Field(1, ge=1, le=8)
    speedFactor: Optional[float] = Field(None, gt=0, le=1)
    policy: Literal["drain", "hold"] = "drain"

    @property
    def end(self) -> float:
        return self.start + self.duration

    def speed_factor(self) -> float:
        if self.speedFactor is not None:
            return self.speedFactor
        return DEFAULT_SPEED_FACTOR[self.type]


class WeatherWindow(_Strict):
    kind: Literal["rain", "fog", "snow", "ice"]
    severity: float = Field(1.0, ge=0, le=1)
    start: float = Field(0.0, ge=0, le=86400)
    duration: float = Field(..., gt=0, le=86400)

    @property
    def end(self) -> float:
        return self.start + self.duration


class Surge(_Strict):
    """Event-day demand: the matching flows' rates are multiplied by
    ``multiplier`` inside the window. ``origin`` / ``destination`` of ``None``
    match any (so a surge with neither scales every flow)."""

    origin: Optional[str] = None
    destination: Optional[str] = None
    start: float = Field(..., ge=0, le=86400)
    duration: float = Field(..., gt=0, le=86400)
    multiplier: float = Field(..., ge=0, le=10)

    @property
    def end(self) -> float:
        return self.start + self.duration

    def matches(self, flow: Flow) -> bool:
        return (self.origin is None or self.origin == flow.origin) and (
            self.destination is None or self.destination == flow.destination
        )


class Scenario(_Strict):
    incidents: List[Incident] = Field(default_factory=list, max_length=MAX_EVENTS)
    weather: List[WeatherWindow] = Field(default_factory=list, max_length=MAX_EVENTS)
    surges: List[Surge] = Field(default_factory=list, max_length=MAX_EVENTS)
    # When a link is fully blocked, new vehicles (and vehicles already driving
    # towards it) take the shortest path that avoids it, if one exists.
    reroute: bool = True

    @property
    def is_empty(self) -> bool:
        return not (self.incidents or self.weather or self.surges)

    def windows(self) -> List[tuple[float, float]]:
        out = [(i.start, i.end) for i in self.incidents]
        out += [(w.start, w.end) for w in self.weather]
        out += [(s.start, s.end) for s in self.surges]
        return out

    def disruption_end(self) -> Optional[float]:
        """When the last disruption ends (None for an empty scenario)."""
        w = self.windows()
        return max(e for _, e in w) if w else None

    def disruption_start(self) -> Optional[float]:
        w = self.windows()
        return min(s for s, _ in w) if w else None


def validate_scenario(
    graph: RoadGraph, flows: List[Flow], scenario: Scenario
) -> List[str]:
    """Human-readable problems (empty when the scenario fits the network)."""
    errors: List[str] = []
    links = graph.link_map()
    nodes = graph.node_map()
    for n, inc in enumerate(scenario.incidents):
        for lid in inc.links:
            if lid not in links:
                errors.append(f"incidents[{n}] refers to unknown link {lid!r}")
    for n, s in enumerate(scenario.surges):
        for label, ref in (("origin", s.origin), ("destination", s.destination)):
            if ref is not None and ref not in nodes:
                errors.append(f"surges[{n}].{label} {ref!r} is not a node")
        if not any(s.matches(f) for f in flows):
            errors.append(f"surges[{n}] matches none of the flows")
    for n, w in enumerate(scenario.weather):
        if w.kind not in WEATHER_KINDS:  # pragma: no cover - schema already checks
            errors.append(f"weather[{n}] has unknown kind {w.kind!r}")
    return errors
