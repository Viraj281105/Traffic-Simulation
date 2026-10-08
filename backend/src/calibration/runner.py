"""Validate a calibration request and run it.

``validate_calibration_request`` is cheap and never simulates.
``run_calibration`` is a pure function of its payload and the code version:
no clock, no randomness beyond the seeds it records, so the same request
returns the same result.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.calibration.compare import build_rows
from src.calibration.models import (
    CALIBRATION_RESULT_FORMAT,
    CALIBRATION_RESULT_VERSION,
    MAX_SIMULATED_SECONDS,
    CalibrationOptions,
    ObservationSet,
    observations_fingerprint,
)
from src.calibration.rating import (
    INSUFFICIENT_DATA,
    OVERALL_RULE_TEXT,
    THRESHOLDS,
    THRESHOLDS_VERSION,
    classify,
)
from src.calibration.simulate import simulate_once
from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.core.scenario import (
    JUNCTION_STRATEGY,
    ScenarioDocument,
    Turning,
    compile_scenario,
    parse_scenario,
    scenario_fingerprint,
    validate_scenario,
)
from src.study.calibration import calibration_status

# A scenario that offers this much more/less than was observed is flagged.
FLOW_MISMATCH_RATIO = 0.20
SHARE_MISMATCH_POINTS = 0.10
MIN_REPETITIONS_FOR_SPREAD = 3
SHORT_WINDOW_SECONDS = 120.0


class CalibrationError(ValueError):
    """The request cannot be run; ``errors`` says why, in plain words."""

    def __init__(self, errors: List[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _messages(err: ValidationError) -> List[str]:
    out = []
    for e in err.errors():
        where = ".".join(str(p) for p in e.get("loc", ()) if p != "__root__")
        msg = str(e.get("msg", "invalid")).removeprefix("Value error, ")
        out.append(f"{where}: {msg}" if where else msg)
    return out


def apply_fit(
    doc: ScenarioDocument, obs: ObservationSet, fit: List[str]
) -> ScenarioDocument:
    """A copy of ``doc`` with the chosen observed inputs written in. The
    original is untouched; anything not observed keeps the scenario's value."""
    fitted = doc.model_copy(deep=True)
    arms = fitted.approaches.present()
    if "demand" in fit:
        for approach, vph in obs.flow_vph().items():
            arm = next((a for d, a in arms.items() if d.value == approach), None)
            if arm is not None:
                arm.vehiclesPerHour = vph
    if "turning" in fit:
        for approach, shares in obs.turning_shares().items():
            arm = next((a for d, a in arms.items() if d.value == approach), None)
            if arm is not None:
                arm.turning = Turning(
                    left=shares.get("left", 0.0),
                    straight=shares.get("straight", 0.0),
                    right=shares.get("right", 0.0),
                    uturn=shares.get("uturn"),
                )
    if "mix" in fit and obs.vehicleMix is not None:
        fitted.vehicles.mix = obs.vehicleMix.model_copy(deep=True)
    return fitted


def _mismatch_warnings(doc: ScenarioDocument, obs: ObservationSet) -> List[str]:
    """Where the scenario as given already disagrees with what was observed
    (inputs, not results) — a likely sign it is the wrong scenario."""
    warnings: List[str] = []
    arms = {d.value: a for d, a in doc.approaches.present().items()}
    for approach, vph in obs.flow_vph().items():
        offered = arms[approach].vehiclesPerHour
        if vph > 0 and abs(offered - vph) / vph > FLOW_MISMATCH_RATIO:
            warnings.append(
                f"Scenario mismatch: {approach} offers {offered:g} veh/h but "
                f"{vph:g} veh/h was observed (use options.fit=['demand'] to simulate "
                "the observed demand)."
            )
    for approach, shares in obs.turning_shares().items():
        t = arms[approach].turning.model_dump()
        for move, share in shares.items():
            if abs((t.get(move) or 0.0) - share) > SHARE_MISMATCH_POINTS:
                warnings.append(
                    f"Scenario mismatch: {approach} {move} share is "
                    f"{(t.get(move) or 0.0):.2f} in the scenario, {share:.2f} observed."
                )
    if obs.vehicleMix is not None and doc.vehicles.mix is not None:
        sc = doc.vehicles.mix.model_dump()
        for cls, share in obs.mix_shares().items():
            if abs(sc.get(cls, 0.0) - share) > SHARE_MISMATCH_POINTS:
                warnings.append(
                    f"Scenario mismatch: {cls} share is {sc.get(cls, 0.0):.2f} in "
                    f"the scenario, {share:.2f} observed."
                )
    return warnings


class _Prepared:
    def __init__(
        self,
        doc: ScenarioDocument,
        fitted_doc: ScenarioDocument,
        obs: ObservationSet,
        options: CalibrationOptions,
        strategy: str,
        warnings: List[str],
    ) -> None:
        self.doc = doc
        self.fitted_doc = fitted_doc
        self.obs = obs
        self.options = options
        self.strategy = strategy
        self.warnings = warnings


