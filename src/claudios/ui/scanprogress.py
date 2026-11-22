"""Fortschritt und Restzeit-Schätzung der Scan-Anzeige (ohne Oberfläche, einzeln testbar).

Anteile am Balken: Seiten laden 0–40 %, Zusatzprüfungen 40–50 %, externe Links 50–60 %, Prüfungen 60–100 %. Das Seitenlimit
(250) ist nur eine Obergrenze: der Crawl-Anteil ist bei 60 Seiten voll, damit der Balken bei kleinen Websites nicht stehen
bleibt. Die Restzeit wird je Abschnitt aus den bisher fertigen Schritten hochgerechnet (grobe Schätzung, die Schritte sind
unterschiedlich lang) und erst nach den ersten Schritten gezeigt. Im Crawl gibt es keine Schätzung."""
from __future__ import annotations

import time
from collections.abc import Callable


def overall_percent(kind: str, cur: int, total: int) -> int:
    total = max(total, 1)
    done = max(0, min(cur, total))
    if kind == "crawl":
        value = 40 * min(1.0, cur / min(total, 60))
    elif kind == "probe":
        value = 40 + 10 * done / total
    elif kind == "link":
        value = 50 + 10 * done / total
    elif kind == "check":
        value = 60 + 40 * done / total
    else:
        value = 100 * done / total
    return max(0, min(100, int(value)))


def format_duration(seconds: float, lang: str = "de") -> str:
    whole = max(0, int(round(seconds)))
    minutes, rest = divmod(whole, 60)
    return f"{minutes} min {rest} s" if minutes else f"{rest} s"


class PhaseClock:
    MIN_DONE = 2
    MIN_SECONDS = 3.0

    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._kind: str | None = None
        self._t0 = 0.0

    def update(self, kind: str, cur: int, total: int) -> float | None:
        """Geschätzte Restsekunden des aktuellen Abschnitts oder None, solange es zu früh ist."""
        moment = self._now()
        if kind != self._kind:
            self._kind, self._t0 = kind, moment
        if kind == "crawl":
            return None
        done = max(0, cur - 1)  # gemeldet wird vor dem Schritt
        elapsed = moment - self._t0
        if done < self.MIN_DONE or elapsed < self.MIN_SECONDS:
            return None
        return elapsed / done * max(0, total - done)
