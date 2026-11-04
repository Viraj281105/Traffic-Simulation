# ADR-021: Network Graph Model, Vehicle Handoff and Import Formats

## Status

**Proposed** (V3.9 W39 / V4.0 W40, features F5 and F11). Becomes Accepted when the project owner confirms the decisions marked "open" below.

## Date

2026-11-04

## Context

The V1.9 `urbanflow-network` document (`backend/src/networks/models.py`) describes junctions as scenario references with N/E/S/W arm slots, one edge per arm and direction, acyclic only. Its execution model hands over *flow* (veh/h) from upstream to downstream junctions; it carries no vehicles, has no queue spillback, and rejects any two-way road (a cycle).

F5 needs vehicles that travel between junctions, and F11 needs real networks (OpenStreetMap, SUMO) whose junctions have any number of arms and whose roads are two-way. Neither fits the arm-slot model.

## Decision

1. **A second, general model: `urbanflow-graph` v1** (`networks/graph.py`). Nodes have local-metre positions, a `kind` (`junction` or `gate`) and an optional `control: signal`. Links are directed, with `length`, `lanes`, `speed` (m/s) and `name`. Two-way roads are two links. Ids are strings, sorted for every output, so the same graph always serialises the same way.
2. **The V1.9 network document is kept** as the junction-scenario coupling model and is not changed. `graph_to_network` converts the subset it can hold (arm by compass bearing; gates with a single role; acyclic) and says why when it cannot.
3. **Routing** is Dijkstra on free-flow time, ties broken by link id. An optional per-link penalty (seconds) is the hook for congestion-aware routing in W41+.
4. **Vehicle handoff** (`networks/network_sim.py`) is mesoscopic: a vehicle crosses a link in its free-flow time, waits in the link's FIFO queue, and is handed to the next link of its route when its node passes it. A node passes at most `lanes x 0.5 veh/s` per incoming link, only if the next link has room (storage `lanes x length / 7.5 m`), and at signal nodes only while the link's axis has green (two phases, 60 s cycle). A full next link blocks the head of the queue, which is how spillback arises. Vehicles are created only at gates (counted, or counted as blocked at entry if the first link is full) and removed only at their destination gate.
5. **Conservation** is an invariant reported in every result: `entered = completed + active` and `generated = entered + blockedAtEntry`. Property tests run it over seeds and load levels.
6. **Determinism**: one `random.Random(seed)` drives arrivals; nodes are processed in id order.
7. **Import and export** read text (no live network calls) and return an `ImportResult` with `errors` (fatal), `messages` (what was skipped or assumed) and the graph:
   * OpenStreetMap XML and Overpass JSON: drivable `highway` classes only, ways split at shared nodes, ends and signals, `maxspeed`/`lanes`/`oneway` honoured, defaults per class.
   * SUMO `.net.xml`: import and export; export then import preserves ids, topology, geometry, lanes, speed, gates and signals (tested). Lane-level connections and traffic-light programs are counted and reported, not kept.
   * GTFS: stops, route stop sequences and headways. Synchro UTDF: per-approach lanes and volumes, cycle and offset. Neither builds a graph; both say so.
   * XML with a DOCTYPE or entities is refused.
8. **Validation** (`validate_graph`) returns `errors` (block use) and `warnings` as sentences meant for an upload screen, plus summary stats.
9. **API**: a new router (`networks/import_api.py`, prefix `/api/v2/network-graphs`), stateless, registered with the same API-key and signed-in-user dependencies as the V1.9 router.

## Performance budget (open)

The F5 budget is not yet fixed. Measured so far: the two-junction corridor (14 links) runs 600 simulated seconds in about 0.03 s on the development machine. The 10+ junction budget is to be measured and recorded here before acceptance.

## Alternatives considered

* **Extend `urbanflow-network`.** Rejected: arm slots, one edge per arm and acyclicity are baked into its validator and every test of it; two-way OSM roads cannot be expressed.
* **Wrap the single-junction engine per node now.** Deferred: the engine's junction geometry is built from a scenario; a mesoscopic handoff proves routing, conservation and the import path first. The `JunctionExecutor` seam in `execution.py` is where a per-junction engine would plug in later (open decision: whether W41 does).
* **Adopt OSMnx/GeoPandas now.** Rejected for W39: a fixture-driven parser has no extra dependencies and no network access; OSMnx can feed the same `import_osm` text later.
* **Lane-level graph (SUMO style).** Rejected: link-level routing is enough for F5, and lane connections can be added as optional link metadata.

## Consequences

* Two network documents coexist; the graph is the import and run model, the V1.9 document remains the scenario-coupling model.
* The mesoscopic model is **in-model only**: it is not calibrated, and car-following, lane changing and conflict resolution inside a junction are not simulated. Results must be labelled accordingly.
* Signal timing at imported signals is the default two-phase pattern; SUMO and Synchro timing is read as a note, not applied.
* Open: where gates sit for imported OSM data (currently dead ends of the extract), and whether to snap GTFS stops to the graph (W41).
