"""``.ufpkg`` experiment packages: build, verify, and (safely) extract (W7 Stage 4, ADR-013).

A package is a ZIP archive holding::

    manifest.json     the ``urbanflow-experiment-manifest`` v1 document
    experiment.json   the request that was run
    result.json       the completed result
    SHA256SUMS        ``<sha256>  <member>`` for every other member (LF, sorted)
    sidecars/<name>   optional files declared in ``manifest.sidecars`` (.json, .csv, .txt)

Verification works entirely in memory and never runs, imports or deserializes anything but JSON: the
archive is checked member by member under hard limits (compressed size, entry count, bytes actually read,
compression ratio), every member's exact bytes are compared with ``SHA256SUMS``, and the manifest, the
request and the result are cross-checked and their fingerprints recomputed. **Integrity is not
authenticity**: all of this shows a package is internally consistent, not who made it.

The replay class is derived from the provenance the manifest records (code revision, Python version,
driver-aggression parameters); it is not established by re-running the experiment.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import logging
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from src.api.contracts_v3 import (
    NORMATIVE_INTEGRITY_STATEMENT,
    PackageVerificationReport,
)
from src.core.limits import nested_deeper_than
from src.core.provenance import GIT_COMMIT_HASH, PYTHON_VERSION
from src.planning.models import fingerprint_of
from src.scenario.documents import parse_scenario, scenario_fingerprint
from src.uncertainty.spec import UncertaintySpec, fingerprint
from src.vehicles.driver_aggression import compute_aggression_parameter_hash

from . import limits
from .manifest import (
    DEFAULT_PACKAGE_KIND,
    MANIFEST_FORMAT,
    SidecarMetadata,
    is_known_package_kind,
    sidecar_path_error,
    validate_manifest_semantic,
    validate_manifest_structure,
)
from .models import RESULT_FORMAT, ExperimentRequest

logger = logging.getLogger(__name__)

PACKAGE_EXTENSION = ".ufpkg"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_NAME = "experiment.json"
RESULT_NAME = "result.json"
CHECKSUMS_NAME = "SHA256SUMS"
SIDECAR_DIR = "sidecars"
ROOT_MEMBERS = (MANIFEST_NAME, EXPERIMENT_NAME, RESULT_NAME, CHECKSUMS_NAME)
SIDECAR_EXTENSIONS = (".json", ".csv", ".txt")

# A member name segment: letters, digits, underscore, dot, hyphen; never a leading dot.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}$")
_SUMS_LINE_RE = re.compile(r"^([0-9a-f]{64})  (\S.*)$")
MAX_MEMBER_NAME = 120
# Highest accepted ratio of uncompressed to compressed bytes for a member that is more than a few KiB.
MAX_COMPRESSION_RATIO = 200
_RATIO_FLOOR_BYTES = 64 * 1024
MAX_JSON_MEMBER_BYTES = 40 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024

# Leading bytes of executables, scripts and nested archives: refused whatever the member is called.
_FORBIDDEN_MAGIC = (
    (b"MZ", "a Windows executable"),
    (b"\x7fELF", "an ELF executable"),
    (b"#!", "a script"),
    (b"PK\x03\x04", "a nested archive"),
    (b"PK\x05\x06", "a nested archive"),
    (b"\xfe\xed\xfa", "a Mach-O executable"),
    (b"\xcf\xfa\xed\xfe", "a Mach-O executable"),
    (b"\xca\xfe\xba\xbe", "a Java class or universal binary"),
    (b"\x1f\x8b", "a gzip archive"),
    (b"7z\xbc\xaf", "a 7-zip archive"),
    (b"Rar!", "a RAR archive"),
)


class PackageError(Exception):
    """A package could not be built (the message is safe to show)."""


class PackageTooLarge(PackageError):  # noqa: N818
    """The package would exceed the size limit (HTTP 413)."""


# ---------------------------------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------------------------------
def _display(name: str) -> str:
    """A member name made safe to put in a message: printable ASCII only, shortened."""
    cleaned = "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in name)
    return repr(cleaned[:60] + ("..." if len(cleaned) > 60 else ""))


def member_name_error(name: str) -> Optional[str]:
    """Why ``name`` is not an acceptable member name, or None.

    Allowed: the four root members, and ``sidecars/<file>`` with a .json, .csv or .txt extension. Every
    segment is checked against a character allow-list, so traversal, absolute and drive paths,
    backslashes, control characters, empty or dotted segments and Windows-reserved names cannot occur."""
    if not name or len(name) > MAX_MEMBER_NAME:
        return "has an empty or over-long name"
    if name in ROOT_MEMBERS:
        return None
    parts = name.split("/")
    if len(parts) != 2 or parts[0] != SIDECAR_DIR:
        return "is not a recognised package member"
    leaf = parts[1]
    if not _SEGMENT_RE.match(leaf):
        return "has characters outside the allowed set"
    if leaf.endswith((".", " ")):
        return "has a name Windows would alter"
    if sidecar_path_error(name) is not None:
        return "is not a safe relative path"
    if not leaf.lower().endswith(SIDECAR_EXTENSIONS):
        return "has a file type that is not allowed in a package"
    return None


def _forbidden_content(data: bytes) -> Optional[str]:
    for magic, what in _FORBIDDEN_MAGIC:
        if data.startswith(magic):
            return what
    return None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_checksums(members: Dict[str, bytes]) -> bytes:
    """``SHA256SUMS`` for ``members`` (every member except SHA256SUMS itself): LF, sorted by name."""
    lines = [f"{_sha256(members[name])}  {name}" for name in sorted(members)]
    return ("\n".join(lines) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------------------------------
def _canonical_json(document: Any) -> bytes:
    return (
        json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def build_package(
    request: Dict[str, Any],
    result: Dict[str, Any],
    created_at: str,
    sidecars: Optional[Dict[str, bytes]] = None,
) -> bytes:
    """The ``.ufpkg`` bytes of a completed experiment. Deterministic: the same inputs give the same bytes.

    ``sidecars`` maps a file name (inside ``sidecars/``) to its bytes; each is declared in the manifest."""
    if result.get("format") != RESULT_FORMAT or not isinstance(
        result.get("manifest"), dict
    ):
        raise PackageError("only a completed experiment can be exported")
    members: Dict[str, bytes] = {
        EXPERIMENT_NAME: _canonical_json(request),
        RESULT_NAME: _canonical_json(result),
    }
    declared: List[Dict[str, Any]] = []
    for leaf, content in sorted((sidecars or {}).items()):
        name = f"{SIDECAR_DIR}/{leaf}"
        problem = member_name_error(name)
        if problem or _forbidden_content(content):
            raise PackageError(f"sidecar {_display(leaf)} is not allowed in a package")
        members[name] = content
        declared.append(
            SidecarMetadata(
                name=leaf,
                kind=leaf.rsplit(".", 1)[-1],
                path=name,
                sha256=_sha256(content),
            ).model_dump(mode="json")
        )
    manifest = dict(result["manifest"])
    manifest["sidecars"] = declared
    manifest["createdAt"] = created_at
    manifest["packageChecksums"] = {
        name: _sha256(content) for name, content in sorted(members.items())
    }
    members[MANIFEST_NAME] = _canonical_json(manifest)
    members[CHECKSUMS_NAME] = render_checksums(members)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in (
            *ROOT_MEMBERS[:3],
            *sorted(n for n in members if "/" in n),
            CHECKSUMS_NAME,
        ):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.create_system = 3
            archive.writestr(info, members[name])
    data = buffer.getvalue()
    if len(data) > limits.MAX_PACKAGE_BYTES:
        raise PackageTooLarge(
            f"the package would be {len(data):,} bytes, over the {limits.MAX_PACKAGE_BYTES:,}-byte limit"
        )
    return data


# ---------------------------------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------------------------------
class _Read:
    """Everything the archive checks produce: the members' bytes (when readable) and the errors."""

    def __init__(self) -> None:
        self.members: Dict[str, bytes] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, message: str) -> None:
        if message not in self.errors:
            self.errors.append(message)


