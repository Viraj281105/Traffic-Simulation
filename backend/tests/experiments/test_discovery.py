"""Discovery Lab (W6): search correctness, determinism, budget, seed hygiene, baselines, honesty, packages."""

from __future__ import annotations

import io
import json
import math
import random
import time
import zipfile
from typing import Any, Dict, List, Optional, Sequence

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from src.discovery import nsga2
from src.discovery.models import (
    BASELINES,
    Budget,
    Regime,
    SearchSpec,
    planned_runs,
)
from src.discovery.router import create_router as create_discovery_router
from src.discovery.search import Candidate, Outcome, Search, SeedPools
from src.discovery.service import DiscoveryService
from src.discovery.space import BOUNDS, clamp, random_genome, validate_candidate
from src.experiments import limits
from src.experiments.package import inspect_package, render_checksums

from .conftest import as_user

ALICE, BOB = "alice", "bob"


def _x(genome: Dict[str, Any]) -> List[float]:
    """Three independent genes of the signalised roundabout, scaled to [0, 1]."""
    return [
        (genome["meterGreenNS"] - 10.0) / 30.0,
        (genome["meterGreenEW"] - 10.0) / 30.0,
        (genome["yellow"] - 3.0) / 2.0,
    ]


def zdt1(genome: Dict[str, Any]) -> tuple[float, float]:
    x = _x(genome)
    f1 = x[0]
    g = 1.0 + 9.0 * sum(x[1:]) / (len(x) - 1)
    return f1, g * (1.0 - math.sqrt(f1 / g))


class SyntheticEvaluator:
    """ZDT1 on two genes (known Pareto front, hypervolume 2/3 against (1, 1)); records every call."""

    def __init__(self, held_out_penalty: float = 0.0) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.held_out_penalty = held_out_penalty

    def __call__(
        self,
        candidates: Sequence[Candidate],
        seeds: Sequence[int],
        regime: Regime,
        phase: str,
    ):
        self.calls.append({"phase": phase, "seeds": list(seeds), "n": len(candidates)})
        out: List[Outcome] = []
        for cand in candidates:
            if cand.genome is None:
                f1, f2 = 0.5, 0.5
            else:
                f1, f2 = zdt1(cand.genome)
                if phase == "held_out":
                    f1 += self.held_out_penalty
            out.append(Outcome((f1, f2, 0.0, 0.0), {}, [f1] * len(seeds)))
        return out


def spec(**budget: Any) -> SearchSpec:
    b = {
        "population": 12,
        "generations": 6,
        "tuningSeeds": 1,
        "selectionSeeds": 2,
        "heldOutSeeds": 10,
        "unseenGrid": False,
    }
    b.update(budget)
    return SearchSpec(
        strategies=["signalised_roundabout"],
        budget=Budget.model_validate(b),
        regime=Regime.model_validate({"duration": 60, "warmup": 10}),
        seed=3,
    )


# ---- D5: the algorithm, on a synthetic problem -------------------------------------------------------


def test_search_reaches_90_percent_of_the_known_hypervolume():
    s = Search(spec(population=24, generations=20), SyntheticEvaluator())
    s.run()
    points = [obj[:2] for _g, obj, _gen in s.archive.values() if obj is not None]
    front = [points[i] for i in nsga2.non_dominated_sort(points)[0]]
    hv = nsga2.hypervolume_2d(front, (1.0, 1.0))
    assert hv >= 0.9 * (2.0 / 3.0), hv


def test_nsga2_primitives():
    pts = [(1.0, 2.0), (2.0, 1.0), (2.0, 2.0), None, (0.5, 3.0)]
    fronts = nsga2.non_dominated_sort(pts)
    assert fronts[0] == [0, 1, 4] and fronts[-1] == [3]
    assert nsga2.select_survivors(pts, 3) == [0, 1, 4]
    assert nsga2.hypervolume_2d([(0.0, 0.0)], (1.0, 1.0)) == 1.0


# ---- D1: determinism ------------------------------------------------------------------------------


def test_same_spec_and_seed_give_the_same_trace():
    a = Search(spec(), SyntheticEvaluator()).run()
    b = Search(spec(), SyntheticEvaluator()).run()
    assert a["traceFingerprint"] == b["traceFingerprint"]
    other = spec()
    other = other.model_copy(update={"seed": 4})
    assert (
        Search(other, SyntheticEvaluator()).run()["traceFingerprint"]
        != a["traceFingerprint"]
    )


# ---- D2: validity ---------------------------------------------------------------------------------


def test_clamping_keeps_10000_random_genomes_within_bounds():
    rng = random.Random(0)
    for _ in range(10_000):
        raw = {k: rng.uniform(lo - 100, hi + 100) for k, (lo, hi) in BOUNDS.items()}
        raw["strategy"] = rng.choice(
            ["fixed_time", "adaptive", "roundabout", "signalised_roundabout"]
        )
        raw["spillbackGuard"] = rng.random() < 0.5
        g = clamp(raw)
        for key, (lo, hi) in BOUNDS.items():
            assert lo <= g[key] <= hi, (key, g[key])
        assert g["maxGreen"] >= g["minGreen"] + 5 - 1e-9
        cycle = g["nsGreen"] + g["ewGreen"] + 2 * (g["yellow"] + g["allRed"])
        assert cycle <= 120 + 1e-6


