"""API-Schlüssel für optionale Dienste (zurzeit nur Safe Browsing). Sie liegen im Windows-Anmeldeinformationsspeicher,
nie in einer Datei, nie im Bericht, nie im Protokoll. Ohne dauerhaften Speicher (andere Systeme) nur im Arbeitsspeicher."""
from __future__ import annotations

import re

_STATE: dict = {"store": None}
_VALID = re.compile(r"^[A-Za-z0-9_\-]{20,128}$")
KNOWN = ("safebrowsing",)


def _store():
    if _STATE["store"] is None:
        from ..gsc.credstore import get_store  # erst hier: vermeidet einen Importzyklus

        _STATE["store"] = get_store()
    return _STATE["store"]


def _name(service: str) -> str:
    if service not in KNOWN:
        raise ValueError("unknown service")
    return f"Claudios/apikey-{service}"


def valid_key(value: str) -> bool:
    return bool(_VALID.match(value or ""))


def get(service: str) -> str | None:
    raw = _store().read(_name(service))
    text = raw.strip() if raw else ""
    return text if valid_key(text) else None


def has_key(service: str) -> bool:
    return get(service) is not None


def set_key(service: str, value: str) -> None:
    text = (value or "").strip()
    if not valid_key(text):
        raise ValueError("invalid key format")
    _store().write(_name(service), text)


def delete(service: str) -> None:
    _store().delete(_name(service))


def persistent() -> bool:
    return bool(getattr(_store(), "persistent", False))
