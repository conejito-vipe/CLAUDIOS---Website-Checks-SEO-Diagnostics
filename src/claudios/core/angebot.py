"""Daten der Pro-Seite (Vergleich Normal und Pro): vorbereitet, aber AUS, bis der Autor es einschaltet.

AKTIV ist im Auslieferungszustand falsch und wird nur lokal über verwaltung.json eingeschaltet: die Seite erscheint nirgends in der Navigation, es gibt keinen Kauf und keine Preise.
Das Programm prüft nichts online und speichert keine Zahlungsdaten; Lizenzschlüssel und Schaltdatei kommen von der Verwaltung."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import lizenz, schalt

AKTIV = False
FEATURES: tuple[dict[str, Any], ...] = (
    {"id": "pruefung", "normal": True, "pro": True},
    {"id": "export", "normal": True, "pro": True},
    {"id": "verlauf", "normal": True, "pro": True},
    {"id": "aktive_pruefungen", "normal": True, "pro": True},
)


def state(base: Path, today: date | None = None) -> dict[str, Any]:
    """Alles für die Seite: Lizenz, Stand der Schaltdatei, Vergleich. Ist AKTIV falsch, kommt nur {"aktiv": False}."""
    if not AKTIV:
        return {"aktiv": False}
    data = schalt.load(base)
    return {"aktiv": True, "lizenz": lizenz.state(base, today), "features": FEATURES,
            "schalt": None if data is None else {"serial": data["serial"], "seit": data["seit"],
                                                 "aktiv": data["aktiv"], "gesperrt": len(data["gesperrt"])},
            "abruf_moeglich": bool(schalt.SCHALT_URL)}
