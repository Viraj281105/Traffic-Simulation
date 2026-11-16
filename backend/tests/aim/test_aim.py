"""AIM: geometry, reservations, safety checker, comparison and router (F20)."""

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.aim.experiment import run_comparison
from src.aim.geometry import build_geometry
from src.aim.manager import Request, ReservationManager
from src.aim.router import router
from src.aim.safety import validate
from src.aim.simulation import SimConfig, run
from src.aim.trajectory import KinParams, plan_for

SEEDS = (1, 2, 3, 4)
DEMANDS = (100.0, 300.0, 500.0)


def cfg(mode: str, demand: float, seed: int, **kw: object) -> SimConfig:
    return SimConfig(mode=mode, duration=120.0, demand_vph=demand, seed=seed, **kw)  # type: ignore[arg-type]


def test_geometry_tiles_and_windows() -> None:
    geo = build_geometry()
    assert geo.tile_count == 49
    straight = geo.windows[(0, "straight")]
    assert {w[0] for w in straight} <= set(range(49))
    # opposing straights share no tile at the lane offsets, crossing ones do
    south = {w[0] for w in geo.windows[(0, "straight")]}
    west = {w[0] for w in geo.windows[(1, "straight")]}
    assert south & west
    assert geo.length[(0, "left")] > geo.length[(0, "right")]


def test_plan_hits_entry_time_within_bounds() -> None:
    p = KinParams()
    plan = plan_for(-150.0, p.vmax, 0.0, 20.0, 10.0, -25.0, p)
    assert plan is not None
    x, v = plan.state(20.0)
    assert abs(x) < 1e-6 and abs(v - 10.0) < 1e-6
    stop = plan_for(-150.0, p.vmax, 0.0, 60.0, 10.0, -25.0, p)
    assert stop is not None and stop.stops
    assert plan_for(-150.0, p.vmax, 0.0, 5.0, 10.0, -25.0, p) is None


def test_reservation_never_granted_on_conflicting_tile() -> None:
    manager = ReservationManager(build_geometry(radius=1.5))
    p = KinParams()
    first = Request(1, 0, "straight", 4.5, 20.0, 10.0)
    second = Request(2, 1, "straight", 4.5, 20.0, 10.0)  # crosses the first

    def plan(t: float):  # type: ignore[no-untyped-def]
        return plan_for(-150.0, p.vmax, 0.0, t, 10.0, -25.0, p)

    r1 = manager.request(first, plan)
    assert r1 is not None and not r1.counter_offer
    assert manager.conflict_shift(second, 20.0) > 0
    r2 = manager.request(second, plan)
    assert r2 is not None and r2.counter_offer and r2.t_entry > 20.0
    with pytest.raises(ValueError):
        manager.book(second, 20.0, r2.plan)
    # audit the whole book: per tile, reservations are separated by the buffer
    for tile in {t for r in manager.history for t, _, _ in r.tile_intervals}:
        spans = sorted(
            (a, b) for r in manager.history for t, a, b in r.tile_intervals if t == tile
        )
        for (_, b1), (a2, _) in zip(spans, spans[1:]):
            assert a2 - b1 >= manager.config.time_buffer - 1e-9


