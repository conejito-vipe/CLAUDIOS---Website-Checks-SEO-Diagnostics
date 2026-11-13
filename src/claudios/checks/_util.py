from __future__ import annotations

from ..core.findings import Finding, Severity

S = Severity


class CheckSkipped(Exception):
    """Eine Prüfung konnte nicht ausgeführt werden (z. B. fehlende Daten): zählt nie als bestanden."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def F(cid: str, sev: Severity, url: str, de: str, en: str, evidence: str = "") -> Finding:
    return Finding(cid, sev, url, de, en, evidence)