def test_only_validated_genomes_reach_the_evaluator(monkeypatch):
    rng = random.Random(1)
    regime = Regime.model_validate({"duration": 60, "warmup": 10})
    reasons = [
        validate_candidate(
            regime,
            random_genome(
                rng, ["fixed_time", "adaptive", "roundabout", "signalised_roundabout"]
            ),
        )
        for _ in range(200)
    ]
    assert all(r is None or isinstance(r, str) for r in reasons)

    rejected: List[str] = []
    import src.discovery.search as search_module

    def picky(regime: Regime, genome: Dict[str, Any]) -> Optional[str]:
        if genome["meterGreenNS"] > 30:
            rejected.append(genome["strategy"])
            return "validator: planted rejection"
        return None

    monkeypatch.setattr(search_module, "validate_candidate", picky)
    seen: List[float] = []

    class Spy(SyntheticEvaluator):
        def __call__(self, candidates, seeds, regime, phase):
            seen.extend(
                c.genome["meterGreenNS"] for c in candidates if c.genome is not None
            )
            return super().__call__(candidates, seeds, regime, phase)

    result = Search(spec(), Spy()).run()
    assert rejected and all(v <= 30 for v in seen)
    assert result["rejected"]["rejected_by_validator"] == len(rejected)


# ---- D3: budget and cancellation -------------------------------------------------------------------


def test_the_budget_is_never_exceeded():
    sp = spec(unseenGrid=True)
    ev = SyntheticEvaluator()
    result = Search(sp, ev).run()
    used = sum(c["n"] * len(c["seeds"]) for c in ev.calls)
    assert used == result["runs"]["used"] <= planned_runs(sp)


def test_cancel_returns_a_consistent_incomplete_result():
    ev = SyntheticEvaluator()
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 3

    result = Search(spec(), ev, should_stop=stop).run()
    assert result["status"] == "cancelled" and result["complete"] is False
    assert result["heldOut"] is None
    assert len(ev.calls) == 3  # stopped at a batch boundary
    assert result["runs"]["used"] == sum(c["n"] * len(c["seeds"]) for c in ev.calls)


# ---- D4: seed hygiene ------------------------------------------------------------------------------


def test_seed_pools_are_disjoint_and_held_out_is_sealed():
    pools = SeedPools(7, 3, 5, 10)
    with pytest.raises(RuntimeError):
        _ = pools.held_out
    pools.release()
    held = set(pools.held_out)
    assert not held & set(pools.tuning) and not held & set(pools.selection)
    assert not set(pools.tuning) & set(pools.selection)
    assert pools.held_out_hash == SeedPools.hash_of(pools.held_out)


def test_held_out_seeds_are_never_used_before_the_search_ends():
    ev = SyntheticEvaluator()
    result = Search(spec(unseenGrid=True), ev).run()
    phases = [c["phase"] for c in ev.calls]
    first_held = phases.index("held_out")
    assert all(p in ("tuning", "selection") for p in phases[:first_held])
    held = set(next(c["seeds"] for c in ev.calls if c["phase"] == "held_out"))
    for call in ev.calls[:first_held]:
        assert not held & set(call["seeds"])
    committed = result["seedPools"]["heldOutHashCommittedBeforeSearch"]
    held_list = next(c["seeds"] for c in ev.calls if c["phase"] == "held_out")
    assert committed == SeedPools.hash_of(held_list)


# ---- D7: honest reporting --------------------------------------------------------------------------


def test_a_tuning_winner_that_loses_on_held_out_is_reported():
    result = Search(spec(), SyntheticEvaluator(held_out_penalty=5.0)).run()
    assert result["bestOnTuningLosesOnHeldOut"] is True
    rows = result["heldOut"]["candidates"].values()
    assert all(
        v["meanDifference"] > 0 for r in rows for v in r["versusBaselines"].values()
    )
    assert "EXPERIMENTAL" in result["experimental"]


# ---- D6: baselines are the unchanged controllers -----------------------------------------------------


def test_baselines_equal_a_direct_run_of_the_same_scenario(monkeypatch):
    from src.discovery.evaluator import SimulationEvaluator, objectives_of
    from src.discovery.space import regime_scenario
    from src.scenario.documents import ScenarioDocument, compile_scenario
    from src.study.runner import SimTask, run_simulation_tasks

    monkeypatch.setenv("STUDY_WORKERS", "0")
    regime = Regime.model_validate(
        {"duration": 60, "warmup": 5, "vehiclesPerHour": 400}
    )
    outcome = SimulationEvaluator()(
        [Candidate("fixed_time")], [11], regime, "held_out"
    )[0]
    doc = regime_scenario(regime)
    doc["simulation"]["seed"] = 11
    direct = run_simulation_tasks(
        [
            SimTask(
                compile_scenario(ScenarioDocument.model_validate(doc), "fixed_time"),
                "signal",
                60.0,
                "direct",
            )
        ]
    )
    expected, _metrics, _per_seed, _reason = objectives_of(direct)
    assert outcome.objectives == expected


