"""Einrichtung fehlender Komponenten beim Start (im Splash). Mehrere Komponenten laufen gleichzeitig, Abhängigkeiten
(depends) werden eingehalten: hängt ein Download, laufen die anderen weiter. Scheitert eine Komponente, scheitern nur ihre
Abhängigen. Die Planung (run_schedule) kennt keine Oberfläche und ist einzeln testbar."""
from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from ..components import manager
from ..components.lock import load_lock
from ..core.errors import ClaudiosError, ErrorCode as E

OPTIONAL = frozenset({"pw-browsers"})  # groß und nur für das Profil Tief nötig: nie automatisch


def pending_components(lock=None, status=None) -> list:
    """Komponenten, die fehlen oder veraltet sind (ohne die optionalen). Bei jedem Fehler: nichts tun."""
    try:
        comps = load_lock() if lock is None else lock
        get = status or manager.status
        return [c for c in comps if c.name not in OPTIONAL and get(c) in ("missing", "outdated")]
    except Exception:  # noqa: BLE001 – der Start darf daran nicht scheitern
        return []


def run_schedule(comps, install: Callable, *, workers: int = 3, cancel: threading.Event | None = None,
                 on_finish: Callable[[str, Exception | None], None] | None = None) -> dict:
    """Installiert comps mit höchstens `workers` gleichzeitigen Läufen. Ergebnis je Name: None oder die Ausnahme.
    Komponenten, die wegen Abbruch nie starteten, fehlen im Ergebnis."""
    cancel = cancel or threading.Event()
    cond = threading.Condition()
    waiting = {c.name: c for c in comps}
    running: set[str] = set()
    results: dict[str, Exception | None] = {}

    def settle(name: str, outcome: Exception | None) -> None:  # nur unter dem Lock
        results[name] = outcome
        if on_finish is not None:
            on_finish(name, outcome)
        cond.notify_all()

    def blocker(comp) -> tuple[str, str]:
        for dep in comp.depends:
            if dep in results:
                if results[dep] is not None:
                    return "failed", dep
            elif dep in waiting or dep in running:
                return "wait", dep
        return "ready", ""

    def worker() -> None:
        while True:
            with cond:
                job = None
                while job is None:
                    if cancel.is_set():
                        return
                    for name, comp in list(waiting.items()):
                        kind, dep = blocker(comp)
                        if kind == "failed":
                            del waiting[name]
                            settle(name, ClaudiosError(E.COMPONENT_MISSING, reason=dep))
                        elif kind == "ready" and job is None:
                            del waiting[name]
                            running.add(name)
                            job = comp
                    if job is not None:
                        break
                    if not waiting:
                        return
                    if not running:  # nichts startbar und nichts läuft: Abhängigkeitskreis, alles scheitert
                        for name in list(waiting):
                            del waiting[name]
                            settle(name, ClaudiosError(E.COMPONENT_MISSING, reason="dependency cycle"))
                        return
                    cond.wait(0.5)
            try:
                install(job)
                outcome: Exception | None = None
            except Exception as exc:  # noqa: BLE001 – jeder Fehler wird dem Nutzer mit Grund gezeigt
                outcome = exc
            with cond:
                running.discard(job.name)
                settle(job.name, outcome)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, min(workers, len(waiting))))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


class BootState:
    """Fortschritt für die Anzeige: fertige Komponenten und Prozent der laufenden."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.finished = 0
        self._pct: dict[str, int] = {}
        self._done: set[str] = set()

    def update(self, name: str, done: int, total: int) -> None:
        if name in self._done:
            return
        self._pct[name] = max(0, min(100, int(done / total * 100))) if total else 0

    def finish(self, name: str) -> None:
        if name in self._done:
            return
        self._done.add(name)
        self._pct.pop(name, None)
        self.finished += 1

    def percent(self) -> int:
        if not self.total:
            return 100
        return min(100, int((self.finished + sum(self._pct.values()) / 100) / self.total * 100))

    def active_text(self, titles: dict[str, str], limit: int = 3) -> str:
        items = [f"{titles.get(name, name)} {pct} %" for name, pct in list(self._pct.items())[:limit]]
        return ", ".join(items) or "…"


class BootInstaller(QThread):
    progress = Signal(str, str, int, int)
    one_done = Signal(str, object)
    done = Signal(object)

    def __init__(self, comps: list, workers: int = 3) -> None:
        super().__init__()
        self._comps = list(comps)
        self._workers = workers
        self._stop = threading.Event()

    def run(self) -> None:
        def install(comp) -> None:
            manager.install(comp, progress=lambda name, phase, d, total: self.progress.emit(name, phase, d, total),
                            cancel=self._stop)

        results = run_schedule(self._comps, install, workers=self._workers, cancel=self._stop,
                               on_finish=lambda name, exc: self.one_done.emit(name, exc))
        self.done.emit([(c.name, results[c.name]) for c in self._comps if c.name in results])

    def cancel(self) -> None:
        self._stop.set()
