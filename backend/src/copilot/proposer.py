"""The deterministic proposer (keywords -> intent) and the builder (intent -> experiment document).

The deterministic proposer is the baseline and the fallback. It is **not** called AI anywhere: it fills the
intent from keywords and states every assumption it makes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .catalog import ALTERNATIVE_TITLES, DEMAND_VPH, DEPTH_CONDITIONS
from .models import ExperimentIntent, Provenance

PROPOSER_VERSION = "deterministic-1"

_ALTERNATIVE_PATTERNS: List[Tuple[str, str]] = [
    # Order matters: the more specific roundabout first, and its words are removed before the next test.
    (
        "signalised_roundabout",
        r"signali[sz]ed\s+roundabouts?|metered(?:[-\s]entry)?\s+roundabouts?|"
        r"roundabouts?\s+with\s+(?:signals|metering)|turbo",
    ),
    (
        "roundabout",
        r"(?:conventional\s+|normal\s+|plain\s+|unsignali[sz]ed\s+)?roundabouts?",
    ),
    ("adaptive", r"adaptive|actuated|responsive|smart\s+signal"),
    (
        "fixed_time",
        r"fixed[-\s]?time|pre-?timed|fixed\s+signal|traffic\s+lights?|signal(?:ised)?\s+junction",
    ),
]

_SECRET_OR_BYPASS = re.compile(
    r"api[_\s-]?key|secret|password|token|bypass|ignore (?:the |all |previous )*(?:rules|instructions|quota)|"
    r"unlimited|disable (?:the )?quota|system prompt",
    re.IGNORECASE,
)
_SUPERIORITY = re.compile(
    r"\bprove\b|\bguarantee|\bbest\b|\boptimal\b|definitively", re.IGNORECASE
)

_MAX_ARM_VPH = 1200


def propose_deterministic(
    question: str,
) -> Tuple[ExperimentIntent, Dict[str, Provenance]]:
    """Fill an intent from keywords. Returns the intent and which fields came from a rule."""
    text = " ".join(question.lower().split())
    provenance: Dict[str, Provenance] = {}
    assumptions: List[str] = []
    warnings: List[str] = []

    found: List[Tuple[int, str]] = []
    remaining = text
    for kind, pattern in _ALTERNATIVE_PATTERNS:
        match = re.search(pattern, remaining)
        if match:
            found.append((match.start(), kind))
            remaining = re.sub(pattern, " " * 3, remaining)
    found.sort()
    alternatives = [kind for _, kind in found]
    if len(alternatives) < 2:
        mentioned = (
            ", ".join(ALTERNATIVE_TITLES[a] for a in alternatives) or "no control"
        )
        alternatives = list(
            dict.fromkeys(alternatives + ["fixed_time", "adaptive", "roundabout"])
        )[:3]
        assumptions.append(
            f"The question names {mentioned}; compared against the standard alternatives: "
            + ", ".join(ALTERNATIVE_TITLES[a] for a in alternatives)
            + "."
        )
    provenance["alternatives"] = "rule"

    baseline: Optional[str] = None
    base_match = re.search(
        r"(?:against|versus|vs\.?|compared (?:to|with)|baseline)\s+(?:an?\s+|the\s+)?([a-z\- ]{3,40})",
        text,
    )
    if base_match:
        tail = base_match.group(1)
        for kind, pattern in _ALTERNATIVE_PATTERNS:
            if kind in alternatives and re.match(pattern, tail):
                baseline = kind
                break
    if baseline is None:
        baseline = "fixed_time" if "fixed_time" in alternatives else alternatives[0]
        assumptions.append(
            f"Baseline: {ALTERNATIVE_TITLES[baseline]} (the conventional reference)."
        )
    provenance["baseline"] = "rule"

    aggression: Optional[str] = None
    if re.search(r"highly aggressive|very aggressive|high aggression|aggressive", text):
        aggression = "high"
    elif re.search(r"moderate(?:ly)? aggress|somewhat aggress", text):
        aggression = "moderate"
    elif re.search(r"calm|cautious|polite|standard driv", text):
        aggression = "standard"
    if aggression:
        provenance["aggression"] = "rule"

    demand = "moderate"
    if re.search(r"near[-\s]capacity|saturat|gridlock|over capacity", text):
        demand = "near_capacity"
    elif re.search(r"peak|rush|heavy traffic|congest|busy|high demand", text):
        demand = "peak"
    elif re.search(r"light traffic|off[-\s]peak|quiet|low demand|night", text):
        demand = "light"
    else:
        assumptions.append(
            f"Demand: moderate ({DEMAND_VPH['moderate']} veh/h per arm), none was given."
        )
    provenance["demand"] = "rule"

    uneven = bool(
        re.search(
            r"uneven|unbalanced|imbalanc|directional|tidal|one[-\s]sided|asymmetric",
            text,
        )
    )
    provenance["unevenDemand"] = "rule"

    mix = "default"
    if re.search(r"bus|truck|lorr|heavy vehicle|freight|hgv", text):
        mix = "heavy_vehicles"
    elif re.search(r"two[-\s]wheeler|motorcycle|motorbike|scooter|bike", text):
        mix = "two_wheelers"
    provenance["mix"] = "rule"

    depth = "standard"
    if re.search(r"\b(?:quick|fast|rough|preliminary)\b", text):
        depth = "quick"
    elif re.search(r"\b(?:thorough|rigorous|robust|careful|detailed)\b", text):
        depth = "thorough"
    provenance["depth"] = "rule"

    replications = 2
    rep_match = re.search(
        r"(\d+)\s+(?:replications|repetitions|seeds|runs per condition)", text
    )
    if rep_match:
        replications = max(2, min(5, int(rep_match.group(1))))
    provenance["replications"] = "rule"

    indicator = "averageDelay"
    if re.search(r"p95|95(?:th)?\s*percentile|worst[-\s]case|tail", text):
        indicator = "p95Delay"
    elif re.search(r"median", text):
        indicator = "medianDelay"
    provenance["primaryIndicator"] = "rule"

    if _SECRET_OR_BYPASS.search(question):
        warnings.append(
            "Part of the question asks for something the Copilot cannot do (credentials, quota or "
            "rule changes); it was ignored. Quotas and validation always apply."
        )
    if _SUPERIORITY.search(question):
        warnings.append(
            "An experiment can show how alternatives compare under the stated assumptions; it cannot "
            "prove that one is best or optimal in the real world."
        )

    clarification = None
    if len(found) == 0 and aggression is None and demand == "moderate" and not uneven:
        clarification = (
            "The question names no control, demand or driver behaviour, so every choice below is an "
            "assumption. Say which alternatives and traffic you have in mind for a closer proposal."
        )

    intent = ExperimentIntent(
        alternatives=alternatives,  # type: ignore[arg-type]
        baseline=baseline,  # type: ignore[arg-type]
        aggression=aggression,  # type: ignore[arg-type]
        demand=demand,  # type: ignore[arg-type]
        unevenDemand=uneven,
        mix=mix,  # type: ignore[arg-type]
        depth=depth,  # type: ignore[arg-type]
        replications=replications,
        primaryIndicator=indicator,  # type: ignore[arg-type]
        uncertainAggression=aggression is not None,
        assumptions=assumptions[:8],
        warnings=warnings[:8],
        clarification=clarification,
    )
    return intent, provenance


# ---------------------------------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------------------------------
def _metered_entry_patch() -> Dict[str, Any]:
    return {
        "roundabout": {
            "entryControl": "metered_entry",
            "entryMetering": {
                "phases": [
                    {"entries": ["north", "south"], "green": 20.0},
                    {"entries": ["east", "west"], "green": 20.0},
                ]
            },
        }
    }


_STRATEGY_OF = {
    "fixed_time": "fixed_time",
    "adaptive": "adaptive",
    "roundabout": "roundabout",
    "signalised_roundabout": "roundabout",
}


def build_experiment(
    intent: ExperimentIntent, question: str
) -> Tuple[Dict[str, Any], List[str]]:
    """The ``urbanflow-experiment`` document for an intent, plus suggested follow-up checks."""
    per_arm = DEMAND_VPH[intent.demand]
    if intent.unevenDemand:
        major, minor = min(round(per_arm * 1.4), _MAX_ARM_VPH), round(per_arm * 0.6)
        volumes = {"north": major, "south": major, "east": minor, "west": minor}
    else:
        volumes = {d: per_arm for d in ("north", "south", "east", "west")}
    scenario: Dict[str, Any] = {
        "format": "urbanflow-scenario",
        "version": 1,
        "name": "Copilot proposal junction",
        "junction": {"type": "fixed_time_signal"},
        "approaches": {
            d: {
                "lanes": 1,
                "vehiclesPerHour": vph,
                "turning": {"left": 0.2, "straight": 0.6, "right": 0.2},
            }
            for d, vph in volumes.items()
        },
        "simulation": {"duration": 240, "warmup": 30, "seed": 7},
    }
    if intent.mix == "heavy_vehicles":
        scenario["vehicles"] = {
            "mix": {
                "car": 0.65,
                "suv": 0.1,
                "bus": 0.1,
                "truck": 0.15,
                "motorcycle": 0.0,
            }
        }
    elif intent.mix == "two_wheelers":
        scenario["vehicles"] = {
            "mix": {
                "car": 0.45,
                "suv": 0.1,
                "bus": 0.05,
                "truck": 0.0,
                "motorcycle": 0.4,
            }
        }
    if intent.aggression is not None:
        scenario["traffic"] = {"driverAggression": intent.aggression}

    alternatives = []
    for kind in intent.alternatives:
        alt: Dict[str, Any] = {
            "id": kind[:32],
            "label": ALTERNATIVE_TITLES[kind],
            "strategy": _STRATEGY_OF[kind],
        }
        if kind == "signalised_roundabout":
            alt["patch"] = _metered_entry_patch()
        alternatives.append(alt)

    factors: List[Dict[str, Any]] = [
        {
            "id": "demand",
            "kind": "demand_scale",
            "distribution": {"kind": "uniform"},
            "bounds": [0.8, 1.2],
            "basis": "assumed",
            "rationale": "Demand is rarely known to better than about 20 percent; assumed, not observed.",
        }
    ]
    if intent.unevenDemand:
        factors.append(
            {
                "id": "turning",
                "kind": "turning_shift",
                "distribution": {"kind": "uniform"},
                "bounds": [-0.3, 0.3],
                "basis": "assumed",
                "rationale": "Uneven demand usually comes with uncertain turning shares; assumed range.",
            }
        )
    if intent.mix == "heavy_vehicles":
        factors.append(
            {
                "id": "mix",
                "kind": "mix_shift",
                "distribution": {"kind": "uniform"},
                "bounds": [-0.3, 0.3],
                "basis": "assumed",
                "rationale": "The heavy-vehicle share varies between days; assumed range.",
            }
        )
    if intent.uncertainAggression:
        factors.append(
            {
                "id": "headway",
                "kind": "headway_scale",
                "distribution": {"kind": "uniform"},
                "bounds": [0.8, 1.2],
                "basis": "assumed",
                "rationale": "Following behaviour within an aggression profile is uncertain; IDM headway "
                "is a proxy (the engine has no reaction delay).",
            }
        )

    experiment = {
        "format": "urbanflow-experiment",
        "version": 1,
        "name": ("Copilot: " + " ".join(question.split()))[:120],
        "scenario": scenario,
        "alternatives": alternatives,
        "baseline": (intent.baseline or intent.alternatives[0])[:32],
        "uncertainty": {
            "format": "urbanflow-uncertainty-spec",
            "version": 1,
            "name": "Copilot uncertainty specification",
            "factors": factors,
            "conditions": DEPTH_CONDITIONS[intent.depth],
            "replications": intent.replications,
            "seed": 11,
            "primaryIndicator": intent.primaryIndicator,
        },
    }
    checks = [
        "Widen the demand range (for example 0.6 to 1.4) to see where the preferred alternative changes.",
        "Repeat with replications = 3 to check the within-condition noise.",
    ]
    if intent.aggression != "high":
        checks.append("Repeat under the high driver-aggression profile.")
    if not intent.unevenDemand:
        checks.append("Repeat with uneven directional demand.")
    return experiment, checks