# ---- service, API and package (D8) ------------------------------------------------------------------


@pytest.fixture
def api(make_service):
    service = make_service()
    lab = DiscoveryService(
        service, evaluator_factory=lambda progress: SyntheticEvaluator()
    )
    app = FastAPI()

    def user(x_user: str = Header(default="")) -> str:
        if not x_user:
            raise HTTPException(status_code=401, detail="no user")
        return x_user

    app.include_router(create_discovery_router(user_dependency=user, service=lab))
    return TestClient(app), lab, service


def body(**budget: Any) -> Dict[str, Any]:
    return json.loads(spec(**budget).model_dump_json())


def wait(client: TestClient, sid: str, user: str = ALICE) -> Dict[str, Any]:
    for _ in range(500):
        st = client.get(
            f"/api/v3/discovery/searches/{sid}", headers=as_user(user)
        ).json()
        if st["status"] not in ("queued", "running"):
            return st
        time.sleep(0.02)
    raise AssertionError("search never finished")


def test_search_lifecycle_through_the_api(api):
    client, _lab, service = api
    est = client.post(
        "/api/v3/discovery/estimate", json=body(), headers=as_user(ALICE)
    ).json()
    assert est["runs"] == planned_runs(spec()) and est["wallTime"] == "unverified"
    started = client.post(
        "/api/v3/discovery/searches", json=body(), headers=as_user(ALICE)
    )
    assert started.status_code == 202
    sid = started.json()["id"]
    assert wait(client, sid)["status"] == "completed"
    result = client.get(
        f"/api/v3/discovery/searches/{sid}/result", headers=as_user(ALICE)
    ).json()
    assert (
        result["complete"]
        and result["pareto"]
        and result["heldOut"]["baselines"].keys() == set(BASELINES)
    )
    # Unused budget is refunded.
    assert service.usage.used(ALICE) == pytest.approx(result["runs"]["used"] * 60)
    # Others cannot see it.
    assert (
        client.get(
            f"/api/v3/discovery/searches/{sid}", headers=as_user(BOB)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v3/discovery/searches/{sid}/package", headers=as_user(BOB)
        ).status_code
        == 404
    )
    assert [
        s["id"]
        for s in client.get("/api/v3/discovery/searches", headers=as_user(ALICE)).json()
    ] == [sid]


def test_a_search_over_the_daily_budget_is_refused(api, monkeypatch):
    client, _lab, _service = api
    monkeypatch.setattr(limits, "MAX_DAILY_SIMULATED_SECONDS_PER_USER", 100)
    res = client.post("/api/v3/discovery/searches", json=body(), headers=as_user(ALICE))
    assert (
        res.status_code == 429
        and "maxDailySimulatedSecondsPerUser" in res.json()["detail"]
    )


def test_the_package_verifies_and_tampering_is_caught(api):
    client, _lab, _service = api
    sid = client.post(
        "/api/v3/discovery/searches", json=body(), headers=as_user(ALICE)
    ).json()["id"]
    wait(client, sid)
    data = client.get(
        f"/api/v3/discovery/searches/{sid}/package", headers=as_user(ALICE)
    ).content
    report = inspect_package(data)
    assert report.internallyConsistent, report.errors
    assert report.kind == "discovery_search" and report.replayClass == "exact"

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = {i.filename: zf.read(i) for i in zf.infolist()}
    result = json.loads(members["result.json"])
    result["evaluationLog"][0]["objectives"] = [0, 0, 0, 0]
    members["result.json"] = json.dumps(result).encode()
    body_members = {k: v for k, v in members.items() if k != "SHA256SUMS"}
    members["SHA256SUMS"] = render_checksums(body_members)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for k, v in members.items():
            zf.writestr(k, v)
    tampered = inspect_package(buf.getvalue())
    assert not tampered.internallyConsistent
    assert any(
        "trace fingerprint" in e or "packageChecksums" in e for e in tampered.errors
    )


def test_at_most_two_searches_per_user(api):
    client, lab, _service = api
    import threading

    gate = threading.Event()

    class Slow(SyntheticEvaluator):
        def __call__(self, *a, **k):
            gate.wait(10)
            return super().__call__(*a, **k)

    lab.evaluator_factory = lambda progress: Slow()
    try:
        for _ in range(2):
            assert (
                client.post(
                    "/api/v3/discovery/searches", json=body(), headers=as_user(ALICE)
                ).status_code
                == 202
            )
        third = client.post(
            "/api/v3/discovery/searches", json=body(), headers=as_user(ALICE)
        )
        assert (
            third.status_code == 429
            and "maxActiveSearchesPerUser" in third.json()["detail"]
        )
    finally:
        gate.set()
