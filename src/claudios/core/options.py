"""Lokale Optionen: nichts wird an Dritte gesendet. Standard ist überall AUS.
Gespeichert wird nur 'Option: an/aus' in config/options.json."""
from __future__ import annotations

import json

from .. import paths
from .errors import ClaudiosError, ErrorCode as E

KNOWN = ("screenshots",)


def _file():
    return paths.config_dir() / "options.json"


def _load() -> dict:
    try:
        data = json.loads(_file().read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def enabled(name: str) -> bool:
    return name in KNOWN and _load().get(name) is True


def set_enabled(name: str, value: bool) -> None:
    if name not in KNOWN:
        raise ValueError("unknown option")
    current = _load()
    data = {key: current.get(key) is True for key in KNOWN}
    data[name] = bool(value)
    try:
        _file().write_text(json.dumps(data), "utf-8")
    except OSError as exc:
        raise ClaudiosError(E.FS_ERROR, reason=type(exc).__name__) from None
