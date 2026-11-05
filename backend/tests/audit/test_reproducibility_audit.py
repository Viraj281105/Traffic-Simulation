"""The reproducibility audit script repeats exactly on tiny scenarios (R2)."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "reproducibility_audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("reproducibility_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_reproduces_all_scenarios():
    mod = _load()
    sizes = mod.Sizes(
        study_duration=4.0,
        study_seeds=2,
        network_duration=20.0,
        calib_duration=20.0,
        calib_budget=3,
    )
    outcomes = mod.audit(sizes)
    assert len(outcomes) == 3
    for o in outcomes:
        assert o.ok, (o.name, o.problems, o.hash_a, o.hash_b)
        assert o.config_hash == "" or len(o.config_hash) == 64


def test_canonical_ignores_timestamps_and_key_order():
    mod = _load()
    a = {"x": 1, "createdAt": "2026-01-01", "y": [{"timestamp": 5, "z": 2}]}
    b = {"y": [{"z": 2}], "x": 1}
    assert mod.canonical(a) == mod.canonical(b)
    assert json.loads(mod.canonical(a)) == {"x": 1, "y": [{"z": 2}]}


def test_differing_outputs_are_flagged():
    mod = _load()
    assert mod.digest(mod.canonical({"a": 1})) != mod.digest(mod.canonical({"a": 2}))
