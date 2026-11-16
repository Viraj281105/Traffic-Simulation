"""On-device safety interlock: a pure state machine (no I/O, no clock).

Rules (mirrored in ``hardware/signal-head/main.py``):
- heads N,S are group 0; E,W are group 1. Two heads of different groups are
  never both "go" (green, amber or red_amber).
- green -> red always passes through amber held for ``min_amber`` seconds.
- a head leaves red only when every conflicting head has been red for at least
  ``min_all_red`` seconds; grants are sequential, so two groups requesting at
  once cannot both win.
- fail-safe (heartbeat timeout, invalid/conflicting command, interlock trip)
  forces flashing red (or all red) at once and holds for ``failsafe_hold``
  seconds after a valid message arrives before normal operation resumes.
"""

from dataclasses import dataclass
from typing import Dict, List, Literal, Tuple

APPROACHES = ("N", "E", "S", "W")
GROUP = {"N": 0, "S": 0, "E": 1, "W": 1}
COMMAND_COLOURS = ("red", "amber", "green", "red_amber")
GO = ("green", "amber", "red_amber")
EPS = 1e-9
MAX_EVENTS = 1000

Heads = Dict[str, str]


@dataclass(frozen=True)
class InterlockConfig:
    min_amber: float = 3.0
    min_all_red: float = 1.0
    heartbeat_timeout: float = 2.0
    failsafe_hold: float = 2.0
    failsafe_mode: Literal["flashing_red", "all_red"] = "flashing_red"

    def __post_init__(self) -> None:
        for name in ("min_amber", "min_all_red", "heartbeat_timeout", "failsafe_hold"):
            v = getattr(self, name)
            if not 0.0 <= v <= 600.0:
                raise ValueError(f"{name} must lie in [0, 600]")
        if self.failsafe_mode not in ("flashing_red", "all_red"):
            raise ValueError("failsafe_mode must be flashing_red or all_red")


def conflicting_go(heads: Heads) -> bool:
    groups = {GROUP[h] for h, c in heads.items() if c in GO}
    return len(groups) > 1


class Interlock:
    def __init__(self, cfg: InterlockConfig, now: float = 0.0) -> None:
        self.cfg = cfg
        self.heads: Heads = {h: "red" for h in APPROACHES}
        self.desired: Heads = dict(self.heads)
        self._since: Dict[str, float] = {h: now for h in APPROACHES}
        self.failsafe = False
        self.reason = ""
        self._fs_since = now
        self._recover = False
        self.events: List[Tuple[float, str, str]] = []
        self.events_dropped = 0

    def _log(self, t: float, kind: str, detail: str) -> None:
        if len(self.events) >= MAX_EVENTS:
            self.events_dropped += 1
        else:
            self.events.append((t, kind, detail))

    def _set(self, h: str, colour: str, now: float) -> None:
        self.heads[h] = colour
        self._since[h] = now

    def set_desired(self, heads: Heads) -> None:
        self.desired = dict(heads)

    def request_recovery(self) -> None:
        self._recover = True

    def trip(self, now: float, reason: str) -> None:
        if self.failsafe:
            self._fs_since, self._recover = now, False
            return
        self.failsafe, self.reason = True, reason
        self._fs_since, self._recover = now, False
        colour = "flashing_red" if self.cfg.failsafe_mode == "flashing_red" else "red"
        for h in APPROACHES:
            self._set(h, colour, now)
        self._log(now, "failsafe", reason)

    def step(self, now: float) -> None:
        cfg = self.cfg
        if self.failsafe:
            if self._recover and now - self._fs_since >= cfg.failsafe_hold - EPS:
                self.failsafe, self.reason = False, ""
                for h in APPROACHES:
                    self._set(h, "red", now)
                self._log(now, "recovered", "")
            return
        for h in APPROACHES:
            c, d = self.heads[h], self.desired[h]
            if c == d:
                continue
            if d == "red":
                if c in ("green", "red_amber"):
                    self._set(h, "amber" if c == "green" else "red", now)
                elif c == "amber" and now - self._since[h] >= cfg.min_amber - EPS:
                    self._set(h, "red", now)
            elif c == "red":
                if d in ("green", "red_amber") and all(
                    self.heads[x] == "red"
                    and now - self._since[x] >= cfg.min_all_red - EPS
                    for x in APPROACHES
                    if GROUP[x] != GROUP[h]
                ):
                    self._set(h, d, now)
            elif d != "red_amber":  # go -> go within a group (amber <-> green)
                self._set(h, d, now)
        if conflicting_go(self.heads):  # defence in depth: must be unreachable
            self.trip(now, "conflict_detected")
