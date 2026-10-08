"""V1.8 — observed-data input and simulated-vs-observed comparison.

An isolated, read-only consumer of the V1.5 core: it compiles a scenario
document, runs the unchanged engine, and compares what the run produced with
observations the user supplies. It never edits physics, the scenario schema or
any V1.6/V1.7 module. See docs/engineering/v18-v20-contracts.md and
docs/research/calibration.md.
"""

from src.calibration.models import (
    CALIBRATION_RESULT_FORMAT,
    OBSERVATIONS_FORMAT,
    CalibrationOptions,
    ObservationSet,
)
from src.calibration.runner import (
    CalibrationError,
    run_calibration,
    validate_calibration_request,
)

__all__ = [
    "CALIBRATION_RESULT_FORMAT",
    "OBSERVATIONS_FORMAT",
    "CalibrationError",
    "CalibrationOptions",
    "ObservationSet",
    "run_calibration",
    "validate_calibration_request",
]
