"""The V2.0 study's two optional attachments: a V1.8 calibration run and a V1.9
network.

* ``calibration.runId`` -- a stored ``/api/v2/calibration`` run. Its status is
  carried into ``validity``; it only applies when the study's scenario is the
  scenario that run simulated (original or fitted). A different scenario is an
  error, never silently ignored.
* ``subject.network`` -- accepted when it has exactly one junction with an
  inline scenario; that junction (with route-implied volume and turning) is
  what runs. Multi-junction execution is not part of this build and is
  refused with a plain message rather than approximated.
* Every study also reports the single-junction network that represents its
  scenario, so the scenario can be inspected in the network model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.calibration import store as calibration_store
from src.calibration.runner import CalibrationError, fitted_scenario
from src.core.scenario import ScenarioDocument, scenario_fingerprint
from src.networks.compile import LIMITATIONS, compile_network, derive_node_scenarios
from src.networks.from_scenario import JUNCTION_ID, scenario_to_network
from src.networks.models import (
    EXECUTION_MODEL,
    NetworkDocument,
    network_fingerprint,
    serialize_network,
)
from src.networks.validate import parse_network, validate_network
from src.planning.models import PlanningStudy


def _calibration_record(study: PlanningStudy, errors: List[str]) -> Optional[Dict[str, Any]]:
    if study.calibration is None:
        return None
    try:
        record = calibration_store.get(study.calibration.runId)
    except Exception as exc:  # the table or database is unusable
        errors.append(f"calibration: could not read stored runs ({exc})")
        return None
    if record is None:
        errors.append(
            f"calibration: run {study.calibration.runId!r} not found "
            "(create one with POST /api/v2/calibration/runs)"
        )
    return record


def resolve_subject(study: PlanningStudy) -> Dict[str, Any]:
    """The scenario dict this study will run, plus what produced it.

    ``{scenario, errors, calibrationRecord, networkDocument}``; ``scenario``
    is None when ``errors`` is not empty."""
    errors: List[str] = []
    record = _calibration_record(study, errors)
    network_doc: Optional[NetworkDocument] = None
    scenario: Optional[Dict[str, Any]] = None

    if study.subject.network is not None:
        check = validate_network(study.subject.network)
        if not check["valid"]:
            errors.extend(f"subject.network: {e}" for e in check["errors"])
        else:
            network_doc, _ = parse_network(study.subject.network)
            assert network_doc is not None
            junctions = [n for n in network_doc.nodes if n.kind == "junction"]
            inline = [j for j in junctions if isinstance(j.scenario, ScenarioDocument)]
            if len(junctions) != 1 or len(inline) != 1:
                errors.append(
                    f"subject.network: this build runs one junction per study; "
                    f"the network has {len(junctions)} junction(s) "
                    f"({len(inline)} with an inline scenario). Multi-junction "
                    "execution is not available."
                )
            else:
                derived, derive_errors = derive_node_scenarios(network_doc)
                errors.extend(derive_errors)
                scenario = derived.get(inline[0].id)
    elif study.subject.scenario is not None:
        scenario = study.subject.scenario
    elif (
        record is not None and study.calibration and study.calibration.useFittedScenario
    ):
        try:
            scenario = fitted_scenario(record["request"])
        except CalibrationError as err:
            errors.extend(f"calibration: {e}" for e in err.errors)

    if errors:
        scenario = None
    return {
        "scenario": scenario,
        "errors": errors,
        "calibrationRecord": record,
        "networkDocument": network_doc,
    }


def calibration_block(
    study: PlanningStudy, record: Optional[Dict[str, Any]], base: ScenarioDocument
) -> Dict[str, Any]:
    """``{block, errors, warnings}``; ``block`` is None without a calibration."""
    if record is None or study.calibration is None:
        return {"block": None, "errors": [], "warnings": []}
    result = record["result"]
    meta = result["meta"]
    fp = scenario_fingerprint(base)
    original = result["scenario"]["fingerprint"]
    fitted = result["scenario"]["fittedFingerprint"]
    errors: List[str] = []
    warnings: List[str] = []
    if fp == fitted:
        relation = "fitted_scenario"
    elif fp == original:
        relation = "original_scenario"
        warnings.append(
            "calibration: the study uses the scenario as given, not the fitted "
            "copy the calibration simulated; set calibration.useFittedScenario "
            "to study the fitted one."
        )
    else:
        relation = "mismatch"
        errors.append(
            f"calibration: run {record['id']!r} was for scenario {original} "
            f"(fitted {fitted}); this study's scenario is {fp}. A calibration "
            "only applies to the scenario it was run on."
        )
    cal = result["fieldCalibration"]
    block = {
        "runId": record["id"],
        "status": cal["status"],
        "relation": relation,
        "scenarioFingerprint": original,
        "fittedFingerprint": fitted,
        "observationsFingerprint": meta["observationsFingerprint"],
        "observationsName": meta.get("observationsName"),
        "appliedFit": result.get("appliedFit", []),
        "compared": cal["coverage"]["compared"],
        "caveats": list(result.get("caveats", [])),
        "gitCommit": meta.get("gitCommit"),
        "seeds": meta.get("seeds"),
        "note": (
            "Field calibration compares simulated and observed quantities for "
            "the scenario above; it is separate from the engine's capacity "
            "calibration (validity.engineCapacityCalibration)."
        ),
    }
    return {"block": block, "errors": errors, "warnings": warnings}


def network_block(
    base: ScenarioDocument, submitted: Optional[NetworkDocument]
) -> Dict[str, Any]:
    """The study's network-model view. ``submitted`` is the network the study
    was given; otherwise the single-junction network derived from the scenario.
    """
    origin = "submitted"
    if submitted is None:
        origin = "derived_from_scenario"
        submitted, _ = parse_network(scenario_to_network(base))
    try:
        if submitted is None:
            raise ValueError("derived network failed structural validation")
        plan = compile_network(submitted)
    except Exception as exc:  # the study still runs; the view says why it is absent
        return {
            "origin": origin,
            "status": "unavailable",
            "fingerprint": None,
            "reason": str(exc),
            "limitations": list(LIMITATIONS),
        }
    return {
        "origin": origin,
        "status": "representation_only"
        if origin == "derived_from_scenario"
        else "single_junction_run",
        "fingerprint": network_fingerprint(submitted),
        "junctionNode": JUNCTION_ID
        if origin == "derived_from_scenario"
        else next(n.id for n in submitted.nodes if n.kind == "junction"),
        "nodeCount": len(submitted.nodes),
        "edgeCount": len(submitted.edges),
        "routeCount": len(submitted.routes),
        "executionModel": EXECUTION_MODEL,
        "executed": "one junction (the scenario); no inter-junction coupling",
        "limitations": list(LIMITATIONS),
        "plan": {
            "order": plan["order"],
            "nodes": plan["nodes"],
            "edges": plan["edges"],
            "routes": plan["routes"],
        },
        "document": serialize_network(submitted),
    }
