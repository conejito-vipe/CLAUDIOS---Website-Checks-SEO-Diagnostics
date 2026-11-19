"""Welche Stufe gilt für die eingegebene Domain? Reine Anzeige-Logik ohne Oberfläche und ohne Netzwerk.
Die Berechtigung selbst prüft weiter gsc/session.py live vor jedem Scan (scan_overrides)."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.errors import ClaudiosError
from ..core.guard import normalize_input
from ..gsc.session import match_property

KEYS = {"level1": "scan.level1", "armed": "scan.level_armed", "level2": "scan.level2",
        "nomatch": "scan.level_nomatch"}


@dataclass(frozen=True)
class LevelInfo:
    level: int
    state: str  # level1 | armed | level2 | nomatch
    prop: str = ""


def level_info(raw_url: str, allow_localhost: bool, session) -> LevelInfo:
    if not session.level2:
        return LevelInfo(1, "level1")
    try:
        target = normalize_input(raw_url, allow_localhost)
    except ClaudiosError:
        return LevelInfo(1, "armed")  # noch keine gültige Adresse
    if target.loopback:
        return LevelInfo(1, "level1")
    prop = match_property(session.sites, target.host)
    if prop is None:
        return LevelInfo(1, "nomatch")
    return LevelInfo(2, "level2", prop)
