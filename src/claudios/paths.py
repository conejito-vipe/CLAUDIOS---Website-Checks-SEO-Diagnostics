"""Speicherorte. Unter Windows: %LOCALAPPDATA%\\Claudios."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / "Claudios"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sub(name: str) -> Path:
    path = data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_dir() -> Path:
    return _sub("tools")


def cache_dir() -> Path:
    return _sub("cache")


def logs_dir() -> Path:
    return _sub("logs")


def config_dir() -> Path:
    return _sub("config")


def reports_dir() -> Path:
    """Standardordner für Berichte (wird nur beim Speichern angelegt)."""
    return Path.home() / "Documents" / "Claudios" / "Reports"


def assets_dir() -> Path | None:
    here = Path(__file__).resolve()
    for cand in (here.parents[2] / "assets", here.parent / "assets"):
        if cand.is_dir():
            return cand
    return None