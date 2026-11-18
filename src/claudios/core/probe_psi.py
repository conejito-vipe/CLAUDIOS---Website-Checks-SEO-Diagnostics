"""PageSpeed Insights (Google, liefert Lighthouse-Werte und CrUX-Felddaten). NUR mit eingeschaltetem Schalter
'pagespeed' (Standard: aus). Eine einzige Abfrage (mobil) mit der Adresse der Startseite. Google ruft die Seite dabei
selbst ab und sieht die IP des Nutzers. Ohne Schlüssel gilt ein kleines Kontingent: bei HTTP 429 gilt die Prüfung als
nicht ausgeführt. Format der Antwort aus dem Gedächtnis, ungeprüft. Ausgewertet in checks/web_services.py."""
from __future__ import annotations

import json

from . import services, thirdparty
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

NAME = "psi"
MIN_LEVEL = 1
ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORIES = ("performance", "seo", "accessibility", "best-practices")
_LAB = (("largest-contentful-paint", "lcp_ms"), ("first-contentful-paint", "fcp_ms"),
        ("total-blocking-time", "tbt_ms"), ("cumulative-layout-shift", "cls"), ("speed-index", "si_ms"))


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def parse(data) -> dict | None:
    """Zieht die wenigen Werte aus der Antwort. None, wenn nichts Brauchbares darin steht."""
    if not isinstance(data, dict):
        return None
    lighthouse = data.get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        return None
    cats = lighthouse.get("categories") if isinstance(lighthouse.get("categories"), dict) else {}
    scores = {}
    for key in CATEGORIES:
        entry = cats.get(key)
        score = _num(entry.get("score")) if isinstance(entry, dict) else None
        if score is not None and 0 <= score <= 1:
            scores[key.replace("-", "_")] = round(score * 100)
    audits = lighthouse.get("audits") if isinstance(lighthouse.get("audits"), dict) else {}
    lab = {}
    for name, key in _LAB:
        audit = audits.get(name)
        value = _num(audit.get("numericValue")) if isinstance(audit, dict) else None
        if value is not None:
            lab[key] = round(value, 3) if key == "cls" else round(value)
    field, overall = {}, None
    experience = data.get("loadingExperience")
    if isinstance(experience, dict):
        if isinstance(experience.get("overall_category"), str):
            overall = experience["overall_category"][:20]
        metrics = experience.get("metrics")
        for name, metric in list(metrics.items())[:12] if isinstance(metrics, dict) else []:
            if isinstance(metric, dict) and isinstance(metric.get("category"), str):
                field[str(name)[:60]] = {"percentile": _num(metric.get("percentile")),
                                         "category": metric["category"][:20]}
    if not scores and not lab:
        return None
    return {"scores": scores, "lab": lab, "field": field, "overall": overall}


def _skip(reason: str) -> dict:
    return {"enabled": True, "skip": reason}


async def collect(gk, snap, resolver) -> dict:
    if not services.enabled("pagespeed"):
        return {"enabled": False, "skip": "psi_disabled"}
    if snap.target.loopback:
        return _skip("localhost")
    params = [("url", snap.target.url), ("strategy", "mobile")] + [("category", c) for c in CATEGORIES]
    try:
        status, raw, truncated = await thirdparty.request(
            "GET", ENDPOINT, params=params, max_bytes=LIMITS.psi_body_max, timeout=LIMITS.psi_timeout_seconds,
            cancel=getattr(gk, "cancel", None))
    except ClaudiosError as exc:
        if exc.code == E.SCAN_CANCELLED:
            raise
        return _skip("psi_unreachable")
    if status != 200:
        return _skip(f"psi_http_{status}")
    if truncated:
        return _skip("psi_too_large")
    try:
        parsed = parse(json.loads(raw.decode("utf-8", errors="replace")))
    except (ValueError, RecursionError):
        parsed = None
    if parsed is None:
        return _skip("psi_unreadable")
    return {"enabled": True, "skip": None, **parsed}
