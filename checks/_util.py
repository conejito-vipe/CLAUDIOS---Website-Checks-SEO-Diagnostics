from __future__ import annotations

from ..core.findings import Finding, Severity

S = Severity


def F(cid: str, sev: Severity, url: str, de: str, en: str, evidence: str = "") -> Finding:
    return Finding(cid, sev, url, de, en, evidence)
