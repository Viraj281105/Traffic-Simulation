"""``SensitivityResult``: Sobol indices for one metric of one experiment.

Source: ``experiments/<id>/sensitivity.json`` (format ``urbanflow-sensitivity`` v1)::

    {"format": "urbanflow-sensitivity", "version": 1,
     "metric": {"id": "mean_delay_s", "label": "Mean delay", "unit": "s"},
     "inputs": {"arrivalRate": {"label": "Arrival rate", "unit": "veh/h"}},
     "result": <the dict returned by src.study.sensitivity.sobol_lite>}

Only the Sobol method has first-order indices, so a one-at-a-time result is not available here. The sampler
can return estimates slightly outside 0 to 1; the contract is a fraction, so those are clipped to the range
and the method note says how many were.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .numbers import finite

SENSITIVITY_FORMAT = "urbanflow-sensitivity"
METHOD_NAME = (
    "Sobol indices (first-order and total-order, Saltelli and Jansen estimators)"
)


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


def build_sensitivity(
    experiment_id: str, doc: Mapping[str, Any], metric: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if doc.get("format") != SENSITIVITY_FORMAT:
        return None
    info = doc.get("metric")
    result = doc.get("result")
    if not isinstance(info, dict) or not isinstance(result, dict):
        return None
    mid, label, unit = info.get("id"), info.get("label"), info.get("unit")
    if not (isinstance(mid, str) and isinstance(label, str) and isinstance(unit, str)):
        return None
    if metric is not None and metric != mid:
        return None
    if result.get("method") != "sobol-lite":
        return None
    seed, samples = result.get("seed"), result.get("nSamples")
    ranking = result.get("ranking")
    if (
        not isinstance(seed, int)
        or not isinstance(samples, int)
        or not isinstance(ranking, list)
    ):
        return None
    raw_names = doc.get("inputs")
    names: Mapping[str, Any] = raw_names if isinstance(raw_names, dict) else {}
    inputs: List[Dict[str, Any]] = []
    clipped = 0
    for row in ranking:
        if not isinstance(row, dict) or not isinstance(row.get("input"), str):
            return None
        first, total = finite(row.get("firstOrder")), finite(row.get("totalOrder"))
        if first is None or total is None:
            # A constant output has no variance to share out: nothing to report.
            return None
        if row.get("clipped"):
            clipped += 1
        meta = names.get(row["input"])
        meta = meta if isinstance(meta, dict) else {}
        input_label, input_unit = meta.get("label"), meta.get("unit")
        inputs.append(
            {
                "id": row["input"],
                "label": input_label if isinstance(input_label, str) else row["input"],
                "unit": input_unit if isinstance(input_unit, str) else None,
                "firstOrder": _clip(first),
                "total": _clip(total),
                "ci": None,
            }
        )
    if not inputs:
        return None
    note = str(result.get("note") or "")
    if clipped:
        note += (
            f" {clipped} of {len(inputs)} inputs had an estimate outside 0 to 1, "
            "shown clipped to that range."
        )
    return {
        "experimentId": experiment_id,
        "metric": {"id": mid, "label": label, "unit": unit},
        "method": {
            "name": METHOD_NAME,
            "seed": seed,
            "samples": samples,
            "note": note.strip() or None,
        },
        "inputs": inputs,
    }
