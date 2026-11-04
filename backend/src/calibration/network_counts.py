"""Count-file loader for network calibration (F11 / package 1B).

CSV columns (header required, any order, case-insensitive):

  link_id         graph link id the sensor measures        (required)
  interval_start  ISO-8601 timestamp or seconds (a number)  (required)
  count           vehicles counted in the interval          (required, >= 0)
  sensor_id       sensor identifier                         (optional)

Every problem is reported as a plain sentence with its line number. Nothing
here raises on bad input: :func:`load_counts_csv` returns the usable records
plus ``errors`` (block use) and ``warnings`` (do not).

Aggregation rule (:meth:`CountSet.link_flows_vph`): per (link, sensor) the
rate is ``sum(count) / (intervals present x interval length) x 3600``; a link
measured by several sensors takes the mean of its sensors' rates. Missing
intervals are not zero: the rate uses the intervals that are present.
"""

from __future__ import annotations

import csv
import hashlib
import io
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REQUIRED_COLUMNS = ("link_id", "interval_start", "count")
OPTIONAL_COLUMNS = ("sensor_id",)
DEFAULT_INTERVAL_SECONDS = 900.0
MAX_ROWS = 200_000


@dataclass(frozen=True)
class CountRecord:
    link_id: str
    start: float  # seconds (epoch seconds for ISO input)
    start_label: str  # as written in the file
    count: float
    sensor_id: str = ""


@dataclass
class CountSet:
    records: List[CountRecord]
    interval_seconds: float
    interval_inferred: bool = False
    source: str = "inline"
    sha256: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors and bool(self.records)

    def interval_starts(self) -> List[float]:
        return sorted({r.start for r in self.records})

    def link_ids(self) -> List[str]:
        return sorted({r.link_id for r in self.records})

    def sensors(self) -> List[str]:
        return sorted({r.sensor_id for r in self.records if r.sensor_id})

    def window(self, last_intervals: int) -> "CountSet":
        """The records of the last ``last_intervals`` distinct interval starts."""
        starts = self.interval_starts()[-max(1, last_intervals) :]
        keep = set(starts)
        return CountSet(
            records=[r for r in self.records if r.start in keep],
            interval_seconds=self.interval_seconds,
            interval_inferred=self.interval_inferred,
            source=self.source,
            sha256=self.sha256,
            errors=list(self.errors),
            warnings=list(self.warnings),
        )

    def link_flows_vph(self) -> Dict[str, float]:
        per_sensor: Dict[Tuple[str, str], List[float]] = {}
        for r in self.records:
            per_sensor.setdefault((r.link_id, r.sensor_id), []).append(r.count)
        rates: Dict[str, List[float]] = {}
        for (link, _sensor), counts in sorted(per_sensor.items()):
            hours = len(counts) * self.interval_seconds / 3600.0
            rates.setdefault(link, []).append(sum(counts) / hours)
        return {k: sum(v) / len(v) for k, v in sorted(rates.items())}

    def provenance(self) -> Dict[str, object]:
        starts = self.interval_starts()
        labels = {r.start: r.start_label for r in self.records}
        return {
            "source": self.source,
            "sha256": self.sha256,
            "rows": len(self.records),
            "links": len(self.link_ids()),
            "sensors": self.sensors(),
            "intervals": len(starts),
            "intervalSeconds": self.interval_seconds,
            "intervalSecondsInferred": self.interval_inferred,
            "firstIntervalStart": labels[starts[0]] if starts else None,
            "lastIntervalStart": labels[starts[-1]] if starts else None,
            "warnings": list(self.warnings),
        }


def _parse_start(text: str) -> Optional[float]:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _infer_interval(starts: Sequence[float]) -> Optional[float]:
    if len(starts) < 2:
        return None
    deltas = [b - a for a, b in zip(starts, starts[1:]) if b - a > 0]
    return statistics.median(deltas) if deltas else None


