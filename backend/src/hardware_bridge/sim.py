"""Run bridge + device simulator + channel on a simulated clock."""

from dataclasses import dataclass, field
from typing import Any, Dict

from src.aim.manager import SignalPlan
from src.hardware_bridge.bridge import SignalBridge
from src.hardware_bridge.bus import InProcessHwBus
from src.hardware_bridge.device import SignalDevice
from src.hardware_bridge.interlock import InterlockConfig
from src.hardware_bridge.measure import summarise
from src.v2x.channel import Channel, ChannelConfig

MAX_DURATION_S = 600.0
MAX_STEPS = 12_000


@dataclass
class SimSpec:
    device: str = "sim-head-1"
    duration_s: float = 120.0
    dt_s: float = 0.1
    green_s: float = 25.0
    yellow_s: float = 3.0
    all_red_s: float = 2.0
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    uplink: ChannelConfig | None = None  # defaults to the same as the downlink
    seed: int = 0
    interlock: InterlockConfig = field(default_factory=InterlockConfig)

    def validate(self) -> None:
        if not 0.0 < self.duration_s <= MAX_DURATION_S:
            raise ValueError(f"duration_s must lie in (0, {MAX_DURATION_S:g}]")
        if not 0.01 <= self.dt_s <= 5.0:
            raise ValueError("dt_s must lie in [0.01, 5]")
        if self.duration_s / self.dt_s > MAX_STEPS:
            raise ValueError(f"at most {MAX_STEPS} steps (duration_s / dt_s)")


def run_simulation(spec: SimSpec) -> Dict[str, Any]:
    spec.validate()
    down = Channel(spec.channel, spec.seed)
    up = Channel(spec.uplink or spec.channel, spec.seed + 1)
    bus = InProcessHwBus(down, up)
    device = SignalDevice(spec.device, bus, spec.interlock)
    plan = SignalPlan(spec.green_s, spec.yellow_s, spec.all_red_s)
    bridge = SignalBridge(bus, spec.device, plan)
    steps = int(round(spec.duration_s / spec.dt_s))
    for i in range(steps + 1):
        t = round(i * spec.dt_s, 9)
        bus.advance_to(t)
        device.tick(t)
        bridge.step(t)
        bus.advance_to(t)
        device.tick(t)
    bus.advance_to(spec.duration_s + 30.0)  # flush in-flight messages
    return {
        "simulated": True,
        "label": "SIMULATED: virtual device and in-process channel; no real hardware",
        "device": spec.device,
        "durationS": spec.duration_s,
        "lampTimeline": [{"t": t, "heads": h} for t, h in device.lamp_log],
        "lampTimelineTruncated": device.lamp_log_truncated,
        "interlockEvents": [
            {"t": t, "kind": k, "detail": d} for t, k, d in device.il.events
        ],
        "interlockEventsDropped": device.il.events_dropped,
        "latency": summarise(bridge, device),
        "channel": {
            "downlink": spec.channel.to_dict(),
            "uplink": (spec.uplink or spec.channel).to_dict(),
            "downlinkLost": bus.down_stats.lost,
            "uplinkLost": bus.up_stats.lost,
        },
        "finalStatus": bridge.last_status,
    }
