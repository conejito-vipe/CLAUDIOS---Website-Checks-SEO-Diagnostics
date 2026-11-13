"""Speicherorte. Unter Windows: %LOCALAPPDATA%\\Claudios."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / "Claudios"
    path.mkdir(parents=True, exist_ok=True)
    return path


def assets_dir() -> Path | None:
    here = Path(__file__).resolve()
    for cand in (here.parents[2] / "assets", here.parent / "assets"):
        if cand.is_dir():
            return cand
    return None
