"""V2X message schemas, channel model and the in-process bus (F19)."""

import pytest
from pydantic import ValidationError

from src.v2x.bus import Envelope, InProcessBus
from src.v2x.channel import Channel, ChannelConfig
from src.v2x.messages import (
    BasicSafetyMessage,
    HazardWarning,
    SignalPhaseAndTiming,
    parse_message,
    schemas,
    topic_for,
)


def bsm(**kw: object) -> BasicSafetyMessage:
    base: dict[str, object] = {
        "vehicleId": "v1",
        "x": 1.0,
        "y": 2.0,
        "speed": 10.0,
        "heading": 90.0,
        "timestamp": 3.0,
    }
    base.update(kw)
    return BasicSafetyMessage.model_validate(base)


# -- schemas -----------------------------------------------------------------


def test_valid_messages_round_trip_with_camel_case() -> None:
    m = bsm()
    wire = m.model_dump(by_alias=True)
    assert wire["vehicleId"] == "v1"
    assert parse_message(wire) == m


@pytest.mark.parametrize(
    "field,value",
    [
        ("speed", -1.0),
        ("speed", 500.0),
        ("heading", 360.0),
        ("heading", -0.1),
        ("timestamp", -1.0),
        ("x", 1e9),
        ("vehicleId", ""),
        ("vehicleId", "v" * 65),
    ],
)
def test_bsm_rejects_out_of_range(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        bsm(**{field: value})


def test_bsm_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        bsm(extra=1)


def test_spat_bounds_and_unique_groups() -> None:
    ok = {
        "intersection": "J00",
        "timestamp": 1.0,
        "phases": [{"group": "ew", "state": "green", "timeToChange": 12.0}],
    }
    assert SignalPhaseAndTiming.model_validate(ok).phases[0].time_to_change == 12.0
    bad_state = {**ok, "phases": [{"group": "ew", "state": "blue", "timeToChange": 1}]}
    with pytest.raises(ValidationError):
        SignalPhaseAndTiming.model_validate(bad_state)
    too_long = {**ok, "phases": [{"group": "ew", "state": "red", "timeToChange": 1e6}]}
    with pytest.raises(ValidationError):
        SignalPhaseAndTiming.model_validate(too_long)
    dup = {**ok, "phases": ok["phases"] * 2}  # type: ignore[operator]
    with pytest.raises(ValidationError):
        SignalPhaseAndTiming.model_validate(dup)
    many = {
        **ok,
        "phases": [
            {"group": f"g{i}", "state": "red", "timeToChange": 1} for i in range(17)
        ],
    }
    with pytest.raises(ValidationError):
        SignalPhaseAndTiming.model_validate(many)


def test_hazard_bounds() -> None:
    base = {
        "hazardId": "h1",
        "hazard": "incident",
        "linkId": "A>B",
        "severity": 3,
        "timestamp": 10.0,
    }
    assert HazardWarning.model_validate(base).severity == 3
    for patch in (
        {"severity": 0},
        {"severity": 6},
        {"hazard": "meteor"},
        {"description": "x" * 141},
        {"validUntil": 5.0},
    ):
        with pytest.raises(ValidationError):
            HazardWarning.model_validate({**base, **patch})


def test_parse_message_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        parse_message({"kind": "nope"})
    with pytest.raises(ValueError):
        parse_message({})


def test_topics() -> None:
    assert topic_for("spat", "J00") == "urbanflow/v2x/spat/J00"
    for kind, node in (("nope", "J"), ("bsm", ""), ("bsm", "a/b"), ("bsm", "#")):
        with pytest.raises(ValueError):
            topic_for(kind, node)
    assert set(schemas()) == {"bsm", "spat", "hazard"}


# -- channel -----------------------------------------------------------------


def draws(ch: Channel, n: int, distance: float = 0.0) -> list[tuple[bool, float]]:
    return [
        (t.delivered, t.latency_s) for t in (ch.transmit(distance) for _ in range(n))
    ]


def test_channel_is_deterministic_given_seed() -> None:
    cfg = ChannelConfig("uniform", 100.0, 50.0, 0.3, 300.0)
    a, b, c = Channel(cfg, 7), Channel(cfg, 7), Channel(cfg, 8)
    assert draws(a, 200, 100.0) == draws(b, 200, 100.0)
    assert draws(Channel(cfg, 7), 200, 100.0) != draws(c, 200, 100.0)


def test_fork_is_reproducible_and_independent_of_other_forks() -> None:
    cfg = ChannelConfig(loss_probability=0.5)
    root = Channel(cfg, 3)
    first = draws(root.fork(5), 50)
    root.fork(1).transmit()  # using another fork changes nothing
    assert draws(Channel(cfg, 3).fork(5), 50) == first
    assert draws(Channel(cfg, 3).fork(6), 50) != first


def test_loss_rate_is_within_tolerance() -> None:
    n = 20000
    for p in (0.05, 0.3, 0.8):
        ch = Channel(ChannelConfig(loss_probability=p), 11)
        lost = sum(1 for _ in range(n) if not ch.transmit().delivered)
        assert abs(lost / n - p) < 0.015


def test_range_limit_and_zero_loss() -> None:
    ch = Channel(ChannelConfig(range_m=100.0), 1)
    assert ch.transmit(99.0).delivered
    out = ch.transmit(101.0)
    assert not out.delivered and out.reason == "out_of_range"
    assert all(t.delivered for t in (ch.transmit(1.0) for _ in range(500)))


def test_latency_distributions() -> None:
    const = Channel(ChannelConfig("constant", 80.0), 1)
    assert {const.transmit().latency_s for _ in range(20)} == {0.08}
    uni = Channel(ChannelConfig("uniform", 100.0, 40.0), 1)
    lats = [uni.transmit().latency_s for _ in range(2000)]
    assert 0.06 <= min(lats) and max(lats) <= 0.14
    assert abs(sum(lats) / len(lats) - 0.1) < 0.004
    exp = Channel(ChannelConfig("exponential", 50.0, 100.0), 1)
    lats = [exp.transmit().latency_s for _ in range(4000)]
    assert min(lats) >= 0.05 and abs(sum(lats) / len(lats) - 0.15) < 0.01


def test_higher_loss_only_removes_deliveries_same_seed() -> None:
    a = Channel(ChannelConfig(loss_probability=0.2), 5)
    b = Channel(ChannelConfig(loss_probability=0.6), 5)
    for _ in range(500):
        ta, tb = a.transmit(), b.transmit()
        assert not (tb.delivered and not ta.delivered)


@pytest.mark.parametrize(
    "kw",
    [
        {"loss_probability": 1.5},
        {"loss_probability": -0.1},
        {"latency_ms": -1.0},
        {"latency_ms": 1e9},
        {"range_m": 0.0},
        {"latency_kind": "weird"},
    ],
)
def test_channel_config_validation(kw: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ChannelConfig(**kw)  # type: ignore[arg-type]


# -- in-process bus ----------------------------------------------------------


def test_bus_delivers_in_time_then_publication_order() -> None:
    bus = InProcessBus(Channel(ChannelConfig("constant", 100.0), 1))
    got: list[Envelope] = []
    bus.subscribe("r1", "bsm", handler=got.append)
    for i, t in enumerate((0.0, 0.0, 0.05)):
        bus.publish("bsm", "n", bsm(vehicleId=f"v{i}"), now=t)
    assert bus.advance_to(0.09) == 0
    assert bus.advance_to(0.2) == 3
    assert [e.message.vehicle_id for e in got] == ["v0", "v1", "v2"]  # type: ignore[union-attr]
    assert [round(e.delivered_at, 3) for e in got] == [0.1, 0.1, 0.15]
    assert got[0].topic == "urbanflow/v2x/bsm/n"
    assert round(got[2].age, 3) == 0.1


def test_bus_latency_reorders_messages_deterministically() -> None:
    def run() -> list[str]:
        bus = InProcessBus(Channel(ChannelConfig("uniform", 200.0, 190.0), 4))
        got: list[Envelope] = []
        bus.subscribe("r", "bsm", handler=got.append)
        for i in range(20):
            bus.publish("bsm", "n", bsm(vehicleId=f"v{i}"), now=i * 0.01)
        bus.advance_to(5.0)
        return [e.message.vehicle_id for e in got]  # type: ignore[union-attr]

    order = run()
    assert order == run()
    assert order != sorted(order, key=lambda s: int(s[1:]))  # jitter reordered


def test_bus_topic_filter_range_and_stats() -> None:
    bus = InProcessBus(Channel(ChannelConfig(range_m=50.0, loss_probability=0.0), 1))
    near: list[Envelope] = []
    far: list[Envelope] = []
    other: list[Envelope] = []
    bus.subscribe("near", "bsm", "n1", handler=near.append, position=(10.0, 0.0))
    bus.subscribe("far", "bsm", "+", handler=far.append, position=(500.0, 0.0))
    bus.subscribe("other", "bsm", "n2", handler=other.append, position=(0.0, 0.0))
    bus.publish("bsm", "n1", bsm(), now=0.0, origin=(0.0, 0.0))
    bus.advance_to(1.0)
    assert (len(near), len(far), len(other)) == (1, 0, 0)
    assert bus.stats.attempted == 2 and bus.stats.out_of_range == 1
    assert bus.stats.delivery_ratio == 0.5


def test_bus_clock_cannot_run_backwards() -> None:
    bus = InProcessBus(Channel(ChannelConfig(), 1))
    bus.advance_to(5.0)
    with pytest.raises(ValueError):
        bus.advance_to(1.0)
    with pytest.raises(ValueError):
        bus.publish("bsm", "n", bsm(), now=1.0)
    bus.close()
    assert bus.pending() == 0