def _read_members(data: bytes, out: _Read) -> None:
    """Open the archive and read every member under the limits. Fills ``out.members``."""
    if not data:
        out.error("the package is empty")
        return
    if len(data) > limits.MAX_PACKAGE_BYTES:
        out.error(f"the package is larger than {limits.MAX_PACKAGE_BYTES:,} bytes")
        return
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, NotImplementedError, EOFError, OSError, ValueError):
        out.error("the file is not a valid ZIP archive")
        return
    with archive:
        infos = archive.infolist()
        if len(infos) > limits.MAX_PACKAGE_ENTRIES:
            out.error(f"the package has more than {limits.MAX_PACKAGE_ENTRIES} entries")
            return
        seen: set[str] = set()
        declared_total = 0
        acceptable: List[zipfile.ZipInfo] = []
        for info in infos:
            name = info.filename
            folded = name.casefold()
            problem = member_name_error(name)
            if info.is_dir():
                out.error(f"{_display(name)} is a directory entry")
                continue
            if problem:
                out.error(f"member {_display(name)} {problem}")
                continue
            if folded in seen:
                out.error(f"member {_display(name)} appears more than once")
                continue
            seen.add(folded)
            if info.flag_bits & 0x1:
                out.error(f"member {_display(name)} is encrypted")
                continue
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                out.error(
                    f"member {_display(name)} uses an unsupported compression method"
                )
                continue
            file_type = stat.S_IFMT(
                info.external_attr >> 16
            )  # 0 when the archiver set no type
            if file_type and file_type != stat.S_IFREG:
                out.error(f"member {_display(name)} is a link or special file")
                continue
            declared_total += info.file_size
            if info.file_size > limits.MAX_PACKAGE_UNCOMPRESSED_BYTES:
                out.error(
                    f"member {_display(name)} is larger than the unpacked size limit"
                )
                continue
            if (
                info.file_size > _RATIO_FLOOR_BYTES
                and info.file_size > MAX_COMPRESSION_RATIO * max(info.compress_size, 1)
            ):
                out.error(f"member {_display(name)} is compressed suspiciously well")
                continue
            acceptable.append(info)
        if declared_total > limits.MAX_PACKAGE_UNCOMPRESSED_BYTES:
            out.error(
                f"the package unpacks to more than {limits.MAX_PACKAGE_UNCOMPRESSED_BYTES:,} bytes"
            )
            return
        if out.errors:
            return  # nothing is read from an archive that already broke a structural rule

        budget = limits.MAX_PACKAGE_UNCOMPRESSED_BYTES
        for info in acceptable:
            cap = min(budget, info.file_size)
            try:
                with archive.open(info) as handle:
                    content = handle.read(
                        cap + 1
                    )  # one byte over detects a lying header
                    if len(content) > cap or handle.read(1):
                        out.error(
                            f"member {_display(info.filename)} is larger than it declares"
                        )
                        return
            except (
                zipfile.BadZipFile,
                NotImplementedError,
                EOFError,
                OSError,
                RuntimeError,
            ):
                out.error(f"member {_display(info.filename)} is corrupt or unreadable")
                return
            if len(content) != info.file_size:
                out.error(
                    f"member {_display(info.filename)} is shorter than it declares"
                )
                return
            budget -= len(content)
            out.members[info.filename] = content