def _prepare(payload: Any) -> Tuple[Optional[_Prepared], List[str], List[str]]:
    if not isinstance(payload, dict):
        return None, ["The request must be a JSON object"], []
    errors: List[str] = []

    doc, scenario_errors = parse_scenario(payload.get("scenario"))
    errors.extend(f"scenario: {e}" for e in scenario_errors)

    obs: Optional[ObservationSet] = None
    try:
        obs = ObservationSet.model_validate(payload.get("observations"))
    except ValidationError as err:
        errors.extend(f"observations: {m}" for m in _messages(err))

    options = CalibrationOptions.model_validate({})
    try:
        options = CalibrationOptions.model_validate(payload.get("options") or {})
    except ValidationError as err:
        errors.extend(f"options: {m}" for m in _messages(err))

    if doc is None or obs is None or errors:
        return None, errors, []

    # The observations must describe THIS scenario.
    actual = scenario_fingerprint(doc)
    if obs.scenarioFingerprint and obs.scenarioFingerprint != actual:
        errors.append(
            f"Scenario mismatch: the observations were collected for scenario "
            f"{obs.scenarioFingerprint}, but this scenario is {actual}"
        )
    present = {d.value for d in doc.approaches.present()}
    named = (
        {f.approach for f in obs.approachFlows}
        | {t.approach for t in obs.turningMovements}
        | {q.approach for q in obs.queues}
        | {t.approach for t in obs.travelTimes}
    )
    for approach in sorted(named - present):
        errors.append(
            f"Scenario mismatch: observations name the {approach} approach, "
            "which this scenario does not have"
        )
    if "mix" in options.fit and obs.vehicleMix is None:
        errors.append("fit 'mix' needs observations.vehicleMix")
    if "demand" in options.fit and not obs.approachFlows:
        errors.append("fit 'demand' needs observations.approachFlows")
    if "turning" in options.fit and not obs.turningMovements:
        errors.append("fit 'turning' needs observations.turningMovements")

    strategy = options.strategy or JUNCTION_STRATEGY[doc.junction.type]
    sim = doc.simulation
    window = sim.duration - sim.warmup
    if window <= 0:
        errors.append("simulation.warmup must be shorter than simulation.duration")
    if options.seeds * sim.duration > MAX_SIMULATED_SECONDS:
        errors.append(
            f"{options.seeds} seeds x {sim.duration:g} s exceeds the "
            f"{MAX_SIMULATED_SECONDS:g} simulated-second limit for one calibration "
            "run; use fewer seeds or a shorter duration"
        )
    if errors:
        return None, errors, []

    warnings: List[str] = []
    if window < SHORT_WINDOW_SECONDS:
        warnings.append(
            f"The measured window is only {window:g} s; simulated flows, queues "
            "and travel times will be noisy."
        )
    if obs.signal is not None and strategy == "roundabout":
        warnings.append("Signal observations are ignored for a roundabout.")
    if not options.fit:
        warnings.extend(_mismatch_warnings(doc, obs))

    fitted_doc = apply_fit(doc, obs, list(options.fit))
    check = validate_scenario(fitted_doc.model_dump(), [strategy])
    if not check["valid"]:
        return None, [f"scenario: {e}" for e in check["errors"]], []
    warnings.extend(check.get("warnings") or [])
    return _Prepared(doc, fitted_doc, obs, options, strategy, warnings), [], warnings


def fitted_scenario(request: Any) -> Dict[str, Any]:
    """The scenario a stored calibration run actually simulated: the request's
    scenario with the observed inputs it asked for written in (``appliedFit``).
    Pure, no simulation; the V2.0 planning study uses it as its subject."""
    prepared, errors, _ = _prepare(request)
    if prepared is None:
        raise CalibrationError(errors)
    return prepared.fitted_doc.model_dump(mode="json")


def validate_calibration_request(payload: Any) -> Dict[str, Any]:
    """{valid, errors, warnings, ...fingerprints, planned comparisons}."""
    prepared, errors, warnings = _prepare(payload)
    if prepared is None:
        return {"valid": False, "errors": errors, "warnings": warnings}
    obs = prepared.obs
    planned = {
        "approachFlow": len(obs.approachFlows),
        "turningShare": len(obs.turningMovements),
        "vehicleClassShare": len(obs.mix_shares()),
        "queue": sum(
            (q.meanVehicles is not None) + (q.maxVehicles is not None)
            for q in obs.queues
        ),
        "meanTravelTime": len(obs.travelTimes),
        "averageGreenDuration": int(
            obs.signal is not None and prepared.strategy != "roundabout"
        ),
    }
    return {
        "valid": True,
        "errors": [],
        "warnings": warnings,
        "strategy": prepared.strategy,
        "scenarioFingerprint": scenario_fingerprint(prepared.doc),
        "fittedScenarioFingerprint": scenario_fingerprint(prepared.fitted_doc),
        "observationsFingerprint": observations_fingerprint(obs),
        "plannedComparisons": planned,
        "seeds": prepared.options.seeds,
    }


