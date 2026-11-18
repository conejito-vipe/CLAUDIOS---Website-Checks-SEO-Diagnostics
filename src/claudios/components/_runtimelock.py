"""Liest components/runtime-lock.json (vom Workflow 'Laufzeit-Sperrdatei erzeugen'). Ohne Datei oder bei einem
unvollständigen Eintrag bleibt die Komponente ungepinnt und wird nie installiert. Dateien mit Unterstrich lädt
der Komponenten-Lader nicht."""
from __future__ import annotations

import json
import re
import sys
from importlib import resources

_HEX = re.compile(r"^[0-9a-f]{64}$")


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def parse_entry(data: object, key: str) -> dict:
    """Eintrag 'python' oder 'pip' aus den geladenen Daten; leer, wenn etwas fehlt oder ungültig ist."""
    try:
        item = data[key]  # type: ignore[index]
        url, digest = str(item["url"]), str(item["sha256"]).lower()
        size, version = int(item["size"]), str(item["version"])
    except (KeyError, TypeError, ValueError):
        return {}
    if not url.startswith("https://") or not _HEX.match(digest) or size <= 0:
        return {}
    return {"url": url, "sha256": digest, "size": size, "version": version}


def entry(key: str) -> dict:
    try:
        text = resources.files("claudios.components").joinpath("runtime-lock.json").read_text("utf-8")
        return parse_entry(json.loads(text), key)
    except (OSError, ValueError):
        return {}
