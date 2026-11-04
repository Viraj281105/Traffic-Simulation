"""Network metrics, congestion propagation, map data and the router (F5)."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.netmetrics import (
    congestion_analysis,
    map_data,
    network_metrics,
    run_recorded,
)
from src.netmetrics.recorder import Recorder
from src.netmetrics.router import router
from src.networks.graph import GraphLink, GraphNode, RoadGraph
from src.networks.grid import (
    build_three_by_three,
    build_twelve_junction_network,
    grid_flows,
    twelve_junction_flows,
)
from src.networks.network_sim import Flow, simulate_network

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _link(
    a: str, b: str, length: float, lanes: int = 2, speed: float = 13.89
) -> GraphLink:
    return GraphLink(
        id=f"{a}>{b}", **{"from": a, "to": b}, length=length, lanes=lanes, speed=speed
    )


def bottleneck_chain() -> RoadGraph:
    """A -> J1 -> J2 -> B where the last link is short and one lane: the jam
    starts at J2>B and must grow backwards, J1>J2 then A>J1."""
    nodes = [
        GraphNode(id="A", x=0, y=0, kind="gate"),
        GraphNode(id="J1", x=400, y=0),
        GraphNode(id="J2", x=800, y=0),
        GraphNode(id="B", x=860, y=0, kind="gate"),
    ]
    links = [
        _link("A", "J1", 400),
        _link("J1", "J2", 400),
        _link("J2", "B", 60, lanes=1),
    ]
    return RoadGraph(name="bottleneck", nodes=nodes, links=links)


# --- observer does not change the run ---------------------------------------


def test_recording_does_not_change_the_result() -> None:
    g = build_three_by_three()
    plain = simulate_network(g, grid_flows(3, 3), duration=300, seed=2)
    recorded, rec = run_recorded(g, grid_flows(3, 3), 300, seed=2)
    assert plain == recorded
    assert isinstance(rec, Recorder) and rec.occ.shape == (300, len(g.links))


# --- network-wide metrics ---------------------------------------------------


def test_metrics_are_consistent_with_the_run() -> None:
    g = build_twelve_junction_network()
    flows = twelve_junction_flows(500)
    res = simulate_network(g, flows, duration=600, seed=3)
    m = network_metrics(g, flows, duration=600, seed=3)
    n = m["network"]
    assert n["completed"] == res["completed"] and n["conserved"]
    assert n["throughputVph"] == pytest.approx(res["completed"] / 600 * 3600, abs=0.01)
    assert n["totalDelaySeconds"] == pytest.approx(
        res["meanDelaySeconds"] * res["completed"], rel=1e-3
    )
    assert n["meanTravelSeconds"] == res["meanTravelSeconds"]
    # per-link passes agree with the engine
    for lid, row in m["perLink"].items():
        assert row["passed"] == res["perLink"][lid]["passed"]
        assert row["peakOccupancy"] <= res["perLink"][lid]["peakOccupancy"]
        assert 0.0 <= row["meanOccupancyRatio"] <= 1.0
    # exited vehicles over the series equal completions (all destinations are gates)
    assert sum(s["exitedVehicles"] for s in m["series"]) == res["completed"]
    # node throughput: gates pass what completes
    gate_passed = sum(v["passed"] for v in m["perNode"].values() if v["kind"] == "gate")
    assert gate_passed == res["completed"]
    assert m["perNode"]["J11"]["meanOccupancy"] > 0


def test_fundamental_diagram_points() -> None:
    g = build_three_by_three()
    m = network_metrics(
        g, grid_flows(3, 3, 700), duration=600, seed=1, bucket_seconds=30
    )
    pts = m["fundamentalDiagram"]["points"]
    assert len(pts) == 20 and len(m["series"]) == 20
    assert all(
        p["densityVehPerKmLane"] >= 0 and p["flowVehPerHourLane"] >= 0 for p in pts
    )
    assert max(p["densityVehPerKmLane"] for p in pts) > min(
        p["densityVehPerKmLane"] for p in pts
    )
    peak = m["fundamentalDiagram"]["peakFlow"]
    assert peak["flowVehPerHourLane"] == max(p["flowVehPerHourLane"] for p in pts)
    # flow per lane cannot exceed saturation (0.5 veh/s/lane = 1800 veh/h/lane)
    assert peak["flowVehPerHourLane"] <= 1800.0


def test_per_link_diagram_is_optional_and_bucket_count_matches() -> None:
    g = build_three_by_three()
    m = network_metrics(
        g,
        grid_flows(3, 3),
        duration=95,
        seed=1,
        bucket_seconds=30,
        per_link_diagram=True,
    )
    assert "perLink" in m["fundamentalDiagram"]
    assert all(
        len(v) == 4 for v in m["fundamentalDiagram"]["perLink"].values()
    )  # 30+30+30+5
    assert (
        "perLink"
        not in network_metrics(g, grid_flows(3, 3), duration=95)["fundamentalDiagram"]
    )


def test_metrics_are_json_serialisable_and_deterministic() -> None:
    g = build_three_by_three()
    a = network_metrics(g, grid_flows(3, 3), duration=200, seed=6)
    assert json.loads(json.dumps(a)) == a
    assert a == network_metrics(g, grid_flows(3, 3), duration=200, seed=6)


# --- spillback and congestion spread ----------------------------------------


def test_spillback_is_detected_when_the_next_link_is_full() -> None:
    c = congestion_analysis(
        bottleneck_chain(), [Flow("A", "B", 3600)], duration=600, seed=1
    )
    ev = c["spillback"]["events"]
    assert ev and ev[0]["link"] == "J1>J2" and ev[0]["blockedBy"] == "J2>B"
    assert (
        ev[0]["durationSeconds"] >= 5
        and c["spillback"]["summary"]["linksAffected"] >= 1
    )
    assert c["run"]["conserved"] and c["run"]["blockedAtEntry"] > 0


def test_no_spillback_in_light_traffic() -> None:
    c = congestion_analysis(
        bottleneck_chain(), [Flow("A", "B", 200)], duration=600, seed=1
    )
    assert c["spillback"]["events"] == [] and c["spread"]["congestedLinks"] == 0
    assert c["spread"]["origin"] is None and c["spread"]["meanSpeedMps"] is None


def test_congestion_spreads_upstream_in_order_on_a_corridor() -> None:
    c = congestion_analysis(
        bottleneck_chain(), [Flow("A", "B", 3600)], duration=600, seed=1
    )
    sp = c["spread"]
    assert sp["origin"] == "J2>B"
    assert [e["link"] for e in sp["order"]] == ["J2>B", "J1>J2", "A>J1"]
    onsets = [e["onsetSeconds"] for e in sp["order"]]
    assert onsets == sorted(onsets) and len(set(onsets)) == 3
    assert [e["direction"] for e in sp["order"]] == [None, "upstream", "upstream"]
    assert (
        sp["maxHops"] == 2
        and sp["upstreamSpeedMps"] > 0
        and sp["downstreamSpeedMps"] is None
    )
    assert sp["durationSeconds"] == pytest.approx(onsets[-1] - onsets[0])
    # heatmap rows come out in the same congestion order
    assert c["heatmap"]["linkIds"] == ["J2>B", "J1>J2", "A>J1"]


def test_heatmap_shape_and_values() -> None:
    g = build_three_by_three()
    c = congestion_analysis(
        g, grid_flows(3, 3, 900), duration=300, seed=2, bucket_seconds=30
    )
    h = c["heatmap"]
    assert len(h["bucketStarts"]) == 10 and h["bucketStarts"][:3] == [0.0, 30.0, 60.0]
    assert (
        len(h["linkIds"])
        == len(g.links)
        == len(h["values"])
        == len(h["queue"])
        == len(h["blockedFraction"])
    )
    assert all(len(row) == 10 for row in h["values"])
    assert all(0.0 <= v <= 1.0 for row in h["values"] for v in row)
    assert all(0.0 <= v <= 1.0 for row in h["blockedFraction"] for v in row)
    assert [r["id"] for r in c["links"]] == h["linkIds"]
    assert json.loads(json.dumps(c)) == c


def test_congestion_analysis_is_deterministic_and_conserving_over_seeds() -> None:
    g = build_three_by_three()
    for seed in (1, 2, 3):
        a = congestion_analysis(g, grid_flows(3, 3, 1500), duration=300, seed=seed)
        assert a["run"]["conserved"]
        assert a == congestion_analysis(
            g, grid_flows(3, 3, 1500), duration=300, seed=seed
        )


def test_heavy_grid_spreads_between_junctions() -> None:
    g = build_twelve_junction_network()
    c = congestion_analysis(g, twelve_junction_flows(1400), duration=900, seed=5)
    sp = c["spread"]
    assert sp["congestedLinks"] >= 3 and sp["maxHops"] >= 1
    assert all(e["rank"] == i + 1 for i, e in enumerate(sp["order"]))
    assert c["spillback"]["summary"]["events"] > 0


def test_oversized_analysis_is_refused() -> None:
    g = build_twelve_junction_network()
    with pytest.raises(ValueError):
        run_recorded(g, twelve_junction_flows(), duration=3600, seed=1, dt=0.01)


# --- map data ----------------------------------------------------------------


def test_map_data_with_and_without_geo() -> None:
    g = build_three_by_three()  # no lat/lon on the nodes
    plain = map_data(g)
    assert (
        plain["hasGeo"] is False
        and "lat" not in plain["nodes"][0]
        and "pathLatLon" not in plain["links"][0]
    )
    assert (
        plain["boundsLocal"]["minX"] == -250.0
        and len(plain["nodes"]) == 21
        and len(plain["links"]) == 48
    )
    placed = map_data(g, 51.5, -0.12, link_values={"J00>J01": 0.5}, value_label="occ")
    assert (
        placed["hasGeo"] is True
        and placed["boundsLatLon"]["north"] > placed["boundsLatLon"]["south"]
    )
    link = next(k for k in placed["links"] if k["id"] == "J00>J01")
    assert (
        link["value"] == 0.5
        and link["bearingDegrees"] == 90.0
        and len(link["pathLatLon"]) == 2
    )
    assert placed["valueLabel"] == "occ"
    native = map_data(build_twelve_junction_network())
    assert (
        native["hasGeo"] is True and map_data(build_twelve_junction_network()) == native
    )


# --- router ------------------------------------------------------------------

BASE = "/api/v2/network-metrics"


def test_api_grid() -> None:
    r = client.get(f"{BASE}/grid", params={"rows": 2, "cols": 4})
    assert r.status_code == 200
    body = r.json()
    assert body["validation"]["valid"] and body["graph"]["format"] == "urbanflow-graph"
    assert body["flows"] and body["map"]["format"] == "urbanflow-map-data"
    twelve = client.get(f"{BASE}/grid", params={"preset": "12-junction"}).json()
    assert twelve["validation"]["stats"]["junctions"] == 12 and twelve["map"]["hasGeo"]
    assert client.get(f"{BASE}/grid", params={"rows": 99}).status_code == 422


def test_api_simulate_defaults_and_map() -> None:
    r = client.post(
        f"{BASE}/simulate", json={"duration": 120, "seed": 3, "includeMap": True}
    )
    assert r.status_code == 200
    body = r.json()
    assert (
        body["format"] == "urbanflow-network-metrics" and body["network"]["conserved"]
    )
    assert len(body["perLink"]) == 48 and body["map"]["links"][0]["value"] is not None
    again = client.post(
        f"{BASE}/simulate", json={"duration": 120, "seed": 3, "includeMap": True}
    ).json()
    assert again == body


def test_api_simulate_custom_graph_and_errors() -> None:
    from src.networks.graph import serialize_graph

    graph = serialize_graph(bottleneck_chain())
    flows = [{"origin": "A", "destination": "B", "vehiclesPerHour": 900}]
    ok = client.post(
        f"{BASE}/simulate", json={"graph": graph, "flows": flows, "duration": 60}
    )
    assert ok.status_code == 200 and ok.json()["network"]["entered"] > 0
    assert (
        client.post(f"{BASE}/simulate", json={"graph": graph}).status_code == 422
    )  # no flows
    bad = [{"origin": "A", "destination": "ZZ", "vehiclesPerHour": 10}]
    assert (
        client.post(f"{BASE}/simulate", json={"graph": graph, "flows": bad}).status_code
        == 422
    )
    assert (
        client.post(f"{BASE}/simulate", json={"graph": {"nodes": 3}}).status_code == 422
    )
    assert client.post(f"{BASE}/simulate", json={"duration": 99999}).status_code == 422


def test_api_congestion() -> None:
    from src.networks.graph import serialize_graph

    graph = serialize_graph(bottleneck_chain())
    flows = [{"origin": "A", "destination": "B", "vehiclesPerHour": 3600}]
    r = client.post(
        f"{BASE}/congestion",
        json={
            "graph": graph,
            "flows": flows,
            "duration": 600,
            "includeMap": True,
            "bucketSeconds": 60,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["format"] == "urbanflow-congestion"
    assert [e["link"] for e in body["spread"]["order"]] == ["J2>B", "J1>J2", "A>J1"]
    assert len(body["heatmap"]["bucketStarts"]) == 10
    assert body["map"]["valueLabel"] == "peakOccupancyRatio"
