"""``/api/v2/hardware``: status registry and a bounded SIMULATED run of the
signal-head bridge. No real hardware, broker or network is contacted.

Register in ``main.py`` (same dependencies as the other network routers)::

    from src.hardware_bridge.router import router as hardware_router
    app.include_router(
        hardware_router,
        dependencies=[Depends(require_api_key), Depends(get_current_user_id)],
    )
"""

from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.hardware_bridge.bus import DEVICE_RE
from src.hardware_bridge.interlock import InterlockConfig
from src.hardware_bridge.sim import MAX_DURATION_S, SimSpec, run_simulation
from src.v2x.channel import ChannelConfig, LatencyKind

router = APIRouter(prefix="/api/v2/hardware", tags=["hardware"])

MAX_DEVICES = 100
_REGISTRY: Dict[str, Dict[str, Any]] = {}


class ChannelIn(BaseModel):
    latencyKind: LatencyKind = "constant"
    latencyMs: float = Field(default=20.0, ge=0, le=10_000)
    jitterMs: float = Field(default=0.0, ge=0, le=10_000)
    lossProbability: float = Field(default=0.0, ge=0, le=1)


class SimulateRequest(BaseModel):
    device: str = Field(default="sim-head-1", max_length=32)
    durationS: float = Field(default=120.0, gt=0, le=MAX_DURATION_S)
    dtS: float = Field(default=0.1, ge=0.01, le=5.0)
    greenS: float = Field(default=25.0, gt=0, le=120)
    yellowS: float = Field(default=3.0, gt=0, le=20)
    allRedS: float = Field(default=2.0, ge=0, le=20)
    channel: ChannelIn = ChannelIn()
    seed: int = Field(default=0, ge=0, le=2**31 - 1)
    minAmberS: float = Field(default=3.0, ge=0, le=20)
    minAllRedS: float = Field(default=1.0, ge=0, le=20)
    heartbeatTimeoutS: float = Field(default=2.0, gt=0, le=60)
    failsafeMode: Literal["flashing_red", "all_red"] = "flashing_red"


def _chan(c: ChannelIn) -> ChannelConfig:
    return ChannelConfig(c.latencyKind, c.latencyMs, c.jitterMs, c.lossProbability)


@router.get("/status")
def hardware_status() -> Dict[str, Any]:
    return {
        "simulated": True,
        "note": "in-memory registry of simulated devices; no real hardware",
        "devices": list(_REGISTRY.values()),
    }


@router.post("/simulate")
def simulate(req: SimulateRequest) -> Dict[str, Any]:
    if not DEVICE_RE.match(req.device):
        raise HTTPException(422, "device must match [A-Za-z0-9_-]{1,32}")
    if req.device not in _REGISTRY and len(_REGISTRY) >= MAX_DEVICES:
        raise HTTPException(429, "device registry is full")
    try:
        spec = SimSpec(
            device=req.device,
            duration_s=req.durationS,
            dt_s=req.dtS,
            green_s=req.greenS,
            yellow_s=req.yellowS,
            all_red_s=req.allRedS,
            channel=_chan(req.channel),
            seed=req.seed,
            interlock=InterlockConfig(
                min_amber=req.minAmberS,
                min_all_red=req.minAllRedS,
                heartbeat_timeout=req.heartbeatTimeoutS,
                failsafe_mode=req.failsafeMode,
            ),
        )
        result = run_simulation(spec)
    except ValueError as err:
        raise HTTPException(422, str(err)) from err
    last: Optional[Dict[str, Any]] = result["finalStatus"]
    _REGISTRY[req.device] = {
        "device": req.device,
        "simulated": True,
        "lastStatus": last,
        "latency": result["latency"],
    }
    return result
