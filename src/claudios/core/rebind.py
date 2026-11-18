"""Erneute Adressprüfung vor und nach Werkzeug-Läufen (ZAP, Browser). Chromium und ZAP lösen Namen selbst auf und
lassen sich nicht an die geprüfte IP binden. Wechselt die Antwort inzwischen auf eine nicht öffentliche Adresse
(DNS-Rebinding), wirft recheck TARGET_PRIVATE. Ein DNS-Ausfall allein ist kein Grund zum Abbruch.
Grenze: Das erkennt einen Wechsel vor oder nach dem Lauf, verhindert ihn aber nicht mitten im Lauf."""
from __future__ import annotations

from .errors import ClaudiosError, ErrorCode as E
from .guard import resolve_public
from .limits import LIMITS


def _hosts(gk) -> list[str]:
    """Die Zielseite zuerst, dann die bisher verbundenen Hosts derselben Website (höchstens rebind_hosts_max)."""
    others = sorted(h for h in getattr(gk, "_ips", {}) if h != gk.target.host and gk.same_site(h))
    return ([gk.target.host] + others)[: LIMITS.rebind_hosts_max]


async def recheck(gk) -> int:
    """Gibt die Zahl der erfolgreich geprüften Hosts zurück. Wirft TARGET_PRIVATE, wenn ein Host nicht öffentlich ist."""
    checked = 0
    for host in _hosts(gk):
        try:
            await resolve_public(gk.resolver, host, gk.allow_localhost)
        except ClaudiosError as exc:
            if exc.code == E.TARGET_PRIVATE:
                raise
            continue  # keine Antwort: unbekannt, nicht verdächtig
        checked += 1
    return checked
