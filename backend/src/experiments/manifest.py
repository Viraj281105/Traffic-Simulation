"""Experiment reproducibility manifest (V3.0 Product Strategy §6, ADR-013, ADR-016).

Every experiment result, and every .ufpkg, carries an urbanflow-experiment-manifest (v1).
The manifest's assumptions block records:
- Resolved driverAggression profile name (e.g. 'standard', 'moderate', 'high').
- The parameter set hash (16-hex SHA-256) of the resolved multipliers and invariants.
- The required scientific disclaimer.
- The declared uncertainty factor assumptions with their distributions, bounds, basis, and rationales.
"""

from __future__ import annotations

import re
from urllib.parse import unquote
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.scenario.documents import (
    ScenarioDocument,
    scenario_driver_aggression,
    scenario_fingerprint,
)
from src.uncertainty.spec import Factor
from src.vehicles.driver_aggression import (
    DRIVER_AGGRESSION_DISCLAIMER,
    compute_aggression_parameter_hash,
)

MANIFEST_FORMAT = "urbanflow-experiment-manifest"
MANIFEST_VERSION = 1
DEFAULT_PACKAGE_KIND = "robustness_experiment"
KNOWN_PACKAGE_KINDS: frozenset[str] = frozenset({DEFAULT_PACKAGE_KIND})


_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
# Windows aliases a segment with trailing dots/spaces to the trimmed name, and
# reserves device names (with or without an extension), so neither may appear.
_WINDOWS_RESERVED_RE = re.compile(
    r"^(con|prn|aux|nul|conin\$|conout\$|com[0-9¹²³]|lpt[0-9¹²³])(\..*)?$",
    re.IGNORECASE,
)
_WINDOWS_FORBIDDEN_CHARS = frozenset('<>:"|?*')
SIDECAR_FIELDS: Tuple[str, ...] = ("name", "kind", "path", "sha256")
_SIDECAR_MAX_LENGTHS = {"name": 120, "kind": 64, "path": 256}


def is_valid_sha256(value: Any) -> bool:
    """True for a str of exactly 64 hexadecimal characters (no whitespace)."""
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def sidecar_path_error(path: Any) -> Optional[str]:
    """Why ``path`` is not a safe relative package path, or None when it is.

    A sidecar path must stay inside the package: a non-empty, forward-slash,
    relative path whose every segment is a plain name. Rejected: absolute paths
    (POSIX, Windows drive, UNC), backslashes, ``.``/``..``/empty segments
    (including percent-encoded forms), control characters and surrounding
    whitespace, a trailing slash, and names Windows would alias or reserve
    (trailing dot/space, ``CON``/``NUL``/``COM1`` and friends, ``<>:"|?*``).
    """
    if not isinstance(path, str) or not path:
        return "must be a non-empty string"
    if path != path.strip():
        return "must not have leading or trailing whitespace"
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        return "must not contain control characters"
    if "\\" in path:
        return "must use '/' separators, not backslashes"
    if path.startswith("/") or _DRIVE_RE.match(path):
        return "must be relative, not absolute"
    for segment in path.split("/"):
        if segment in ("", ".", "..") or unquote(segment) in (".", ".."):
            return "must not contain empty, '.' or '..' segments"
        if segment.endswith((".", " ")):
            return "segments must not end with a dot or space"
        if _WINDOWS_FORBIDDEN_CHARS.intersection(segment):
            return "must not contain Windows-forbidden characters"
        if _WINDOWS_RESERVED_RE.match(segment):
            return "must not use a reserved device name"
    return None


def _check_sha256_map_key(path: Any) -> str:
    error = sidecar_path_error(path)
    if error:
        raise ValueError(f"packageChecksums key {error}")
    return str(path)


