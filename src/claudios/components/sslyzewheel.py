"""Festes sslyze-Wheel für die eingebettete Python-Laufzeit.

sslyze lässt sich dort nicht zuverlässig aus dem Quellarchiv bauen. Der Workflow „sslyze-Wheel erzeugen" baut das Wheel
auf dem Windows-Runner aus dem per Hash geprüften Quellarchiv (pip-sslyze.json), legt es als Release-Asset ab und schreibt
Adresse und SHA256 in sslyze-wheel.json. Das Programm lädt es mit Prüfsumme und installiert es ohne Bauen. Fehlt die Datei,
gilt der alte Weg. Diese Datei braucht nur die Standardbibliothek (der Workflow lädt sie ohne Paket-Import)."""
from __future__ import annotations

import json
import re
from importlib import resources

PIN_FILE = "sslyze-wheel.json"
_HEX = re.compile(r"^[0-9a-f]{64}$")
_NAME = re.compile(r"^[A-Za-z0-9._+-]+\.whl$")


def split_blocks(text: str) -> list[tuple[str, str]]:
    """Zerlegt eine pip-Anforderungsliste in (Name, Block). Ein Block beginnt in Spalte 1 mit dem Paketnamen."""
    blocks: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith("#"):
            name = re.split(r"[=<>!~;\s\[@]", line, maxsplit=1)[0].lower().replace("_", "-")
            blocks.append((name, [line]))
        else:
            blocks[-1][1].append(line)
    return [(name, "\n".join(lines)) for name, lines in blocks if "".join(lines).strip()]


def only_requirement(text: str, name: str) -> str:
    return "\n".join(block for key, block in split_blocks(text) if key == name.lower()) + "\n"


def without_requirement(text: str, name: str) -> str:
    return "\n".join(block for key, block in split_blocks(text) if key and key != name.lower()) + "\n"


def parse_pin(raw: str) -> dict:
    """Gültige Angaben oder ein leeres Dict (Adresse https, SHA256 mit 64 Hexzeichen, Dateiname ohne Pfad)."""
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    url, sha, name = str(data.get("url", "")), str(data.get("sha256", "")).lower(), str(data.get("filename", ""))
    if not url.startswith("https://") or not _HEX.match(sha) or not _NAME.match(name):
        return {}
    try:
        size = int(data.get("size", 0))
    except (TypeError, ValueError):
        size = 0
    return {"url": url, "sha256": sha, "filename": name, "size": size, "version": str(data.get("version", ""))}


def load_pin() -> dict:
    try:
        raw = resources.files("claudios.components").joinpath(PIN_FILE).read_text("utf-8")
    except (OSError, FileNotFoundError, ModuleNotFoundError):
        return {}
    return parse_pin(raw)
