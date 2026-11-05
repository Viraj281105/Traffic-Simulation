"""Independent safety audit of a priority run's signal log.

Reads only the controller's phase-transition log and the plan's configured
durations, so it checks what the signal actually did rather than what the
controller intended.

Rules, each reported with the transitions that break it:

* **No conflicting green-to-green.** A transition from one green directly to a
  green of different directions has no clearance between them.
* **Yellow in full.** A yellow phase lasts at least the plan's yellow time.
* **All-red in full.** A red (all-red) phase lasts at least the plan's all-red
  time.
* **Minimum green.** A green that was ended by priority (pre-emption, the end
  of a pre-emption hold, or early green) had been green for at least the
  safety minimum. Greens that end on
  the plan's own schedule are the plan's business and are not judged here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

PRIORITY_REASONS = ("preempt-clearance", "preempt-recovery", "transit-early-green")


def audit_phase_log(
    log: Sequence[Dict[str, Any]],
    *,
    yellow_s: float,
    all_red_s: float,
    min_green_s: float,
    time_step_s: float,
) -> Dict[str, Any]:
    tol = time_step_s * 1.01
    violations: List[Dict[str, Any]] = []
    for row in log:
        kind = None
        if row["fromColor"] == "green" and row["toColor"] == "green":
            if row["fromDirections"] != row["toDirections"]:
                kind = "green-to-green"
        elif row["fromColor"] == "yellow" and row["phaseSeconds"] < yellow_s - tol:
            kind = "short-yellow"
        elif row["fromColor"] == "red" and row["phaseSeconds"] < all_red_s - tol:
            kind = "short-all-red"
        elif (
            row["fromColor"] == "green"
            and row["reason"] in PRIORITY_REASONS
            and row["greenAge"] is not None
            and row["greenAge"] < min_green_s - tol
        ):
            kind = "short-green"
        if kind is not None:
            violations.append({"type": kind, **row})
    return {"transitions": len(log), "violations": violations, "ok": not violations}
