"""Fortschritt für Downloads ohne eigene Fortschrittsmeldung (Playwright lädt Browser still).

Der Beobachter misst, wie stark Ordner (Zielordner und temporärer Ordner) seit dem Start gewachsen sind, und meldet daraus
einen Näherungswert. Die Gesamtgröße ist nur geschätzt: Der Wert nähert sich 100 % nie ganz an, steht still, wenn nichts
wächst, und ist keine echte Prozentzahl."""
from __future__ import annotations

import contextlib
import math
import os
import threading
from collections.abc import Callable, Iterable
from pathlib import Path


def folder_bytes(path: Path) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                pass
    return total


def progress_fraction(grown: int, expected: int) -> float:
    """0 bei 0 Byte, wächst gleichmäßig weiter, bleibt unter 0,99."""
    if grown <= 0 or expected <= 0:
        return 0.0
    return min(0.99, 1.0 - math.exp(-grown / expected))


class SizeWatcher:
    def __init__(self, folders: Iterable[Path], expected: int, report: Callable[[int, int], None], *,
                 base: int = 50, span: int = 45, total: int = 100, interval: float = 1.0) -> None:
        self._folders = [Path(f) for f in folders]
        self._expected, self._report = expected, report
        self._base, self._span, self._total, self._interval = base, span, total, interval
        self._start = 0
        self._last = -1
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _size(self) -> int:
        return sum(folder_bytes(folder) for folder in self._folders)

    def tick(self) -> int:
        grown = max(0, self._size() - self._start)
        pct = self._base + int(self._span * progress_fraction(grown, self._expected))
        if pct != self._last:
            self._last = pct
            with contextlib.suppress(Exception):
                self._report(pct, self._total)
        return pct

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self.tick()

    def __enter__(self) -> SizeWatcher:
        self._start = self._size()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(5)
