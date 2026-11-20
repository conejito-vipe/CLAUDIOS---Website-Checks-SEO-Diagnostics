"""Sorgt dafür, dass PyInstaller alle Teile von httpx, httpcore und h2 einsammelt, die dnspython für DNS über HTTPS
braucht. dnspython lädt httpcore._backends.sync nur indirekt; fehlt es im gebauten Programm, meldet dnspython NoDOH und
kein Scan kann eine Domain auflösen. doh_status() prüft beim Start jeden Baustein einzeln und liefert den Grund."""
from __future__ import annotations

import importlib

try:
    import h2.config  # noqa: F401
    import h2.connection  # noqa: F401
    import h2.events  # noqa: F401
    import hpack  # noqa: F401
    import httpcore._backends.sync  # noqa: F401
    import httpx  # noqa: F401
    import hyperframe.frame  # noqa: F401
except ImportError:  # in der Entwicklung nicht schlimm, im gebauten Programm meldet app.py das beim Start
    pass

REQUIRED = ("httpx", "httpcore", "httpcore._backends.sync")
OPTIONAL = ("h2.connection", "anyio", "certifi")


def doh_status() -> tuple[bool, str]:
    """(ok, Beschreibung). ok ist False, wenn ein nötiger Baustein fehlt oder dnspython DoH selbst abgeschaltet hat."""
    problems: list[str] = []
    ok = True
    for name in REQUIRED + OPTIONAL:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 – jeder Fehler ist hier eine Auskunft
            problems.append(f"{name}: {type(exc).__name__}: {exc}")
            ok = ok and name not in REQUIRED
    try:
        query = importlib.import_module("dns.query")
        if getattr(query, "have_doh", None) is False:
            problems.append("dns.query.have_doh is False")
            ok = False
    except Exception as exc:  # noqa: BLE001
        problems.append(f"dns.query: {type(exc).__name__}: {exc}")
        ok = False
    return ok, "; ".join(problems) or "ok"


def doh_available() -> bool:
    """True, wenn die Bausteine für DNS über HTTPS (httpx, httpcore, dnspython) geladen werden können."""
    return doh_status()[0]
