"""Schreibweise: im Programm immer CLAUDIOS. Ersetzt "Claudios" in den Oberflächentexten (nur Werte, nie Schlüssel;
Dateinamen wie claudios.log sind klein geschrieben und bleiben). Wird beim Start einmal aufgerufen (app.py)."""
from __future__ import annotations

OLD, NEW = "Claudios", "CLAUDIOS"


def branded(value: str) -> str:
    return value.replace(OLD, NEW)


def brand_all(texts: dict[str, dict[str, str]]) -> int:
    """Ersetzt in allen Sprachen und gibt die Zahl der geänderten Texte zurück."""
    changed = 0
    for table in texts.values():
        for key, value in list(table.items()):
            new = branded(value)
            if new != value:
                table[key] = new
                changed += 1
    return changed
