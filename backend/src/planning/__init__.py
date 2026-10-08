"""V2.0 integrated planning / decision support.

An orchestration layer over the V1.5 core: it never runs the engine itself.
A study = one scenario x several alternatives x demand scales x repeated
seeds, executed through ``study.control_comparison.run_scenario_comparison``
and reduced to indicators, paired comparisons, rule-based findings and an
exportable report. It reports evidence for *this* scenario and *these*
conditions -- never a universal winner.
"""

from src.planning.models import (  # noqa: F401
    PLANNING_RESULT_FORMAT,
    PLANNING_STUDY_FORMAT,
    PlanningStudy,
)
