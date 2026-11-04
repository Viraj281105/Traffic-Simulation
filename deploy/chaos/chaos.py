#!/usr/bin/env python3
"""Chaos helpers for the UrbanFlow stack (package 1D, F15). Standard library only.

SAFE BY DEFAULT: every subcommand that would change something prints the plan and
exits unless ``--execute`` is given. Run it only against a stack you own.

  python deploy/chaos/chaos.py kill-backend            # dry run: prints the docker commands
  python deploy/chaos/chaos.py kill-backend --execute --down-seconds 20
  python deploy/chaos/chaos.py latency-proxy --listen 9000 --target 127.0.0.1:8000 \
        --delay-ms 400 --jitter-ms 100 --seconds 60 --execute
  python deploy/chaos/chaos.py probe --url http://127.0.0.1:8000/health --seconds 60

``kill-backend`` kills the compose service (``docker compose kill``), keeps it down for
``--down-seconds`` while a probe records failures, restarts it, and reports how long it took
for ``/health`` to answer again. ``latency-proxy`` is a TCP proxy that delays every chunk it
forwards: point a client (k6 ``BASE_URL``) at the proxy to simulate a slow network.
``probe`` just measures availability and can run alongside either.

WRITTEN, not verified against a live Docker stack in the dev environment; the planning and
probe logic is covered by backend/tests/observability/test_chaos_script.py.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Callable, List, Optional, Sequence, Tuple

DEFAULT_HEALTH = "http://127.0.0.1:8000/health"


def compose_cmd(compose_files: Sequence[str], *args: str) -> List[str]:
    cmd = ["docker", "compose"]
    for f in compose_files:
        cmd += ["-f", f]
    return cmd + list(args)


def plan_kill_backend(
    compose_files: Sequence[str], service: str, down_seconds: float
) -> List[str]:
    """Human-readable steps of the kill/restart experiment."""
    return [
        "probe " + DEFAULT_HEALTH + " in the background (records failures)",
        shlex.join(compose_cmd(compose_files, "kill", service)),
        f"wait {down_seconds:g} s with the service down",
        shlex.join(compose_cmd(compose_files, "start", service)),
        "poll /health until it answers 200 again; report time to recovery",
    ]


def probe_once(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return bool(resp.status == 200)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def probe(
    url: str,
    seconds: float,
    interval: float = 0.5,
    check: Callable[[str], bool] = probe_once,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Tuple[int, int]:
    """Probe ``url`` for ``seconds``. Returns (successes, failures)."""
    ok = bad = 0
    end = clock() + seconds
    while clock() < end:
        if check(url):
            ok += 1
        else:
            bad += 1
        sleep(interval)
    return ok, bad


def wait_healthy(
    url: str,
    timeout: float,
    check: Callable[[str], bool] = probe_once,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Optional[float]:
    """Seconds until ``url`` is healthy, or None if it never is within ``timeout``."""
    start = clock()
    while clock() - start < timeout:
        if check(url):
            return clock() - start
        sleep(0.5)
    return None


def cmd_kill_backend(args: argparse.Namespace) -> int:
    steps = plan_kill_backend(args.compose_file, args.service, args.down_seconds)
    if not args.execute:
        print("DRY RUN (add --execute to run). Plan:")
        for i, s in enumerate(steps, 1):
            print(f"  {i}. {s}")
        return 0
    subprocess.run(compose_cmd(args.compose_file, "kill", args.service), check=True)
    t0 = time.monotonic()
    time.sleep(args.down_seconds)
    subprocess.run(compose_cmd(args.compose_file, "start", args.service), check=True)
    recovered = wait_healthy(args.url, args.recovery_timeout)
    down_for = time.monotonic() - t0
    if recovered is None:
        print(f"FAIL: {args.url} not healthy {args.recovery_timeout:g} s after restart")
        return 1
    print(f"down {down_for - recovered:.1f} s, healthy again {recovered:.1f} s after restart")
    return 0


async def _pipe(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    delay_ms: float,
    jitter_ms: float,
) -> None:
    try:
        while data := await reader.read(65536):
            wait = max(0.0, delay_ms + random.uniform(-jitter_ms, jitter_ms)) / 1000
            await asyncio.sleep(wait)
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def latency_proxy(
    listen_port: int,
    target_host: str,
    target_port: int,
    delay_ms: float,
    jitter_ms: float,
    seconds: float,
) -> None:
    async def handle(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
        try:
            tr, tw = await asyncio.open_connection(target_host, target_port)
        except OSError:
            w.close()
            return
        await asyncio.gather(
            _pipe(r, tw, delay_ms, jitter_ms), _pipe(tr, w, delay_ms, jitter_ms)
        )

    server = await asyncio.start_server(handle, "127.0.0.1", listen_port)
    try:
        await asyncio.sleep(seconds)
    finally:
        server.close()
        await server.wait_closed()


def cmd_latency_proxy(args: argparse.Namespace) -> int:
    host, _, port = args.target.rpartition(":")
    plan = (
        f"TCP proxy 127.0.0.1:{args.listen} -> {args.target}, +{args.delay_ms:g} ms "
        f"(+/-{args.jitter_ms:g}) per chunk, for {args.seconds:g} s"
    )
    if not args.execute:
        print("DRY RUN (add --execute to run). Plan: " + plan)
        return 0
    print(plan)
    asyncio.run(
        latency_proxy(
            args.listen,
            host or "127.0.0.1",
            int(port),
            args.delay_ms,
            args.jitter_ms,
            args.seconds,
        )
    )
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    ok, bad = probe(args.url, args.seconds, args.interval)
    total = ok + bad
    print(f"{ok}/{total} probes healthy ({(ok / total if total else 0):.1%})")
    return 0 if bad == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("kill-backend", help="kill and restart the backend container")
    k.add_argument("--compose-file", action="append", default=None)
    k.add_argument("--service", default="backend")
    k.add_argument("--down-seconds", type=float, default=15.0)
    k.add_argument("--recovery-timeout", type=float, default=120.0)
    k.add_argument("--url", default=DEFAULT_HEALTH)
    k.add_argument("--execute", action="store_true")
    k.set_defaults(func=cmd_kill_backend)

    lp = sub.add_parser("latency-proxy", help="TCP proxy that adds latency")
    lp.add_argument("--listen", type=int, default=9000)
    lp.add_argument("--target", default="127.0.0.1:8000")
    lp.add_argument("--delay-ms", type=float, default=300.0)
    lp.add_argument("--jitter-ms", type=float, default=50.0)
    lp.add_argument("--seconds", type=float, default=60.0)
    lp.add_argument("--execute", action="store_true")
    lp.set_defaults(func=cmd_latency_proxy)

    pr = sub.add_parser("probe", help="measure /health availability")
    pr.add_argument("--url", default=DEFAULT_HEALTH)
    pr.add_argument("--seconds", type=float, default=30.0)
    pr.add_argument("--interval", type=float, default=0.5)
    pr.set_defaults(func=cmd_probe)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "compose_file", 0) is None:
        args.compose_file = ["docker-compose.yml"]
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
