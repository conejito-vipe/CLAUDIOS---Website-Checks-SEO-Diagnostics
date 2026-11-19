"""Safe Browsing (Google): prüft die Adressen der eigenen Website gegen die Listen für Schadsoftware und Phishing.
NUR mit eingeschaltetem Schalter und eigenem API-Schlüssel (Seite 'Externe Dienste', Standard: aus). Gesendet werden
höchstens safebrowsing_urls_max Adressen der geprüften Website ohne Parameter, nie Inhalte. Google sieht die IP des
Nutzers. Endpunkt und Antwortformat (v4 threatMatches:find) aus dem Gedächtnis, ungeprüft. Ausgewertet in
checks/web_services.py."""
from __future__ import annotations

import json
from urllib.parse import urlsplit, urlunsplit

from .. import __version__
from . import apikeys, services, thirdparty
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS
from .redact import redact_url

NAME = "safebrowsing"
MIN_LEVEL = 1
ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
THREATS = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"]


def urls_to_check(snap) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in [snap.target.url] + [pg.url for pg in snap.pages if pg.status == 200]:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            continue
        clean = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", "", ""))
        if clean not in seen:
            seen.add(clean)
            out.append(clean)
        if len(out) >= LIMITS.safebrowsing_urls_max:
            break
    return out


def _body(urls: list[str]) -> dict:
    return {
        "client": {"clientId": "claudios", "clientVersion": __version__},
        "threatInfo": {"threatTypes": THREATS, "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"],
                       "threatEntries": [{"url": url} for url in urls]},
    }


def _skip(reason: str) -> dict:
    return {"enabled": True, "skip": reason}


async def collect(gk, snap, resolver) -> dict:
    if not services.enabled("safebrowsing"):
        return {"enabled": False, "skip": "safebrowsing_disabled"}
    if snap.target.loopback:
        return _skip("localhost")
    try:
        key = apikeys.get("safebrowsing")
    except Exception:  # noqa: BLE001 – ein Speicherfehler heißt nur: kein Schlüssel
        key = None
    if not key:
        return _skip("safebrowsing_no_key")
    urls = urls_to_check(snap)
    try:
        status, raw, truncated = await thirdparty.request(
            "POST", ENDPOINT, params={"key": key}, json_body=_body(urls), max_bytes=LIMITS.safebrowsing_body_max,
            timeout=LIMITS.third_party_timeout_seconds, cancel=getattr(gk, "cancel", None))
    except ClaudiosError as exc:
        if exc.code == E.SCAN_CANCELLED:
            raise
        return _skip("safebrowsing_unreachable")
    if status != 200:
        return _skip(f"safebrowsing_http_{status}")
    if truncated:
        return _skip("safebrowsing_too_large")
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except (ValueError, RecursionError):
        return _skip("safebrowsing_unreadable")
    if not isinstance(data, dict):
        return _skip("safebrowsing_unreadable")
    found = data.get("matches")
    matches = []
    for item in (found if isinstance(found, list) else [])[:20]:
        if not isinstance(item, dict):
            continue
        threat = item.get("threat")
        url = str(threat.get("url", "")) if isinstance(threat, dict) else ""
        matches.append({"type": str(item.get("threatType", "UNKNOWN"))[:40], "url": redact_url(url)[:200]})
    return {"enabled": True, "skip": None, "checked": len(urls), "matches": matches}