def load_counts_csv(
    text: str,
    *,
    interval_seconds: Optional[float] = None,
    known_links: Optional[Iterable[str]] = None,
    source: str = "inline",
) -> CountSet:
    """Parse and validate a count CSV. ``interval_seconds`` is the length of
    one interval; when omitted it is the median gap between interval starts
    (900 s with a warning if there is only one interval).
    ``known_links`` (graph link ids) makes unknown links a warning and drops
    them; an empty result is then an error."""
    errors: List[str] = []
    warnings: List[str] = []
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    result = CountSet(
        [], interval_seconds or DEFAULT_INTERVAL_SECONDS, False, source, digest
    )

    if not text.strip():
        result.errors = ["The count file is empty"]
        return result
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = [h.strip().lower() for h in next(reader)]
    except StopIteration:
        result.errors = ["The count file is empty"]
        return result
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        result.errors = [
            "The count file header is missing column(s) "
            + ", ".join(missing)
            + f". Expected: {', '.join(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)} "
            f"(optional: {', '.join(OPTIONAL_COLUMNS)}); found: {', '.join(header)}"
        ]
        return result
    idx = {c: header.index(c) for c in header}
    unknown_cols = [c for c in header if c not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    if unknown_cols:
        warnings.append("Ignored unknown column(s): " + ", ".join(unknown_cols))

    known: Optional[Set[str]] = set(known_links) if known_links is not None else None
    records: List[CountRecord] = []
    seen: Set[Tuple[str, str, float]] = set()
    unknown_links: Dict[str, int] = {}
    max_errors = 20
    for line_no, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(records) + len(errors) >= MAX_ROWS:
            errors.append(f"The count file has more than {MAX_ROWS} rows; split it")
            break
        if len(row) < len(header):
            errors.append(
                f"Line {line_no}: expected {len(header)} fields, found {len(row)}"
            )
            continue
        link = row[idx["link_id"]].strip()
        label = row[idx["interval_start"]].strip()
        raw_count = row[idx["count"]].strip()
        sensor = row[idx["sensor_id"]].strip() if "sensor_id" in idx else ""
        problems = []
        if not link:
            problems.append("link_id is empty")
        start = _parse_start(label)
        if start is None:
            problems.append(
                f"interval_start {label!r} is not an ISO-8601 time or a number of seconds"
            )
        try:
            count = float(raw_count)
            if count != count or count in (float("inf"), float("-inf")):
                raise ValueError
            if count < 0:
                problems.append(f"count {raw_count} is negative")
        except ValueError:
            count = 0.0
            problems.append(f"count {raw_count!r} is not a number")
        if problems:
            errors.append(f"Line {line_no}: " + "; ".join(problems))
            continue
        assert start is not None
        if known is not None and link not in known:
            unknown_links[link] = unknown_links.get(link, 0) + 1
            continue
        key = (link, sensor, start)
        if key in seen:
            errors.append(
                f"Line {line_no}: duplicate reading for link {link!r}"
                + (f", sensor {sensor!r}" if sensor else "")
                + f" at {label}"
            )
            continue
        seen.add(key)
        records.append(CountRecord(link, start, label, count, sensor))
    if len(errors) > max_errors:
        extra = len(errors) - max_errors
        errors = errors[:max_errors] + [f"... and {extra} more problem(s)"]
    if unknown_links:
        listed = ", ".join(
            f"{k!r} ({n} rows)" for k, n in sorted(unknown_links.items())[:10]
        )
        warnings.append(
            f"Ignored {sum(unknown_links.values())} row(s) for {len(unknown_links)} link id(s) "
            f"not in the network: {listed}"
        )
    if not records and not errors:
        errors.append(
            "No usable count rows"
            + (" (no link id in the file matches the network)" if unknown_links else "")
        )

    starts = sorted({r.start for r in records})
    inferred = False
    if interval_seconds is None:
        guess = _infer_interval(starts)
        if guess is None:
            warnings.append(
                f"Only one interval in the file; assuming {DEFAULT_INTERVAL_SECONDS:g} s "
                "per interval. Pass the interval length to override"
            )
            interval_seconds = DEFAULT_INTERVAL_SECONDS
        else:
            interval_seconds, inferred = guess, True
    elif interval_seconds <= 0:
        errors.append("The interval length must be positive")
        interval_seconds = DEFAULT_INTERVAL_SECONDS
    if inferred and starts:
        gaps = sum(
            1 for a, b in zip(starts, starts[1:]) if b - a > interval_seconds * 1.5
        )
        if gaps:
            warnings.append(
                f"{gaps} gap(s) in the interval starts are longer than 1.5 x {interval_seconds:g} s; "
                "missing intervals are skipped, not counted as zero"
            )
    if records:
        short = [
            lid
            for lid in sorted({r.link_id for r in records})
            if sum(1 for r in records if r.link_id == lid) < 2
        ]
        if len(starts) > 1 and short:
            warnings.append(
                f"{len(short)} link(s) have a single reading and are weak evidence: "
                + ", ".join(short[:5])
            )
    result.records = records
    result.interval_seconds = float(interval_seconds)
    result.interval_inferred = inferred
    result.errors = errors
    result.warnings = warnings
    return result


def load_counts_file(path: str, **kwargs: Any) -> CountSet:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return load_counts_csv(fh.read(), source=kwargs.pop("source", path), **kwargs)


def counts_to_csv(records: Iterable[CountRecord]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["link_id", "interval_start", "count", "sensor_id"])
    for r in sorted(records, key=lambda r: (r.start, r.link_id, r.sensor_id)):
        count = int(r.count) if float(r.count).is_integer() else r.count
        writer.writerow([r.link_id, r.start_label, count, r.sensor_id])
    return out.getvalue()
