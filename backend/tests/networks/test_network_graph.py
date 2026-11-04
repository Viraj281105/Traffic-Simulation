"""W39/W40: graph model, routing, vehicle handoff, importers, validation, API.
Fixtures live in ``fixtures/``; nothing here touches the network."""

import base64
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.networks.corridor import build_two_junction_corridor, corridor_flows
from src.networks.graph import (
    GraphLink,
    GraphNode,
    RoadGraph,
    graph_to_network,
    serialize_graph,
    shortest_path,
    validate_graph,
)
from src.networks.import_api import router
from src.networks.network_sim import Flow, simulate_network
from src.networks.osm_import import import_osm
from src.networks.sumo_io import export_sumo, import_sumo
from src.networks.transit_import import import_gtfs, import_gtfs_zip, import_synchro
from src.networks.validate import validate_network

FIX = Path(__file__).parent / "fixtures"
app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _link(i: str, a: str, b: str, length: float = 100.0, **kw: Any) -> GraphLink:
    return GraphLink(id=i, **{"from": a, "to": b}, length=length, **kw)


# --- graph and routing -----------------------------------------------------


def test_shortest_path_prefers_faster_route_and_is_deterministic() -> None:
    g = RoadGraph(
        nodes=[GraphNode(id=n) for n in "ABCD"],
        links=[
            _link("AB", "A", "B", 100, speed=5),  # 20 s
            _link("BD", "B", "D", 100, speed=5),  # 20 s
            _link("AC", "A", "C", 150, speed=15),  # 10 s
            _link("CD", "C", "D", 150, speed=15),  # 10 s
        ],
    )
    assert shortest_path(g, "A", "D") == ["AC", "CD"]
    assert shortest_path(g, "A", "D", penalty={"AC": 30.0}) == ["AB", "BD"]
    assert shortest_path(g, "D", "A") is None
    assert shortest_path(g, "A", "A") == []
    assert shortest_path(g, "A", "nope") is None


def test_corridor_shape() -> None:
    g = build_two_junction_corridor()
    assert {n.id for n in g.nodes if n.kind == "junction"} == {"J1", "J2"}
    assert validate_graph(g)["valid"]
    assert shortest_path(g, "W", "E") == ["W>J1", "J1>J2", "J2>E"]
    assert shortest_path(g, "N1", "S2") == ["N1>J1", "J1>J2", "J2>S2"]


# --- vehicles across the network -------------------------------------------


def test_vehicles_cross_both_junctions_and_count_is_conserved() -> None:
    g = build_two_junction_corridor()
    res = simulate_network(g, corridor_flows(), duration=600, seed=7)
    assert res["entered"] > 100 and res["completed"] > 50
    assert res["conserved"] and res["entered"] == res["completed"] + res["active"]
    assert res["perNode"]["J1"]["passed"] > 0 and res["perNode"]["J2"]["passed"] > 0
    assert res["perLink"]["J1>J2"]["passed"] > 0  # handed J1 -> link -> J2
    assert res["unroutable"] == []
    ff = res["routes"][0]["freeFlowSeconds"]
    assert res["meanTravelSeconds"] >= min(r["freeFlowSeconds"] for r in res["routes"])
    assert ff == pytest.approx(1000 / 13.89, abs=0.5)


def test_run_is_deterministic_and_seed_sensitive() -> None:
    g = build_two_junction_corridor()
    a = simulate_network(g, corridor_flows(), duration=300, seed=3)
    assert a == simulate_network(g, corridor_flows(), duration=300, seed=3)
    assert a != simulate_network(g, corridor_flows(), duration=300, seed=4)


@pytest.mark.parametrize("seed", [1, 2, 3, 11])
@pytest.mark.parametrize("vph", [200.0, 1500.0, 5000.0])
def test_conservation_property_under_load(seed: int, vph: float) -> None:
    g = build_two_junction_corridor()
    flows = [Flow("W", "E", vph), Flow("E", "W", vph), Flow("N1", "S2", vph / 2)]
    res = simulate_network(g, flows, duration=240, seed=seed)
    assert res["conserved"]
    assert res["generated"] == res["entered"] + res["blockedAtEntry"]
    # Nothing exceeds its storage.
    links = g.link_map()
    for lid, stat in res["perLink"].items():
        assert stat["peakOccupancy"] <= max(1, int(links[lid].lanes * links[lid].length / 7.5))


