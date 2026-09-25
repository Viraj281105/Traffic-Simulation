"""Whether a study scenario is inside the calibrated comparison.

docs/reports/v1-known-limitations.md §1 and §3 and
docs/reports/comparative_report.md §2 establish that the signal-vs-roundabout
comparison is calibrated only with ONE lane per approach: the roundabout is
modelled with a single circulating lane, so extra entry lanes add weaving
conflicts without adding the spiral lane assignment that gives a real
multi-lane roundabout its capacity. Results for more lanes are exploratory.

Every study output (sweep, Monte Carlo validation, report) carries this
status so a consumer can never mistake an exploratory multi-lane result for
the calibrated baseline.
"""

from typing import Any, Dict

CALIBRATED_LANES_PER_APPROACH = 1

# What the engine builds when a config omits ``roads.lanesPerApproach``
# (core/engine.py). An unspecified config is therefore NOT the calibrated one.
ENGINE_DEFAULT_LANES_PER_APPROACH = 2

CALIBRATED_NOTE = (
    "Calibrated comparison: one lane per approach, the configuration both "
    "geometries are validated for."
)
EXPLORATORY_NOTE = (
    "Exploratory, not calibrated: this scenario uses more than one lane per "
    "approach, but the roundabout is modelled with a single circulating "
    "lane. Read the roundabout's results as indicative only; do not treat "
    "them as the calibrated baseline."
)


def _lane_counts(config: Dict[str, Any]) -> Dict[str, int]:
    roads = config.get("roads") or {}
    lanes = roads.get("lanesPerApproach", ENGINE_DEFAULT_LANES_PER_APPROACH)
    if isinstance(lanes, dict):
        return {
            d: int(lanes.get(d, ENGINE_DEFAULT_LANES_PER_APPROACH))
            for d in ("north", "south", "east", "west")
        }
    return {d: int(lanes) for d in ("north", "south", "east", "west")}


def calibration_status(config: Dict[str, Any]) -> Dict[str, Any]:
    """{calibrated, lanesPerApproach, note} for a study configuration."""
    lanes = _lane_counts(config)
    calibrated = all(n == CALIBRATED_LANES_PER_APPROACH for n in lanes.values())
    return {
        "calibrated": calibrated,
        "lanesPerApproach": lanes,
        "note": CALIBRATED_NOTE if calibrated else EXPLORATORY_NOTE,
    }
