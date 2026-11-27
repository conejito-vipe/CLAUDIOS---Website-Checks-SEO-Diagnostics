"""Verständliche Namen für Prüfungen (statt der Kennung wie BRW-AXE-001). Die Kennung bleibt nur intern und in den
maschinenlesbaren Dateien; in allem, was Menschen lesen, steht der Titel."""
from __future__ import annotations

from ..checks import load_all
from .registry import REGISTRY


def check_title(check_id: str, lang: str) -> str:
    load_all()
    try:
        meta = REGISTRY[check_id].meta
    except (KeyError, AttributeError):
        return check_id
    titles = getattr(meta, "title", None)
    if isinstance(titles, dict):
        return str(titles.get(lang) or titles.get("de") or check_id).strip()
    return str(titles or check_id).strip()
