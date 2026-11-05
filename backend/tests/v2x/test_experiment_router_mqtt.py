"""Cooperative experiment harness, behaviour model, router and MQTT adapter."""

from typing import Any, Dict, List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.networks.grid import build_three_by_three, grid_flows
from src.networks.network_sim import simulate_network
from src.v2x.behaviour import (
    HALF_CYCLE,
    Hazard,
    seconds_to_green,
    spat_for,
)
from src.v2x.bus import Envelope
from src.v2x.channel import ChannelConfig
from src.v2x.experiment import SensitivitySpec, run_experiment
from src.v2x.messages import BasicSafetyMessage, topic_for
from src.v2x.mqtt_bus import MqttBus, MqttUnavailableError, paho_available
from src.v2x.router import router
from src.v2x.traces import run_traced

GRAPH = build_three_by_three()
FLOWS = grid_flows(3, 3, 400.0)
SEEDS = [1, 2, 3]


def delay(res: Dict[str, Any], row: int = -1) -> Dict[str, Any]:
    return res["sweep"][row]["metrics"]["delaySeconds"]


# -- traces and signal knowledge ---------------------------------------------


def test_traced_baseline_equals_plain_simulation() -> None:
    plain = simulate_network(GRAPH, FLOWS, 300.0, 4)
    traced, traces = run_traced(GRAPH, FLOWS, 300.0, 4)
    assert traced == plain
    assert traces and all(t.completed for t in traces)
    assert len(traces) == plain["completed"]


