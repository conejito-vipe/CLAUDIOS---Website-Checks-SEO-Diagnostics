"""Zertifikate aus den öffentlichen Zertifikats-Logs (Certificate Transparency) über crt.sh. NUR wenn der Schalter 'crtsh' auf
der Seite 'Externe Dienste' an ist (Standard: aus). Eine Anfrage an Dritte über den Gatekeeper (external=True: DoH, öffentliche
IP, IP-Bindung, Tempo, Limits): gesendet wird nur die registrierbare Domain; crt.sh sieht die IP-Adresse des Nutzers.
Gespeichert werden nur Hostnamen, Anzahl und Ausstellernamen der letzten Zertifikate, nie die Zertifikate selbst.
Antwortformat (Felder name_value, issuer_name, not_before): Gedächtniswissen, ungeprüft; crt.sh antwortet oft langsam."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from . import services
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

NAME = "ct"
MIN_LEVEL = 1
ENDPOINT = "https://crt.sh/"
MAX_ROWS = 5000
RECENT_DAYS = 30
_HOST = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$")
_ISSUER = re.compile(r"(?:^|,\s*)O=([^,]+)")


def parse_rows(data, domain: str) -> dict:
    """Aus der Liste der Log-Einträge: Hostnamen der Domain, Zahl der Einträge und Aussteller der letzten Zeit."""
    if not isinstance(data, list):
        raise ValueError("not a list")
    hosts: set[str] = set()
    recent: dict[str, int] = {}
    cutoff = datetime.now(UTC) - timedelta(days=RECENT_DAYS)
    for row in data[:MAX_ROWS]:
        if not isinstance(row, dict):
            continue
        for raw in str(row.get("name_value", "")).splitlines():
            name = raw.strip().lower().removeprefix("*.")
            if (name == domain or name.endswith("." + domain)) and _HOST.match(name):
                hosts.add(name)
        try:
            issued = datetime.fromisoformat(str(row.get("not_before", ""))[:19]).replace(tzinfo=UTC)
        except ValueError:
            continue
        if issued >= cutoff:
            match = _ISSUER.search(str(row.get("issuer_name", "")))
            issuer = (match.group(1) if match else str(row.get("issuer_name", "")))[:60].strip()
            recent[issuer] = recent.get(issuer, 0) + 1
    return {"hosts": sorted(hosts)[:500], "entries": min(len(data), MAX_ROWS), "recent_issuers": recent}


async def collect(gk, snap, resolver) -> dict:
    if not services.enabled("crtsh"):
        return {"enabled": False, "skip": "ct_disabled"}
    if snap.target.loopback:
        return {"enabled": True, "skip": "localhost"}
    domain = snap.target.registrable
    url = f"{ENDPOINT}?q={quote('%.' + domain, safe='')}&output=json"
    try:
        resp = await gk.fetch(url, external=True, max_bytes=LIMITS.ct_body_max)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        return {"enabled": True, "skip": "ct_unreachable"}
    if resp.status != 200:
        return {"enabled": True, "skip": f"ct_http_{resp.status}"}
    if resp.truncated:
        return {"enabled": True, "skip": "ct_too_large"}
    try:
        parsed = parse_rows(json.loads(resp.body.decode("utf-8", errors="replace")), domain)
    except (ValueError, RecursionError):
        return {"enabled": True, "skip": "ct_unreadable"}
    return {"enabled": True, "skip": None, **parsed}
