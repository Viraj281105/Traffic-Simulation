import json
import py_compile
import random
from pathlib import Path
from typing import Any, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.aim.manager import SignalPlan
from src.hardware_bridge import router as hw_router
from src.hardware_bridge.bridge import SignalBridge, plan_heads
from src.hardware_bridge.bus import InProcessHwBus, MqttHwBus, device_topic
from src.hardware_bridge.device import SignalDevice
from src.hardware_bridge.interlock import GO, GROUP, InterlockConfig, conflicting_go
from src.hardware_bridge.measure import percentile
from src.hardware_bridge.sim import SimSpec, run_simulation
from src.v2x.channel import Channel, ChannelConfig

DEV = "dev1"
CMD = device_topic(DEV, "command")
CFG = InterlockConfig(min_amber=3.0, min_all_red=1.0, heartbeat_timeout=2.0)


def make(cfg: InterlockConfig = CFG) -> SignalDevice:
    bus = InProcessHwBus(Channel(ChannelConfig()), Channel(ChannelConfig()))
    return SignalDevice(DEV, bus, cfg)


def cmd(seq: int, ts: float, **heads: str) -> str:
    h = {"N": "red", "E": "red", "S": "red", "W": "red"}
    h.update(heads)
    return json.dumps(
        {"v": 1, "type": "cmd", "device": DEV, "seq": seq, "ts": ts, "heads": h}
    )


def check_log(dev: SignalDevice, cfg: InterlockConfig) -> None:
    last_go_end = {0: -1e9, 1: -1e9}
    was_go = {0: False, 1: False}
    for t, heads in dev.lamp_log:
        assert not conflicting_go(heads), (t, heads)
        for g in (0, 1):
            go = any(c in GO for h, c in heads.items() if GROUP[h] == g)
            if go and not was_go[g]:
                assert t - last_go_end[1 - g] >= cfg.min_all_red - 1e-6, (t, heads)
            if was_go[g] and not go:
                last_go_end[g] = t
            was_go[g] = go


@pytest.mark.parametrize("seed", range(40))
def test_interlock_never_conflicts_under_garbage(seed: int) -> None:
    rng = random.Random(seed)
    dev = make()
    t, seq = 0.0, 0
    sent: List[str] = []
    for _ in range(400):
        t += rng.choice([0.05, 0.1, 0.3, 1.0])
        roll = rng.random()
        if roll < 0.45:
            seq += 1
            msg = cmd(
                seq,
                t,
                **{
                    h: rng.choice(["red", "green", "amber", "red_amber"])
                    for h in "NESW"
                },
            )
            sent.append(msg)
        elif roll < 0.6 and sent:
            msg = rng.choice(sent)  # duplicate or reordered replay
        elif roll < 0.8:
            msg = rng.choice(
                [
                    "",
                    "{",
                    "null",
                    "[1]",
                    '{"v":1}',
                    "\x00\xff",
                    cmd(seq + 1, t, N="purple"),
                ]
            )
        else:
            seq += 1
            g = rng.choice(
                [("N", "S"), ("E", "W")]
            )  # coherent, valid, group-alternating
            msg = cmd(seq, t, **{h: "green" for h in g})
            sent.append(msg)
        dev.on_message(CMD, msg, t)
        dev.tick(t)
        assert not conflicting_go(dev.il.heads)
    check_log(dev, CFG)


def test_conflicting_command_is_rejected_and_fails_safe() -> None:
    dev = make()
    dev.on_message(CMD, cmd(1, 0.0, N="green", E="green"), 0.1)
    dev.tick(0.1)
    assert dev.mode == "failsafe"
    assert set(dev.il.heads.values()) == {"flashing_red"}
    assert dev.counters["invalid"] == 1


def test_green_to_red_passes_through_min_amber_and_all_red() -> None:
    dev = make()
    t, seq = 0.0, 0
    log: List[Any] = []
    for i in range(0, 200):
        t = i * 0.1
        seq += 1
        heads = {"N": "green", "S": "green"} if t < 3 else {"E": "green", "W": "green"}
        dev.on_message(CMD, cmd(seq, t, **heads), t)
        dev.tick(t)
        log.append((t, dict(dev.il.heads)))
    assert dev.mode == "normal"
    ns_amber = [t for t, h in log if h["N"] == "amber"]
    assert ns_amber and ns_amber[-1] - ns_amber[0] >= 2.8
    assert any(h["E"] == "green" for _, h in log)
    check_log(dev, CFG)


def test_heartbeat_timeout_fails_safe_then_recovers() -> None:
    dev = make()
    dev.on_message(CMD, cmd(1, 0.0, N="green", S="green"), 0.0)
    for i in range(1, 16):
        dev.tick(i * 0.1)
    assert dev.il.heads["N"] == "green"
    dev.tick(2.5)  # > 2 s of silence
    assert dev.mode == "failsafe" and dev.il.reason == "heartbeat_timeout"
    assert all(c == "flashing_red" for c in dev.il.heads.values())
    dev.on_message(
        CMD, json.dumps({"v": 1, "type": "hb", "device": DEV, "seq": 2, "ts": 2.6}), 2.6
    )
    dev.tick(2.7)
    assert dev.mode == "failsafe"  # hold not elapsed
    dev.on_message(
        CMD, json.dumps({"v": 1, "type": "hb", "device": DEV, "seq": 3, "ts": 4.7}), 4.7
    )
    dev.tick(4.8)
    assert dev.mode == "normal"


