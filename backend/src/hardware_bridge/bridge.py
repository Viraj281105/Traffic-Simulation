"""Bridge: a simulated fixed-time signal plan -> per-timestep head commands.

Publishes ``{"v":1,"type":"cmd","device","seq","ts","heads":{N,E,S,W}}`` on
``urbanflow/hw/<device>/command`` every step, plus ``"type":"hb"`` heartbeats
every ``heartbeat_interval`` s (one shared, strictly increasing sequence).
Colours are red / amber / green / red_amber. It listens on the status topic
and records round-trip times from the device's ack (``ackSeq``/``ackTs``).
"""

import json
from typing import Any, Callable, Dict, List, Optional

from src.aim.manager import SignalPlan
from src.hardware_bridge.bus import HwBus, device_topic
from src.hardware_bridge.interlock import Heads

GROUP_HEADS = (("N", "S"), ("E", "W"))


def plan_heads(plan: SignalPlan, t: float, red_amber_s: float = 1.0) -> Heads:
    """Phase colour for each approach at time ``t`` (phase 0 serves N,S;
    phase 1 serves E,W). The last ``red_amber_s`` of each all-red shows
    red_amber on the group about to get green."""
    half = plan.green + plan.yellow + plan.all_red
    pos = t % plan.cycle
    phase = 0 if pos < half else 1
    local = pos - phase * half
    heads: Heads = {h: "red" for g in GROUP_HEADS for h in g}
    if local < plan.green:
        colour = "green"
    elif local < plan.green + plan.yellow:
        colour = "amber"
    else:
        colour = "red"
    for h in GROUP_HEADS[phase]:
        heads[h] = colour
    if plan.all_red >= red_amber_s > 0 and local >= half - red_amber_s:
        for h in GROUP_HEADS[1 - phase]:
            heads[h] = "red_amber"
    return heads


class SignalBridge:
    def __init__(
        self,
        bus: HwBus,
        device: str,
        plan: SignalPlan,
        *,
        heartbeat_interval: float = 1.0,
        red_amber_s: float = 1.0,
        on_status: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.bus, self.device, self.plan = bus, device, plan
        self.command_topic = device_topic(device, "command")
        self.heartbeat_interval, self.red_amber_s = heartbeat_interval, red_amber_s
        self.seq = 0
        self.commands_sent = 0
        self.heartbeats_sent = 0
        self.rtt_s: List[float] = []
        self.last_status: Optional[Dict[str, Any]] = None
        self._on_status = on_status
        self._next_hb = 0.0
        bus.subscribe(device_topic(device, "status"), self._on_status_msg)

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def step(self, now: float) -> Heads:
        """Publish the command for time ``now`` (and a heartbeat when due)."""
        heads = plan_heads(self.plan, now, self.red_amber_s)
        body: Dict[str, Any] = {
            "v": 1,
            "type": "cmd",
            "device": self.device,
            "seq": self._next_seq(),
            "ts": now,
            "heads": heads,
        }
        self.bus.publish(self.command_topic, json.dumps(body), now=now)
        self.commands_sent += 1
        if now + 1e-9 >= self._next_hb:
            hb = {
                "v": 1,
                "type": "hb",
                "device": self.device,
                "seq": self._next_seq(),
                "ts": now,
            }
            self.bus.publish(self.command_topic, json.dumps(hb), now=now)
            self.heartbeats_sent += 1
            self._next_hb = now + self.heartbeat_interval
        return heads

    def _on_status_msg(self, topic: str, payload: str, rx_time: float) -> None:
        try:
            body = json.loads(payload)
        except ValueError:
            return
        if not isinstance(body, dict):
            return
        self.last_status = body
        ack_ts = body.get("ackTs")
        if isinstance(ack_ts, (int, float)) and body.get("ackSeq") is not None:
            self.rtt_s.append(rx_time - float(ack_ts))
        if self._on_status is not None:
            self._on_status(body)