def run_calibration(payload: Any) -> Dict[str, Any]:
    """Run the scenario under the seeds requested and compare with the
    observations. Raises ``CalibrationError`` for an invalid request."""
    prepared, errors, warnings = _prepare(payload)
    if prepared is None:
        raise CalibrationError(errors)

    doc, fitted, obs = prepared.doc, prepared.fitted_doc, prepared.obs
    options, strategy = prepared.options, prepared.strategy
    base_seed = (
        options.baseSeed if options.baseSeed is not None else fitted.simulation.seed
    )
    seeds = [base_seed + i for i in range(options.seeds)]

    tallies: List[Dict[str, Any]] = []
    config: Dict[str, Any] = {}
    for seed in seeds:
        per_seed = fitted.model_copy(deep=True)
        per_seed.simulation.seed = seed
        config_i = compile_scenario(per_seed, strategy)
        if not config:
            config = config_i
        tallies.append(simulate_once(config_i, strategy))

    rows = build_rows(obs, tallies, strategy, list(options.fit))
    rated = [r["rating"] for r in rows if r["rating"] is not None]
    classification = classify(rated)

    caveats = [
        "Simulated values are means over the repetitions of the unchanged V1.5 "
        "engine. Ratings apply fixed presentation thresholds (see "
        "`thresholds`); they are not a statistical test.",
        "Agreement on the compared quantities says nothing about quantities that "
        "were not observed.",
    ]
    if options.seeds < MIN_REPETITIONS_FOR_SPREAD:
        caveats.append(
            f"Only {options.seeds} repetition(s): the spread across seeds is not "
            "a reliable measure of simulation variability."
        )
    if options.fit:
        caveats.append(
            "Inputs written from the observations ("
            + ", ".join(options.fit)
            + ") are not independent evidence; comparisons on them show the "
            "simulation reproduces its input, not that the model is calibrated."
        )
    unrated = [r["metric"] for r in rows if r["rating"] is None]
    if unrated:
        caveats.append(
            "Not compared (no simulated vehicles in the window): "
            + ", ".join(sorted(set(unrated)))
        )
    if any(t["metrics"]["vehicleLimitReached"] for t in tallies):
        caveats.append(
            "The vehicle limit was reached in at least one run, so demand was "
            "truncated; flow comparisons may be biased low."
        )
    if classification["overall"] == INSUFFICIENT_DATA:
        caveats.append("Nothing could be rated, so no classification is given.")
    kinds = sorted({r["kind"] for r in rows})
    if kinds == ["flow"]:
        caveats.append("Only approach flow was compared.")

    warmup = tallies[0]["warmup"]
    return {
        "format": CALIBRATION_RESULT_FORMAT,
        "version": CALIBRATION_RESULT_VERSION,
        "fieldCalibration": {
            "status": classification["overall"],
            "classification": classification,
            "thresholds": THRESHOLDS,
            "thresholdsVersion": THRESHOLDS_VERSION,
            "overallRule": OVERALL_RULE_TEXT,
            "coverage": {
                "compared": kinds,
                "observedSeries": {
                    "approachFlows": bool(obs.approachFlows),
                    "turningMovements": bool(obs.turningMovements),
                    "vehicleMix": obs.vehicleMix is not None,
                    "signal": obs.signal is not None and strategy != "roundabout",
                    "queues": bool(obs.queues),
                    "travelTimes": bool(obs.travelTimes),
                },
            },
            # The existing, unrelated meaning of "calibrated" (V1.0 capacity
            # curve); embedded unchanged so the two are never confused.
            "engineCapacityCalibration": calibration_status(config),
        },
        "comparisons": rows,
        "appliedFit": list(options.fit),
        "warnings": warnings,
        "caveats": caveats,
        "scenario": {
            "name": doc.name,
            "strategy": strategy,
            "fingerprint": scenario_fingerprint(doc),
            "fittedFingerprint": scenario_fingerprint(fitted),
        },
        "meta": {
            "schemaVersion": CALIBRATION_RESULT_VERSION,
            "observationsFingerprint": observations_fingerprint(obs),
            "observationsName": obs.name,
            "observationPeriod": obs.period.model_dump(),
            "seeds": seeds,
            "baseSeed": base_seed,
            "repetitions": options.seeds,
            "duration": fitted.simulation.duration,
            "warmupTime": warmup,
            "measuredSeconds": tallies[0]["measuredSeconds"],
            "timeStep": tallies[0]["timeStep"],
            "gitCommit": GIT_COMMIT_HASH,
            "pythonVersion": PYTHON_VERSION,
            "deterministic": True,
            "engineModel": "UrbanFlow V1.5 core (unchanged)",
        },
    }
