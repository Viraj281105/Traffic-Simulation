"""Whether a study scenario is inside the calibrated comparison.

docs/reports/v1-known-limitations.md §1 and §3 and
docs/reports/comparative_report.md §2 establish that the signal-vs-roundabout
comparison is calibrated only with ONE lane per approach. With more lanes both
geometries genuinely change — the signal gets per-movement turning lanes and
the roundabout one circulating ring per entry lane, and capacity rises with
lanes for both — but the roundabout has no lane markings (spiral assignment),
so a driver leaving from an inner ring crosses the outer ring, and those runs
are not collision-free across the whole demand range (about one contact per
ten multi-lane runs, 2026-09-25 matrix). Results for more lanes are therefore
exploratory.

Every study output (sweep, Monte Carlo validation, report) carries this
status so a consumer can never mistake an exploratory multi-lane result for
the calibrated baseline.
"""

from typing import Any, Dict, List

CALIBRATED_LANES_PER_APPROACH = 1

# What the engine builds when a config omits ``roads.lanesPerApproach``
# (core/engine.py). An unspecified config is therefore NOT the calibrated one.
ENGINE_DEFAULT_LANES_PER_APPROACH = 2

CALIBRATED_NOTE = (
    "Calibrated comparison: one lane per approach, the configuration both "
    "geometries are validated for."
)
EXPLORATORY_NOTE = (
    "Exploratory, not calibrated: more than one lane per approach. Both "
    "junctions model every lane, but drivers leaving the roundabout from an "
    "inner ring cross the outer ring without lane markings, and multi-lane "
    "runs are not collision-free across the whole demand range. Read the "
    "results as indicative; do not treat them as the calibrated baseline."
)

# Reference capacity (veh/h, whole junction) per lane count: the mean of the
# two controls' measured maximum served flow (seeds 1-3, 240 s, 30 s warm-up,
# offered 4,320 and 5,400 veh/h; comparative_report.md §2). The same number
# for both controls, so a demand level defined against it favours neither.
# Mirrored by frontend src/types/demand.ts (test_demand_levels keeps the two
# in step).
REFERENCE_CAPACITY_VPH: Dict[int, int] = {1: 1250, 2: 2180, 3: 2620}

# Demand levels as a share of the reference capacity (degree of saturation).
DEMAND_LEVEL_RATIOS: Dict[str, float] = {
    "light": 0.25,
    "moderate": 0.5,
    "busy": 0.75,
    "near": 0.9,
    "capacity": 1.0,
    "over": 1.3,
}


def demand_vph(level: str, lanes: int) -> int:
    """Total arrivals (veh/h, rounded to 10) for a named level."""
    cap = REFERENCE_CAPACITY_VPH[max(1, min(3, int(lanes)))]
    return int(round(DEMAND_LEVEL_RATIOS[level] * cap / 10.0) * 10)


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


# Sweep demand levels (share of the reference capacity), the frontend's
# "Standard" preset in src/types/demand.ts.
STANDARD_SWEEP_RATIOS = [0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.2, 1.6]


def sweep_rates(lanes: int = CALIBRATED_LANES_PER_APPROACH) -> List[float]:
    """Whole-junction arrival rates (veh/s) of the standard sweep."""
    cap = REFERENCE_CAPACITY_VPH[max(1, min(3, int(lanes)))]
    return [round(r * cap / 3600.0, 3) for r in STANDARD_SWEEP_RATIOS]


# Warm-up excluded from every study's metrics: the 30 s the calibrated study
# and the live comparison use, shortened for short runs so at least three
# quarters of a run is always measured. Warm-ups of 15 s (sweep) and 5 s
# (validation) used to be hard-coded, so the studies measured start-up
# transients the live comparison excluded.
STUDY_WARMUP_SECONDS = 30.0


def study_warmup(duration: float) -> float:
    return min(STUDY_WARMUP_SECONDS, 0.25 * float(duration))