def test_spillback_blocks_entry_when_overloaded() -> None:
    res = simulate_network(build_two_junction_corridor(), [Flow("W", "E", 7200)], duration=300, seed=1)
    assert res["blockedAtEntry"] > 0 and res["conserved"]


def test_unroutable_flow_is_reported() -> None:
    g = build_two_junction_corridor(oneway=True)
    res = simulate_network(g, [Flow("E", "W", 300)], duration=60)
    assert res["unroutable"] == ["E->W"] and res["entered"] == 0


def test_signal_gives_each_axis_turns() -> None:
    g = build_two_junction_corridor()
    res = simulate_network(g, [Flow("W", "E", 900), Flow("N1", "S1", 900)], duration=600, seed=2)
    assert res["perLink"]["W>J1"]["passed"] > 0 and res["perLink"]["N1>J1"]["passed"] > 0


# --- validation messages ---------------------------------------------------


def test_validation_messages_are_readable() -> None:
    bad = {
        "nodes": [{"id": "A"}, {"id": "A"}, {"id": "B"}],
        "links": [
            {"id": "1", "from": "A", "to": "Z", "length": 50},
            {"id": "2", "from": "B", "to": "B", "length": 50, "lanes": 12},
            {"id": "2", "from": "A", "to": "B", "length": 50000},
        ],
    }
    out = validate_graph(bad)
    assert not out["valid"]
    text = " | ".join(out["errors"])
    for needle in ("Duplicate node id 'A'", "unknown node 'Z'", "same node", "12 lanes", "Duplicate link id '2'", "limit is 20000"):
        assert needle in text
    assert validate_graph({})["errors"] == ["The network has no nodes; nothing was imported"]
    assert not validate_graph([1])["valid"]
    assert validate_graph({"nodes": [{"id": "A"}], "links": [{"id": "x", "from": "A", "to": "A", "length": -1}]})["errors"]


def test_validation_warnings_for_split_networks() -> None:
    g = RoadGraph(
        nodes=[GraphNode(id=n) for n in "ABCD"] + [GraphNode(id="G", kind="gate")],
        links=[_link("AB", "A", "B"), _link("CD", "C", "D", length=2.0)],
    )
    out = validate_graph(g)
    assert out["valid"]
    joined = " | ".join(out["warnings"])
    assert "2 separate parts" in joined or "3 separate parts" in joined
    assert "only 2 m long" in joined and "Node 'G' has no links" in joined
    assert "Junction 'A' has no entry link" in joined
    assert "No entry gate" in joined


# --- OSM -------------------------------------------------------------------


def test_osm_xml_import() -> None:
    res = import_osm((FIX / "small.osm").read_text())
    assert res.graph is not None and not res.errors
    g = res.graph
    nodes, links = g.node_map(), g.link_map()
    assert nodes["2"].kind == "junction" and nodes["3"].control == "signal"
    assert nodes["1"].kind == "gate" and nodes["5"].kind == "gate"
    # Main Street split at 2 and 3, both ways; maxspeed 30 mph, lanes 2 -> 1 per direction.
    assert {"100:0", "100:0r", "100:1", "100:2r"} <= set(links)
    assert links["100:0"].speed == pytest.approx(13.41, abs=0.01) and links["100:0"].lanes == 1
    assert links["100:0"].length == pytest.approx(140.0, abs=3)
    assert links["100:0"].name == "Main Street"
    assert "400:0" in links and "400:0r" not in links  # oneway
    assert not any(k.id.startswith(("300", "500")) for k in g.links)
    joined = " ".join(res.messages)
    assert "footway x1" in joined and "Way 500 skipped" in joined
    assert validate_graph(g)["valid"]
    # Local coordinates are metres around the centre.
    assert abs(nodes["1"].x) < 400 and abs(nodes["5"].y) < 400
    assert shortest_path(g, "1", "4") == ["100:0", "100:1", "100:2"]


