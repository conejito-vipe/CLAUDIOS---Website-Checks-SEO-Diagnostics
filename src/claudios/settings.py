"""Einstellungen: nur Sprache und Localhost-Schalter. Die Grenzen stehen bewusst NICHT hier."""
from __future__ import annotations

import json

from .paths import data_dir


def _file():
    return data_dir() / "config" / "settings.json"


def load() -> dict:
    try:
        data = json.loads(_file().read_text("utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    language = data.get("language")
    return {
        "language": language if language in ("de", "en") else None,
        "allow_localhost": data.get("allow_localhost") is True,
    }


def save(settings: dict) -> None:
    path = _file()
    path.parent.mkdir(parents=True, exist_ok=True)
    keep = {"language": settings.get("language"), "allow_localhost": bool(settings.get("allow_localhost"))}
    path.write_text(json.dumps(keep, indent=2), "utf-8")
