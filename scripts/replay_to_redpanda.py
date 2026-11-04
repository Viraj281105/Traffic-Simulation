#!/usr/bin/env python3
"""Replay a recorded observations CSV into Redpanda/Kafka as JSON messages (package 1D, #14).

The CSV is the network-calibration counts format (backend/src/calibration/network_counts.py):
required columns ``link_id``, ``interval_start``, ``count``; extra columns (e.g. ``sensor_id``)
are carried through. One message per row, keyed by ``link_id`` so one link stays ordered:

    {"link_id": "L1", "interval_start": "0", "count": 12.0, "sensor_id": "s1", "seq": 0}

Examples:
    python scripts/replay_to_redpanda.py counts.csv --dry-run
    python scripts/replay_to_redpanda.py counts.csv --bootstrap localhost:19092 --rate 50
    python scripts/replay_to_redpanda.py counts.csv --loop 3

``kafka-python`` (``pip install kafka-python``) or ``confluent-kafka`` is imported only when
publishing for real, so ``--dry-run`` needs no extra package. A dry run prints the JSON lines
and publishes nothing.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

REQUIRED = ("link_id", "interval_start", "count")
DEFAULT_TOPIC = "urbanflow.observations"


def read_rows(path: Path) -> Iterator[Dict[str, Any]]:
    """Yield one record per CSV row (header required, case-insensitive)."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        names = [(n or "").strip().lower() for n in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED if c not in names]
        if missing:
            raise SystemExit(f"{path}: missing required column(s): {', '.join(missing)}")
        for line_no, raw in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            try:
                count = float(row["count"])
            except ValueError:
                print(f"skip line {line_no}: bad count {row['count']!r}", file=sys.stderr)
                continue
            if not row["link_id"] or count < 0:
                print(f"skip line {line_no}: empty link_id or negative count", file=sys.stderr)
                continue
            out: Dict[str, Any] = {k: v for k, v in row.items() if k not in REQUIRED}
            out.update(link_id=row["link_id"], interval_start=row["interval_start"], count=count)
            yield out


def encode(record: Dict[str, Any], seq: int) -> bytes:
    return json.dumps({**record, "seq": seq}, sort_keys=True, separators=(",", ":")).encode()


def make_sender(
    bootstrap: str, topic: str
) -> Tuple[Callable[[str, bytes], None], Callable[[], None]]:
    """(send, close) for a real broker. Imports the client library lazily."""
    try:
        from kafka import KafkaProducer  # type: ignore[import-not-found]
    except ImportError:
        KafkaProducer = None  # noqa: N806
    if KafkaProducer is not None:
        producer = KafkaProducer(bootstrap_servers=bootstrap, acks="all", linger_ms=20)

        def send(key: str, value: bytes) -> None:
            producer.send(topic, key=key.encode(), value=value)

        def close() -> None:
            producer.flush()
            producer.close()

        return send, close
    try:
        from confluent_kafka import Producer  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit(
            "Publishing needs kafka-python or confluent-kafka: pip install kafka-python "
            "(or use --dry-run)"
        )
    cp = Producer({"bootstrap.servers": bootstrap, "acks": "all"})

    def csend(key: str, value: bytes) -> None:
        cp.produce(topic, key=key.encode(), value=value)
        cp.poll(0)

    return csend, lambda: cp.flush()


def replay(
    rows: Sequence[Dict[str, Any]],
    send: Callable[[str, bytes], None],
    rate: float = 0.0,
    loop: int = 1,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Send every row ``loop`` times, at most ``rate`` msgs/s (0 = unthrottled)."""
    seq = 0
    for _ in range(max(1, loop)):
        for rec in rows:
            send(rec["link_id"], encode(rec, seq))
            seq += 1
            if rate > 0:
                sleep(1.0 / rate)
    return seq


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("csv", type=Path)
    ap.add_argument("--bootstrap", default="localhost:19092")
    ap.add_argument("--topic", default=DEFAULT_TOPIC)
    ap.add_argument("--rate", type=float, default=0.0, help="messages per second (0 = unthrottled)")
    ap.add_argument("--loop", type=int, default=1, help="replay the file this many times")
    ap.add_argument("--dry-run", action="store_true", help="print the messages, publish nothing")
    args = ap.parse_args(argv)

    rows: List[Dict[str, Any]] = list(read_rows(args.csv))
    if not rows:
        print("no usable rows", file=sys.stderr)
        return 1
    if args.dry_run:
        n = replay(
            rows,
            lambda key, value: print(f"[dry-run] {args.topic} key={key} {value.decode()}"),
            loop=args.loop,
        )
        print(f"[dry-run] would publish {n} message(s) to {args.topic} on {args.bootstrap}")
        return 0
    send, close = make_sender(args.bootstrap, args.topic)
    try:
        n = replay(rows, send, args.rate, args.loop)
    finally:
        close()
    print(f"published {n} message(s) to {args.topic} on {args.bootstrap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
