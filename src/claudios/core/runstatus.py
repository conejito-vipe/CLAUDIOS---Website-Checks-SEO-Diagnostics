"""Wann ein Scan "mit Einschränkungen" heißt: nur, wenn eine Prüfung wegen eines Problems nicht lief.
Gewollte Gründe zählen nicht: die Stufe 2 (level2_required), fehlende Search-Console-Daten (no_gsc_data) und vom Nutzer
abgeschaltete Dienste (Gründe, die auf _disabled enden). Jeder andere Grund zählt, auch unbekannte: die Liste kann nur zu
streng sein, nie zu locker. Die Zeile "N Prüfungen nicht ausgeführt" in den Ergebnissen bleibt davon unberührt."""
from __future__ import annotations

EXPECTED = frozenset({"level2_required", "no_gsc_data"})


def limits_scan(state: str) -> bool:
    """True, wenn dieser Ausführungszustand den Scan als eingeschränkt gelten lässt."""
    if state == "ran":
        return False
    head, _sep, rest = state.partition(":")
    if head != "skipped":
        return True
    reason = rest.split(":", 1)[0]
    return not (reason in EXPECTED or reason.endswith("_disabled"))