def test_spat_prediction_matches_the_signal() -> None:
    for t in (0.0, 7.5, 29.9, 30.0, 45.0, 59.9, 75.0):
        msg = spat_for("J00", t)
        ew_green = int(t // HALF_CYCLE) % 2 == 0
        for at in (t, t + 3.0, t + 31.0, t + 61.7, t + 100.0):
            truth_ew = int(at // HALF_CYCLE) % 2 == 0
            g_ew = seconds_to_green(msg, "ew", at)
            assert (g_ew == 0.0) == truth_ew
            assert (seconds_to_green(msg, "ns", at) == 0.0) == (not truth_ew)
            if not truth_ew:  # waiting: green really starts g seconds later
                later = at + g_ew + 1e-6
                assert int(later // HALF_CYCLE) % 2 == 0
        assert (msg.phases[0].state == "green") == ew_green


# -- experiment --------------------------------------------------------------


def test_zero_penetration_is_exactly_the_baseline() -> None:
    res = run_experiment(GRAPH, FLOWS, duration=300.0, seeds=SEEDS, penetrations=[0.0])
    row = res["sweep"][0]
    assert row["connectedVehicles"] == 0
    assert delay(res, 0)["change"] == 0.0
    assert row["messageDeliveryRatio"] is None


def test_cooperation_helps_at_zero_latency_and_loss() -> None:
    res = run_experiment(
        GRAPH, FLOWS, duration=400.0, seeds=SEEDS, penetrations=[0.0, 0.5, 1.0]
    )
    d_half, d_full = delay(res, 1), delay(res, 2)
    assert d_half["change"] <= 0.0 and d_full["change"] <= d_half["change"]
    assert d_full["change"] < 0.0
    stops = res["sweep"][2]["metrics"]["stops"]
    assert stops["change"] < 0.0
    assert res["sweep"][2]["metrics"]["fuelLitres"]["change"] < 0.0
    assert res["sweep"][2]["messageDeliveryRatio"] == 1.0
    assert res["sweep"][2]["stopsAvoided"] > 0
    paired = stops["paired"]
    assert paired["n_pairs"] == 3 and paired["ci_upper"] < 0.0


def test_benefit_grows_with_penetration() -> None:
    res = run_experiment(
        GRAPH, FLOWS, duration=400.0, seeds=SEEDS, penetrations=[0.25, 0.5, 0.75, 1.0]
    )
    changes = [delay(res, i)["change"] for i in range(4)]
    assert changes == sorted(changes, reverse=True)  # more negative each step


def test_benefit_shrinks_as_loss_rises_fixed_seeds() -> None:
    benefits: List[float] = []
    for loss in (0.0, 0.3, 0.6, 0.9):
        res = run_experiment(
            GRAPH,
            FLOWS,
            duration=400.0,
            seeds=SEEDS,
            penetrations=[1.0],
            channel=ChannelConfig(loss_probability=loss),
        )
        benefits.append(-delay(res, 0)["change"])
    assert benefits[0] > 0.0
    assert benefits == sorted(benefits, reverse=True)
    assert benefits[-1] < benefits[0]


def test_benefit_shrinks_as_latency_rises_and_old_messages_expire() -> None:
    benefits = []
    for lat in (0.0, 1000.0, 5000.0, 9000.0):
        res = run_experiment(
            GRAPH,
            FLOWS,
            duration=400.0,
            seeds=SEEDS,
            penetrations=[1.0],
            channel=ChannelConfig(latency_ms=lat),
        )
        benefits.append(-delay(res, 0)["change"])
        if lat == 0.0:
            assert res["sweep"][0]["meanMessageAgeAtUseSeconds"] == 0.0
    assert benefits == sorted(benefits, reverse=True)
    assert benefits[-1] == 0.0  # 9 s old on arrival: past the 5 s validity


def test_range_limit_reduces_delivery_and_benefit() -> None:
    full = run_experiment(GRAPH, FLOWS, duration=400.0, seeds=SEEDS, penetrations=[1.0])
    short = run_experiment(
        GRAPH,
        FLOWS,
        duration=400.0,
        seeds=SEEDS,
        penetrations=[1.0],
        channel=ChannelConfig(range_m=60.0),
    )
    assert short["sweep"][0]["messageDeliveryRatio"] < 1.0
    assert -delay(short, 0)["change"] <= -delay(full, 0)["change"]


def test_experiment_is_deterministic() -> None:
    kw: Dict[str, Any] = dict(
        duration=300.0,
        seeds=[1, 2],
        penetrations=[0.5],
        channel=ChannelConfig("uniform", 200.0, 100.0, 0.2),
    )
    assert run_experiment(GRAPH, FLOWS, **kw) == run_experiment(GRAPH, FLOWS, **kw)


def test_sensitivity_grid_and_provenance() -> None:
    res = run_experiment(
        GRAPH,
        FLOWS,
        duration=300.0,
        seeds=SEEDS,
        penetrations=[1.0],
        channel=ChannelConfig(range_m=300.0),
        sensitivity=SensitivitySpec(1.0, (0.0, 3000.0), (0.0, 0.9)),
    )
    cells = {
        (c["latencyMs"], c["lossProbability"]): c for c in res["sensitivity"]["cells"]
    }
    assert len(cells) == 4
    best = cells[(0.0, 0.0)]["delayBenefitSeconds"]
    assert best >= cells[(3000.0, 0.0)]["delayBenefitSeconds"] >= 0.0
    assert best >= cells[(0.0, 0.9)]["delayBenefitSeconds"] >= 0.0
    assert cells[(0.0, 0.9)]["deliveryRatio"] < 0.2
    prov = res["provenance"]
    assert prov["channel"]["rangeM"] == 300.0 and prov["seeds"] == SEEDS
    assert prov["assumptions"] and prov["behaviour"]["min_speed_fraction"] == 0.4


def test_hazard_rerouting_helps_and_degrades_with_loss() -> None:
    hz = Hazard("J11>J12", 100.0, 90.0)

    def coop_delay(loss: float) -> float:
        res = run_experiment(
            GRAPH,
            FLOWS,
            duration=400.0,
            seeds=[1, 2],
            penetrations=[1.0],
            hazard=hz,
            channel=ChannelConfig(loss_probability=loss),
        )
        row = res["sweep"][0]
        assert row["reroutes"] > 0
        return float(row["metrics"]["delaySeconds"]["cooperative"])

    base = run_experiment(
        GRAPH, FLOWS, duration=400.0, seeds=[1, 2], penetrations=[0.0], hazard=hz
    )["baseline"]["mean"]["delaySeconds"]
    no_loss, heavy = coop_delay(0.0), coop_delay(0.95)
    assert no_loss < base
    assert no_loss <= heavy <= base


def test_unknown_hazard_link_is_rejected() -> None:
    with pytest.raises(ValueError):
        run_experiment(GRAPH, FLOWS, hazard=Hazard("nope", 0.0, 10.0))


# -- router ------------------------------------------------------------------

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_schemas_endpoint() -> None:
    body = client.get("/api/v2/v2x/schemas").json()
    assert body["kinds"] == ["bsm", "spat", "hazard"]
    assert body["topic"] == "urbanflow/v2x/<kind>/<node>"
    assert "vehicleId" in body["schemas"]["bsm"]["properties"]
    assert "paired_t" in body["methods"]


def test_experiment_endpoint() -> None:
    r = client.post(
        "/api/v2/v2x/experiment",
        json={
            "duration": 300,
            "seeds": [1, 2],
            "penetrations": [0, 1],
            "channel": {"latencyMs": 100, "lossProbability": 0.1},
            "sensitivity": {
                "penetration": 1,
                "latenciesMs": [0, 1000],
                "lossProbabilities": [0, 0.5],
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [row["penetration"] for row in body["sweep"]] == [0, 1]
    assert body["provenance"]["channel"]["lossProbability"] == 0.1
    assert len(body["sensitivity"]["cells"]) == 4
    assert body["sweep"][1]["metrics"]["stops"]["change"] < 0


@pytest.mark.parametrize(
    "patch",
    [
        {"seeds": [1]},
        {"seeds": list(range(11))},
        {"seeds": [1, 1]},
        {"duration": 5000},
        {"penetrations": [1.5]},
        {"penetrations": [0.1] * 7},
        {"channel": {"lossProbability": 2}},
        {"channel": {"latencyMs": -5}},
        {"grid": {"rows": 9, "cols": 9}},
        {"hazard": {"linkId": "nope"}},
        {"sensitivity": {"latenciesMs": [0] * 7}},
        {"sensitivity": {"lossProbabilities": [1.5]}},
        {"method": "magic"},
    ],
)
def test_experiment_endpoint_bounds(patch: Dict[str, Any]) -> None:
    body = {"duration": 100, "seeds": [1, 2], "penetrations": [1], **patch}
    assert client.post("/api/v2/v2x/experiment", json=body).status_code == 422


# -- MQTT adapter ------------------------------------------------------------


class FakeClient:
    def __init__(self) -> None:
        self.on_message: Any = None
        self.published: List[tuple[str, str, int]] = []
        self.subscribed: List[str] = []
        self.calls: List[str] = []

    def connect(self, host: str, port: int, keepalive: int) -> None:
        self.calls.append(f"connect {host}:{port}")

    def loop_start(self) -> None:
        self.calls.append("loop_start")

    def loop_stop(self) -> None:
        self.calls.append("loop_stop")

    def disconnect(self) -> None:
        self.calls.append("disconnect")

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))

    def subscribe(self, pattern: str, qos: int = 0) -> None:
        self.subscribed.append(pattern)


class Msg:
    def __init__(self, topic: str, payload: str) -> None:
        self.topic, self.payload = topic, payload.encode()


def _bsm() -> BasicSafetyMessage:
    return BasicSafetyMessage(
        vehicleId="v1", x=0, y=0, speed=5, heading=10, timestamp=1.0
    )


def test_mqtt_adapter_topics_and_round_trip_with_fake_client() -> None:
    fake = FakeClient()
    bus = MqttBus(client=fake, clock=lambda: 2.5)
    got: List[Envelope] = []
    bus.subscribe("r", "bsm", handler=got.append)
    bus.subscribe("r2", "bsm", "J00", handler=got.append)
    assert fake.subscribed == ["urbanflow/v2x/bsm/+", "urbanflow/v2x/bsm/J00"]
    bus.publish("bsm", "J00", _bsm())
    topic, payload, _ = fake.published[0]
    assert topic == topic_for("bsm", "J00") and '"vehicleId":"v1"' in payload
    fake.on_message(None, None, Msg(topic, payload))
    assert len(got) == 2 and got[0].delivered_at == 2.5 and got[0].age == 1.5
    # A node only the wildcard subscriber hears; malformed payload, out-of-range payload and kind mismatch drop.
    fake.on_message(None, None, Msg("urbanflow/v2x/bsm/J99", payload))
    fake.on_message(None, None, Msg(topic, "{not json"))
    fake.on_message(
        None, None, Msg(topic, payload.replace('"speed":5.0', '"speed":999'))
    )
    fake.on_message(None, None, Msg("urbanflow/v2x/spat/J00", payload))
    fake.on_message(None, None, Msg("other/topic", payload))
    assert len(got) == 3 and bus.rejected == 4  # J99 reaches only the wildcard
    bus.connect()
    bus.close()
    assert fake.calls == [
        "connect localhost:1883",
        "loop_start",
        "loop_stop",
        "disconnect",
    ]


def test_mqtt_adapter_validates_qos() -> None:
    with pytest.raises(ValueError):
        MqttBus(client=FakeClient(), qos=3)


def test_mqtt_without_paho_raises_a_clear_error() -> None:
    if paho_available():
        pytest.skip("paho-mqtt is installed")
    with pytest.raises(MqttUnavailableError):
        MqttBus()


def test_mqtt_default_client_builds_when_paho_is_installed() -> None:
    pytest.importorskip("paho.mqtt.client")
    bus = MqttBus(client_id="urbanflow-test")  # builds a client, never connects
    assert bus.rejected == 0
