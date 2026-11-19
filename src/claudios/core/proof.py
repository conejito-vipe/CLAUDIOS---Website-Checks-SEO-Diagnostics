"""Beleg für die Verifizierung (Stufe 2): entsteht nur durch die Live-Prüfung der Search-Console-Properties
(gsc/session.py), gilt für genau einen Host und eine Property, 15 Minuten und einmal. Der Scan fordert ihn selbst ein.
Hinweis: Er liegt im Arbeitsspeicher; wer den Quellcode ändert, kann ihn fälschen (Reibung, kein Schutz)."""
from __future__ import annotations

import time
from urllib.parse import urlsplit

from .errors import ClaudiosError, ErrorCode as E

TTL_SECONDS = 900.0
_issued: dict[tuple[str, str], float] = {}


def property_covers(prop: str, host: str) -> bool:
    """Deckt die Property die GANZE Domain ab? sc-domain: ja, URL-Präfix nur https mit Pfad / und gleichem Host."""
    host = host.lower().rstrip(".")
    if prop.startswith("sc-domain:"):
        domain = prop[10:].lower().rstrip(".")
        return bool(domain) and (host == domain or host.endswith("." + domain))
    parts = urlsplit(prop)
    return parts.scheme == "https" and (parts.hostname or "").lower() == host and parts.path in ("", "/")


def issue(host: str, prop: str, now: float | None = None) -> None:
    now = time.time() if now is None else now
    for key in [k for k, t in _issued.items() if now - t > TTL_SECONDS]:
        del _issued[key]
    _issued[(host.lower(), prop)] = now


def require(host: str, prop: str | None, now: float | None = None) -> None:
    """Wirft PERM_LEVEL2, wenn kein gültiger, frischer Beleg für diesen Host vorliegt. Gilt nur einmal."""
    now = time.time() if now is None else now
    if not prop or not property_covers(prop, host):
        raise ClaudiosError(E.PERM_LEVEL2)
    issued = _issued.pop((host.lower(), prop), None)
    if issued is None or now - issued > TTL_SECONDS:
        raise ClaudiosError(E.PERM_LEVEL2)