class SidecarMetadata(BaseModel):
    """Metadata descriptor for a sidecar file bundled within a package (.ufpkg)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120)
    kind: str = Field(..., min_length=1, max_length=64)
    path: str = Field(
        ...,
        max_length=256,
        description=(
            "Relative path inside the package using '/' separators; absolute paths and "
            "'.', '..' or empty segments are rejected."
        ),
    )
    sha256: str = Field(..., pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("path")
    @classmethod
    def _safe_path(cls, v: str) -> str:
        error = sidecar_path_error(v)
        if error:
            raise ValueError(f"sidecar path {error}")
        return v

    @field_validator("sha256")
    @classmethod
    def _exact_sha256(cls, v: str) -> str:
        if not is_valid_sha256(v):
            raise ValueError("sha256 must be exactly 64 hexadecimal characters")
        return v


class ManifestFactor(BaseModel):
    """Factor assumptions recorded in the manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,31}$")
    kind: str
    distribution: Dict[str, Any]
    bounds: List[float] = Field(..., min_length=2, max_length=2)
    basis: Literal["assumed", "observed", "user"] = "assumed"
    rationale: str = Field("", max_length=500)


class ManifestAssumptions(BaseModel):
    """Assumptions block of an experiment manifest."""

    model_config = ConfigDict(extra="forbid")

    driverAggression: str
    driverAggressionHash: str
    disclaimer: str
    factors: List[ManifestFactor] = Field(default_factory=list)