def test_checker_catches_injected_overlap() -> None:
    result = run(cfg("aim", 300.0, 1))
    assert result.safety.passed
    tracks = copy.deepcopy(result.tracks)
    clone = copy.deepcopy(tracks[len(tracks) // 2])
    clone.vid = 10_000  # a ghost driving the very same trajectory
    report = validate(tracks + [clone], build_geometry(), 0.1)
    assert report.conflicts > 0 and not report.passed


def test_checker_flags_deadlock_and_bounds() -> None:
    tracks = copy.deepcopy(run(cfg("aim", 200.0, 2)).tracks)
    tracks[0].exited = False
    assert validate(tracks, build_geometry(), 0.1).deadlock
    tracks = copy.deepcopy(run(cfg("aim", 200.0, 2)).tracks)
    tracks[1].vs[5] += 5.0
    assert not validate(tracks, build_geometry(), 0.1).passed


@pytest.mark.parametrize("mode", ["aim", "signal"])
def test_zero_conflicts_no_deadlock_over_seeds(mode: str) -> None:
    for demand in DEMANDS:
        for seed in SEEDS:
            s = run(cfg(mode, demand, seed), keep_tracks=False).safety
            assert s.conflicts == 0 and not s.deadlock and s.passed, (
                mode,
                demand,
                seed,
            )
            assert s.minGapSeconds is None or s.minGapSeconds >= 0.2


def test_determinism() -> None:
    a = run(cfg("aim", 300.0, 7))
    b = run(cfg("aim", 300.0, 7))
    assert a.metrics == b.metrics
    assert [t.xs for t in a.tracks] == [t.xs for t in b.tracks]
    assert run(cfg("aim", 300.0, 8)).metrics != a.metrics


def mean_delay(mode: str, demand: float, **kw: object) -> float:
    vals = [run(cfg(mode, demand, s, **kw), False).metrics["meanDelay"] for s in SEEDS]
    return sum(vals) / len(vals)


def test_signal_delay_grows_with_demand() -> None:
    delays = [mean_delay("signal", d) for d in DEMANDS]
    assert delays[0] < delays[1] < delays[2]


def test_aim_beats_signal_at_moderate_demand() -> None:
    assert mean_delay("aim", 300.0) < mean_delay("signal", 300.0)


def test_message_loss_retries_and_stays_safe() -> None:
    clean = run(cfg("aim", 300.0, 3), False)
    lossy = run(cfg("aim", 300.0, 3, loss_probability=0.6), False)
    assert clean.metrics["lostMessages"] == 0
    assert lossy.metrics["lostMessages"] > 0
    assert lossy.metrics["requests"] > clean.metrics["requests"]
    assert lossy.safety.passed
    assert lossy.metrics["entered"] == lossy.metrics["vehicles"]  # all still served


def test_run_comparison_shape() -> None:
    out = run_comparison(
        [1, 2, 3],
        [200.0],
        duration=90.0,
        loss_probabilities=[0.0, 0.5],
        stress_demand=200.0,
    )
    row = out["sweep"][0]
    assert set(row["comparison"]) == {"meanDelay", "stopsPerVehicle", "throughputVph"}
    assert out["provenance"]["inModelBestCase"] and out["gateGAim"]["passed"]
    assert len(out["messageLossStress"]) == 2
    assert {"conflicts", "minGapSeconds", "deadlock", "maxAccel", "passed"} <= set(
        row["aim"]["safety"]
    )


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_router_catalogue_and_comparison() -> None:
    cat = client.get("/api/v2/aim/catalogue").json()
    assert cat["geometry"]["tiles"] == 49 and cat["limits"]["maxSeeds"] == 10
    body = {
        "durationSeconds": 60,
        "seeds": [1, 2],
        "demandsVehPerHourPerApproach": [200],
        "messageLoss": {"demandVehPerHourPerApproach": 200, "lossProbabilities": [0.5]},
    }
    res = client.post("/api/v2/aim/comparison", json=body)
    assert res.status_code == 200
    assert res.json()["sweep"][0]["aim"]["safety"]["passed"]


@pytest.mark.parametrize(
    "patch",
    [
        {"durationSeconds": 601},
        {"seeds": list(range(11))},
        {"seeds": [1, 1]},
        {"demandsVehPerHourPerApproach": [901]},
        {"leftFraction": 0.5, "rightFraction": 0.6},
        {
            "durationSeconds": 600,
            "seeds": list(range(10)),
            "demandsVehPerHourPerApproach": [100, 200, 300, 400, 500, 600],
        },
    ],
)
def test_router_bounds(patch: dict) -> None:  # type: ignore[type-arg]
    assert client.post("/api/v2/aim/comparison", json=patch).status_code == 422
