"""Orchestrates a planning study over the existing comparison machinery.

No simulation logic lives here. For every alternative the runner calls
``run_scenario_comparison`` (injectable, so tests can feed canned output) with
the alternative's patched scenario, one strategy, the shared seeds and demand
scales, then reduces the output to indicators, paired comparisons, findings
and a report.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.core.scenario import (
    STRATEGY_TITLES,
    ScenarioDocument,
    parse_scenario,
    scenario_fingerprint,
    total_vehicles_per_hour,
)
from src.planning import indicators as ind
from src.planning import links
from src.planning.alternatives import (
    AlternativeSource,
    DefaultStrategyAlternatives,
    InlineAlternatives,
    ResolvedAlternative,
    resolve_all,
)
from src.planning.comparison import COMPARED, vs_baseline
from src.planning.findings import MIN_SEEDS_ADEQUATE, MIN_SEEDS_ANY, generate_findings
from src.planning.models import (
    PLANNING_RESULT_FORMAT,
    SCHEMA_VERSION,
    PlanningStudy,
    fingerprint_of,
)
from src.planning.report import build_report
from src.study.runner import Progress

ComparisonFn = Callable[..., Dict[str, Any]]

HIGH_VARIABILITY_CV = 0.3


class PlanningError(ValueError):
    """The study cannot be run; ``errors`` lists every reason."""

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _default_comparison() -> ComparisonFn:
    from src.study.control_comparison import run_scenario_comparison

    return run_scenario_comparison


def source_for(study: PlanningStudy) -> AlternativeSource:
    if study.alternatives:
        return InlineAlternatives(study.alternatives)
    return DefaultStrategyAlternatives()


def prepare(
    study: PlanningStudy, source: Optional[AlternativeSource] = None
) -> Dict[str, Any]:
    """Validate without simulating. ``{valid, errors, warnings, ...}``."""
    subject = links.resolve_subject(study)
    base, errors = (
        parse_scenario(subject["scenario"]) if subject["scenario"] else (None, [])
    )
    errors = list(subject["errors"]) + list(errors)
    if base is None:
        return {
            "valid": False,
            "errors": errors,
            "warnings": [],
            "alternatives": [],
            "base": None,
        }
    cal = links.calibration_block(study, subject["calibrationRecord"], base)
    network = links.network_block(base, subject["networkDocument"])
    resolved = resolve_all(base, source or source_for(study))
    errors = cal["errors"] + [e for r in resolved for e in r.errors]
    warnings = cal["warnings"] + [w for r in resolved for w in r.warnings]
    if not resolved:
        errors.append("At least one alternative is required")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "alternatives": resolved,
        "base": base,
        "calibration": cal["block"],
        "network": network,
        "runs": len(resolved) * len(study.demand.scales) * study.repetitions.seeds,
    }


def _geometry(doc: ScenarioDocument) -> Dict[str, Any]:
    arms: Dict[str, Any] = {}
    for direction, arm in doc.approaches.present().items():
        arms[direction.value] = {
            "lanes": arm.lanes,
            "length": arm.length,
            "vehiclesPerHour": arm.vehiclesPerHour,
            "turning": {
                k: v for k, v in arm.turning.model_dump().items() if v is not None
            },
            "bearing": arm.bearing,
            "laneWidth": arm.laneWidth,
        }
    return {
        "arms": arms,
        "armCount": len(arms),
        "roads": doc.roads.model_dump(),
    }


def _scenario_block(base: ScenarioDocument, study: PlanningStudy) -> Dict[str, Any]:
    fp = scenario_fingerprint(base)
    mix = base.vehicles.mix.model_dump() if base.vehicles.mix else None
    return {
        "id": f"scn_{fp}",
        "name": base.name,
        "fingerprint": fp,
        "geometry": _geometry(base),
        "traffic": {
            "totalVehiclesPerHour": total_vehicles_per_hour(base),
            "arrivalPattern": base.simulation.arrivalPattern,
        },
        "vehicleMix": mix or {"car": 1.0},
        "vehicleMixDefaulted": mix is None,
        "demand": {
            "baseVehiclesPerHour": total_vehicles_per_hour(base),
            "scales": study.demand.scales,
            "growthLabel": study.demand.growthLabel,
        },
        "control": {"baselineJunctionType": base.junction.type},
        "simulation": {
            "duration": base.simulation.duration,
            "warmup": base.simulation.warmup,
            "timeStep": base.simulation.timeStep,
        },
    }


def _reliability_flags(results: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    if n < MIN_SEEDS_ANY:
        flags.append(
            {
                "code": "small_sample",
                "severity": "warning",
                "message": f"Only {n} repetition(s): intervals are undefined or very wide; treat every reading as inconclusive.",
            }
        )
    elif n < MIN_SEEDS_ADEQUATE:
        flags.append(
            {
                "code": "small_sample",
                "severity": "caution",
                "message": f"{n} repetitions: indicative only; {MIN_SEEDS_ADEQUATE}+ recommended.",
            }
        )
    for i, r in enumerate(results):
        cv = ((r.get("reliability") or {}).get("delayAcrossSeeds") or {}).get(
            "coefficientOfVariation"
        )
        if cv is not None and cv > HIGH_VARIABILITY_CV:
            flags.append(
                {
                    "code": "high_variability",
                    "severity": "caution",
                    "alternativeId": r["alternativeId"],
                    "demandScale": r["demandScale"],
                    "message": f"Mean delay varies strongly across seeds (CV {cv:.2f}).",
                    "path": f"results[{i}].reliability.delayAcrossSeeds",
                }
            )
        if r.get("vehicleLimitReached"):
            flags.append(
                {
                    "code": "vehicle_limit",
                    "severity": "warning",
                    "alternativeId": r["alternativeId"],
                    "demandScale": r["demandScale"],
                    "message": "Vehicle limit reached; outputs may be truncated.",
                    "path": f"results[{i}].vehicleLimitReached",
                }
            )
    return flags


def run_study(
    study: PlanningStudy,
    *,
    comparison_fn: Optional[ComparisonFn] = None,
    source: Optional[AlternativeSource] = None,
    progress: Optional[Progress] = None,
) -> Dict[str, Any]:
    prepared = prepare(study, source)
    if not prepared["valid"]:
        raise PlanningError(prepared["errors"])
    base: ScenarioDocument = prepared["base"]
    resolved: List[ResolvedAlternative] = prepared["alternatives"]
    run = comparison_fn or _default_comparison()

    reps = study.repetitions
    confidence = reps.confidenceLevel
    scales = study.demand.scales
    base_seed = base.simulation.seed if reps.baseSeed is None else reps.baseSeed
    groups = list(study.indicators)

    # One comparison per distinct (strategy, scenario); identical alternatives
    # share the run rather than repeating it.
    cache: Dict[Tuple[str, Optional[str]], Dict[str, Any]] = {}
    for alt in resolved:
        key = (alt.spec.strategy, alt.fingerprint)
        if key in cache:
            continue
        cache[key] = run(
            alt.document,
            [alt.spec.strategy],
            num_seeds=reps.seeds,
            base_seed=base_seed,
            demand_scales=scales,
            confidence_level=confidence,
            progress=progress,
        )

    baseline_id = resolved[0].id
    result_rows: List[Dict[str, Any]] = []
    alternatives_out: List[Dict[str, Any]] = []
    compiled: Dict[str, Any] = {}
    fingerprints: Dict[str, str] = {}
    seeds: List[int] = []
    vehicle_limit = False
    calibration: Dict[str, Any] = {}

    for alt in resolved:
        strategy = alt.spec.strategy
        comp = cache[(strategy, alt.fingerprint)]
        # Fingerprint propagation: what ran is what we validated.
        if comp.get("fingerprint") not in (None, alt.fingerprint):
            raise PlanningError(
                [
                    f"{alt.id}: comparison fingerprint {comp.get('fingerprint')} "
                    f"does not match the alternative's {alt.fingerprint}"
                ]
            )
        seeds = list(comp["seeds"])
        compiled[alt.id] = (comp.get("compiledConfigs") or {}).get(strategy)
        fingerprints[alt.id] = alt.fingerprint or ""
        calibration[alt.id] = comp.get("calibration")
        alternatives_out.append(
            {
                "id": alt.id,
                "label": alt.label,
                "strategy": strategy,
                "strategyTitle": STRATEGY_TITLES.get(strategy, strategy),
                "isBaseline": alt.id == baseline_id,
                "patch": alt.spec.patch,
                "changesFromBase": alt.changes,
                "fingerprint": alt.fingerprint,
                "warnings": alt.warnings,
            }
        )
        for row in comp["results"]:
            scale = row["demandScale"]
            seed_rows = [r for r in comp["perSeed"] if r["demandScale"] == scale]
            vehicle_limit = vehicle_limit or bool(row.get("vehicleLimitReached"))
            block = ind.build_groups(row, seed_rows, strategy, confidence, groups)
            series = {
                key: ind._seed_values(seed_rows, strategy, key) for key, *_ in COMPARED
            }
            result_rows.append(
                {
                    "alternativeId": alt.id,
                    "demandScale": scale,
                    "demandVph": row["demandVph"],
                    "vehicleLimitReached": bool(row.get("vehicleLimitReached")),
                    **block,
                    "perApproach": ind.per_approach(seed_rows, strategy),
                    "perVehicleType": ind.per_vehicle_type(seed_rows, strategy),
                    "signalTiming": ind.signal_timing(row, strategy),
                    "seriesBySeed": series,
                }
            )

    comparisons = vs_baseline(result_rows, baseline_id, confidence)

    caveats = []
    for aid, cal in calibration.items():
        if (
            isinstance(cal, dict)
            and not cal.get("calibrated", False)
            and cal.get("note")
        ):
            note = f"Exploratory (not capacity-calibrated): {cal['note']}"
            if note not in caveats:
                caveats.append(note)
    n = len(seeds)
    cal_block = prepared["calibration"]
    net_block = prepared["network"]
    if cal_block is not None:
        caveats.append(
            f"Field calibration ({cal_block['status']}) covers: "
            f"{', '.join(cal_block['compared']) or 'nothing rated'}. "
            "Quantities not observed remain unvalidated."
        )
    validity = {
        "fieldCalibration": cal_block["status"] if cal_block else "not_provided",
        "fieldCalibrationDetail": cal_block,
        "engineCapacityCalibration": calibration,
        "vehicleLimitReached": vehicle_limit,
        "exploratory": True,
        "caveats": caveats,
    }
    reliability = {
        "repetitions": n,
        "seeds": seeds,
        "baseSeed": base_seed,
        "confidenceLevel": confidence,
        "sampleAdequacy": "single_run"
        if n < 2
        else ("small" if n < MIN_SEEDS_ADEQUATE else "adequate"),
        "flags": _reliability_flags(result_rows, n),
    }
    findings = generate_findings(
        alternatives_out, result_rows, comparisons, seeds, validity, groups
    )

    scenario = _scenario_block(base, study)
    request = study.model_dump(mode="json")
    first = next(iter(cache.values()))
    result: Dict[str, Any] = {
        "format": PLANNING_RESULT_FORMAT,
        "version": SCHEMA_VERSION,
        "name": study.name,
        "objective": study.objective,
        "scenario": scenario,
        "alternatives": alternatives_out,
        "summary": {
            "baseline": baseline_id,
            "alternatives": len(resolved),
            "scales": scales,
            "seeds": n,
            "findings": len(findings),
            "recommendationBasis": (
                "None. This study reports evidence for this scenario and these "
                "demand levels only; it does not rank or recommend a control."
            ),
        },
        "results": result_rows,
        "comparison": {
            "baselineId": baseline_id,
            "vsBaseline": comparisons,
            "tieTolerance": first.get("tieTolerance"),
            "method": first.get("method"),
        },
        "reliability": reliability,
        "findings": findings,
        "limitations": [
            "Results describe this scenario and these demand levels; they do not transfer to other junctions or conditions.",
            "Readings are per metric and per demand scale; there is no overall winner.",
            "Several metrics, alternatives and scales are read without multiple-comparison correction.",
            "Safety indicators are exploratory rare-event proxies, not crash predictions.",
            "Environmental indicators are stop-and-go/idling proxies; no emissions model exists.",
            (
                f"Field calibration run {cal_block['runId']} is attached "
                f"(status {cal_block['status']}); it validates only the compared "
                "quantities of that scenario."
                if cal_block
                else "No field data calibration is attached to this study."
            ),
            "Network model: "
            + (
                "the scenario is represented as a single-junction network; "
                if net_block["origin"] == "derived_from_scenario"
                else "a single-junction network was run; "
            )
            + "multi-junction execution is not part of this study.",
        ],
        "validity": validity,
        "calibration": cal_block,
        "network": net_block,
    }
    result["meta"] = {
        "schemaVersion": SCHEMA_VERSION,
        "format": PLANNING_RESULT_FORMAT,
        "createdAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "gitCommit": GIT_COMMIT_HASH,
        "pythonVersion": PYTHON_VERSION,
        "scenarioFingerprint": scenario["fingerprint"],
        "scenarioFingerprints": fingerprints,
        "inputFingerprint": fingerprint_of(request),
        "seeds": seeds,
        "baseSeed": base_seed,
        "timeStep": base.simulation.timeStep,
        "duration": first.get("duration", base.simulation.duration),
        "warmupTime": first.get("warmupTime", base.simulation.warmup),
        "compiledConfigs": compiled,
        "calibrationRunId": cal_block["runId"] if cal_block else None,
        "calibrationFingerprint": (
            cal_block["observationsFingerprint"] if cal_block else None
        ),
        "networkFingerprint": net_block["fingerprint"],
        "engineModel": "UrbanFlow V1.5 core",
        "executionModel": "one scenario comparison per alternative; shared seeds pair alternatives",
        "reproduce": {
            "endpoint": "/api/v2/planning/{id}/reproduce",
            "deterministic": True,
        },
        "request": request,
    }
    result["meta"]["resultFingerprint"] = result_fingerprint(result)
    result["report"] = build_report(result)
    return result


def result_fingerprint(result: Dict[str, Any]) -> str:
    """Hash of the evidence only (no timestamps/report), for reproducibility."""
    return fingerprint_of(
        {
            k: result[k]
            for k in (
                "scenario",
                "alternatives",
                "results",
                "comparison",
                "reliability",
                "findings",
                "validity",
                "calibration",
                "network",
            )
        }
    )