def _parse_checksums(raw: bytes, out: _Read) -> Optional[Dict[str, str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        out.error("SHA256SUMS is not valid UTF-8 text")
        return None
    if "\r" in text or not text.endswith("\n"):
        out.error("SHA256SUMS must use LF line endings and end with a newline")
        return None
    sums: Dict[str, str] = {}
    for number, line in enumerate(text[:-1].split("\n"), start=1):
        match = _SUMS_LINE_RE.match(line)
        if not match:
            out.error(f"SHA256SUMS line {number} is not '<sha256>  <member>'")
            return None
        digest, name = match.groups()
        if name in sums:
            out.error(f"SHA256SUMS lists a member more than once (line {number})")
            return None
        sums[name] = digest
    if list(sums) != sorted(sums):
        out.error("SHA256SUMS is not sorted by member name")
    return sums


def _check_integrity(out: _Read) -> Optional[Dict[str, str]]:
    """Every member except SHA256SUMS must be listed, and its exact bytes must match."""
    if CHECKSUMS_NAME not in out.members:
        out.error("SHA256SUMS is missing")
        return None
    sums = _parse_checksums(out.members[CHECKSUMS_NAME], out)
    if sums is None:
        return None
    others = {n for n in out.members if n != CHECKSUMS_NAME}
    for name in sorted(set(sums) - others):
        out.error(f"SHA256SUMS lists {_display(name)}, which is not in the package")
    for name in sorted(others - set(sums)):
        out.error(f"member {_display(name)} is not listed in SHA256SUMS")
    for name in sorted(others & set(sums)):
        if not hmac.compare_digest(_sha256(out.members[name]), sums[name]):
            out.error(f"member {_display(name)} does not match its SHA-256")
    return sums


def _load_json(name: str, out: _Read, maximum: int) -> Optional[Any]:
    raw = out.members.get(name)
    if raw is None:
        out.error(f"{name} is missing")
        return None
    if len(raw) > maximum:
        out.error(f"{name} is too large")
        return None
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        out.error(f"{name} is not valid JSON")
        return None
    if nested_deeper_than(document, limits.MAX_DOCUMENT_DEPTH):
        out.error(f"{name} is nested too deeply")
        return None
    return document


def _check_sidecars(manifest: Dict[str, Any], out: _Read) -> None:
    declared = manifest.get("sidecars") or []
    declared_paths = set()
    for entry in declared:
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str) or member_name_error(path) is not None:
            out.error("a declared sidecar path is not an allowed package member")
            continue
        declared_paths.add(path)
        content = out.members.get(path)
        if content is None:
            out.error(f"declared sidecar {_display(path)} is not in the package")
            continue
        if not hmac.compare_digest(
            _sha256(content), str(entry.get("sha256", "")).lower()
        ):
            out.error(
                f"sidecar {_display(path)} does not match the digest in the manifest"
            )
        what = _forbidden_content(content)
        if what:
            out.error(f"sidecar {_display(path)} looks like {what}")
        if b"\x00" in content:
            out.error(f"sidecar {_display(path)} is not text")
        else:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                out.error(f"sidecar {_display(path)} is not UTF-8 text")
    for name in sorted(n for n in out.members if n.startswith(f"{SIDECAR_DIR}/")):
        if name not in declared_paths:
            out.error(f"sidecar {_display(name)} is not declared in the manifest")


def _check_robustness_documents(
    manifest: Dict[str, Any], sums: Optional[Dict[str, str]], out: _Read
) -> None:
    """Cross-check manifest, request and result, and recompute the fingerprints they carry."""
    request = _load_json(EXPERIMENT_NAME, out, MAX_JSON_MEMBER_BYTES)
    result = _load_json(RESULT_NAME, out, MAX_JSON_MEMBER_BYTES)
    if not isinstance(request, dict) or not isinstance(result, dict):
        return
    checksums = manifest.get("packageChecksums")
    if isinstance(checksums, dict) and sums is not None:
        for name, digest in checksums.items():
            if sums.get(name) != str(digest).lower():
                out.error(
                    f"manifest packageChecksums disagree with SHA256SUMS for {_display(str(name))}"
                )
    try:
        parsed_request = ExperimentRequest.model_validate(request)
    except ValidationError:
        out.error("experiment.json is not a valid experiment request")
        parsed_request = None
    if result.get("format") != RESULT_FORMAT:
        out.error("result.json is not an experiment result")
        return
    try:
        spec = UncertaintySpec.model_validate(result.get("specification"))
        recomputed_spec = fingerprint(spec)
    except (ValidationError, ValueError, TypeError):
        out.error("result.json holds no valid uncertainty specification")
        return
    if recomputed_spec != result.get(
        "specFingerprint"
    ) or recomputed_spec != manifest.get("specFingerprint"):
        out.error("the specification fingerprint does not match the specification")
    if parsed_request is not None:
        if fingerprint(parsed_request.uncertainty) != recomputed_spec:
            out.error(
                "experiment.json and result.json describe different specifications"
            )
        base, _errors = parse_scenario(parsed_request.scenario)
        if base is None:
            out.error("experiment.json holds no valid scenario")
        elif scenario_fingerprint(base) != manifest.get("scenarioFingerprint"):
            out.error("the scenario fingerprint does not match the scenario")
    try:
        evidence = {
            "scenarioFingerprint": result["scenario"]["fingerprint"],
            "alternatives": [
                [a["id"], a["strategy"], a["fingerprint"]]
                for a in result["alternatives"]
            ],
            "baseline": result["baseline"],
            "specFingerprint": result["specFingerprint"],
            "analysis": result["analysis"],
        }
        recomputed = fingerprint_of(evidence)
    except (KeyError, TypeError, ValueError):
        out.error("result.json is missing fields needed to check its fingerprint")
        return
    if recomputed != result.get("resultFingerprint") or recomputed != manifest.get(
        "resultFingerprint"
    ):
        out.error("the result fingerprint does not match the result")


def _replay_class(manifest: Dict[str, Any], out: _Read) -> str:
    """Compare the recorded provenance with this server. Not a re-run: it says how likely an identical
    replay is, from what the package records."""
    differs = "differs (engine or runtime changed)"
    assumptions = manifest.get("assumptions")
    if not isinstance(assumptions, dict):
        return differs
    try:
        mine = compute_aggression_parameter_hash(assumptions.get("driverAggression"))
    except Exception:  # noqa: BLE001 - an unknown profile is a mismatch, not a crash
        mine = None
    if mine is None or mine != assumptions.get("driverAggressionHash"):
        out.warnings.append(
            "the driver-aggression parameters differ from this server's, so a replay would differ"
        )
        return differs
    commit, python = manifest.get("gitCommit"), manifest.get("pythonVersion")
    if not commit or not python:
        out.warnings.append(
            "the manifest records no code revision or Python version (a pre-W7 package); "
            "a replay can be compared but not matched exactly"
        )
        return "comparable"
    if python.split(".")[:2] != PYTHON_VERSION.split(".")[:2]:
        out.warnings.append("the package was made with a different Python version")
        return differs
    if commit == GIT_COMMIT_HASH and python == PYTHON_VERSION:
        return "exact"
    out.warnings.append(
        "the package was made by a different code revision of the engine"
    )
    return "comparable"


def _summary(manifest: Dict[str, Any], out: _Read) -> Dict[str, Any]:
    assumptions = manifest.get("assumptions")
    assumptions = assumptions if isinstance(assumptions, dict) else {}
    keep = (
        "format",
        "version",
        "kind",
        "scenarioFingerprint",
        "specFingerprint",
        "resultFingerprint",
        "gitCommit",
        "pythonVersion",
        "createdAt",
    )
    summary: Dict[str, Any] = {
        key: manifest[key] for key in keep if isinstance(manifest.get(key), (str, int))
    }
    summary["driverAggression"] = assumptions.get("driverAggression")
    summary["driverAggressionHash"] = assumptions.get("driverAggressionHash")
    summary["members"] = [
        {
            "name": name,
            "bytes": len(out.members[name]),
            "sha256": _sha256(out.members[name]),
        }
        for name in sorted(out.members)
    ]
    return summary


def inspect_package(data: bytes) -> PackageVerificationReport:
    """Verify a ``.ufpkg`` in memory. Never raises for bad input: problems are listed in the report."""
    out = _Read()
    kind = "unknown"
    manifest_summary: Dict[str, Any] = {}
    replay = "differs (engine or runtime changed)"
    try:
        _read_members(data, out)
        if not out.errors:
            sums = _check_integrity(out)
            manifest = _load_json(MANIFEST_NAME, out, MAX_MANIFEST_BYTES)
            if isinstance(manifest, dict):
                kind = str(manifest.get("kind") or DEFAULT_PACKAGE_KIND)[:64]
                structural_ok, problem = validate_manifest_structure(manifest)
                if not structural_ok:
                    out.error(f"manifest: {problem}")
                else:
                    _check_sidecars(manifest, out)
                    if is_known_package_kind(manifest.get("kind")):
                        try:
                            validate_manifest_semantic(manifest)
                        except ValueError:
                            out.error(
                                "manifest does not satisfy the experiment manifest schema"
                            )
                        else:
                            _check_robustness_documents(manifest, sums, out)
                    else:
                        out.warnings.append(
                            f"package kind {_display(kind)} is not recognised: only its structure and "
                            "checksums were verified, not its contents"
                        )
                manifest_summary = _summary(manifest, out)
                if manifest.get("format") == MANIFEST_FORMAT and is_known_package_kind(
                    manifest.get("kind")
                ):
                    replay = _replay_class(manifest, out)
                else:
                    out.warnings.append("replay evaluation was skipped")
            elif manifest is not None:
                out.error("manifest.json must be a JSON object")
    except Exception:  # noqa: BLE001 - verification must report, never crash
        logger.exception("package inspection failed")
        out.error("the package could not be inspected")
    return PackageVerificationReport(
        kind=kind,
        replayClass=replay,  # type: ignore[arg-type]
        internallyConsistent=not out.errors,
        integrityNote=NORMATIVE_INTEGRITY_STATEMENT,
        manifestSummary=manifest_summary,
        errors=out.errors,
        warnings=out.warnings,
    )


# ---------------------------------------------------------------------------------------------------
# Extraction (for an importer that needs files on disk; the API itself never extracts)
# ---------------------------------------------------------------------------------------------------
def extract_package(data: bytes, destination: Path) -> List[Path]:
    """Write a *verified* package's members under ``destination`` and return the paths written.

    The package is verified first and refused unless it is internally consistent. Independently of that,
    every target is resolved and must stay inside the extraction root (no symlink or traversal can
    escape it), and files are created exclusively, so nothing existing is overwritten."""
    report = inspect_package(data)
    if not report.internallyConsistent:
        raise PackageError("the package failed verification and was not extracted")
    out = _Read()
    _read_members(data, out)
    if out.errors:  # pragma: no cover - verification just passed
        raise PackageError("the package failed verification and was not extracted")
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for name in sorted(out.members):
        target = _resolve_inside(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Created directories could be links: re-resolve after creating them.
        _resolve_inside(root, name)
        with open(target, "xb") as handle:
            handle.write(out.members[name])
        written.append(target)
    return written


def _resolve_inside(root: Path, member: str) -> Path:
    """The path of ``member`` under ``root``, resolved (links followed); it must stay inside ``root``."""
    relative = PurePosixPath(member)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise PackageError("a member path escapes the extraction root")
    target = (root / Path(*relative.parts)).resolve()
    if root not in target.parents:
        raise PackageError("a member path escapes the extraction root")
    return target
