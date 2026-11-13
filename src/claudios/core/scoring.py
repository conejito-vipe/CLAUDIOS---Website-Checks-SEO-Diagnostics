from __future__ import annotations

import math
from collections import defaultdict

from .findings import Finding, Severity
from .registry import REGISTRY

PENALTY = {Severity.INFO: 0, Severity.NOTE: 1, Severity.WARNING: 3, Severity.ERROR: 7, Severity.CRITICAL: 15}
CHECK_CAP = 20


def compute_scores(findings: list[Finding], executed: dict[str, str]) -> dict:
    """Je Prüfung: Strafpunkte nach schwerstem Befund (+ log2 der Anzahl, max. 5), gedeckelt auf 20.
    Je Kategorie: 100 minus Summe. Gesamt: Mittelwert der Kategorien. Orientierungswert, kein Gütesiegel.
    Nicht ausgeführte Prüfungen zählen nicht (weder als bestanden noch als durchgefallen)."""
    by_check: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_check[f.check_id].append(f)
    cats: dict[str, int] = defaultdict(int)
    ran_cats: set[str] = set()
    for cid, status in executed.items():
        if status != "ran" or cid not in REGISTRY:
            continue
        cat = REGISTRY[cid].meta.category
        ran_cats.add(cat)
        fs = by_check.get(cid, [])
        if fs:
            worst = max(f.severity for f in fs)
            extra = min(5.0, math.log2(len(fs))) if len(fs) > 1 and PENALTY[worst] > 0 else 0.0
            cats[cat] += min(CHECK_CAP, round(PENALTY[worst] + extra))
    scores = {c: max(0, 100 - cats[c]) for c in sorted(ran_cats)}
    overall = round(sum(scores.values()) / len(scores)) if scores else 0
    return {"overall": overall, "categories": scores}
