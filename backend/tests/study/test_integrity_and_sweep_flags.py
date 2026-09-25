"""Integrity check covers both geometries; sweep tiers carry their limits.

Regression for: the integrity/reproducibility check stepped both controls but
verified only the signal engine (mass conservation, speeds, determinism), its
docstring promised a green-exclusivity invariant that was never implemented,
and `massConservationValid` simply meant "no violations of any kind".
"""

from typing import Any, Dict, List

import pytest

from src.snapshot.dual_orchestrator import DualSimulationOrchestrator
from src.study import validation
from src.study.calibration import calibration_status
from src.study.validation import run_invariant_checks
from src.study.volume_sweep import run_volume_sweep_experiment

# ── integrity check ─────────────────────────────────────────────────────────


def test_clean_run_reports_every_check_for_both_geometries() -> None:
    res = run_invariant_checks(duration=3.0, time_step=0.1, random_seed=7)
    assert res["valid"] is True
    assert res["isDeterministic"] is True
    assert res["massConservationValid"] is True
    assert res["nonNegativeSpeedsValid"] is True
    assert res["signalGreenExclusivityValid"] is True
    assert set(res["geometries"]) == {"signal", "roundabout"}
    for geometry in res["geometries"].values():
        assert geometry["valid"] is True
        assert geometry["isDeterministic"] is True
    assert any("both geometries" in c for c in res["checked"])
    assert any("signal greens" in c for c in res["checked"])


def test_a_roundabout_conservation_violation_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_init = DualSimulationOrchestrator.__init__

    def broken_init(self: Any, config: Dict[str, Any]) -> None:
        original_init(self, config)
        engine = self.engine_roundabout
        real_step = engine.step
        state = {"n": 0}

        def step() -> None:
            real_step()
            state["n"] += 1
            if state["n"] == 2 and engine.spawner is not None:
                engine.spawner.spawned_count += 1  # a vehicle "created" from nowhere

        engine.step = step

    monkeypatch.setattr(DualSimulationOrchestrator, "__init__", broken_init)
    res = run_invariant_checks(duration=2.0, time_step=0.1, random_seed=7)

    assert res["valid"] is False
    assert res["massConservationValid"] is False
    assert res["geometries"]["roundabout"]["valid"] is False
    assert res["geometries"]["signal"]["valid"] is True
    assert any("roundabout vehicle conservation" in v for v in res["violations"])
    # The old check (signal only) would have reported this run as valid.


def test_a_roundabout_negative_speed_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_init = DualSimulationOrchestrator.__init__

    def broken_init(self: Any, config: Dict[str, Any]) -> None:
        original_init(self, config)
        engine = self.engine_roundabout
        real_step = engine.step

        state = {"n": 0}

        def step() -> None:
            real_step()
            state["n"] += 1
            # Only on the final tick: the engine itself rejects a negative
            # speed on the next update, so this is the corruption the
            # invariant check must see.
            if state["n"] == 100:
                for v in engine.pool.active_vehicles:
                    v.speed = -1.0

        engine.step = step

    monkeypatch.setattr(DualSimulationOrchestrator, "__init__", broken_init)
    res = run_invariant_checks(duration=10.0, time_step=0.1, random_seed=7)
    assert res["nonNegativeSpeedsValid"] is False
    assert res["geometries"]["roundabout"]["valid"] is False
    assert res["geometries"]["signal"]["valid"] is True


def test_conflicting_signal_greens_are_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_init = DualSimulationOrchestrator.__init__

    def broken_init(self: Any, config: Dict[str, Any]) -> None:
        original_init(self, config)

        def get_state() -> Dict[str, Any]:
            return {
                "signals": [
                    {"direction": "north", "color": "green"},
                    {"direction": "east", "color": "green"},
                ]
            }

        self.controller_signal.get_state = get_state

    monkeypatch.setattr(DualSimulationOrchestrator, "__init__", broken_init)
    res = run_invariant_checks(duration=1.0, time_step=0.1, random_seed=7)
    assert res["signalGreenExclusivityValid"] is False
    assert res["valid"] is False
    assert res["geometries"]["signal"]["valid"] is False
    assert res["geometries"]["roundabout"]["valid"] is True


