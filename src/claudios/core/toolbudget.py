"""Gesamtbudget und Mindestpause für Werkzeug-Läufe, die das Ziel belasten (Browser, ZAP, sslyze). Sie laufen alle über
toolrunner.run_tool. Nur während eines Scans aktiv (engine.run_scan öffnet scan_budget), sonst passiert nichts.
Erkannt werden sie am Aufruf: browser_probe.js, shot_probe.js, zap_probe.js oder "-m sslyze". Andere Werkzeuge (Linter,
Installation) zählen nicht. Ein abgelehnter Lauf wirft TOOL_FAILED; die Prüfung gilt dann als nicht ausgeführt, nie als
bestanden. Grenze: Die Laufzeit des ZAP-Daemons selbst zählt nicht mit, nur das Browser-Skript durch ZAP."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass

from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

_SCRIPTS = {"browser_probe.js": "browser", "shot_probe.js": "browser", "zap_probe.js": "zap"}
_STATE: dict[str, ScanBudget | None] = {"budget": None}


def classify(args: Iterable[object]) -> str | None:
    """'browser', 'zap', 'sslyze' oder None (zählt nicht)."""
    items = [str(a) for a in args]
    for item in items:
        kind = _SCRIPTS.get(item.replace("\\", "/").rsplit("/", 1)[-1])
        if kind:
            return kind
    for first, second in zip(items, items[1:], strict=False):
        if first == "-m" and second == "sslyze":
            return "sslyze"
    return None


@dataclass
class Slot:
    budget: ScanBudget
    kind: str
    started: float
    max_seconds: float

    def cap(self, seconds: float) -> float:
        """Das Zeitlimit des Laufs, gekürzt auf die Restzeit des Budgets."""
        return min(seconds, self.max_seconds)


class ScanBudget:
    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._clock, self._sleep = clock, sleep
        self._lock = threading.Lock()
        self.used = 0.0
        self.runs: dict[str, int] = {}
        self._last_end: float | None = None

    def remaining(self) -> float:
        return max(0.0, LIMITS.tool_total_seconds - self.used)

    def begin(self, kind: str) -> Slot:
        with self._lock:
            if self.runs.get(kind, 0) >= LIMITS.tool_runs_per_kind:
                raise ClaudiosError(E.TOOL_FAILED, reason=f"{kind}: too many runs in one scan")
            if self.remaining() < LIMITS.tool_min_run_seconds:
                raise ClaudiosError(E.TOOL_FAILED, reason="budget: tool time of this scan used up")
            self.runs[kind] = self.runs.get(kind, 0) + 1
            last = self._last_end
        if last is not None:
            wait = last + LIMITS.tool_min_pause_seconds - self._clock()
            if wait > 0:
                self._sleep(min(wait, LIMITS.tool_min_pause_seconds))
        return Slot(self, kind, self._clock(), self.remaining())

    def end(self, slot: Slot) -> None:
        now = self._clock()
        with self._lock:
            self.used += max(0.0, now - slot.started)
            self._last_end = now


@contextmanager
def scan_budget(budget: ScanBudget | None = None):
    previous = _STATE["budget"]
    active = budget if budget is not None else ScanBudget()
    _STATE["budget"] = active
    try:
        yield active
    finally:
        _STATE["budget"] = previous


def current() -> ScanBudget | None:
    return _STATE["budget"]


def acquire(args: Iterable[object]) -> Slot | None:
    """Platz im Budget für diesen Lauf (kann warten oder TOOL_FAILED werfen). None: nicht erfasst."""
    budget = _STATE["budget"]
    if budget is None:
        return None
    kind = classify(args)
    return budget.begin(kind) if kind else None


def release(slot: Slot | None) -> None:
    if slot is not None:
        slot.budget.end(slot)
