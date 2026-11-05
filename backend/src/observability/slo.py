"""Service level objectives as data, and an evaluator over sampled metrics.

The SLO definitions live in ``deploy/observability/slo.json`` (the same file
drives the Prometheus alert rules' thresholds, the Grafana dashboard and the
k6 thresholds - see docs/operations-observability.md). This module checks them
against a sample of metrics, taken from Prometheus text (``/metrics`` or
``/metrics/prom``): it is the offline/CI counterpart of the dashboards.

Two SLO kinds:

``latency_quantile``
    ``{"id", "kind", "histogram", "quantile", "objective_seconds",
    "match"?: {label: value|[values]}}`` - the quantile of a histogram
    (buckets summed over the matching series, linear interpolation like
    ``histogram_quantile``) must be ``<= objective_seconds``.

``ratio``
    ``{"id", "kind", "good": selector, "total": selector, "objective"}`` -
    ``good / total`` must be ``>= objective``. A selector is
    ``{"metric": name, "match"?: {label: value|[values]}}``; values are summed
    over every matching series.

No data (no samples, or a zero total) gives status ``no_data``, which is not a
violation: an idle service has not broken its objective.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

OK = "ok"
VIOLATED = "violated"
NO_DATA = "no_data"

DEFAULT_SLO_FILE = (
    Path(__file__).resolve().parents[3] / "deploy" / "observability" / "slo.json"
)

_SAMPLE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(?P<labels>.*)\})?\s+(?P<value>\S+)(?:\s+\d+)?\s*$"
)
_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')

Match = Mapping[str, Union[str, Sequence[str]]]


@dataclass(frozen=True)
class Sample:
    name: str
    labels: Dict[str, str]
    value: float


@dataclass
class SloResult:
    id: str
    status: str
    value: Optional[float]
    objective: float
    detail: str = ""
    description: str = field(default="")

    @property
    def violated(self) -> bool:
        return self.status == VIOLATED


def parse_prometheus_text(text: str) -> List[Sample]:
    """Parse the Prometheus text exposition format (comments are skipped)."""
    out: List[Sample] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE.match(line)
        if not m:
            continue
        raw = m.group("value")
        try:
            value = float(raw.replace("+Inf", "inf").replace("-Inf", "-inf"))
        except ValueError:
            continue
        labels = {
            k: v.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
            for k, v in _LABEL.findall(m.group("labels") or "")
        }
        out.append(Sample(m.group("name"), labels, value))
    return out


def load_slos(path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """Load and validate the SLO definitions (default: deploy/observability/slo.json)."""
    doc = json.loads(Path(path or DEFAULT_SLO_FILE).read_text(encoding="utf-8"))
    slos = doc.get("slos")
    if not isinstance(slos, list) or not slos:
        raise ValueError("SLO file needs a non-empty 'slos' list")
    seen: set[str] = set()
    for slo in slos:
        sid = slo.get("id")
        if not sid or sid in seen:
            raise ValueError(f"SLO id missing or duplicated: {sid!r}")
        seen.add(sid)
        kind = slo.get("kind")
        if kind == "latency_quantile":
            need = ("histogram", "quantile", "objective_seconds")
        elif kind == "ratio":
            need = ("good", "total", "objective")
        else:
            raise ValueError(f"SLO {sid}: unknown kind {kind!r}")
        for key in need:
            if key not in slo:
                raise ValueError(f"SLO {sid}: missing {key!r}")
    return list(slos)


def _matches(sample: Sample, match: Optional[Match]) -> bool:
    for key, want in (match or {}).items():
        have = sample.labels.get(key)
        if isinstance(want, str):
            if have != want:
                return False
        elif have not in want:
            return False
    return True


def _sum(samples: Iterable[Sample], selector: Mapping[str, Any]) -> Optional[float]:
    name = selector["metric"]
    values = [
        s.value
        for s in samples
        if s.name == name and _matches(s, selector.get("match"))
    ]
    return sum(values) if values else None


def histogram_quantile(
    samples: Iterable[Sample], histogram: str, q: float, match: Optional[Match] = None
) -> Optional[float]:
    """Quantile of ``histogram`` from its ``_bucket`` samples (None if empty)."""
    buckets: Dict[float, float] = {}
    for s in samples:
        if s.name != f"{histogram}_bucket" or not _matches(s, match):
            continue
        le = s.labels.get("le")
        if le is None:
            continue
        bound = math.inf if le in ("+Inf", "Inf") else float(le)
        buckets[bound] = buckets.get(bound, 0.0) + s.value
    if not buckets or buckets.get(math.inf, 0.0) <= 0:
        return None
    ordered = sorted(buckets.items())
    total = ordered[-1][1]
    rank = q * total
    prev_bound, prev_count = 0.0, 0.0
    for bound, count in ordered:
        if count >= rank:
            if math.isinf(bound):
                return prev_bound  # beyond the last finite bucket: its upper edge
            span = count - prev_count
            if span <= 0:
                return bound
            return prev_bound + (bound - prev_bound) * (rank - prev_count) / span
        prev_bound, prev_count = bound, count
    return prev_bound


def evaluate_slo(slo: Mapping[str, Any], samples: Sequence[Sample]) -> SloResult:
    sid = str(slo["id"])
    desc = str(slo.get("description", ""))
    if slo["kind"] == "latency_quantile":
        objective = float(slo["objective_seconds"])
        value = histogram_quantile(
            samples, slo["histogram"], float(slo["quantile"]), slo.get("match")
        )
        if value is None:
            return SloResult(sid, NO_DATA, None, objective, "no histogram data", desc)
        ok = value <= objective
        return SloResult(
            sid,
            OK if ok else VIOLATED,
            value,
            objective,
            f"p{int(float(slo['quantile']) * 100)}={value:.3f}s, limit {objective}s",
            desc,
        )
    objective = float(slo["objective"])
    good = _sum(samples, slo["good"])
    total = _sum(samples, slo["total"])
    if not total:
        return SloResult(sid, NO_DATA, None, objective, "no events", desc)
    ratio = (good or 0.0) / total
    return SloResult(
        sid,
        OK if ratio >= objective else VIOLATED,
        ratio,
        objective,
        f"{ratio:.4f} of {int(total)} events, need {objective}",
        desc,
    )


def evaluate_all(
    samples: Sequence[Sample], slos: Optional[Sequence[Mapping[str, Any]]] = None
) -> List[SloResult]:
    return [
        evaluate_slo(s, samples) for s in (slos if slos is not None else load_slos())
    ]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python -m src.observability.slo <metrics.txt|-|URL> [slo.json]``.

    Exit status 1 when any SLO is violated. Reads Prometheus text from a file,
    stdin (``-``) or an http(s) URL (``METRICS_TOKEN`` is sent as a bearer
    token when set)."""
    import os
    import sys
    import urllib.request

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(main.__doc__)
        return 2
    src = args[0]
    if src == "-":
        text = sys.stdin.read()
    elif src.startswith(("http://", "https://")):
        req = urllib.request.Request(src)
        token = os.getenv("METRICS_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            text = resp.read().decode("utf-8")
    else:
        text = Path(src).read_text(encoding="utf-8")
    results = evaluate_all(
        parse_prometheus_text(text), load_slos(args[1] if len(args) > 1 else None)
    )
    for r in results:
        print(f"{r.status.upper():9} {r.id}: {r.detail}")
    return 1 if any(r.violated for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