def test_roundabout_nondeterminism_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: List[Any] = []
    original = validation._final_metrics

    def diverging(orch: Any, geometry: str) -> Dict[str, Any]:
        if not seen:
            seen.append(orch)
        metrics = dict(original(orch, geometry))
        if geometry == "roundabout" and orch is not seen[0]:
            metrics["throughput"] = metrics["throughput"] + 1
        return metrics

    monkeypatch.setattr(validation, "_final_metrics", diverging)
    res = run_invariant_checks(duration=2.0, time_step=0.1, random_seed=7)
    assert res["isDeterministic"] is False
    assert res["geometries"]["roundabout"]["isDeterministic"] is False
    assert res["geometries"]["signal"]["isDeterministic"] is True
    assert res["valid"] is False


# ── sweep flags, defaults, calibration ──────────────────────────────────────


@pytest.fixture()
def sweep_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.database.db as db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "sweep.db"))


def test_sweep_defaults_to_the_calibrated_single_lane_comparison(
    sweep_db: None,
) -> None:
    res = run_volume_sweep_experiment(arrival_rates=[0.2], duration=2.0)
    assert res["calibration"]["calibrated"] is True
    assert res["calibration"]["lanesPerApproach"] == {
        "north": 1,
        "south": 1,
        "east": 1,
        "west": 1,
    }
    assert res["seedsPerTier"] == 1
    assert res["tieTolerance"] == {"absSeconds": 1.0, "relative": 0.05}


def test_multi_lane_sweep_is_labelled_exploratory(sweep_db: None) -> None:
    res = run_volume_sweep_experiment(
        arrival_rates=[0.2],
        duration=2.0,
        custom_config={
            "roads": {
                "lanesPerApproach": {"north": 2, "south": 2, "east": 2, "west": 2}
            }
        },
    )
    assert res["calibration"]["calibrated"] is False
    assert "Exploratory, not calibrated" in res["calibration"]["note"]


def test_sweep_low_sample_is_inconclusive_not_a_winner(sweep_db: None) -> None:
    # 3 s of simulated traffic: far fewer than 20 vehicles exit on each side.
    res = run_volume_sweep_experiment(arrival_rates=[0.2, 0.4], duration=3.0)
    for run in res["runs"]:
        assert run["winner"] == "inconclusive"
        assert run["inconclusiveReason"] == "low_sample"
    assert res["curves"]["crossoverArrivalRate"] is None
    assert res["curves"]["crossoverBracketArrivalRates"] is None


def test_sweep_flags_a_tier_whose_demand_hit_the_vehicle_limit(sweep_db: None) -> None:
    res = run_volume_sweep_experiment(
        arrival_rates=[0.8],
        duration=20.0,
        custom_config={"traffic": {"totalVehicles": 5}},
    )
    run = res["runs"][0]
    assert run["vehicleLimitReached"] is True
    assert run["winner"] == "inconclusive"
    assert run["inconclusiveReason"] == "vehicle_limit_reached"
    assert run["signal"]["metrics"]["vehicleLimit"] == 5


def test_validation_lists_seeds_that_hit_the_vehicle_limit() -> None:
    res = validation.run_statistical_validation(
        config={
            "simulation": {"timeStep": 0.1, "duration": 30.0, "warmupTime": 1.0},
            "traffic": {"arrivalRate": 1.0, "totalVehicles": 3},
        },
        num_seeds=2,
        duration=30.0,
    )
    assert sorted(res["vehicleLimitReachedSeeds"]) == sorted(res["seeds"])


# ── calibration status ──────────────────────────────────────────────────────


def test_calibration_status_requires_one_lane_on_every_approach() -> None:
    assert calibration_status({"roads": {"lanesPerApproach": 1}})["calibrated"] is True
    # An omitted lane count builds the engine default (2 lanes): not calibrated.
    assert calibration_status({})["calibrated"] is False
    assert calibration_status({"roads": {"lanesPerApproach": 2}})["calibrated"] is False
    mixed = {
        "roads": {"lanesPerApproach": {"north": 1, "south": 1, "east": 1, "west": 2}}
    }
    status = calibration_status(mixed)
    assert status["calibrated"] is False
    assert status["lanesPerApproach"]["west"] == 2