def test_all_red_failsafe_mode() -> None:
    dev = make(InterlockConfig(failsafe_mode="all_red"))
    dev.tick(5.0)
    assert dev.mode == "failsafe" and set(dev.il.heads.values()) == {"red"}


def test_percentile_and_known_channel_latency() -> None:
    assert percentile([1, 2, 3, 4], 50) == 2 and percentile([], 50) is None
    res = run_simulation(
        SimSpec(duration_s=60, channel=ChannelConfig(latency_ms=40.0), seed=3)
    )
    lat = res["latency"]
    assert lat["roundTrip"]["p50Ms"] == pytest.approx(80.0, abs=0.01)
    assert lat["oneWay"]["p99Ms"] == pytest.approx(40.0, abs=0.01)
    assert lat["commandsDropped"] == 0 and lat["commandsLate"] == 0
    assert lat["commandToLamp"]["count"] > 0
    assert not res["interlockEvents"]


def test_loss_and_late_counts() -> None:
    res = run_simulation(
        SimSpec(
            duration_s=60,
            channel=ChannelConfig(latency_ms=300.0, loss_probability=0.2),
            seed=5,
        )
    )
    lat = res["latency"]
    assert lat["commandsDropped"] > 0
    assert lat["commandsLate"] == lat["commandsReceived"]  # 300 ms > 250 ms threshold
    assert res["channel"]["downlinkLost"] > 0
    assert not any(e["kind"] == "conflict_detected" for e in res["interlockEvents"])


def test_total_loss_trips_failsafe() -> None:
    res = run_simulation(
        SimSpec(duration_s=30, channel=ChannelConfig(loss_probability=1.0))
    )
    assert any(e["detail"] == "heartbeat_timeout" for e in res["interlockEvents"])
    assert res["lampTimeline"][-1]["heads"]["N"] == "flashing_red"


def test_bridge_sequence_numbers_and_plan_heads() -> None:
    bus = InProcessHwBus(Channel(ChannelConfig()), Channel(ChannelConfig()))
    got: List[dict[str, Any]] = []
    bus.subscribe(CMD, lambda _t, p, _rx: got.append(json.loads(p)))
    bridge = SignalBridge(bus, DEV, SignalPlan(10.0, 3.0, 2.0), heartbeat_interval=1.0)
    for i in range(30):
        bridge.step(i * 0.1)
    bus.advance_to(10.0)
    seqs = [m["seq"] for m in got]
    assert seqs == list(range(1, len(seqs) + 1))
    assert {m["type"] for m in got} == {"cmd", "hb"}
    assert sum(m["type"] == "hb" for m in got) == 3
    plan = SignalPlan(10.0, 3.0, 2.0)
    assert plan_heads(plan, 1.0)["N"] == "green" and plan_heads(plan, 1.0)["E"] == "red"
    assert plan_heads(plan, 11.0)["N"] == "amber"
    assert (
        plan_heads(plan, 14.2)["E"] == "red_amber"
        and plan_heads(plan, 14.2)["N"] == "red"
    )
    assert plan_heads(plan, 16.0)["E"] == "green"


def test_mqtt_bus_with_fake_client() -> None:
    class Fake:
        on_message: Any = None

        def __init__(self) -> None:
            self.published: List[Any] = []

        def publish(self, topic: str, payload: str, qos: int = 0) -> None:
            self.published.append((topic, payload))

        def subscribe(self, topic: str, qos: int = 0) -> None:
            pass

    fake = Fake()
    bus = MqttHwBus(client=fake, clock=lambda: 7.0)
    seen: List[Any] = []
    bus.subscribe(CMD, lambda t, p, rx: seen.append((t, p, rx)))
    bus.publish(CMD, "x")
    assert fake.published == [(CMD, "x")]

    class Msg:
        topic, payload = CMD, b"hello"

    fake.on_message(None, None, Msg())
    assert seen == [(CMD, "hello", 7.0)]


def test_firmware_compiles() -> None:
    fw = Path(__file__).resolve().parents[3] / "hardware" / "signal-head" / "main.py"
    py_compile.compile(str(fw), doraise=True, cfile=str(fw.with_suffix(".pyc.tmp")))
    fw.with_suffix(".pyc.tmp").unlink()


def client() -> TestClient:
    app = FastAPI()
    app.include_router(hw_router.router)
    return TestClient(app)


def test_router_simulate_and_status() -> None:
    c = client()
    hw_router._REGISTRY.clear()
    assert c.get("/api/v2/hardware/status").json()["devices"] == []
    r = c.post("/api/v2/hardware/simulate", json={"durationS": 40, "device": "bench-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True and "no real hardware" in body["label"]
    assert body["lampTimeline"] and body["latency"]["roundTrip"]["count"] > 0
    st = c.get("/api/v2/hardware/status").json()
    assert st["simulated"] is True and st["devices"][0]["device"] == "bench-1"


def test_router_bounds() -> None:
    c = client()
    assert (
        c.post("/api/v2/hardware/simulate", json={"durationS": 601}).status_code == 422
    )
    assert (
        c.post("/api/v2/hardware/simulate", json={"device": "a/b"}).status_code == 422
    )
    assert (
        c.post(
            "/api/v2/hardware/simulate", json={"durationS": 600, "dtS": 0.01}
        ).status_code
        == 422
    )
