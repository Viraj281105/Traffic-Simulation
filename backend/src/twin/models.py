"""Typed observation: vehicles counted on one link during one interval."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Observation(BaseModel):
    """``count`` vehicles left ``link_id`` in the interval that starts at
    ``timestamp`` (seconds on the feed's own clock). ``mean_speed`` is m/s."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    link_id: str = Field(..., alias="linkId", min_length=1, max_length=64)
    timestamp: float = Field(..., ge=0)
    count: int = Field(..., ge=0)
    mean_speed: Optional[float] = Field(None, alias="meanSpeed", ge=0)
