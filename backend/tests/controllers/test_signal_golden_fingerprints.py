"""The signalised junction reproduces its recorded fixed-seed fingerprints.

V3.1 W31 (F4): whole-run regression pins for the fixed-time and adaptive
signals, the counterpart of ``test_roundabout_golden_fingerprints.py``. Pins,
harness and the meaning of each pin (exact vs portable) are in
``signal_golden.py`` and ``roundabout_golden.py``. The fast cases run in the
ordinary CI job, the full corpus in the ``signal-golden`` slow shard.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tests.controllers.roundabout_golden import environment_key, fingerprint_run
from tests.controllers.signal_golden import (
    CORPUS,
    baseline_digest,
    compile_case,
    load_fixture,
)

_FIXTURE = load_fixture()
_PINNED: List[Dict[str, Any]] = _FIXTURE["cases"]
_RUNS: Dict[str, Dict[str, Any]] = {}

_DO_NOT_RERECORD = (
    "Do not re-record the fixture to make this pass: a changed fingerprint "
    "means signal behaviour changed. If that is intended, re-record with "
    "--record --force, update BASELINE_DIGEST in this diff and state the reason."
)


def _run(case: Dict[str, Any]) -> Dict[str, Any]:
    """One simulation per case per session, shared by both pin tests."""
    if case["id"] not in _RUNS:
        _RUNS[case["id"]] = fingerprint_run(case["config"], case["path"])
    return _RUNS[case["id"]]


def _params() -> List[Any]:
    return [
        pytest.param(c, id=c["id"], marks=() if c["fast"] else (pytest.mark.slow,))
        for c in _PINNED
    ]


@pytest.mark.parametrize("case", _params())
def test_signal_matches_its_exact_pin(case: Dict[str, Any]) -> None:
    env = environment_key()
    pinned = case["exact"].get(env)
    if pinned is None:
        pytest.skip(
            f"no exact pin for {env} (pinned: {sorted(case['exact'])}); the "
            "portable pin still runs. Add one with --add-environment from the "
            "recording commit."
        )
    assert _run(case)["exact"] == pinned, (
        f"{case['id']} ({case['path']} path) is not bit-identical to the "
        f"recorded run on {env}. {_DO_NOT_RERECORD}"
    )


@pytest.mark.parametrize("case", _params())
def test_signal_matches_its_portable_pin(case: Dict[str, Any]) -> None:
    assert _run(case)["portable"] == case["expected"], (
        f"{case['id']} ({case['path']} path) no longer reproduces the recorded "
        f"run to 1 um / 12 significant digits. {_DO_NOT_RERECORD}"
    )


# The baseline itself, pinned. Re-recording, removing a case or hand-editing a
# pin changes the fixture, so it fails here until this constant is edited in
# the same diff, which is where a reviewer sees the baseline moved. Exact pins
# for further environments are not part of it (see baseline_digest).
BASELINE_DIGEST = "0b862ccb85ab514a2e28b0e7a782faa183ca9a57355797310dcb944b1f2ceac6"


def test_the_baseline_fixture_is_the_recorded_one() -> None:
    assert baseline_digest(_FIXTURE) == BASELINE_DIGEST, (
        "tests/fixtures/signal_golden_fingerprints.json changed in a way that "
        f"moves the baseline. {_DO_NOT_RERECORD}"
    )


def test_every_corpus_case_is_pinned_and_nothing_else() -> None:
    assert [c["id"] for c in _PINNED] == [c["id"] for c in CORPUS]


def test_every_case_has_at_least_one_exact_pin() -> None:
    assert all(c["exact"] for c in _PINNED)


def test_fast_corpus_is_large_enough_to_gate_a_push() -> None:
    assert sum(1 for c in _PINNED if c["fast"]) >= 12


def test_the_corpus_covers_the_layouts_it_claims() -> None:
    """Both signal strategies, 1 and 2 lanes, three- and four-arm junctions,
    mixed vehicles, custom timings, both controller-building paths, no
    collision in any recorded run, and fast and slow cases."""
    configs = [c["config"] for c in _PINNED]
    assert {c["strategy"] for c in _PINNED} == {"fixed_time", "adaptive"}
    assert {c["config"]["roads"]["lanesPerApproach"] for c in _PINNED} >= {1, 2}
    assert any("vehicleMix" in c["vehicleGeneration"] for c in configs)
    assert {c["path"] for c in _PINNED} == {"direct", "study-signal"}
    assert any(c["fast"] for c in _PINNED) and not all(c["fast"] for c in _PINNED)
    arms = {len(c["geometry"].get("arms") or range(4)) for c in configs}
    assert arms == {3, 4}
    assert all(c["expected"]["collisions"] == 0 for c in _PINNED)
    assert all(c["expected"]["exited"] > 0 for c in _PINNED)


@pytest.mark.parametrize(
    "case", [c for c in CORPUS if c["fast"]], ids=lambda c: c["id"]
)
def test_pinned_configs_are_what_the_corpus_compiles_to(case: Dict[str, Any]) -> None:
    """The stored configs are the corpus documents compiled today. The pins
    keep testing their stored config if the compiler changes; this test is
    what notices that it did."""
    pinned = next(c for c in _PINNED if c["id"] == case["id"])
    assert compile_case(case) == pinned["config"]


def test_baseline_digest_ignores_exact_pins() -> None:
    changed = {
        **_FIXTURE,
        "cases": [
            {**c, "exact": {**c["exact"], "other-env": {"trajectory": "x"}}}
            for c in _PINNED
        ],
    }
    assert baseline_digest(changed) == baseline_digest(_FIXTURE)
