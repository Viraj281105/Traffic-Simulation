"""The chaos script's planning and probing logic (package 1D). Nothing is executed."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import List

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "deploy" / "chaos" / "chaos.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("chaos_script", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


chaos = _load()


def test_kill_is_dry_run_by_default(capsys: pytest.CaptureFixture[str]) -> None:
    assert chaos.main(["kill-backend"]) == 0
    out = capsys.readouterr().out
    assert (
        "DRY RUN" in out and "docker compose -f docker-compose.yml kill backend" in out
    )


def test_latency_proxy_is_dry_run_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert chaos.main(["latency-proxy", "--delay-ms", "250"]) == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_probe_counts_with_fake_clock() -> None:
    now = [0.0]
    results: List[bool] = [True, True, False, True]

    def check(url: str) -> bool:
        return results.pop(0) if results else True

    def sleep(s: float) -> None:
        now[0] += s

    ok, bad = chaos.probe("u", 2.0, 0.5, check=check, sleep=sleep, clock=lambda: now[0])
    assert (ok, bad) == (3, 1)


def test_wait_healthy_reports_recovery_or_none() -> None:
    now = [0.0]
    calls = {"n": 0}

    def check(url: str) -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    def sleep(s: float) -> None:
        now[0] += s

    got = chaos.wait_healthy("u", 10, check=check, sleep=sleep, clock=lambda: now[0])
    assert got == pytest.approx(1.0)
    never = chaos.wait_healthy(
        "u", 2, check=lambda u: False, sleep=sleep, clock=lambda: now[0]
    )
    assert never is None


def test_plan_lists_kill_and_start() -> None:
    steps = chaos.plan_kill_backend(["a.yml", "b.yml"], "backend", 5)
    joined = "\n".join(steps)
    assert "-f a.yml -f b.yml kill backend" in joined and "start backend" in joined
