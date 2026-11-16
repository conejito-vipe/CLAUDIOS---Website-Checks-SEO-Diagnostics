from __future__ import annotations

import re

from ..core.findings import Finding, Severity
from ..core.numfmt import format_number

S = Severity

# Ganze Zahlen ab 4 Stellen im Fließtext; nicht in Namen, Adressen, Versionen oder mit führender Null.
_BIG = re.compile(r"(?<![\w.,/:=#-])(?!0)\d{4,}(?![\w-]|[.,]\w)")


class CheckSkipped(Exception):
    """Eine Prüfung konnte nicht ausgeführt werden (z. B. fehlende Daten): zählt nie als bestanden."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def group_digits(text: str, lang: str) -> str:
    """Zahlen in Befundtexten nach Sprache formatieren (DE 1.000, EN 1,000)."""
    return _BIG.sub(lambda m: format_number(int(m.group(0)), lang), text)


def F(cid: str, sev: Severity, url: str, de: str, en: str, evidence: str = "") -> Finding:
    return Finding(cid, sev, url, group_digits(de, "de"), group_digits(en, "en"), evidence)