class ExperimentManifest(BaseModel):
    """UrbanFlow experiment reproducibility manifest (v1).

    Adheres to ADR-013 (Decision 2, 3, 6): format + integer version, extra='forbid',
    strictly backward-compatible with pre-W7 manifests through defaulted optional
    `kind` and `sidecars` fields.
    """

    model_config = ConfigDict(extra="forbid")

    format: Literal["urbanflow-experiment-manifest"] = "urbanflow-experiment-manifest"
    version: Literal[1] = 1
    kind: Optional[str] = Field(default=DEFAULT_PACKAGE_KIND, max_length=64)
    scenarioFingerprint: str
    specFingerprint: str
    resultFingerprint: str
    assumptions: ManifestAssumptions
    sidecars: Optional[List[SidecarMetadata]] = Field(default_factory=list)
    gitCommit: Optional[str] = None
    pythonVersion: Optional[str] = None
    dirty: Optional[bool] = None
    createdAt: Optional[str] = None
    packageChecksums: Optional[Dict[str, str]] = None

    @field_validator("packageChecksums")
    @classmethod
    def _checksums_are_safe(
        cls, v: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        for path, digest in (v or {}).items():
            _check_sha256_map_key(path)
            if not is_valid_sha256(digest):
                raise ValueError(
                    "packageChecksums values must be 64 hexadecimal characters"
                )
        return v

    @field_validator("kind", mode="before")
    @classmethod
    def _default_kind(cls, v: Any) -> str:
        return DEFAULT_PACKAGE_KIND if v is None else str(v)

    @field_validator("sidecars", mode="before")
    @classmethod
    def _default_sidecars(cls, v: Any) -> List[Any]:
        return [] if v is None else v


def is_known_package_kind(kind: Optional[str]) -> bool:
    """Return True if kind is a recognized package kind undergoing semantic validation."""
    if not kind:
        return True
    return kind in KNOWN_PACKAGE_KINDS


def validate_manifest_structure(data: Any) -> Tuple[bool, Optional[str]]:
    """Tier 1: Structural & integrity validation for all packages (known and unknown kinds).

    Checks that the manifest is a JSON object with valid format, version,
    fingerprints, and sidecar entry shapes, without enforcing kind-specific
    semantics on unknown kinds.
    """
    if not isinstance(data, dict):
        return False, "Manifest must be a JSON object"
    if data.get("format") != MANIFEST_FORMAT:
        return (
            False,
            f"Invalid format '{data.get('format')}'; expected '{MANIFEST_FORMAT}'",
        )
    if data.get("version") != MANIFEST_VERSION:
        return (
            False,
            f"Unsupported version '{data.get('version')}'; expected {MANIFEST_VERSION}",
        )
    if not isinstance(data.get("scenarioFingerprint"), str):
        return False, "Missing or invalid scenarioFingerprint"
    if not isinstance(data.get("specFingerprint"), str):
        return False, "Missing or invalid specFingerprint"
    if not isinstance(data.get("resultFingerprint"), str):
        return False, "Missing or invalid resultFingerprint"
    sidecars = data.get("sidecars")
    if sidecars is not None:
        if not isinstance(sidecars, list):
            return False, "sidecars must be an array"
        seen_paths: set[str] = set()
        for idx, sc in enumerate(sidecars):
            if not isinstance(sc, dict):
                return False, f"sidecar at index {idx} must be an object"
            for required_field in SIDECAR_FIELDS:
                if required_field not in sc:
                    return False, f"sidecar at index {idx} missing '{required_field}'"
            extra = set(sc) - set(SIDECAR_FIELDS)
            if extra:
                return False, f"sidecar at index {idx} has unexpected field(s)"
            for text_field in SIDECAR_FIELDS:
                if not isinstance(sc[text_field], str):
                    return False, f"sidecar at index {idx} '{text_field}' must be a string"
            for text_field, limit in _SIDECAR_MAX_LENGTHS.items():
                if not sc[text_field] or len(sc[text_field]) > limit:
                    return (
                        False,
                        f"sidecar at index {idx} '{text_field}' must be 1-{limit} characters",
                    )
            path_error = sidecar_path_error(sc["path"])
            if path_error:
                return False, f"sidecar at index {idx} path {path_error}"
            if not is_valid_sha256(sc["sha256"]):
                return (
                    False,
                    f"sidecar at index {idx} sha256 must be 64 hexadecimal characters",
                )
            normalized = sc["path"].casefold()
            if normalized in seen_paths:
                return False, f"sidecar at index {idx} duplicates an earlier path"
            seen_paths.add(normalized)
    return True, None


def validate_manifest_semantic(data: Any) -> ExperimentManifest:
    """Tier 2: Semantic verification for known package kinds.

    Enforces strict schema validation (extra='forbid') for 'robustness_experiment'.
    Raises ValueError for unknown kinds because semantic validation cannot be
    invented without a registered schema.
    """
    valid_struct, err = validate_manifest_structure(data)
    if not valid_struct:
        raise ValueError(f"Structural validation failed: {err}")
    kind = data.get("kind") or DEFAULT_PACKAGE_KIND
    if not is_known_package_kind(kind):
        raise ValueError(
            f"Unknown package kind '{kind}': semantic validation requires a registered schema. "
            "Structural integrity verification only is supported."
        )
    return ExperimentManifest.model_validate(data)


def build_manifest_assumptions(
    scenario: ScenarioDocument,
    factors: Sequence[Factor] = (),
) -> Dict[str, Any]:
    """Build the assumptions block for an experiment manifest.

    Records the driver aggression profile the engine runs (an ``advanced``
    override included) and its parameter hash, the scientific disclaimer,
    and factor assumptions.
    """
    profile = scenario_driver_aggression(scenario)
    param_hash = compute_aggression_parameter_hash(profile)
    return {
        "driverAggression": profile,
        "driverAggressionHash": param_hash,
        "disclaimer": DRIVER_AGGRESSION_DISCLAIMER,
        "factors": [
            {
                "id": f.id,
                "kind": f.kind,
                "distribution": f.distribution.model_dump(
                    mode="json", exclude_none=True
                ),
                "bounds": f.bounds,
                "basis": f.basis,
                "rationale": f.rationale,
            }
            for f in factors
        ],
    }


def build_experiment_manifest(
    *,
    scenario: ScenarioDocument,
    spec_fingerprint: str,
    result_fingerprint: str,
    factors: Sequence[Factor] = (),
    kind: str = DEFAULT_PACKAGE_KIND,
    sidecars: Optional[Sequence[SidecarMetadata | Dict[str, Any]]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an urbanflow-experiment-manifest v1 document."""
    doc: Dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "kind": kind,
        "scenarioFingerprint": scenario_fingerprint(scenario),
        "specFingerprint": spec_fingerprint,
        "resultFingerprint": result_fingerprint,
        "assumptions": build_manifest_assumptions(scenario, factors),
        "sidecars": [
            s.model_dump(mode="json") if isinstance(s, SidecarMetadata) else s
            for s in (sidecars or ())
        ],
    }
    if extra:
        doc.update(extra)
    return doc
