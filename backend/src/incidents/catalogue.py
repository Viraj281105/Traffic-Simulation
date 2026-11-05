"""Built-in networks and the disruption scenario catalogue (F13).

STRESS LAB EXTENSION. The V3 Stress Lab catalogue (``/api/v3/stress/catalogue``)
is part of the pinned V3 OpenAPI snapshot and its generator versions its
outputs, so it is left untouched. The incident, weather and surge scenarios
live here instead and are exposed through ``GET /api/v2/incidents/catalogue``;
they run on the network engine (``src.networks``), which is where closures
and rerouting exist, not on the single-junction engine the V3 Stress Lab uses.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from src.incidents.engine import STRATEGIES
from src.incidents.model import DEFAULT_SPEED_FACTOR
from src.incidents.resilience import (
    AREA_SCALE_SECONDS,
    PEAK_SCALE_SECONDS,
    SCORE_WEIGHTS,
)
from src.incidents.weather import weather_table
from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.networks.graph import RoadGraph
from src.networks.grid import build_grid, grid_flows
from src.networks.network_sim import Flow


class NetworkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["corridor", "grid"] = "corridor"
    rows: int = Field(3, ge=1, le=12)
    cols: int = Field(3, ge=1, le=12)
    spacing: float = Field(300.0, ge=20, le=2000)
    # Grid: vehicles per hour per row flow. Corridor: ignored (use demandScale).
    vehiclesPerHour: float = Field(500.0, ge=0, le=3600)
    demandScale: float = Field(1.0, gt=0, le=4)


def build_network(spec: NetworkSpec) -> Tuple[RoadGraph, List[Flow]]:
    if spec.kind == "corridor":
        graph = build_two_junction_corridor()
        flows = [
            Flow(f.origin, f.destination, f.vehicles_per_hour * spec.demandScale)
            for f in corridor_flows()
        ]
        return graph, flows
    rows, cols = spec.rows, spec.cols
    graph = build_grid(
        rows,
        cols,
        spec.spacing,
        arterial_rows=(rows // 2,) if rows >= 3 else (),
        arterial_cols=(cols // 2,) if cols >= 3 else (),
    )
    flows = [
        Flow(f.origin, f.destination, f.vehicles_per_hour * spec.demandScale)
        for f in grid_flows(rows, cols, spec.vehiclesPerHour)
    ]
    return graph, flows


_CORRIDOR = {"kind": "corridor", "demandScale": 1.8}
_GRID = {"kind": "grid", "rows": 3, "cols": 3, "vehiclesPerHour": 800}


def _preset(
    pid: str,
    family: str,
    title: str,
    description: str,
    network: Dict[str, Any],
    scenario: Dict[str, Any],
    duration: float = 1200.0,
) -> Dict[str, Any]:
    return {
        "id": pid,
        "family": family,
        "title": title,
        "description": description,
        "network": network,
        "scenario": scenario,
        "duration": duration,
    }


PRESETS: List[Dict[str, Any]] = [
    _preset(
        "corridor-crash",
        "incident",
        "Crash on the corridor arterial",
        "One of two lanes of J1>J2 is lost for 4 minutes and the rest crawl.",
        _CORRIDOR,
        {
            "incidents": [
                {
                    "type": "crash",
                    "links": ["J1>J2"],
                    "start": 200,
                    "duration": 240,
                    "lanesBlocked": 1,
                }
            ]
        },
    ),
    _preset(
        "corridor-closure-no-detour",
        "closure",
        "Corridor closed with no detour",
        "Both directions of J1-J2 close for 4 minutes; the corridor has no "
        "alternative, so vehicles wait and arrivals are turned away.",
        _CORRIDOR,
        {
            "incidents": [
                {
                    "type": "closure",
                    "links": ["J1>J2", "J2>J1"],
                    "start": 200,
                    "duration": 240,
                }
            ]
        },
    ),
    _preset(
        "grid-closure-detour",
        "closure",
        "Arterial closure on a 3x3 grid, traffic reroutes",
        "East-bound J11>J12 (middle row) closes for 5 minutes; flows detour "
        "through the outer rows.",
        _GRID,
        {
            "incidents": [
                {
                    "type": "closure",
                    "links": ["J11>J12"],
                    "start": 200,
                    "duration": 300,
                    "policy": "drain",
                }
            ]
        },
    ),
    _preset(
        "grid-blocked-lane",
        "incident",
        "Blocked lane on the grid avenue",
        "One lane of the middle column J01>J11 is blocked for 5 minutes.",
        _GRID,
        {
            "incidents": [
                {
                    "type": "blocked_lane",
                    "links": ["J01>J11"],
                    "start": 200,
                    "duration": 300,
                    "lanesBlocked": 1,
                }
            ]
        },
    ),
    _preset(
        "grid-heavy-rain",
        "weather",
        "Heavy rain on a 3x3 grid",
        "Rain at full severity for 6 minutes: lower speeds, saturation flow "
        "and longer headways everywhere.",
        _GRID,
        {"weather": [{"kind": "rain", "severity": 1.0, "start": 200, "duration": 360}]},
    ),
    _preset(
        "grid-fog",
        "weather",
        "Dense fog on a 3x3 grid",
        "Fog at full severity for 6 minutes.",
        _GRID,
        {"weather": [{"kind": "fog", "severity": 1.0, "start": 200, "duration": 360}]},
    ),
    _preset(
        "grid-snow-ice",
        "weather",
        "Snow turning to ice on a 3x3 grid",
        "Snow for 5 minutes, then ice for 4 minutes (the windows touch).",
        _GRID,
        {
            "weather": [
                {"kind": "snow", "severity": 0.8, "start": 150, "duration": 300},
                {"kind": "ice", "severity": 0.6, "start": 450, "duration": 240},
            ]
        },
    ),
    _preset(
        "grid-event-surge",
        "surge",
        "Event-day surge towards the east gate",
        "Demand on the middle-row flows doubles and a ramp to 2.5x on the "
        "reverse flow for 6 minutes (an event ending).",
        _GRID,
        {
            "surges": [
                {
                    "origin": "GW1",
                    "destination": "GE1",
                    "start": 200,
                    "duration": 360,
                    "multiplier": 2.0,
                },
                {
                    "origin": "GE1",
                    "destination": "GW1",
                    "start": 200,
                    "duration": 360,
                    "multiplier": 2.5,
                },
            ]
        },
    ),
    _preset(
        "grid-storm-and-crash",
        "compound",
        "Rain, a crash and an event surge together",
        "Rain from 150 s, a lane lost on J11>J12 from 250 s and a surge on "
        "the middle-row flows: the worst case in the catalogue.",
        _GRID,
        {
            "weather": [
                {"kind": "rain", "severity": 0.7, "start": 150, "duration": 450}
            ],
            "incidents": [
                {
                    "type": "crash",
                    "links": ["J11>J12"],
                    "start": 250,
                    "duration": 240,
                    "lanesBlocked": 1,
                }
            ],
            "surges": [
                {
                    "origin": "GW1",
                    "destination": "GE1",
                    "start": 250,
                    "duration": 300,
                    "multiplier": 1.6,
                }
            ],
        },
        duration=1500.0,
    ),
]


def preset_by_id(pid: str) -> Optional[Dict[str, Any]]:
    for p in PRESETS:
        if p["id"] == pid:
            return p
    return None


def catalogue() -> Dict[str, Any]:
    return {
        "format": "urbanflow-incident-catalogue",
        "version": 1,
        "inModelOnly": True,
        "disruptionTypes": [
            {
                "type": "crash",
                "effect": "lanesBlocked lanes lost; remaining lanes slowed by "
                "speedFactor. All lanes lost = full block, vehicles on the link held.",
                "defaultSpeedFactor": DEFAULT_SPEED_FACTOR["crash"],
            },
            {
                "type": "blocked_lane",
                "effect": "lanesBlocked lanes lost, speed unchanged.",
                "defaultSpeedFactor": DEFAULT_SPEED_FACTOR["blocked_lane"],
            },
            {
                "type": "closure",
                "effect": "no new vehicles may enter; policy 'drain' lets vehicles "
                "already on the link leave, 'hold' keeps them until it reopens. "
                "With reroute on, flows and en-route vehicles detour if a path exists.",
                "defaultSpeedFactor": DEFAULT_SPEED_FACTOR["closure"],
            },
            {
                "type": "weather",
                "effect": "network-wide multipliers on speed, saturation flow and "
                "headway for kinds rain, fog, snow, ice at severity 0..1.",
            },
            {
                "type": "surge",
                "effect": "multiplies the arrival rate of matching origin-destination "
                "flows inside a time window.",
            },
        ],
        "weather": {
            "fullSeverityFactors": weather_table(),
            "status": "Modelling assumptions inside ranges reported in the weather "
            "adjustment literature; not measurements and not calibrated.",
        },
        "strategies": list(STRATEGIES),
        "scoreFormula": {
            "weights": SCORE_WEIGHTS,
            "peakScaleSeconds": PEAK_SCALE_SECONDS,
            "areaScaleSeconds": AREA_SCALE_SECONDS,
        },
        "scenarios": PRESETS,
        "stressLabExtension": {
            "note": "Exposed here, not in /api/v3/stress/catalogue, because that "
            "catalogue is part of the pinned V3 contract and runs on the "
            "single-junction engine, which has no links to close.",
        },
    }
