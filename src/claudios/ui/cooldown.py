"""Restzeit der Abkühlzeit für die Anzeige. Rechnet wie core/quota.py: ab dem Beginn des letzten Scans. Liest das
Scan-Protokoll nur lesend und ohne Prüfung der Kette (die Prüfung macht der Scan selbst)."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from ..core.limits import LIMITS


def last_scan_start(path: Path) -> float | None:
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return None
    last = None
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("event") == "scan_start" and isinstance(rec.get("t"), (int, float)):
            last = rec["t"] if last is None else max(last, rec["t"])
    return last


def remaining(path: Path, now: float | None = None) -> int:
    """Sekunden bis zum nächsten möglichen Scan (0, wenn er jetzt möglich ist)."""
    last = last_scan_start(path)
    if last is None:
        return 0
    now = time.time() if now is None else now
    return max(0, math.ceil(last + LIMITS.cooldown_seconds - now))
