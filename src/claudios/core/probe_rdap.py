"""Domainablauf per RDAP. NUR wenn der Schalter 'rdap' auf der Seite 'Externe Dienste' an ist (Standard: aus).
Zwei Anfragen an Dritte, beide über den Gatekeeper mit external=True (DoH, öffentliche IP, IP-Bindung, Tempo, Limits):
1. die IANA-Liste der RDAP-Server (RFC 9224), 2. die Abfrage der registrierbaren Domain beim zuständigen Server.
Gesendet wird nur die registrierbare Domain, nicht die Unterseite; der Server sieht die IP-Adresse des Nutzers.
Gespeichert werden nur Ablaufdatum und Status-Wörter. Format der IANA-Liste und Feldnamen: Gedächtniswissen, ungeprüft."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import quote

from . import services
from .errors import ClaudiosError, ErrorCode as E
from .limits import LIMITS

NAME = "rdap"
MIN_LEVEL = 1
BOOTSTRAP = "https://data.iana.org/rdap/dns.json"


def server_for(data, tld: str) -> str | None:
    """Der https-Server der IANA-Liste für diese Endung, mit Schrägstrich am Ende."""
    services_list = data.get("services") if isinstance(data, dict) else None
    for entry in services_list if isinstance(services_list, list) else []:
        if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], list)
                and isinstance(entry[1], list)):
            continue
        if tld in [str(item).lower() for item in entry[0]]:
            for url in entry[1]:
                if isinstance(url, str) and url.startswith("https://"):
                    return url if url.endswith("/") else url + "/"
    return None


def parse_domain(data) -> dict:
    expires = None
    for event in (data.get("events") if isinstance(data, dict) else None) or []:
        if isinstance(event, dict) and str(event.get("eventAction", "")).lower() == "expiration":
            try:
                when = datetime.fromisoformat(str(event.get("eventDate", ""))[:40].replace("Z", "+00:00"))
            except ValueError:
                continue
            expires = (when if when.tzinfo else when.replace(tzinfo=UTC)).isoformat()
            break
    raw = (data.get("status") if isinstance(data, dict) else None) or []
    statuses = [str(item).lower()[:40] for item in raw if isinstance(item, str)][:10]
    return {"expires": expires, "statuses": statuses}


async def _get_json(gk, url: str):
    """(Daten, None) oder (None, Grund). Abbruch und Datenlimit gehen weiter nach oben."""
    try:
        resp = await gk.fetch(url, external=True, max_bytes=LIMITS.rdap_body_max)
    except ClaudiosError as exc:
        if exc.code in (E.SCAN_CANCELLED, E.LIMIT_BYTES):
            raise
        return None, "rdap_unreachable"
    if resp.status != 200:
        return None, f"rdap_http_{resp.status}"
    if resp.truncated:
        return None, "rdap_too_large"
    try:
        return json.loads(resp.body.decode("utf-8", errors="replace")), None
    except (ValueError, RecursionError):
        return None, "rdap_unreadable"


async def collect(gk, snap, resolver) -> dict:
    if not services.enabled(NAME):
        return {"enabled": False, "skip": "rdap_disabled"}
    if snap.target.loopback:
        return {"enabled": True, "skip": "localhost"}
    domain = snap.target.registrable
    boot, reason = await _get_json(gk, BOOTSTRAP)
    if boot is None:
        return {"enabled": True, "skip": reason}
    server = server_for(boot, domain.rsplit(".", 1)[-1].lower())
    if server is None:
        return {"enabled": True, "skip": "rdap_no_server"}
    data, reason = await _get_json(gk, f"{server}domain/{quote(domain, safe='')}")
    if not isinstance(data, dict):
        return {"enabled": True, "skip": reason or "rdap_unreadable"}
    return {"enabled": True, "skip": None, **parse_domain(data)}
