"""V2X message schemas (F19): basic safety message, SPaT and hazard warning.

Loosely modelled on SAE J2735 (BSM, SPaT) but simplified: positions are local
metres in the road graph's frame, times are simulation seconds. Every model
forbids unknown fields and bounds every number and string, so a message from
an untrusted publisher cannot be arbitrarily large or out of range. Field
names are camelCase on the wire (aliases) and snake_case in Python.
"""

from typing import Annotated, Dict, List, Literal, Optional, Type, Union, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_ID = 64
MAX_PHASES = 16
MAX_COORD = 1_000_000.0  # local metres
MAX_SPEED = 90.0  # m/s (324 km/h)
MAX_TIME = 1.0e10  # seconds
MAX_TIME_TO_CHANGE = 3600.0

Kind = Literal["bsm", "spat", "hazard"]
KINDS: tuple[str, ...] = ("bsm", "spat", "hazard")


class _Msg(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)


class BasicSafetyMessage(_Msg):
    """A connected vehicle's position, speed and heading."""

    kind: Literal["bsm"] = "bsm"
    vehicle_id: str = Field(..., alias="vehicleId", min_length=1, max_length=MAX_ID)
    x: float = Field(..., ge=-MAX_COORD, le=MAX_COORD)
    y: float = Field(..., ge=-MAX_COORD, le=MAX_COORD)
    speed: float = Field(..., ge=0, le=MAX_SPEED)  # m/s
    heading: float = Field(..., ge=0, lt=360)  # degrees clockwise from north
    timestamp: float = Field(..., ge=0, le=MAX_TIME)  # generation time, s


class PhaseState(_Msg):
    """One signal group's state and the time until it changes."""

    group: str = Field(..., min_length=1, max_length=16)  # e.g. "ew", "ns"
    state: Literal["green", "yellow", "red"]
    time_to_change: float = Field(
        ..., alias="timeToChange", ge=0, le=MAX_TIME_TO_CHANGE
    )  # s from the message timestamp


class SignalPhaseAndTiming(_Msg):
    """A signalised node's current phase for each signal group."""

    kind: Literal["spat"] = "spat"
    intersection: str = Field(..., min_length=1, max_length=MAX_ID)
    phases: List[PhaseState] = Field(..., min_length=1, max_length=MAX_PHASES)
    timestamp: float = Field(..., ge=0, le=MAX_TIME)

    @model_validator(mode="after")
    def _unique_groups(self) -> "SignalPhaseAndTiming":
        groups = [p.group for p in self.phases]
        if len(set(groups)) != len(groups):
            raise ValueError("signal groups must be unique within one message")
        return self


class HazardWarning(_Msg):
    """A hazard on a link (incident, closure, slippery surface, ...)."""

    kind: Literal["hazard"] = "hazard"
    hazard_id: str = Field(..., alias="hazardId", min_length=1, max_length=MAX_ID)
    hazard: Literal["incident", "closure", "slippery", "congestion", "emergency"]
    link_id: str = Field(..., alias="linkId", min_length=1, max_length=MAX_ID)
    severity: int = Field(..., ge=1, le=5)
    timestamp: float = Field(..., ge=0, le=MAX_TIME)
    valid_until: Optional[float] = Field(
        default=None, alias="validUntil", ge=0, le=MAX_TIME
    )
    description: str = Field(default="", max_length=140)

    @model_validator(mode="after")
    def _expiry_after_start(self) -> "HazardWarning":
        if self.valid_until is not None and self.valid_until < self.timestamp:
            raise ValueError("validUntil must not be before timestamp")
        return self


V2XMessage = Annotated[
    Union[BasicSafetyMessage, SignalPhaseAndTiming, HazardWarning],
    Field(discriminator="kind"),
]

AnyMsg = Union[BasicSafetyMessage, SignalPhaseAndTiming, HazardWarning]

_MODELS: Dict[str, Type[BaseModel]] = {
    "bsm": BasicSafetyMessage,
    "spat": SignalPhaseAndTiming,
    "hazard": HazardWarning,
}


def parse_message(
    payload: dict[str, object],
) -> AnyMsg:
    """Validate ``payload`` by its ``kind``; raises ``ValueError`` on a bad or
    unknown kind (pydantic's ``ValidationError`` is a ``ValueError``)."""
    kind = payload.get("kind")
    if not isinstance(kind, str) or kind not in _MODELS:
        raise ValueError(f"kind must be one of {list(KINDS)}")
    return cast(AnyMsg, _MODELS[kind].model_validate(payload))


def topic_for(kind: str, node: str) -> str:
    """The MQTT topic for a message: ``urbanflow/v2x/<kind>/<node>``."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {list(KINDS)}")
    if not node or len(node) > MAX_ID or any(c in node for c in "/#+\x00"):
        raise ValueError("node must be 1-64 characters without '/', '#', '+' or NUL")
    return f"urbanflow/v2x/{kind}/{node}"


def schemas() -> dict[str, object]:
    """JSON Schemas (wire names) for each message kind."""
    return {k: m.model_json_schema(by_alias=True) for k, m in _MODELS.items()}
