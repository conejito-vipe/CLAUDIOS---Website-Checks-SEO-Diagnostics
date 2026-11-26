"""Einstellungen der Verwaltung (CONEJITO Admin) – ausschließlich lokal, nie im Quelltext und nie auf GitHub.

Öffentlicher Schlüssel, Adresse der Schaltdatei und der Schalter für die Pro-Seite stehen in der Datei `verwaltung.json` im
Datenordner des Programms (neben `lizenz.txt` und `schaltdatei.txt`). Diese Dateien gehören nicht ins Repository (.gitignore);
im ausgelieferten Programm fehlt die Datei, dann ist die Pro-Seite inaktiv und nichts gesperrt.
Format: {"keys": {"<Schlüssel-ID>": "<32 Byte öffentlicher Schlüssel, base64>"}, "schalt_url": "https://…", "pro": true}"""
from __future__ import annotations

import base64
import binascii
import json
import re
from pathlib import Path
from typing import Any

from . import angebot, lizenz, schalt

FILE = "verwaltung.json"
MAX_LEN = 20000
_KID = re.compile(r"^[A-Za-z0-9_-]{1,40}\Z")


def _keys(raw: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for kid, value in raw.items():
            try:
                valid = isinstance(kid, str) and _KID.match(kid) and isinstance(value, str) \
                    and len(base64.b64decode(value, validate=True)) == 32
            except (binascii.Error, ValueError):
                valid = False
            if valid:
                out[kid] = value
    return out


def load(base: Path) -> dict[str, Any]:
    """Liest die Datei; jede Abweichung (fehlt, kaputt, zu groß, falsche Werte) heißt: keine Verwaltung."""
    try:
        with open(Path(base) / FILE, encoding="utf-8") as handle:
            data = json.loads(handle.read(MAX_LEN + 1))
    except (OSError, ValueError, RecursionError):
        return {"keys": {}, "schalt_url": "", "pro": False}
    if not isinstance(data, dict):
        return {"keys": {}, "schalt_url": "", "pro": False}
    url = data.get("schalt_url")
    return {"keys": _keys(data.get("keys")),
            "schalt_url": url if isinstance(url, str) and url.lower().startswith("https://") and len(url) <= 400 else "",
            "pro": data.get("pro") is True}


def apply(base: Path) -> dict[str, Any]:
    """Übernimmt die lokalen Einstellungen in Lizenz-, Schalt- und Angebotsmodul (beim Start aufrufen)."""
    config = load(base)
    lizenz.PUBLIC_KEYS = dict(config["keys"])
    schalt.SCHALT_URL = config["schalt_url"]
    angebot.AKTIV = bool(config["pro"] and config["keys"])  # ohne öffentlichen Schlüssel kann nichts geprüft werden
    return config
