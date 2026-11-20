"""UI-Texte der Karten-Dialoge."""
from __future__ import annotations

from .strings import TEXTS

TEXTS["de"].update({
    "card.ok": "OK", "card.yes": "Ja", "card.no": "Nein", "card.cancel": "Abbrechen", "card.close": "Schließen",
    "card.details": "Details anzeigen", "card.details_hide": "Details ausblenden",
    "card.logs": "Protokolldatei: {path}", "card.open_logs": "Protokollordner öffnen",
})
TEXTS["en"].update({
    "card.ok": "OK", "card.yes": "Yes", "card.no": "No", "card.cancel": "Cancel", "card.close": "Close",
    "card.details": "Show details", "card.details_hide": "Hide details",
    "card.logs": "Log file: {path}", "card.open_logs": "Open log folder",
})
