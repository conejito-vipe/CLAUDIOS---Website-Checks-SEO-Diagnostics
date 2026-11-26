"""Speicherorte. Windows: %LOCALAPPDATA%\\CLAUDIOS, macOS: ~/Library/Application Support/CLAUDIOS, sonst ~/.local/share/CLAUDIOS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_FOLDER = "CLAUDIOS"
LOG_NAME = "CLAUDIOS.log"
_normalized = False


def _normalize_case(path: Path) -> None:
    """Benennt einen vorhandenen Ordner mit anderer Schreibweise (früher Claudios) einmalig um (nur Windows)."""
    global _normalized
    if _normalized:
        return
    _normalized = True
    try:
        if path.exists() and path.name not in os.listdir(path.parent):
            old = next(n for n in os.listdir(path.parent) if n.lower() == path.name.lower())
            (path.parent / old).rename(path)
    except (OSError, StopIteration):
        pass  # nicht schlimm: Windows öffnet den Ordner trotzdem


def data_dir() -> Path:
    if sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    path = Path(base) / APP_FOLDER
    _normalize_case(path)
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
    return Path.home() / "Documents" / APP_FOLDER / "Reports"


def assets_dir() -> Path | None:
    here = Path(__file__).resolve()
    for cand in (here.parents[2] / "assets", here.parent / "assets"):
        if cand.is_dir():
            return cand
    return None