def test_osm_overpass_json_matches_xml_topology() -> None:
    js = import_osm((FIX / "small.overpass.json").read_text())
    assert js.graph is not None
    assert {"100:0", "100:1", "100:2", "200:0", "200:1"} <= set(js.graph.link_map())
    assert js.graph.node_map()["3"].control == "signal"


@pytest.mark.parametrize(
    "text, needle",
    [
        ("not xml", "Not well-formed XML"),
        ("<osm/>", "No drivable roads"),
        ("<gpx/>", "Not OSM XML"),
        ('<!DOCTYPE osm [<!ENTITY x "y">]><osm/>', "DOCTYPE"),
        ('{"nope": 1}', "Not Overpass JSON"),
        ('{"elements": [', "Expecting"),
    ],
)
def test_osm_bad_input_gives_readable_error(text: str, needle: str) -> None:
    res = import_osm(text)
    assert res.graph is None and needle in res.errors[0]


# --- SUMO ------------------------------------------------------------------


def test_sumo_import_skips_internal_and_reports_unsupported() -> None:
    res = import_sumo((FIX / "sample.net.xml").read_text())
    assert res.graph is not None and not res.errors
    g = res.graph
    assert set(g.link_map()) == {"AB", "BA", "BC", "CB"}
    assert g.link_map()["AB"].lanes == 2 and g.link_map()["BC"].speed == 8.33
    assert g.link_map()["BC"].name == "East Street"
    assert g.node_map()["B"].control == "signal" and g.node_map()["A"].kind == "gate"
    assert ":B_internal" not in g.node_map()
    joined = " ".join(res.messages)
    assert "2 lane connection(s)" in joined and "traffic-light program" in joined
    assert "internal edges" in joined
    assert shortest_path(g, "A", "C") == ["AB", "BC"]


def test_sumo_round_trip_preserves_network() -> None:
    for g in (build_two_junction_corridor(), import_osm((FIX / "small.osm").read_text()).graph):
        assert g is not None
        xml = export_sumo(g)
        assert xml == export_sumo(g)  # deterministic
        back = import_sumo(xml)
        assert back.graph is not None and back.errors == []
        a, b = serialize_graph(g), serialize_graph(back.graph)
        strip = lambda d: [{k: v for k, v in n.items() if k not in ("lat", "lon")} for n in d]  # noqa: E731
        assert strip(a["nodes"]) == strip(b["nodes"])
        assert a["links"] == b["links"]


def test_sumo_bad_input() -> None:
    assert "Not a SUMO net" in import_sumo("<osm/>").errors[0]
    assert "Not well-formed" in import_sumo("<net>").errors[0]
    assert "No usable edges" in import_sumo("<net/>").errors[0]


# --- GTFS / Synchro --------------------------------------------------------


def _gtfs() -> Dict[str, str]:
    return {p.name: p.read_text() for p in (FIX / "gtfs").glob("*.txt")}


def test_gtfs_import_routes_and_headway() -> None:
    res = import_gtfs(_gtfs())
    assert not res.errors
    route = res.stats["transit"]["routes"][0]
    assert route["id"] == "R1" and route["stops"] == ["S1", "S2", "S3"]
    assert route["trips"] == 3 and route["meanHeadwaySeconds"] == 600.0
    assert any("Trip 'T9' skipped" in m for m in res.messages) is False  # T9 has no stop_times
    assert res.stats["stops"] == 3


def test_gtfs_missing_files_and_zip() -> None:
    files = _gtfs()
    del files["trips.txt"]
    assert "missing required file(s): trips.txt" in import_gtfs(files).errors[0]
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in _gtfs().items():
            zf.writestr(name, text)
    assert import_gtfs_zip(buf.getvalue()).stats["routes"] == 1
    assert "Not a valid zip" in import_gtfs_zip(b"nope").errors[0]


