"""The capability catalogue a proposer is given: what may be proposed and within which bounds.

Versioned by its hash, which every proposal records, so a proposal can be traced to the catalogue it saw.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, get_args

from src.experiments import limits
from src.uncertainty import spec as uspec

from .models import Aggression, AlternativeKind, DemandLevel, Depth, MixEmphasis

CATALOGUE_VERSION = 1

ALTERNATIVE_TITLES: Dict[str, str] = {
    "fixed_time": "Fixed-time signal",
    "adaptive": "Adaptive (actuated) signal",
    "roundabout": "Conventional roundabout",
    "signalised_roundabout": "Signalised (metered-entry) roundabout",
}

DEMAND_VPH: Dict[str, int] = {
    "light": 300,
    "moderate": 550,
    "peak": 750,
    "near_capacity": 900,
}

DEPTH_CONDITIONS: Dict[str, int] = {"quick": 12, "standard": 24, "thorough": 40}


def catalogue() -> Dict[str, Any]:
    return {
        "format": "urbanflow-copilot-catalogue",
        "version": CATALOGUE_VERSION,
        "alternatives": [
            {"id": k, "title": ALTERNATIVE_TITLES[k]} for k in get_args(AlternativeKind)
        ],
        "aggressionProfiles": list(get_args(Aggression)),
        "demandLevels": {k: DEMAND_VPH[k] for k in get_args(DemandLevel)},
        "vehicleMixEmphasis": list(get_args(MixEmphasis)),
        "studyDepth": {k: DEPTH_CONDITIONS[k] for k in get_args(Depth)},
        "replications": {"min": 2, "max": 5},
        "primaryIndicators": list(get_args(uspec.PrimaryIndicator)),
        "factorKinds": list(get_args(uspec.FactorKind)),
        "quotas": limits.quotas(),
    }


def catalogue_hash() -> str:
    canonical = json.dumps(catalogue(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def alternative_list() -> List[str]:
    return list(get_args(AlternativeKind))
