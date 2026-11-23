"""Kurztext für die Seitenleiste während eines Scans: nur welcher Schritt oder welche Prüfung läuft und die Nummern,
ohne Adressen (die stehen auf der Scan-Seite)."""
from __future__ import annotations

import re

_URL = re.compile(r"https?://\S*")
_TAIL = re.compile(r"[\s\-–—:·|(\[]+$")


def short_activity(message: str, limit: int = 80) -> str:
    first = _URL.sub("", message.split("\n")[0])
    first = " ".join(first.split())
    return _TAIL.sub("", first)[:limit]