def test_synchro_import() -> None:
    res = import_synchro((FIX / "synchro.csv").read_text())
    assert not res.errors
    (inter,) = res.stats["synchro"]["intersections"]
    assert inter["id"] == "1" and inter["cycleSeconds"] == 90 and inter["offsetSeconds"] == 12
    assert inter["lanes"]["NBT"] == 2 and inter["volumes"]["WBT"] == 210
    south = inter["approaches"]["south"]  # northbound traffic enters from the south
    assert south == {"lanes": 3.0, "vehiclesPerHour": 510.0}
    assert "Phases" in " ".join(res.messages)
    assert "No 'Lanes' table" in import_synchro("hello,world\n1,2\n").errors[0]


# --- conversion to the older network model ---------------------------------


def test_graph_to_network_for_oneway_corridor() -> None:
    doc, notes = graph_to_network(build_two_junction_corridor(oneway=True))
    assert doc is not None and notes == []
    out = validate_network(doc)
    assert not any("arm" in e for e in out["errors"]), out["errors"]
    both, notes2 = graph_to_network(build_two_junction_corridor())
    assert both is None and "both an entry and an exit" in notes2[0]


# --- API -------------------------------------------------------------------


def test_api_validate_import_export_simulate() -> None:
    base = "/api/v2/network-graphs"
    corridor = client.get(f"{base}/corridor").json()
    v = client.post(f"{base}/validate", json={"graph": corridor["graph"]}).json()
    assert v["valid"] and v["stats"]["junctions"] == 2
    assert client.post(f"{base}/validate", json={"graph": {"nodes": []}}).json()["valid"] is False

    osm = client.post(f"{base}/import", json={"format": "osm", "content": (FIX / "small.osm").read_text()}).json()
    assert osm["ok"] and osm["validation"]["valid"] and osm["graph"]["source"] == "osm"
    assert osm["messages"] and osm["stats"]["links"] > 0
    sumo = client.post(f"{base}/import", json={"format": "sumo", "content": (FIX / "sample.net.xml").read_text()}).json()
    assert sumo["ok"]
    bad = client.post(f"{base}/import", json={"format": "osm", "content": "garbage"}).json()
    assert bad["ok"] is False and bad["graph"] is None and bad["errors"]
    assert client.post(f"{base}/import", json={"format": "sumo", "content": "  "}).json()["errors"] == ["The file is empty"]
    assert client.post(f"{base}/import", json={"format": "nope", "content": "x"}).status_code == 422

    gt = client.post(f"{base}/import", json={"format": "gtfs", "files": _gtfs()}).json()
    assert gt["ok"] and gt["graph"] is None
    sy = client.post(f"{base}/import", json={"format": "synchro", "content": (FIX / "synchro.csv").read_text()}).json()
    assert sy["ok"] and sy["stats"]["intersections"] == 1
    assert client.post(f"{base}/import", json={"format": "gtfs", "contentBase64": "!!!"}).json()["ok"] is False
    zb = base64.b64encode(b"nope").decode()
    assert "Not a valid zip" in client.post(f"{base}/import", json={"format": "gtfs", "contentBase64": zb}).json()["errors"][0]

    exp = client.post(f"{base}/export/sumo", json={"graph": corridor["graph"]}).json()
    assert exp["filename"] == "network.net.xml" and exp["content"].startswith("<?xml")
    assert client.post(f"{base}/export/sumo", json={"graph": {"nodes": []}}).status_code == 400

    sim = client.post(f"{base}/simulate", json={"duration": 300, "seed": 5}).json()
    assert sim["format"] == "urbanflow-graph-result" and sim["conserved"] and sim["completed"] > 0
    custom = client.post(
        f"{base}/simulate",
        json={"graph": corridor["graph"], "flows": [{"origin": "W", "destination": "E", "vehiclesPerHour": 600}], "seed": 5},
    ).json()
    assert custom["conserved"] and custom["completed"] > 0
    net = client.post(f"{base}/to-network", json={"graph": corridor["graph"]}).json()
    assert net["network"] is None and net["notes"]
